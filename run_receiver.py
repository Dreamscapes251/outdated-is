from http.server import BaseHTTPRequestHandler, HTTPServer

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        with open('webhook_dump_recent.bin', 'wb') as f:
            f.write(post_data)
            
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
        
        print(f"\n[!] RECEIVED POST REQUEST: {content_length} bytes")
        
        if b'PK\x03\x04' in post_data:
            print("[+] SUCCESS: ZIP File payload detected!")
        elif b'Rar!\x1a\x07\x00' in post_data:
            print("[+] SUCCESS: RAR File payload detected!")
        else:
            print("[-] No archive signature found.")
            
        # Exit the server after one request
        import threading
        threading.Thread(target=self.server.shutdown).start()

server = HTTPServer(('127.0.0.1', 5000), WebhookHandler)
print("Listening on 127.0.0.1:5000...")
server.serve_forever()
print("Server shut down.")
