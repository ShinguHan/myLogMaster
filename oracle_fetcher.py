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
            source = self.conditions.get('data_source', 'real')
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
        """임무 1: Real Database에서 특정 시간 범위의 데이터를 조회합니다. (실제 쿼리 반영)"""
        conn = None
        try:
            if not self.conditions.get('start_time') or not self.conditions.get('end_time'):
                end_time = datetime.now()
                start_time = end_time - timedelta(minutes=1)
                self.conditions['start_time'] = start_time.strftime('%Y-%m-%dT%H:%M:%S')
                self.conditions['end_time'] = end_time.strftime('%Y-%m-%dT%H:%M:%S')
                self.progress.emit("Time range not set. Defaulting to last 1 minute.")

            # --- 1. 기본 쿼리 및 파라미터 준비 ---
            # ISO 형식 문자열('YYYY-MM-DDTHH:MI:SS')을 Oracle TO_DATE가 인식하는 형식('YYYY-MM-DD HH24:MI:SS')으로 변환
            start_time_str = self.conditions['start_time'].replace('T', ' ')
            end_time_str = self.conditions['end_time'].replace('T', ' ')
            
            params = {
                'p_start_time': start_time_str,
                'p_end_time': end_time_str
            }
            
            # --- 2. 기본 SELECT 구문 정의 ---
            base_query = """
            SELECT 
                TO_CHAR(
                    (TIMESTAMP '1970-01-01 00:00:00 UTC' + NUMTODSINTERVAL(A.SYSTEMDATE/1000, 'SECOND')) AT TIME ZONE 'America/New_York', 
                    'YYYY-MM-DD HH24:MI:SS.FF3'
                ) AS SystemDate,
                A.SYSTEMDATE AS NumericalTimeStamp,
                LEVELID AS LevelID, 
                CATEGORY AS Category, 
                METHODID AS MethodID, 
                DEVICEID AS DeviceID, 
                TRACKINGID AS TrackingID, 
                MESSAGENAME AS MessageName, 
                ASCIIDATA AS AsciiData, 
                UTL_RAW.CAST_TO_RAW(BINARYDATA) AS BinaryData
            FROM CLASS.LOGDATA A
            """

            # --- 3. WHERE 절 동적 생성 ---
            # 시간 변환 SQL 템플릿
            time_conversion_template = """
            (CAST(
                (FROM_TZ(CAST(TO_DATE(:{time_param}, 'YYYY-MM-DD HH24:MI:SS') AS TIMESTAMP), 'America/New_York') AT TIME ZONE 'UTC')
                AS DATE
            ) - DATE '1970-01-01') * 86400000
            """
            
            where_clauses = [
                "A.SYSTEMDATE >= " + time_conversion_template.format(time_param='p_start_time'),
                "A.SYSTEMDATE < " + time_conversion_template.format(time_param='p_end_time')
            ]
            
            # AppController로부터 고급 필터 조건 가져오기
            adv_clause, adv_params = self.parent()._parse_filter_group(self.conditions.get('advanced_filter', {}))
            if adv_clause:
                where_clauses.append(f"({adv_clause})")
                params.update(adv_params)
            
            final_query = f"{base_query} WHERE {' AND '.join(where_clauses)}"

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
                    
                    columns = [desc[0].upper() for desc in cursor.description]
                    # DataFrame 컬럼 이름을 애플리케이션에서 사용하는 CamelCase로 변경
                    df_chunk = pd.DataFrame(rows, columns=columns)
                    df_chunk.columns = ['SystemDate', 'NumericalTimeStamp', 'LevelID', 'Category', 'MethodID', 'DeviceID', 'TrackingID', 'MessageName', 'AsciiData', 'BinaryData']
                    
                    self.data_fetched.emit(df_chunk)

            if self._is_running and self.conditions.get('tail_after_query'):
                self.progress.emit("Initial data fetched. Starting real-time tailing...")
                self._run_db_real_time(connection=conn)
            else:
                if self._is_running: self.progress.emit("Data fetching complete.")

        except oracledb.DatabaseError as e:
            error_obj, = e.args; self.error.emit(f"DB Error: {error_obj.message}")
        finally:
            if conn and not (self._is_running and self.conditions.get('tail_after_query')):
                conn.close()

    def _run_db_real_time(self, connection=None):
        """임무 2: Real Database에서 새로운 로그를 실시간으로 추적합니다. (실제 쿼리 반영)"""
        conn = connection
        try:
            if not conn:
                self.progress.emit("Connecting to Oracle DB for real-time tailing...")
                db_conn_info = self.conn_info.copy()
                db_conn_info.pop('type', None)
                conn = oracledb.connect(**db_conn_info)
                self.progress.emit("Connection successful. Tailing logs...")
            
            cursor = conn.cursor()
            # ✅ 테이블과 컬럼 이름 수정
            cursor.execute("SELECT MAX(SYSTEMDATE) FROM CLASS.LOGDATA")
            last_timestamp, = cursor.fetchone()
            if last_timestamp is None: last_timestamp = 0

            # ✅ SELECT 구문 수정
            base_query = """
            SELECT 
                TO_CHAR(
                    (TIMESTAMP '1970-01-01 00:00:00 UTC' + NUMTODSINTERVAL(A.SYSTEMDATE/1000, 'SECOND')) AT TIME ZONE 'America/New_York', 
                    'YYYY-MM-DD HH24:MI:SS.FF3'
                ) AS SystemDate,
                A.SYSTEMDATE AS NumericalTimeStamp,
                LEVELID AS LevelID, CATEGORY AS Category, METHODID AS MethodID, 
                DEVICEID AS DeviceID, TRACKINGID AS TrackingID, MESSAGENAME AS MessageName, 
                ASCIIDATA AS AsciiData, UTL_RAW.CAST_TO_RAW(BINARYDATA) AS BinaryData
            FROM CLASS.LOGDATA A
            """

            while self._is_running:
                if self._is_paused:
                    time.sleep(1); continue
                
                time.sleep(2)
                
                # ✅ WHERE 조건 수정
                clauses = ["A.SYSTEMDATE > :ts"]
                params = {'ts': last_timestamp}
                
                keyword = self.conditions.get('realtime_keyword')
                if keyword:
                    clauses.append("INSTR(LOWER(ASCIIDATA), LOWER(:keyword)) > 0")
                    params['keyword'] = keyword

                final_query = f"{base_query} WHERE {' AND '.join(clauses)} ORDER BY A.SYSTEMDATE"
                
                cursor.execute(final_query, params)
                rows = cursor.fetchall()
                if rows:
                    columns = [desc[0].upper() for desc in cursor.description]
                    df_chunk = pd.DataFrame(rows, columns=columns)
                    # DataFrame 컬럼 이름을 애플리케이션에서 사용하는 CamelCase로 변경
                    df_chunk.columns = ['SystemDate', 'NumericalTimeStamp', 'LevelID', 'Category', 'MethodID', 'DeviceID', 'TrackingID', 'MessageName', 'AsciiData', 'BinaryData']
                    
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
                "SystemDate": row_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
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
                    "SystemDate": row_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                    "DeviceID": f"MOCK_RT_{i}",
                    "TrackingID": device_id, 
                    "NumericalTimeStamp": int(row_time.timestamp() * 1000)
                })
                i += 1
            self.data_fetched.emit(pd.DataFrame(mock_data))

