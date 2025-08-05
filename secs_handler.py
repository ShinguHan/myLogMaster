import socket
import struct
import threading
import json
import time
from PySide6.QtCore import QObject, Signal
from types import SimpleNamespace
from validator import validate_message
import database_handler # New Import

# EquipmentHandler is unchanged
class EquipmentHandler(QObject):
    log_signal = Signal(str, str)
    def __init__(self, factory, conn_details):
        super().__init__()
        self.factory = factory
        self.conn_details = conn_details
    def start(self):
        thread = threading.Thread(target=self.run); thread.daemon = True; thread.start()
    def run(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.conn_details['ip'], self.conn_details['port']))
                s.listen()
                self.log_signal.emit("INFO", f"Listening on port {self.conn_details['port']}...")
                conn, _ = s.accept()
                with conn:
                    self.log_signal.emit("INFO", "Connection established.")
                    while True:
                        raw_len = conn.recv(4)
                        if not raw_len: self.log_signal.emit("INFO", "Host disconnected."); break
                        # ... rest of run method is unchanged
        except Exception as e:
            self.log_signal.emit("ERROR", f"Listener failed: {e}")

class ScenarioExecutor(QObject):
    log_signal = Signal(str, str)
    scenario_finished = Signal(dict)

    def __init__(self, factory, scenario_data, conn_details):
        super().__init__()
        self.factory = factory
        self.scenario = scenario_data
        self.conn_details = conn_details
        self.context = {}
        self.report = {"name": scenario_data.get('name'), "result": "Pass", "duration": 0, "steps": []}

    def run(self):
        start_time = time.time()
        self.log_signal.emit("INFO", f"Executing Scenario: {self.report['name']}")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.conn_details['ip'], self.conn_details['port']))
                self.log_signal.emit("INFO", "Host connected.")
                self._execute_steps(self.scenario['steps'], s)
        except Exception as e:
            self.log_signal.emit("ERROR", f"Scenario failed: {e}")
            self.report['result'] = "Fail"
        
        self.report['duration'] = f"{time.time() - start_time:.2f} seconds"
        database_handler.save_test_result(self.report) # Save result to DB
        self.log_signal.emit("INFO", "Scenario finished.")
        self.scenario_finished.emit(self.report)
    
    # ... rest of ScenarioExecutor is unchanged ...
    def start(self):
        thread = threading.Thread(target=self.run); thread.daemon = True; thread.start()
    def _parse_body_recursive(self, body_io):
        items = []; format_code = body_io.read(1)
        if not format_code: return items
        length_byte = int.from_bytes(body_io.read(1), 'big')
        if format_code == b'\x01': items.append(SimpleNamespace(type='L', value=[item for _ in range(length_byte) for item in self._parse_body_recursive(body_io)]))
        elif format_code == b'\x21': items.append(SimpleNamespace(type='U1', value=int.from_bytes(body_io.read(length_byte), 'big')))
        elif format_code == b'\x41': items.append(SimpleNamespace(type='A', value=body_io.read(length_byte).decode('ascii')))
        return items
    def _parse_body(self, body_bytes): return self._parse_body_recursive(__import__('io').BytesIO(body_bytes))
    def _execute_steps(self, steps, sock):
        for step in steps:
            action = step['action']; step_result = "Pass"
            try:
                # ... step execution logic is unchanged ...
                if step_result != "Pass": self.report['result'] = "Fail"
                self.report['steps'].append(f"- {action.upper()} {step.get('message', '')}: {step_result}")
                if self.report['result'] == "Fail": raise Exception("Step failed")
            except Exception as e:
                self.report['result'] = "Fail"; self.report['steps'].append(f"- {action.upper()} {step.get('message', '')}: Fail ({e})"); raise
