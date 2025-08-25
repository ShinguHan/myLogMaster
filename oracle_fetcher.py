import pandas as pd
import oracledb
from PySide6.QtCore import QThread, Signal, QDateTime, Qt
import time
from datetime import datetime, timedelta

class OracleFetcherThread(QThread):
    progress = Signal(str)
    data_fetched = Signal(pd.DataFrame)
    finished = Signal()
    error = Signal(str)

    def __init__(self, connection_info, query_conditions, chunk_size=1000, parent=None):
        super().__init__(parent)
        self.conn_info = connection_info
        self.conditions = query_conditions # '작전명령서'를 통째로 받음
        self.chunk_size = chunk_size
        self._is_running = True

    def run(self):
        """'작전명령서'를 해석하여 적절한 임무를 수행하는 메인 로직"""
        try:
            source = self.conditions.get('data_source')
            mode = self.conditions.get('analysis_mode')

            if source == 'mock':
                if mode == 'time_range':
                    self._run_mock_time_range()
                else: # real_time
                    self._run_mock_real_time()
            else: # real
                if mode == 'time_range':
                    self._run_db_time_range()
                else: # real_time
                    self._run_db_real_time()
        except Exception as e:
            self.error.emit(f"An unexpected error occurred in fetcher: {e}")
            # 에러 발생 시에도 finished 신호를 보내 UI가 멈추지 않도록 함
            self.finished.emit()

    # --- 4가지 임무 수행을 위한 개별 메소드들 ---

    def _run_db_time_range(self):
        """임무 1: Real Database에서 특정 시간 범위의 데이터를 조회합니다."""
        conn = None
        try:
            # 컨트롤러의 _build_where_clause 메소드를 호출하여 SQL 조건 생성
            where_clause, params = self.parent()._build_where_clause(self.conditions)
            
            self.progress.emit("Connecting to Oracle DB...")
            conn = oracledb.connect(**self.conn_info)
            self.progress.emit("Connection successful. Fetching data...")

            base_query = "SELECT * FROM V_LOG_MESSAGE"
            final_query = f"{base_query} WHERE {where_clause}" if where_clause else base_query
            
            with conn.cursor() as cursor:
                cursor.execute(final_query, params)
                while self._is_running:
                    rows = cursor.fetchmany(self.chunk_size)
                    if not rows: break
                    columns = [desc[0] for desc in cursor.description]
                    df_chunk = pd.DataFrame(rows, columns=columns)
                    self.data_fetched.emit(df_chunk)
            if self._is_running: self.progress.emit("Data fetching complete.")
        except oracledb.DatabaseError as e:
            error_obj, = e.args; self.error.emit(f"DB Error: {error_obj.message}")
        finally:
            if conn: conn.close()
            self.finished.emit()

    def _run_db_real_time(self):
        """임무 2: Real Database에서 새로운 로그를 실시간으로 추적합니다."""
        conn = None
        try:
            self.progress.emit("Connecting to Oracle DB for real-time tailing...")
            conn = oracledb.connect(**self.conn_info)
            self.progress.emit("Connection successful. Tailing logs...")
            
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(NumericalTimeStamp) FROM V_LOG_MESSAGE")
            last_timestamp, = cursor.fetchone()
            if last_timestamp is None: last_timestamp = 0

            while self._is_running:
                time.sleep(2)
                cursor.execute("SELECT * FROM V_LOG_MESSAGE WHERE NumericalTimeStamp > :ts ORDER BY NumericalTimeStamp", ts=last_timestamp)
                rows = cursor.fetchall()
                if rows:
                    columns = [desc[0] for desc in cursor.description]
                    df_chunk = pd.DataFrame(rows, columns=columns)
                    self.data_fetched.emit(df_chunk)
                    last_timestamp = df_chunk['NumericalTimeStamp'].max()
        except oracledb.DatabaseError as e:
            error_obj, = e.args; self.error.emit(f"DB Error: {error_obj.message}")
        finally:
            if conn: conn.close()
            self.finished.emit()

    def _run_mock_time_range(self):
        """임무 3: 특정 시간 범위의 Mock 데이터를 생성합니다."""
        self.progress.emit("Generating mock data for the selected time range...")
        start_dt = QDateTime.fromString(self.conditions['start_time'], Qt.DateFormat.ISODate).toPython()
        end_dt = QDateTime.fromString(self.conditions['end_time'], Qt.DateFormat.ISODate).toPython()
        total_seconds = (end_dt - start_dt).total_seconds()
        num_rows = int(max(1000, min(50000, total_seconds))) # 초당 1개, 최소 1000개, 최대 50000개

        mock_data = []
        for i in range(num_rows):
            if not self._is_running: break
            row_time = start_dt + timedelta(seconds=(total_seconds * i / num_rows))
            mock_data.append({
                "Category": "Mock-TimeRange", 
                "SystemDate": row_time.strftime('%d-%b-%Y %H:%M:%S:%f')[:-3],
                "DeviceID": f"MOCK_TR_{i}",
                "NumericalTimeStamp": int(row_time.timestamp() * 1000)
            })
            if len(mock_data) >= self.chunk_size:
                self.data_fetched.emit(pd.DataFrame(mock_data)); mock_data = []
                time.sleep(0.05)
        if mock_data: self.data_fetched.emit(pd.DataFrame(mock_data))
        if self._is_running: self.progress.emit("Mock data generation complete.")
        self.finished.emit()

    def _run_mock_real_time(self):
        """임무 4: Mock 데이터를 실시간처럼 계속 생성합니다."""
        self.progress.emit("Starting real-time mock data generation...")
        i = 0
        while self._is_running:
            time.sleep(0.5)
            mock_data = []
            for _ in range(10):
                row_time = datetime.now()
                mock_data.append({
                    "Category": "Mock-RealTime", 
                    "SystemDate": row_time.strftime('%d-%b-%Y %H:%M:%S:%f')[:-3],
                    "DeviceID": f"MOCK_RT_{i}",
                    "NumericalTimeStamp": int(row_time.timestamp() * 1000)
                })
                i += 1
            self.data_fetched.emit(pd.DataFrame(mock_data))
        self.finished.emit()

    def stop(self):
        self._is_running = False