import os
import platform
import subprocess
import shutil
import uuid
import ctypes
import ctypes.wintypes
import logging
import json

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class SystemInfo:
    _log = logging.getLogger('SystemInfo')

    class MEMORYSTATUSEX(ctypes.Structure):
        _fields_ = [
            ('dwLength', ctypes.wintypes.DWORD),
            ('dwMemoryLoad', ctypes.wintypes.DWORD),
            ('ullTotalPhys', ctypes.c_ulonglong),
            ('ullAvailPhys', ctypes.c_ulonglong),
            ('ullTotalPageFile', ctypes.c_ulonglong),
            ('ullAvailPageFile', ctypes.c_ulonglong),
            ('ullTotalVirtual', ctypes.c_ulonglong),
            ('ullAvailVirtual', ctypes.c_ulonglong),
            ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
        ]

    @classmethod
    def _get_hwid(cls) -> str:
        try:
            result = subprocess.run(
                ['wmic', 'csproduct', 'get', 'uuid'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
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
                result = subprocess.run(
                    ['wmic', 'cpu', 'get', 'name'],
                    capture_output=True, text=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
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
            result = subprocess.run(
                ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
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
            total_gb = mem.ullTotalPhys / (1024 ** 3)
            avail_gb = mem.ullAvailPhys / (1024 ** 3)
            return f'{total_gb:.1f} GB (Available: {avail_gb:.1f} GB)'
        except Exception:
            return 'Unknown'

    @classmethod
    def _get_mac(cls) -> str:
        mac_int = uuid.getnode()
        mac_str = ':'.join(f'{(mac_int >> (8 * i)) & 0xFF:02x}' for i in reversed(range(6)))
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
            total_gb = usage.total / (1024 ** 3)
            used_gb = usage.used / (1024 ** 3)
            free_gb = usage.free / (1024 ** 3)
            pct = (usage.used / usage.total) * 100
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
            lines = [
                f'IP: {data.get("query", "N/A")}',
                f'City: {data.get("city", "N/A")}',
                f'Region: {data.get("regionName", "N/A")}',
                f'Country: {data.get("country", "N/A")}',
                f'ISP: {data.get("isp", "N/A")}',
                f'Timezone: {data.get("timezone", "N/A")}',
                f'Lat/Lon: {data.get("lat", "N/A")}, {data.get("lon", "N/A")}',
            ]
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

        lines = [
            f'OS: {platform.platform()}',
            f'OS Version: {platform.version()}',
            f'Computer Name: {os.getenv("COMPUTERNAME", "Unknown")}',
            f'Username: {username}',
            f'HWID: {cls._get_hwid()}',
            f'CPU: {cls._get_cpu()}',
            f'GPU: {cls._get_gpu()}',
            f'RAM: {cls._get_ram()}',
            f'MAC: {cls._get_mac()}',
            f'Screen: {cls._get_screen_resolution()}',
            f'Disk: {cls._get_disk_info()}',
        ]
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
