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

    def __init__(self, connection_info, query_conditions, chunk_size=1000, use_mock_data=True):
        super().__init__()
        self.conn_info = connection_info
        self.conditions = query_conditions
        self.chunk_size = chunk_size
        self._is_running = True
        self.use_mock_data = use_mock_data # 💡 테스트용 Mock 데이터 사용 여부 플래그

    def run(self):
        """백그라운드에서 실행될 메인 로직"""
        if self.use_mock_data:
            self._run_mock_data_generator()
            return

        conn = None
        try:
            self.progress.emit("Connecting to Oracle DB...")
            # ⭐️ 1. 실제 DB 연결 (환경에 맞게 수정)
            # conn = oracledb.connect(
            #     user=self.conn_info.get('user'),
            #     password=self.conn_info.get('password'),
            #     dsn=self.conn_info.get('dsn')
            # )
            self.progress.emit("Connection successful. Fetching data...")

            # ⭐️ 2. 실제 쿼리 실행
            with conn.cursor() as cursor:
                # TODO: self.conditions를 바탕으로 실제 쿼리문과 바인딩 변수 생성
                # 예시: query = "SELECT * FROM YOUR_LOG_TABLE WHERE SystemDate BETWEEN :start_date AND :end_date"
                query = "SELECT * FROM V_LOG_MESSAGE" # 실제 쿼리문으로 변경
                
                # cursor.execute(query, self.conditions) # 쿼리 조건 바인딩
                cursor.execute(query)

                while self._is_running:
                    rows = cursor.fetchmany(self.chunk_size)
                    if not rows:
                        break
                    
                    columns = [desc[0] for desc in cursor.description]
                    df_chunk = pd.DataFrame(rows, columns=columns)
                    self.data_fetched.emit(df_chunk)

            if self._is_running:
                self.progress.emit("Data fetching complete.")

        # ⭐️ 3. 구체적인 예외 처리
        except oracledb.DatabaseError as e:
            self.error.emit(f"Oracle DB Error: {e}")
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
            for i in range(5000): # 총 5000개 데이터 생성
                if not self._is_running: break
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
                    time.sleep(0.1)  # 네트워크 지연 흉내

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