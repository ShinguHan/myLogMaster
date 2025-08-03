# SECS/GEM Host Simulator (Sender/Client)
# Author: Min-jun Lee
# Version: 0.1.1 - Host Mode TC-001 Compliant

import socket
import struct
import time

# Target Equipment IP and Port
EQUIPMENT_HOST = '127.0.0.1'
EQUIPMENT_PORT = 5000

def create_s1f13_request():
    """Creates the S1F13 Establish Communication Request message."""
    # S1F13 has an empty body.
    s1f13_body = b''
    
    # Header: SessionID=0, S=1, F=13, W-Bit=1, SystemBytes=unique ID
    # Note: W-Bit should be 1 if a reply is expected.
    system_bytes = struct.pack('>I', int(time.time()))
    header = struct.pack('>HBBH', 0, 1 | 0x80, 13, 0) + system_bytes
    
    # Message Length (0 for an empty body)
    length = struct.pack('>I', len(s1f13_body))

    return length + header + s1f13_body

def start_host_mode():
    """Starts the host, connects to equipment, and performs the handshake."""
    print("Host simulator starting...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.connect((EQUIPMENT_HOST, EQUIPMENT_PORT))
            print(f"Successfully connected to Equipment at {EQUIPMENT_HOST}:{EQUIPMENT_PORT}")
        except ConnectionRefusedError:
            print(f"[ERROR] Connection refused. Is the equipment simulator running on port {EQUIPMENT_PORT}?")
            return

        # 1. Create and send S1F13
        s1f13_message = create_s1f13_request()
        print("Sending S1F13 (Establish Communication Request)...")
        s.sendall(s1f13_message)

        # 2. Wait for and receive the S1F14 response
        print("Waiting for S1F14 response...")
        raw_len = s.recv(4)
        if not raw_len:
            print("[ERROR] Did not receive a response.")
            return
            
        msg_len = struct.unpack('>I', raw_len)[0]
        header = s.recv(10)
        body = s.recv(msg_len)

        # 3. Verify the response is S1F14
        session_id, s_type, f_type, p_type, s_bytes = struct.unpack('>HBBH4s', header)
        stream = s_type & 0x7F
        
        if stream == 1 and f_type == 14:
            # The body of S1F14 contains the COMMACK code. Let's check it.
            # L,2 -> U1,1,COMMACK -> L,0
            commack = body[2]
            if commack == 0:
                print(f"SUCCESS: Received S1F14 with COMMACK=0. Handshake complete.")
            else:
                print(f"FAILED: Received S1F14 but COMMACK is {commack}.")
        else:
            print(f"FAILED: Expected S1F14, but received S{stream}F{f_type}.")

if __name__ == '__main__':
    start_host_mode()