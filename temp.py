# shinguhan/mylogmaster/myLogMaster-main/main_window.py

# ... (기존 import)

class MainWindow(QMainWindow):
    # ... (__init__ 메소드는 동일)

    def _create_menu(self):
        menu_bar = self.menuBar()
        
        # 파일 메뉴 (변경 없음)
        file_menu = menu_bar.addMenu("&File")
        # ...
        
        # ✅ 1. View와 Tools 메뉴를 인스턴스 변수로 저장하여 나중에 접근할 수 있도록 함
        self.view_menu = menu_bar.addMenu("&View")
        select_columns_action = QAction("&Select Columns...", self)
        select_columns_action.triggered.connect(self.open_column_selection_dialog)
        self.view_menu.addAction(select_columns_action)
        self.view_menu.addSeparator()
        dashboard_action = QAction("Show Dashboard...", self)
        dashboard_action.triggered.connect(self.show_dashboard)
        self.view_menu.addAction(dashboard_action)

        self.tools_menu = menu_bar.addMenu("&Tools")
        query_builder_action = QAction("Advanced Filter...", self)
        query_builder_action.triggered.connect(self.open_query_builder)
        self.tools_menu.addAction(query_builder_action)
        # ... (나머지 Tools 메뉴 구성은 동일)
        
        help_menu = menu_bar.addMenu("&Help")
        # ...

    def setup_ui_for_mode(self):
        if self.controller.mode == 'realtime':
            self.db_connect_button.setVisible(True)
            self.filter_input.setVisible(False) # 실시간 모드에서는 기본 필터 숨김
            self.auto_scroll_checkbox.setVisible(True)
            self.setWindowTitle(f"Log Analyzer - [DB: {self.controller.connection_name}]")
            self.statusBar().showMessage("Ready to connect to the database.")
        else: # file mode
            self.db_connect_button.setVisible(False)
            self.filter_input.setVisible(True)
            self.auto_scroll_checkbox.setVisible(False) # 파일 모드에서는 자동 스크롤 숨김
            self.setWindowTitle("Log Analyzer - [File Mode]")
            self.statusBar().showMessage("Ready. Please open a log file.")
    
    def start_db_connection(self):
        if self._is_fetching:
            # ... (취소 로직은 동일)
        else:
            # --- 조회 시작 로직 ---
            dialog = QueryConditionsDialog(self)
            if dialog.exec():
                # ... (기존 조회 시작 로직)
                self.controller.start_db_fetch(query_conditions)
                
                self._is_fetching = True
                self.db_connect_button.setText("❌ 데이터 수신 중단")
                self.db_connect_button.setStyleSheet("background-color: #DA4453; color: white;")

                # ✅ 2. 데이터 수신 중에는 분석/뷰 메뉴 비활성화
                if self.controller.mode == 'realtime':
                    self.tools_menu.setEnabled(False)
                    self.view_menu.setEnabled(False)

    def on_fetch_complete(self):
        self._is_fetching = False
        self.db_connect_button.setText("📡 데이터베이스에 연결하여 로그 조회")
        self.db_connect_button.setStyleSheet("") 
        
        # ✅ 3. 작업 완료/취소/에러 시 분석/뷰 메뉴 다시 활성화
        if self.controller.mode == 'realtime':
            self.tools_menu.setEnabled(True)
            self.view_menu.setEnabled(True)
        
        source_model = self.proxy_model.sourceModel()
        if source_model:
            total_rows = source_model.rowCount()
            if self.statusBar().currentMessage() != "Cancelling...":
                 self.statusBar().showMessage(f"Completed. Total {total_rows:,} logs in view.")
                 
    # ... (나머지 코드는 모두 동일)