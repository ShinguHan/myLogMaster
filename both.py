# SECS/GEM Simulator - Integrated Application
# Version: 0.2.2 - Full State Control Cycle

import socket
import struct
import time
import argparse
import threading

# --- Helper Functions (Request-side) ---
def create_s1f13_request():
    system_bytes = struct.pack('>I', int(time.time()))
    header = struct.pack('>HBBH', 0, 1 | 0x80, 13, 0) + system_bytes
    return struct.pack('>I', 0) + header + b''

def create_s1f17_request(): # New
    system_bytes = struct.pack('>I', int(time.time()))
    header = struct.pack('>HBBH', 0, 1 | 0x80, 17, 0) + system_bytes
    return struct.pack('>I', 0) + header + b''

def create_s1f15_request(): # New
    system_bytes = struct.pack('>I', int(time.time()))
    header = struct.pack('>HBBH', 0, 1 | 0x80, 15, 0) + system_bytes
    return struct.pack('>I', 0) + header + b''

# --- Helper Functions (Response-side) ---
def create_s1f14_response(system_bytes):
    body = b'\x01\x02\x21\x01\x00\x01\x00'
    header = struct.pack('>HBBH', 0, 1 | 0x80, 14, 0) + system_bytes
    return struct.pack('>I', len(body)) + header + body

def create_s1f18_response(system_bytes):
    body = b'\x21\x01\x00'
    header = struct.pack('>HBBH', 0, 1 | 0x80, 18, 0) + system_bytes
    return struct.pack('>I', len(body)) + header + body

def create_s1f16_response(system_bytes):
    body = b'\x21\x01\x00'
    header = struct.pack('>HBBH', 0, 1 | 0x80, 16, 0) + system_bytes
    return struct.pack('>I', len(body)) + header + body

# --- Equipment Class (Unchanged from v0.2.1) ---
class Equipment(threading.Thread):
    def __init__(self, host='127.0.0.1', port=5000):
        super().__init__()
        self.host = host
        self.port = port
        self.control_state = 'OFFLINE'
        print(f"Equipment instance created. Initial state: {self.control_state}")
    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((self.host, self.port))
            s.listen()
            conn, addr = s.accept()
            with conn:
                print(f"Equipment accepted connection from {addr}")
                while True:
                    raw_len = conn.recv(4)
                    if not raw_len: break
                    msg_len, = struct.unpack('>I', raw_len)
                    header = conn.recv(10)
                    body = conn.recv(msg_len)
                    s_type, f_type, system_bytes = header[2], header[3], header[6:]
                    stream = s_type & 0x7F
                    print(f"Equipment Received: S{stream}F{f_type}")
                    if stream == 1 and f_type == 13:
                        conn.sendall(create_s1f14_response(system_bytes))
                    elif stream == 1 and f_type == 17:
                        print(f"Changing state: {self.control_state} -> ONLINE")
                        self.control_state = 'ONLINE'
                        conn.sendall(create_s1f18_response(system_bytes))
                    elif stream == 1 and f_type == 15:
                        print(f"Changing state: {self.control_state} -> OFFLINE")
                        self.control_state = 'OFFLINE'
                        conn.sendall(create_s1f16_response(system_bytes))
                print("Equipment connection closed.")

# --- UPDATED Host Class ---
class Host(threading.Thread):
    def __init__(self, host='127.0.0.1', port=5000):
        super().__init__()
        self.host = host
        self.port = port
        print("Host instance created.")
    def run(self):
        print("Host thread starting test sequence...")
        time.sleep(1) 
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect((self.host, self.port))
            except ConnectionRefusedError:
                print("[ERROR] Host could not connect.")
                return

            # Step 1: Establish Communication
            print("Host: Sending S1F13...")
            s.sendall(create_s1f13_request())
            s.recv(1024)
            print("Host: Received S1F14. Handshake complete.")
            time.sleep(0.5)
            
            # Step 2: Request ON-LINE
            print("Host: Sending S1F17...")
            s.sendall(create_s1f17_request())
            s.recv(1024)
            print("Host: Received S1F18. ON-LINE request acknowledged.")
            time.sleep(0.5)

            # Step 3: Request OFF-LINE
            print("Host: Sending S1F15...")
            s.sendall(create_s1f15_request())
            s.recv(1024)
            print("Host: Received S1F16. OFF-LINE request acknowledged.")
        
        print("Host: Test sequence complete.")

# --- Main Entry Point (Unchanged from v0.2.1) ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="SECS/GEM Simulator")
    parser.add_argument('mode', choices=['host', 'equipment', 'both'], help="Mode to run.")
    args = parser.parse_args()
    if args.mode == 'equipment':
        equip_thread = Equipment()
        equip_thread.start()
    elif args.mode == 'host':
        host_thread = Host()
        host_thread.start()
    elif args.mode == 'both':
        print("Running both Equipment and Host for self-testing.")
        equip_thread = Equipment()
        host_thread = Host()
        equip_thread.start()
        host_thread.start()