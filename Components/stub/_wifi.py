import os
import re
import subprocess
import logging


class Wifi:
    _log = logging.getLogger('Wifi')

    @classmethod
    def _get_profiles(cls) -> list[str]:
        profiles: list[str] = []
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'profiles'],
                capture_output=True, text=True, timeout=15,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.splitlines():
                match = re.search(r'All User Profile\s*:\s*(.+)', line)
                if not match:
                    match = re.search(r'Profil \"Tous les utilisateurs\"\s*:\s*(.+)', line)
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
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'profile', f'name={profile}', 'key=clear'],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in result.stdout.splitlines():
                match = re.search(r'Key Content\s*:\s*(.+)', line)
                if not match:
                    match = re.search(r'Contenu de la cl.\s*:\s*(.+)', line)
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
