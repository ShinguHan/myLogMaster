from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QHeaderView, QLabel, QSplitter)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

class ValidationResultDialog(QDialog):
    highlight_log_requested = Signal(int)

    def __init__(self, results_data, log_df, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scenario Validation Detailed Report")
        self.setMinimumSize(900, 600)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)

        self.results_data = results_data
        self.log_df = log_df # ✅ 전체 로그 데이터를 저장

        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Vertical)

        # 상단: 시나리오 시도 목록
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels(["Scenario Name", "Status", "Message", "Context"])
        self.summary_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.summary_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.summary_table.selectionModel().selectionChanged.connect(self.on_attempt_selected)
        # ✅ 1. 헷갈리지 않는 마우스 오버 효과 추가
        self.summary_table.setStyleSheet("QTableWidget::item:hover { background-color: #e8f4ff; }")
        
        # 하단: 상세 타임라인
        self.timeline_view = QTableWidget()
        self.timeline_view.setColumnCount(4)
        self.timeline_view.setHorizontalHeaderLabels(["Step Name", "Timestamp", "Delta (sec)", "Log Index"])
        self.timeline_view.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.timeline_view.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.timeline_view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.timeline_view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.timeline_view.itemDoubleClicked.connect(self.on_log_selected)

        splitter.addWidget(self.summary_table)
        splitter.addWidget(self.timeline_view)
        splitter.setSizes([200, 400])
        main_layout.addWidget(splitter)

        self.populate_summary_table()
        if self.summary_table.rowCount() > 0:
            self.summary_table.selectRow(0)

    def populate_summary_table(self):
        # ... (이전과 동일)
        self.summary_table.setRowCount(len(self.results_data))
        for row, report in enumerate(self.results_data):
            status = report.get('status', 'UNKNOWN'); item_name = QTableWidgetItem(report.get('scenario_name', 'N/A')); item_status = QTableWidgetItem(status); item_msg = QTableWidgetItem(report.get('message', '')); item_context = QTableWidgetItem(str(report.get('context', {})));
            color = {"SUCCESS": QColor("lightgreen"), "FAIL": QColor("lightcoral"), "INCOMPLETE": QColor("lightyellow")}.get(status)
            if color: item_status.setBackground(color)
            self.summary_table.setItem(row, 0, item_name); self.summary_table.setItem(row, 1, item_status); self.summary_table.setItem(row, 2, item_msg); self.summary_table.setItem(row, 3, item_context)

    def on_attempt_selected(self):
        selected_rows = self.summary_table.selectionModel().selectedRows()
        if not selected_rows: 
            self.timeline_view.setRowCount(0)
            return
        
        selected_row_index = selected_rows[0].row()
        report = self.results_data[selected_row_index]
        involved_events = report.get('involved_logs', [])
        
        self.timeline_view.setRowCount(len(involved_events))
        
        last_timestamp = None
        for i, event_info in enumerate(involved_events):
            step_name = event_info.get("step_name", f"Step {i}")
            timestamp = event_info.get("timestamp")
            log_index = event_info.get("log_index")

            # ✅ 2. 타임스탬프와 Delta 정보 표시
            delta_sec_str = ""
            if last_timestamp and timestamp:
                delta = (timestamp - last_timestamp).total_seconds()
                delta_sec_str = f"{delta:.3f}"
            
            # ✅ 3. 구체적인 분석 내용(단계 이름) 표시
            self.timeline_view.setItem(i, 0, QTableWidgetItem(step_name))
            self.timeline_view.setItem(i, 1, QTableWidgetItem(str(timestamp)))
            self.timeline_view.setItem(i, 2, QTableWidgetItem(delta_sec_str))
            self.timeline_view.setItem(i, 3, QTableWidgetItem(str(log_index)))
            
            last_timestamp = timestamp

    def on_log_selected(self, item):
        # ... (이전과 동일)
        log_index_str = self.timeline_view.item(item.row(), 3).text()
        try: self.highlight_log_requested.emit(int(log_index_str));
        except (ValueError, TypeError): pass