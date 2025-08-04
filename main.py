import sys
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, 
                               QDialog, QLineEdit, QFormLayout, QDialogButtonBox)
from PySide6.QtCore import Qt
from simulator_window import SimulatorWindow

class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Connection Details")
        layout = QFormLayout(self)
        self.name_input = QLineEdit("EQ1")
        self.ip_input = QLineEdit("127.0.0.1")
        self.port_input = QLineEdit("5000")
        layout.addRow("Name:", self.name_input)
        layout.addRow("IP Address:", self.ip_input)
        layout.addRow("Port:", self.port_input)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_details(self):
        return {
            "name": self.name_input.text(),
            "ip": self.ip_input.text(),
            "port": int(self.port_input.text())
        }

class ConnectionManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SECS/GEM Tool Suite - Connection Manager")
        self.setGeometry(100, 100, 800, 400)
        self.connections = {}
        self.simulator_windows = {}
        self._setup_ui()

    def _setup_ui(self):
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "IP Address", "Port", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self.launch_simulator)

        add_btn = QPushButton("Add Connection")
        add_btn.clicked.connect(self.add_connection)
        
        # In a real app, Start/Stop Listener buttons would be here
        # For this version, launching the simulator will handle it.

        layout = QVBoxLayout()
        layout.addWidget(add_btn)
        layout.addWidget(self.table)
        
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def add_connection(self):
        dialog = ConnectionDialog(self)
        if dialog.exec():
            details = dialog.get_details()
            conn_id = details['name']
            if conn_id not in self.connections:
                self.connections[conn_id] = details
                self.connections[conn_id]['status'] = "Disconnected"
                self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(len(self.connections))
        for i, (conn_id, details) in enumerate(self.connections.items()):
            self.table.setItem(i, 0, QTableWidgetItem(details['name']))
            self.table.setItem(i, 1, QTableWidgetItem(details['ip']))
            self.table.setItem(i, 2, QTableWidgetItem(str(details['port'])))
            self.table.setItem(i, 3, QTableWidgetItem(details['status']))

    def launch_simulator(self, mi):
        row = mi.row()
        conn_id = self.table.item(row, 0).text()
        
        if conn_id not in self.simulator_windows:
            conn_details = self.connections[conn_id]
            # Pass connection details to the simulator window
            self.simulator_windows[conn_id] = SimulatorWindow(conn_details)
        
        self.simulator_windows[conn_id].show()
        # In a real app, you'd update the status here based on connection events
        self.connections[conn_id]['status'] = "Active"
        self.refresh_table()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    manager = ConnectionManager()
    manager.show()
    sys.exit(app.exec())
