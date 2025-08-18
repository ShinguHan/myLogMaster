import pandas as pd
import oracledb
from PySide6.QtCore import QThread, Signal

class OracleFetcherThread(QThread):
    # 진행 상황(텍스트), 데이터 Chunk(데이터프레임), 완료, 에러를 알리는 신호
    progress = Signal(str)
    data_fetched = Signal(pd.DataFrame)
    finished = Signal()
    error = Signal(str)

    def __init__(self, connection_info, query_conditions, chunk_size=1000):
        super().__init__()
        self.conn_info = connection_info
        self.conditions = query_conditions
        self.chunk_size = chunk_size
        self._is_running = True

    def run(self):
        """백그라운드에서 실행될 메인 로직"""
        try:
            self.progress.emit("Connecting to Oracle DB...")
            # ⭐️ 여기에 실제 oracledb.connect() 코드가 들어갑니다.
            # 예시: conn = oracledb.connect(user=..., password=..., dsn=...)
            # 지금은 테스트를 위해 가상 데이터를 생성합니다.
            
            self.progress.emit("Connection successful. Fetching data...")
            
            # TODO: 실제 쿼리 실행 로직으로 교체
            # cursor = conn.cursor()
            # cursor.execute("SELECT ... WHERE ...", self.conditions)
            
            # --- 가상 데이터 생성 로직 (테스트용) ---
            import time
            from datetime import datetime, timedelta
            
            print("--- Generating mock data for testing ---")
            mock_data = []
            start_time = datetime(2025, 8, 18, 14, 0, 0)
            for i in range(5000):
                row_time = start_time + timedelta(milliseconds=i*10)
                mock_data.append({
                    "Category": "Info", "LevelID": 7, "SystemDate": row_time.strftime('%d-%b-%Y %H:%M:%S:%f')[:-3],
                    "DeviceID": "SUPERCAR01", "MethodID": "mock.data", "TrackingID": f"MOCK_{i}",
                    "AsciiData": f"Mock log entry number {i}", "SourceID": "MockSource",
                    "MessageName": "mock", "LogParserClassName": None, "BinaryData": None,
                    "NumericalTimeStamp": int(row_time.timestamp() * 1000), "ParsedBody": None,
                    "ParsedBodyObject": None, "ParsedType": "Log", "SystemDate_dt": row_time
                })
                if len(mock_data) >= self.chunk_size:
                    if not self._is_running: break
                    df_chunk = pd.DataFrame(mock_data)
                    self.data_fetched.emit(df_chunk)
                    mock_data = []
                    time.sleep(0.5) # 네트워크 지연 흉내
            
            if mock_data and self._is_running:
                df_chunk = pd.DataFrame(mock_data)
                self.data_fetched.emit(df_chunk)
            # --- 가상 데이터 생성 로직 끝 ---

            self.progress.emit("Data fetching complete.")

        except Exception as e:
            self.error.emit(f"Oracle DB Error: {e}")
        finally:
            self.finished.emit()

    def stop(self):
        self._is_running = False