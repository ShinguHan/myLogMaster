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

    def __init__(self, connection_info, query_conditions, templates, chunk_size=1000, parent=None):
        super().__init__(parent)
        self.conn_info = connection_info
        self.conditions = query_conditions
        self.templates = templates
        self.chunk_size = chunk_size
        self._is_running = True
        self._is_paused = False

    def run(self):
        """'작전명령서'를 해석하여 적절한 임무를 수행하는 메인 로직"""
        try:
            # --- 데이터 소스에 따라 DB 조회 또는 Mock 데이터 생성 분기 ---
            source = self.conditions.get('data_source', 'real') # 기본값 real
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
        finally:
            if self._is_running:
                self.finished.emit()

    def stop(self):
        self._is_running = False
    
    def pause(self):
        self._is_paused = True
        self.progress.emit("Paused.")

    def resume(self):
        self._is_paused = False
        self.progress.emit("Resuming...")

    def _run_db_time_range(self):
        """임무 1: Real Database에서 특정 시간 범위의 데이터를 조회합니다."""
        conn = None
        try:
            # --- 1. 기본 쿼리 결정 (템플릿 기반) ---
            template_name = self.conditions.get('query_template', 'Default (SELECT * ...)')
            base_query = "SELECT * FROM V_LOG_MESSAGE" # 기본값
            if template_name != 'Default (SELECT * ...)' and template_name in self.templates:
                template_body = self.templates[template_name].get('query')
                if template_body:
                    base_query = template_body
            
            # --- 2. WHERE 절 동적 생성 ---
            where_clause, params = self.parent()._build_where_clause(self.conditions)
            
            if ' where ' in base_query.lower() and where_clause:
                final_query = f"{base_query} AND ({where_clause})"
            elif where_clause:
                final_query = f"{base_query} WHERE {where_clause}"
            else:
                final_query = base_query
            
            self.progress.emit("Connecting to Oracle DB...")
            db_conn_info = self.conn_info.copy()
            db_conn_info.pop('type', None)
            conn = oracledb.connect(**db_conn_info)
            self.progress.emit("Connection successful. Fetching data...")
            
            with conn.cursor() as cursor:
                cursor.execute(final_query, params)
                while self._is_running:
                    if self._is_paused: time.sleep(0.5); continue
                    rows = cursor.fetchmany(self.chunk_size)
                    if not rows: break
                    columns = [desc[0] for desc in cursor.description]
                    df_chunk = pd.DataFrame(rows, columns=columns)
                    self.data_fetched.emit(df_chunk)

            if self._is_running and self.conditions.get('tail_after_query'):
                self.progress.emit("Initial data fetched. Starting real-time tailing...")
                self._run_db_real_time(connection=conn, initial_where_clause=where_clause, initial_params=params)
            else:
                if self._is_running: self.progress.emit("Data fetching complete.")

        except oracledb.DatabaseError as e:
            error_obj, = e.args; self.error.emit(f"DB Error: {error_obj.message}")
        finally:
            if conn and not (self._is_running and self.conditions.get('tail_after_query')):
                conn.close()

    def _run_db_real_time(self, connection=None, initial_where_clause=None, initial_params=None):
        """임무 2: Real Database에서 새로운 로그를 실시간으로 추적합니다."""
        conn = connection
        try:
            if not conn:
                self.progress.emit("Connecting to Oracle DB for real-time tailing...")
                db_conn_info = self.conn_info.copy()
                db_conn_info.pop('type', None)
                conn = oracledb.connect(**db_conn_info)
                self.progress.emit("Connection successful. Tailing logs...")
            
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(NumericalTimeStamp) FROM V_LOG_MESSAGE")
            last_timestamp, = cursor.fetchone()
            if last_timestamp is None: last_timestamp = 0

            while self._is_running:
                if self._is_paused:
                    time.sleep(1); continue
                
                time.sleep(2)
                
                clauses = ["NumericalTimeStamp > :ts"]
                params = {'ts': last_timestamp}
                base_query = "SELECT * FROM V_LOG_MESSAGE"
                keyword = self.conditions.get('realtime_keyword')

                if initial_where_clause:
                    clauses.append(f"({initial_where_clause})")
                    params.update(initial_params)
                elif keyword:
                    clauses.append("INSTR(LOWER(AsciiData), LOWER(:keyword)) > 0")
                    params['keyword'] = keyword

                final_query = f"{base_query} WHERE {' AND '.join(clauses)} ORDER BY NumericalTimeStamp"
                
                cursor.execute(final_query, params)
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

    def _run_mock_time_range(self):
        """임무 3: 특정 시간 범위의 Mock 데이터를 생성합니다."""
        self.progress.emit("Generating mock data for the selected time range...")
        start_dt = QDateTime.fromString(self.conditions['start_time'], Qt.DateFormat.ISODate).toPython()
        end_dt = QDateTime.fromString(self.conditions['end_time'], Qt.DateFormat.ISODate).toPython()
        total_seconds = (end_dt - start_dt).total_seconds()
        num_rows = int(max(1000, min(50000, total_seconds)))

        mock_data = []
        for i in range(num_rows):
            if not self._is_running: break
            row_time = start_dt + timedelta(seconds=(total_seconds * i / num_rows))
            device_id = f"MOCK_TR_{i}"
            mock_data.append({
                "Category": "Mock-TimeRange", 
                "SystemDate": row_time.strftime('%d-%b-%Y %H:%M:%S:%f')[:-3],
                "DeviceID": f"MOCK_TR_{i}",
                "TrackingID": device_id,
                "NumericalTimeStamp": int(row_time.timestamp() * 1000)
            })
            if len(mock_data) >= self.chunk_size:
                self.data_fetched.emit(pd.DataFrame(mock_data)); mock_data = []
                time.sleep(0.05)
        if mock_data: self.data_fetched.emit(pd.DataFrame(mock_data))
        if self._is_running: self.progress.emit("Mock data generation complete.")

    def _run_mock_real_time(self):
        """임무 4: Mock 데이터를 실시간처럼 계속 생성합니다."""
        self.progress.emit("Starting real-time mock data generation...")
        i = 0
        while self._is_running:
            if self._is_paused:
                time.sleep(1)
                continue
            time.sleep(0.5)
            mock_data = []
            for _ in range(10):
                row_time = datetime.now()
                device_id = f"MOCK_RT_{i}"
                mock_data.append({
                    "Category": "Mock-RealTime", 
                    "SystemDate": row_time.strftime('%d-%b-%Y %H:%M:%S:%f')[:-3],
                    "DeviceID": f"MOCK_RT_{i}",
                    "TrackingID": device_id, 
                    "NumericalTimeStamp": int(row_time.timestamp() * 1000)
                })
                i += 1
            self.data_fetched.emit(pd.DataFrame(mock_data))

