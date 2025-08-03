import socket
import struct
import threading
import json
import time
from PySide6.QtCore import QObject, Signal
from types import SimpleNamespace
from validator import validate_message

class EquipmentHandler(QObject):
    log_signal = Signal(str)
    def __init__(self, factory):
        super().__init__()
        self.factory = factory

    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 5000)); s.listen(); self.log_signal.emit("Equipment listening...")
            conn, _ = s.accept()
            with conn:
                while True:
                    try:
                        raw_len = conn.recv(4)
                        if not raw_len: break
                        msg_len, = struct.unpack('>I', raw_len); header, body = conn.recv(10), conn.recv(msg_len)
                        s, f = header[2] & 0x7F, header[3]; msg_name = f"S{s}F{f}"
                        self.log_signal.emit(f"RECV | {msg_name}")
                        
                        reply_map = {'S2F41': 'S2F42'}
                        if reply_name := reply_map.get(msg_name):
                            # --- TEMPORARY MODIFICATION FOR TESTING ---
                            # This will send a reply that does NOT match the library definition.
                            # It sends L[U1] instead of the expected L[U1, A].
                            if reply_name == 'S2F42':
                                self.log_signal.emit("[TEST] Sending MALFORMED S2F42 reply...")
                                malformed_body = b'\x01\x01\x21\x01\x00' # L,1 -> U1,1,0
                                malformed_header = struct.pack('>HBBH', 0, 2 | 0x80, 42, 0) + header[6:]
                                malformed_reply = struct.pack('>I', len(malformed_body)) + malformed_header + malformed_body
                                conn.sendall(malformed_reply)
                                continue # Skip normal sending
                            # --- END OF MODIFICATION ---
                            
                            conn.sendall(self.factory.create(reply_name)); self.log_signal.emit(f"SENT | {reply_name}")
                    except Exception as e:
                        self.log_signal.emit(f"[ERROR] Equipment handler failed: {e}"); break
    # ... start method ...
    def start(self): 
        thread = threading.Thread(target=self.run); thread.daemon = True; thread.start()

class ScenarioExecutor(QObject):
    log_signal = Signal(str)
    scenario_finished = Signal(dict)
    def __init__(self, factory, scenario_data):
        super().__init__(); self.factory = factory; self.scenario = scenario_data
        self.context = {}; self.report = {"name": scenario_data.get('name'), "result": "Pass", "duration": 0, "steps": []}
    def start(self): thread = threading.Thread(target=self.run); thread.daemon = True; thread.start()
    def _parse_body_recursive(self, body_io):
        items = []; format_code = body_io.read(1)
        if not format_code: return items
        length_byte = struct.unpack('>B', body_io.read(1))[0]
        if format_code == b'\x01': items.append(SimpleNamespace(type='L', value=[item for _ in range(length_byte) for item in self._parse_body_recursive(body_io)]))
        elif format_code == b'\x21': items.append(SimpleNamespace(type='U1', value=struct.unpack('>B', body_io.read(length_byte))[0]))
        elif format_code == b'\x41': items.append(SimpleNamespace(type='A', value=body_io.read(length_byte).decode('ascii')))
        return items
    def _parse_body(self, body_bytes): return self._parse_body_recursive(__import__('io').BytesIO(body_bytes))
    def run(self):
        start_time = time.time(); self.log_signal.emit(f"Executing Scenario: {self.report['name']}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(('127.0.0.1', 5000)); self.log_signal.emit("Host connected.")
                self._execute_steps(self.scenario['steps'], s)
            except Exception as e:
                self.log_signal.emit(f"[ERROR] Scenario failed: {e}"); self.report['result'] = "Fail"
        self.report['duration'] = f"{time.time() - start_time:.2f} seconds"
        self.log_signal.emit("Scenario finished."); self.scenario_finished.emit(self.report)
    def _execute_steps(self, steps, sock):
        for step in steps:
            action = step['action']; step_result = "Pass"
            try:
                if action == 'expect':
                    raw_len = sock.recv(4); msg_len, = struct.unpack('>I', raw_len); header, body = sock.recv(10), sock.recv(msg_len)
                    s, f = header[2] & 0x7F, header[3]; received_msg = f"S{s}F{f}"; self.log_signal.emit(f"RECV | {received_msg}")
                    
                    if received_msg in self.factory.library:
                        spec = self.factory.library[received_msg]; parsed_body = self._parse_body(body)
                        is_valid, error = validate_message(spec, parsed_body)
                        if not is_valid:
                            self.log_signal.emit(f"VALIDATION FAILED for {received_msg}: {error}")
                            step_result = f"Fail: Validation Error - {error}"

                    if received_msg != step['message']: step_result = f"Fail: Expected {step['message']}, got {received_msg}"
                elif action == 'send': sock.sendall(self.factory.create(step['message'])); self.log_signal.emit(f"SENT | {step['message']}")
                
                if step_result != "Pass": self.report['result'] = "Fail"
                self.report['steps'].append(f"- {action.upper()} {step.get('message', '')}: {step_result}")
                if self.report['result'] == "Fail": raise Exception("Step failed")
            except Exception as e:
                self.report['result'] = "Fail"; self.report['steps'].append(f"- {action.upper()} {step.get('message', '')}: Fail ({e})"); raise