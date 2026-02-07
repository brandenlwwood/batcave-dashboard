#!/usr/bin/env python3
"""
HTTPS version of Alfred's Batcave Command Center
Enables microphone access for voice commands
"""

import ssl
import sys
from http.server import HTTPServer
from server import BatcaveHandler

def run_https_server(port=8443):
    """Run HTTPS version of the Batcave server"""
    server_address = ('0.0.0.0', port)
    httpd = HTTPServer(server_address, BatcaveHandler)
    
    # Create SSL context
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    try:
        context.load_cert_chain('cert.pem', 'key.pem')
    except FileNotFoundError:
        print("❌ SSL certificates not found. Run:")
        print("   openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes")
        return
    
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    
    print(f"🦇 Alfred's Batcave Command Center (HTTPS)")
    print(f"🔒 HTTPS Server running on port {port}")
    print(f"🌐 Local: https://localhost:{port}")
    print(f"🌐 Tailscale: https://100.122.252.21:{port}")
    print(f"🎤 Microphone access enabled via HTTPS")
    print(f"⚠️  You'll see a security warning - click 'Advanced' → 'Proceed'")
    print("\\nPress Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\\n🛑 HTTPS Batcave systems offline.")
        httpd.shutdown()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8443
    run_https_server(port)