import pandas as pd
from sqlalchemy import create_engine, text
import json

LOGS_TABLE_NAME = "logs"

class DatabaseManager:
    def __init__(self, connection_name):
        """
        선택된 DB 연결(connection_name)에 해당하는
        고유한 로컬 캐시 파일을 생성하고 관리합니다.
        """
        local_db_file = f"cache_{connection_name}.db"
        self.local_engine = create_engine(f'sqlite:///{local_db_file}')
        self._create_local_tables()
        print(f"DatabaseManager for '{connection_name}' initialized. Using cache file: {local_db_file}")

    def _create_local_tables(self):
        """로컬 캐시에 필요한 모든 테이블을 생성합니다. (테이블이 없을 경우에만)"""
        try:
            with self.local_engine.connect() as connection:
                connection.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {LOGS_TABLE_NAME} (
                    Category TEXT, LevelID INTEGER, SystemDate TEXT, DeviceID TEXT,
                    MethodID TEXT, TrackingID TEXT, AsciiData TEXT, SourceID TEXT,
                    MessageName TEXT, LogParserClassName TEXT, BinaryData TEXT,
                    NumericalTimeStamp INTEGER NOT NULL, ParsedBody TEXT,
                    ParsedBodyObject TEXT, ParsedType TEXT, SystemDate_dt TEXT,
                    PRIMARY KEY (NumericalTimeStamp, DeviceID, TrackingID)
                );
                """))
                
                connection.execute(text("""
                CREATE TABLE IF NOT EXISTS fetch_history (
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    filters_json TEXT NOT NULL,
                    PRIMARY KEY (start_time, end_time, filters_json)
                );
                """))
                
                connection.execute(text("""
                CREATE TABLE IF NOT EXISTS validation_history (
                    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_timestamp TEXT NOT NULL,
                    scenario_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    involved_log_indices TEXT
                );
                """))
            print("Local cache tables are ready.")
        except Exception as e:
            print(f"Error creating local tables: {e}")

    # --- 이하 메서드들은 다음 단계에서 구현될 예정 ---

    def upsert_logs_to_local_cache(self, df):
        if df.empty: return 0
        try:
            rows_affected = df.to_sql(LOGS_TABLE_NAME, self.local_engine, if_exists='append', index=False, chunksize=1000)
            return rows_affected
        except Exception as e:
            print(f"Error during upsert to local cache: {e}")
            return 0

    def read_all_logs_from_cache(self):
        """(임시) 로컬 캐시의 모든 로그를 읽어옵니다."""
        try:
            return pd.read_sql(f'SELECT * FROM {LOGS_TABLE_NAME}', self.local_engine)
        except Exception as e:
            print(f"Error reading from local cache: {e}")
            return pd.DataFrame()