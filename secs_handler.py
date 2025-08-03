import socket
import struct
import threading
import json
import time # Added for duration calculation
from PySide6.QtCore import QObject, Signal
from types import SimpleNamespace

# EquipmentHandler is unchanged
class EquipmentHandler(QObject):
    log_signal = Signal(str)
    def __init__(self, factory): super().__init__(); self.factory = factory
    def start(self): thread = threading.Thread(target=self.run); thread.daemon = True; thread.start()
    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 5000)); s.listen(); self.log_signal.emit("Equipment listening...")
            conn, _ = s.accept()
            with conn:
                self.log_signal.emit("Equipment connection established.")
                while True:
                    try:
                        raw_len = conn.recv(4)
                        if not raw_len: self.log_signal.emit("Host disconnected."); break
                        msg_len, = struct.unpack('>I', raw_len); header, _ = conn.recv(10), conn.recv(msg_len)
                        s, f = header[2] & 0x7F, header[3]; self.log_signal.emit(f"RECV | S{s}F{f}")
                        reply_map = {'S1F13': 'S1F14', 'S1F17': 'S1F18', 'S2F41': 'S2F42', 'S5F1': 'S5F2'}
                        if reply_name := reply_map.get(f"S{s}F{f}"):
                             conn.sendall(self.factory.create(reply_name)); self.log_signal.emit(f"SENT | {reply_name}")
                    except ConnectionResetError: self.log_signal.emit("Host connection closed."); break
                    except Exception as e: self.log_signal.emit(f"[ERROR] Equipment handler failed: {e}"); break

class ScenarioExecutor(QObject):
    log_signal = Signal(str)
    scenario_finished = Signal(dict) # NEW: Signal to emit the final report

    def __init__(self, factory, scenario_data):
        super().__init__()
        self.factory = factory
        self.scenario = scenario_data
        self.context = {}
        self.report = {"name": scenario_data.get('name'), "result": "Pass", "duration": 0, "steps": []}

    def start(self):
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def run(self):
        self.log_signal.emit(f"Executing Scenario: {self.report['name']}")
        start_time = time.time()
        
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(('127.0.0.1', 5000))
                self.log_signal.emit("Host connected.")
                self._execute_steps(self.scenario['steps'], s)
            except Exception as e:
                self.log_signal.emit(f"[ERROR] Scenario failed: {e}")
                self.report['result'] = "Fail"
        
        self.report['duration'] = f"{time.time() - start_time:.2f} seconds"
        self.log_signal.emit("Scenario finished.")
        self.scenario_finished.emit(self.report) # Emit the final report

    def _execute_steps(self, steps, sock):
        for step in steps:
            action = step['action']
            step_result = "Pass"
            
            try:
                if action == 'send':
                    sock.sendall(self.factory.create(step['message']))
                    self.log_signal.emit(f"SENT | {step['message']}")
                elif action == 'expect':
                    raw_len = sock.recv(4); msg_len, = struct.unpack('>I', raw_len)
                    header, body = sock.recv(10), sock.recv(msg_len)
                    s, f = header[2] & 0x7F, header[3]
                    received_msg = f"S{s}F{f}"
                    self.log_signal.emit(f"RECV | {received_msg}")
                    if received_msg != step['message']:
                        step_result = f"Fail: Expected {step['message']}, got {received_msg}"
                # Other actions...
                
                if step_result != "Pass":
                    self.report['result'] = "Fail"
                self.report['steps'].append(f"- {action.upper()} {step.get('message', '')}: {step_result}")
                if self.report['result'] == "Fail": raise Exception("Step failed")

            except Exception as e:
                self.report['result'] = "Fail"
                self.report['steps'].append(f"- {action.upper()} {step.get('message', '')}: Fail ({e})")
                raise # Stop execution on failure