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
    status_signal = Signal(str) # To update dashboard

    def __init__(self, factory, conn_details):
        super().__init__()
        self.factory = factory
        self.conn_details = conn_details

    def start(self):
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def run(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((self.conn_details['ip'], self.conn_details['port']))
                s.listen()
                self.log_signal.emit(f"Equipment listening on port {self.conn_details['port']}...")
                conn, _ = s.accept()
                with conn:
                    self.log_signal.emit("Equipment connection established.")
                    while True:
                        raw_len = conn.recv(4)
                        if not raw_len:
                            self.log_signal.emit("Host disconnected.")
                            break
                        msg_len, = struct.unpack('>I', raw_len)
                        header, body = conn.recv(10), conn.recv(msg_len)
                        s, f = header[2] & 0x7F, header[3]
                        msg_name = f"S{s}F{f}"
                        self.log_signal.emit(f"RECV | {msg_name}")
                        reply_map = {'S1F13': 'S1F14', 'S1F17': 'S1F18', 'S2F41': 'S2F42', 'S5F1': 'S5F2'}
                        if reply_name := reply_map.get(msg_name):
                            try:
                                reply_message = self.factory.create(reply_name)
                                conn.sendall(reply_message)
                                self.log_signal.emit(f"SENT | {reply_name}")
                            except ValueError as e:
                                self.log_signal.emit(f"[ERROR] Equipment failed to create reply '{reply_name}': {e}")
        except Exception as e:
            self.log_signal.emit(f"[ERROR] Listener failed: {e}")

class ScenarioExecutor(QObject):
    log_signal = Signal(str)
    scenario_finished = Signal(dict)
    status_signal = Signal(str)

    def __init__(self, factory, scenario_data, conn_details):
        super().__init__()
        self.factory = factory
        self.scenario = scenario_data
        self.conn_details = conn_details
        self.context = {}
        self.report = {"name": scenario_data.get('name'), "result": "Pass", "duration": 0, "steps": []}

    def start(self):
        thread = threading.Thread(target=self.run)
        thread.daemon = True
        thread.start()

    def run(self):
        start_time = time.time()
        self.log_signal.emit(f"Executing Scenario: {self.report['name']}")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((self.conn_details['ip'], self.conn_details['port']))
                self.log_signal.emit("Host connected.")
                self._execute_steps(self.scenario['steps'], s)
        except Exception as e:
            self.log_signal.emit(f"[ERROR] Scenario failed: {e}")
            self.report['result'] = "Fail"
        
        self.report['duration'] = f"{time.time() - start_time:.2f} seconds"
        self.log_signal.emit("Scenario finished.")
        self.scenario_finished.emit(self.report)
    
    def _parse_body_recursive(self, body_io):
        items = []
        format_code = body_io.read(1)
        if not format_code: return items
        length_byte = int.from_bytes(body_io.read(1), 'big')
        if format_code == b'\x01':
            items.append(SimpleNamespace(type='L', value=[item for _ in range(length_byte) for item in self._parse_body_recursive(body_io)]))
        elif format_code == b'\x21':
            items.append(SimpleNamespace(type='U1', value=int.from_bytes(body_io.read(length_byte), 'big')))
        elif format_code == b'\x41':
            items.append(SimpleNamespace(type='A', value=body_io.read(length_byte).decode('ascii')))
        return items

    def _parse_body(self, body_bytes):
        return self._parse_body_recursive(__import__('io').BytesIO(body_bytes))

    def _execute_steps(self, steps, sock):
        for step in steps:
            action = step['action']
            step_result = "Pass"
            try:
                if action == 'send':
                    params = step.get('params', {})
                    msg = self.factory.create(step['message'], context=self.context, params=params)
                    sock.sendall(msg)
                    self.log_signal.emit(f"SENT | {step['message']}")
                elif action == 'expect':
                    raw_len = sock.recv(4)
                    msg_len, = struct.unpack('>I', raw_len)
                    header, body = sock.recv(10), sock.recv(msg_len)
                    s, f = header[2] & 0x7F, header[3]
                    received_msg = f"S{s}F{f}"
                    self.log_signal.emit(f"RECV | {received_msg}")
                    
                    if received_msg in self.factory.library:
                        spec = self.factory.library[received_msg]
                        parsed_body = self._parse_body(body)
                        is_valid, error = validate_message(spec, parsed_body)
                        if not is_valid:
                            step_result = f"Fail: Validation Error - {error}"
                    
                    if received_msg != step['message']:
                        step_result = f"Fail: Expected {step['message']}, got {received_msg}"

                    if 'save_to_context' in step:
                        parsed_body = self._parse_body(body)
                        key = step['save_to_context']['key']
                        path = step['save_to_context']['path']
                        self.context[key] = eval(path, {"body": parsed_body})
                        self.log_signal.emit(f"Saved to context: {key} = {self.context[key]}")

                elif action == 'if':
                    condition_met = eval(step['condition'], {"context": self.context})
                    self._execute_steps(step.get('then' if condition_met else 'else', []), sock)
                elif action == 'loop':
                    for i in range(step.get('count', 1)):
                        self._execute_steps(step.get('steps', []), sock)
                elif action == 'delay':
                    time.sleep(step.get('seconds', 1))
                elif action == 'log':
                    self.log_signal.emit(f"[SCENARIO LOG] {step['message']}")
                elif action == 'call':
                    with open(step['file'], 'r') as f:
                        sub_scenario = json.load(f)
                    self._execute_steps(sub_scenario['steps'], sock)

                if step_result != "Pass":
                    self.report['result'] = "Fail"
                self.report['steps'].append(f"- {action.upper()} {step.get('message', '')}: {step_result}")
                if self.report['result'] == "Fail":
                    raise Exception("Step failed")
            except Exception as e:
                self.report['result'] = "Fail"
                self.report['steps'].append(f"- {action.upper()} {step.get('message', '')}: Fail ({e})")
                raise
