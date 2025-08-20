# shinguhan/mylogmaster/myLogMaster-main/oracle_fetcher.py

import pandas as pd
import oracledb
from PySide6.QtCore import QThread, Signal
import time
from datetime import datetime, timedelta

class OracleFetcherThread(QThread):
    # 진행 상황(텍스트), 데이터 Chunk(데이터프레임), 완료, 에러를 알리는 신호
    progress = Signal(str)
    data_fetched = Signal(pd.DataFrame)
    finished = Signal()
    error = Signal(str)

    def __init__(self, connection_info, where_clause, params, chunk_size=1000, use_mock_data=False): # ✅ use_mock_data 기본값을 False로 변경
        super().__init__()
        self.conn_info = connection_info
        # ✅ WHERE 절과 파라미터를 직접 받도록 수정
        self.where_clause = where_clause
        self.params = params
        self.chunk_size = chunk_size
        self._is_running = True
        self.use_mock_data = use_mock_data

    def run(self):
        """백그라운드에서 실행될 메인 로직"""
        if self.use_mock_data:
            self._run_mock_data_generator()
            return

        conn = None
        try:
            self.progress.emit("Connecting to Oracle DB...")
            # ⭐️ 실제 DB 연결 (환경에 맞게 수정)
            conn = oracledb.connect(
                user=self.conn_info.get('user'),
                password=self.conn_info.get('password'),
                dsn=self.conn_info.get('dsn')
            )
            self.progress.emit("Connection successful. Fetching data...")

            # ✅ 1. 동적으로 생성된 WHERE 절을 사용하여 최종 쿼리 생성
            base_query = "SELECT * FROM V_LOG_MESSAGE"
            final_query = f"{base_query} WHERE {self.where_clause}"
            
            self.progress.emit(f"Executing query: {final_query}")

            with conn.cursor() as cursor:
                # ✅ 2. 파라미터를 바인딩하여 SQL Injection을 방지하며 안전하게 실행
                cursor.execute(final_query, self.params)
                
                while self._is_running:
                    rows = cursor.fetchmany(self.chunk_size)
                    if not rows:
                        break
                    
                    columns = [desc[0] for desc in cursor.description]
                    df_chunk = pd.DataFrame(rows, columns=columns)
                    self.data_fetched.emit(df_chunk)

            if self._is_running:
                self.progress.emit("Data fetching complete.")
            else:
                self.progress.emit("Fetching cancelled by user.")

        except oracledb.DatabaseError as e:
            # Oracle 에러를 더 사용자 친화적으로 표시
            error_obj, = e.args
            self.error.emit(f"DB Error: {error_obj.message}")
        except Exception as e:
            self.error.emit(f"An unexpected error occurred: {e}")
        finally:
            if conn:
                conn.close()
            self.finished.emit()

    def _run_mock_data_generator(self):
        """테스트용 가상 데이터를 생성하는 로직"""
        try:
            self.progress.emit("Generating mock data for testing...")
            
            mock_data = []
            start_time = datetime(2025, 8, 18, 14, 0, 0)
            for i in range(500000): # 총 5000개 데이터 생성
                # ✅ 루프 시작 시점에 항상 실행 여부 체크
                if not self._is_running:
                    self.progress.emit("Fetching cancelled by user.")
                    break

                row_time = start_time + timedelta(milliseconds=i * 10)
                mock_data.append({
                    "Category": "Info", "LevelID": 7, "SystemDate": row_time.strftime('%d-%b-%Y %H:%M:%S:%f')[:-3],
                    "DeviceID": "SUPERCAR01", "MethodID": "mock.data", "TrackingID": f"MOCK_{i}",
                    "AsciiData": f"Mock log entry number {i}", "SourceID": "MockSource",
                    "MessageName": "mock", "LogParserClassName": None, "BinaryData": None,
                    "NumericalTimeStamp": int(row_time.timestamp() * 1000), "ParsedBody": None,
                    "ParsedBodyObject": None, "ParsedType": "Log", "SystemDate_dt": row_time
                })
                
                if len(mock_data) >= self.chunk_size:
                    df_chunk = pd.DataFrame(mock_data)
                    self.data_fetched.emit(df_chunk)
                    mock_data = []
                    time.sleep(0.01)  # 네트워크 지연 흉내

            if mock_data and self._is_running:
                df_chunk = pd.DataFrame(mock_data)
                self.data_fetched.emit(df_chunk)
            
            self.progress.emit("Mock data generation complete.")
        except Exception as e:
            self.error.emit(f"Mock data generator error: {e}")
        finally:
            self.finished.emit()

    def stop(self):
        self._is_running = False