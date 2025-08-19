# shinguhan/mylogmaster/myLogMaster-main/database_manager.py

import pandas as pd
from sqlalchemy import create_engine, text
import json

LOGS_TABLE_NAME = "logs"

class DatabaseManager:
    # ... (__init__, _create_local_tables, clear_logs_from_cache 메소드는 동일)
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

    def clear_logs_from_cache(self):
        """로컬 캐시의 'logs' 테이블에 있는 모든 데이터를 삭제합니다."""
        try:
            with self.local_engine.connect() as connection:
                with connection.begin(): # 트랜잭션 시작
                    connection.execute(text(f"DELETE FROM {LOGS_TABLE_NAME};"))
            print("Cleared all logs from the local cache.")
            return True
        except Exception as e:
            print(f"Error clearing logs from local cache: {e}")
            return False

    # ✅ 아래 메소드 추가
    def add_fetch_history(self, start_time, end_time, filters):
        """조회 이력을 fetch_history 테이블에 추가합니다."""
        try:
            with self.local_engine.connect() as connection:
                with connection.begin(): # 트랜잭션 시작
                    filters_json = json.dumps(filters)
                    stmt = text("""
                        INSERT INTO fetch_history (start_time, end_time, filters_json)
                        VALUES (:start, :end, :filters)
                        ON CONFLICT(start_time, end_time, filters_json) DO NOTHING
                    """)
                    connection.execute(stmt, {"start": start_time, "end": end_time, "filters": filters_json})
            print(f"Saved fetch history: {start_time} to {end_time}")
        except Exception as e:
            print(f"Error saving fetch history: {e}")

    # ✅ 이 메소드 수정
    def upsert_logs_to_local_cache(self, df):
        """데이터프레임을 트랜잭션을 사용하여 로컬 캐시에 안전하게 저장합니다."""
        if df.empty: return 0
        
        # 트랜잭션 외부에서 연결을 시작합니다.
        with self.local_engine.connect() as connection:
            # 트랜잭션을 시작합니다. 이 블록 내에서 오류 발생 시 자동 롤백됩니다.
            with connection.begin():
                try:
                    # to_sql은 내부적으로 INSERT를 수행합니다.
                    # UNIQUE 제약 조건 충돌 시 IntegrityError가 발생할 수 있습니다.
                    # 이를 방지하기 위해 중복 데이터를 미리 제거합니다.
                    
                    # 1. 기존 DB에 있는 키들을 조회합니다.
                    existing_keys_query = f"SELECT NumericalTimeStamp, DeviceID, TrackingID FROM {LOGS_TABLE_NAME}"
                    existing_keys_df = pd.read_sql(existing_keys_query, connection)
                    
                    if not existing_keys_df.empty:
                        # 2. DataFrame에서 중복되는 데이터를 제거합니다.
                        df = df.merge(existing_keys_df, on=['NumericalTimeStamp', 'DeviceID', 'TrackingID'], how='left', indicator=True)
                        df = df[df['_merge'] == 'left_only'].drop(columns='_merge')

                    if df.empty:
                        print("No new unique logs to add.")
                        return 0

                    # 3. 중복이 제거된 새로운 데이터만 삽입합니다.
                    rows_affected = df.to_sql(LOGS_TABLE_NAME, connection, if_exists='append', index=False, chunksize=1000)
                    return rows_affected if rows_affected is not None else 0
                
                except Exception as e:
                    print(f"Error during upsert to local cache: {e}. Transaction will be rolled back.")
                    # with 블록이 끝나면서 자동으로 롤백됩니다.
                    raise # 에러를 다시 발생시켜 상위 호출자에게 알립니다.
        return 0
    
    def read_all_logs_from_cache(self):
        """(임시) 로컬 캐시의 모든 로그를 읽어옵니다."""
        try:
            return pd.read_sql(f'SELECT * FROM {LOGS_TABLE_NAME}', self.local_engine)
        except Exception as e:
            print(f"Error reading from local cache: {e}")
            return pd.DataFrame()