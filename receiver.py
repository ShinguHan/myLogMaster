# Simplified SECS/GEM Equipment Simulator
# Author: Min-jun Lee
# Version: 0.1.0 - TC-001 Compliant

import socket
import struct

HOST = '127.0.0.1'
PORT = 5000

def create_s1f14_response(system_bytes):
    """Creates the S1F14 Establish Communication Acknowledgment message."""
    # S1F14 Body: [COMMACK, [MDLN, SOFTREV]]. For this demo, COMMACK = 0 (OK).
    s1f14_body = b'\x01\x02\x21\x01\x00\x01\x00' # L,2 | U1,1,0 | L,0
    
    # Header: SessionID=0, S=1, F=14, Wait=False, SystemBytes from request
    header = struct.pack('>HBBH', 0, 1 | 0x80, 14, 0) + system_bytes
    
    # Message Length (integer count of bytes in the message body)
    length = struct.pack('>I', len(s1f14_body))

    return length + header + s1f14_body

def start_server():
    """Starts the server, listens for one connection, and handles it."""
    print("Equipment simulator starting...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        print(f"Server listening on {HOST}:{PORT}...")
        conn, addr = s.accept()
        with conn:
            print(f"Accepted connection from {addr}")
            while True:
                # 1. Receive message length (4 bytes)
                raw_len = conn.recv(4)
                if not raw_len:
                    print("Connection closed by client.")
                    break
                
                msg_len = struct.unpack('>I', raw_len)[0]

                # 2. Receive the header (10 bytes) and body
                header = conn.recv(10)
                body = conn.recv(msg_len)

                # Unpack header to identify the message
                session_id, s_type, f_type, p_type, s_bytes = struct.unpack('>HBBH4s', header)
                stream = s_type & 0x7F
                
                print(f"Received Message: S{stream}F{f_type}")

                # 3. Check if it's S1F13 and respond
                if stream == 1 and f_type == 13:
                    print("S1F13 received. Responding with S1F14.")
                    response = create_s1f14_response(s_bytes)
                    conn.sendall(response)
                    print("S1F14 sent successfully.")

if __name__ == '__main__':
    start_server()