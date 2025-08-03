# SECS/GEM Simulator with Log Filtering
# Version: 0.9.0

import sys, socket, struct, time, json, threading
from PySide6.QtWidgets import QApplication, QMainWindow, QTextEdit, QVBoxLayout, QWidget, QPushButton, QFileDialog, QLineEdit
from PySide6.QtCore import Signal, QObject
from PySide6.QtGui import QAction
from types import SimpleNamespace

# --- MessageFactory, EquipmentHandler, ScenarioExecutor are unchanged ---
class MessageFactory:
    def __init__(self, filepath='message_library.json'):
        with open(filepath, 'r') as f: self.library = json.load(f)
    def create(self, name, **kwargs):
        spec = self.library.get(name); w_bit = kwargs.get('w_bit', True)
        stream = spec['stream'] | (0x80 if w_bit else 0); function = spec['function']
        header = struct.pack('>HBBH', 0, stream, function, 0) + struct.pack('>I', int(time.time()))
        body_def = spec.get('body_definition', [])
        body = b'\x21\x01' + struct.pack('>B', body_def[0]['value']) if body_def and body_def[0]['format'] == 'U1' else b''
        length = struct.pack('>I', len(body))
        return length + header + body

class EquipmentHandler(QObject):
    log_signal = Signal(str)
    def __init__(self, factory): super().__init__(); self.factory = factory
    def start(self): thread = threading.Thread(target=self.run); thread.daemon = True; thread.start()
    def run(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 5000)); s.listen()
            self.log_signal.emit(f"Equipment listening...")
            conn, _ = s.accept()
            with conn:
                while True:
                    raw_len = conn.recv(4);
                    if not raw_len: break
                    msg_len, = struct.unpack('>I', raw_len)
                    header, _ = conn.recv(10), conn.recv(msg_len)
                    s, f = header[2] & 0x7F, header[3]
                    reply_map = {'S1F13': 'S1F14', 'S1F17': 'S1F18'}
                    reply_name = reply_map.get(f"S{s}F{f}")
                    if reply_name: conn.sendall(self.factory.create(reply_name))

class ScenarioExecutor(QObject):
    log_signal = Signal(str)
    def __init__(self, factory, scenario_data):
        super().__init__(); self.factory = factory; self.scenario = scenario_data; self.running = False; self.context = {}
    def start(self):
        self.running = True; thread = threading.Thread(target=self.run); thread.daemon = True; thread.start()
    def _parse_body(self, body_bytes):
        if not body_bytes or body_bytes[0] != 0x21: return []
        return [SimpleNamespace(type='U1', value=struct.unpack('>B', body_bytes[2:])[0])]
    def run(self):
        self.log_signal.emit(f"Executing Scenario: {self.scenario['name']}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.connect(('127.0.0.1', 5000)); self.log_signal.emit("Host connected.")
                self._execute_steps(self.scenario['steps'], s)
                self.log_signal.emit("Scenario finished.")
            except Exception as e:
                self.log_signal.emit(f"[ERROR] Scenario failed: {e}")
    def _execute_steps(self, steps, sock):
        for step in steps:
            if not self.running: break
            action = step['action']
            if action == 'send':
                sock.sendall(self.factory.create(step['message'])); self.log_signal.emit(f"SENT | {step['message']}")
            elif action == 'expect':
                raw_len = sock.recv(4); msg_len, = struct.unpack('>I', raw_len)
                header = sock.recv(10); body = sock.recv(msg_len)
                s, f = header[2] & 0x7F, header[3]; self.log_signal.emit(f"RECV | S{s}F{f}")
                if 'save_to_context' in step:
                    parsed_body = self._parse_body(body)
                    for key, path in step['save_to_context'].items():
                        self.context[key] = eval(path, {"body": parsed_body})
                        self.log_signal.emit(f"Saved: {key} = {self.context[key]}")
            elif action == 'if':
                condition_met = eval(step['condition'], {"context": self.context})
                self._execute_steps(step.get('then' if condition_met else 'else', []), sock)
            # Other actions...

# --- UPDATED Main GUI Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SECS/GEM Simulator v0.9.0"); self.setGeometry(100, 100, 700, 500)
        
        # Application State
        self.current_scenario_path = None
        self.all_logs = [] # NEW: Master list to store all logs for filtering

        # --- Menu Bar ---
        menu_bar = self.menuBar(); file_menu = menu_bar.addMenu("&File")
        save_action = QAction("&Save Project", self); save_action.triggered.connect(self.save_project); file_menu.addAction(save_action)
        load_action = QAction("&Load Project", self); load_action.triggered.connect(self.load_project); file_menu.addAction(load_action)

        # --- NEW: Log Filter UI ---
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter logs...")
        self.filter_input.textChanged.connect(self.filter_logs)

        # --- Main Layout ---
        self.log_area = QTextEdit(); self.log_area.setReadOnly(True)
        self.btn_start_equip = QPushButton("Start Equipment")
        self.btn_load_scenario = QPushButton("Load & Run Scenario")
        
        layout = QVBoxLayout()
        layout.addWidget(self.btn_start_equip)
        layout.addWidget(self.btn_load_scenario)
        layout.addWidget(self.filter_input) # NEW
        layout.addWidget(self.log_area)
        
        container = QWidget(); container.setLayout(layout); self.setCentralWidget(container)
        
        self.btn_start_equip.clicked.connect(self.start_equipment)
        self.btn_load_scenario.clicked.connect(self.load_and_run_scenario)
        
        self.factory = MessageFactory()

    def start_equipment(self):
        handler = EquipmentHandler(self.factory); handler.log_signal.connect(self.log_message); handler.start()
        self.btn_start_equip.setEnabled(False)

    def load_and_run_scenario(self, filepath=None):
        if not filepath:
            filepath, _ = QFileDialog.getOpenFileName(self, "Load Scenario", "", "JSON Files (*.json)")
        if filepath:
            self.current_scenario_path = filepath
            self.log_message(f"Loaded scenario: {filepath}")
            with open(filepath, 'r') as f: scenario_data = json.load(f)
            executor = ScenarioExecutor(self.factory, scenario_data)
            executor.log_signal.connect(self.log_message); executor.start()

    def save_project(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "SECS Project Files (*.secsproj)")
        if filepath:
            with open(filepath, 'w') as f: json.dump({"version": "1.0", "scenario_filepath": self.current_scenario_path}, f, indent=2)
            self.log_message(f"Project saved to {filepath}")

    def load_project(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "SECS Project Files (*.secsproj)")
        if filepath:
            with open(filepath, 'r') as f: project_data = json.load(f)
            self.log_message(f"Project loaded from {filepath}")
            if scenario_path := project_data.get("scenario_filepath"): self.load_and_run_scenario(filepath=scenario_path)

    def log_message(self, message):
        full_log_line = f"[{time.strftime('%H:%M:%S')}] | {message}"
        self.all_logs.append(full_log_line)
        # Only append if it matches the current filter
        filter_text = self.filter_input.text()
        if not filter_text or filter_text.lower() in full_log_line.lower():
            self.log_area.append(full_log_line)

    def filter_logs(self):
        """Repopulate the log view based on the filter text."""
        filter_text = self.filter_input.text().lower()
        self.log_area.clear()
        
        filtered_logs = [log for log in self.all_logs if filter_text in log.lower()]
        self.log_area.setPlainText("\n".join(filtered_logs))
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum()) # Auto-scroll to bottom

if __name__ == '__main__':
    app = QApplication(sys.argv); window = MainWindow(); window.show(); sys.exit(app.exec())