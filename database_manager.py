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

    def upsert_logs_to_local_cache(self, df):
        """
        데이터프레임을 로컬 캐시에 안전하게 저장(upsert)합니다.
        - PK의 None 값을 ''로 변환
        - 데이터 묶음 내 중복 제거
        - DB와 중복되는 데이터 제거
        """
        if df.empty:
            return 0

        pk_cols = ['NumericalTimeStamp', 'DeviceID', 'TrackingID']

        # 1단계: PK 컬럼의 None 값을 빈 문자열로 변환 (NOT NULL 제약 조건 충족)
        for col in ['DeviceID', 'TrackingID']:
            if col in df.columns:
                df[col] = df[col].fillna('')

        # 2단계: 새로 들어온 데이터 묶음(DataFrame) 내에서 중복 제거
        df.drop_duplicates(subset=pk_cols, keep='first', inplace=True)
        if df.empty:
            return 0  # 모든 데이터가 내부 중복이었습니다.

        with self.local_engine.connect() as connection:
            with connection.begin():  # 트랜잭션 시작
                try:
                    # 3단계: DB에 이미 존재하는 데이터와 중복 제거
                    existing_keys_query = f"SELECT {', '.join(pk_cols)} FROM {LOGS_TABLE_NAME}"
                    existing_keys_df = pd.read_sql(existing_keys_query, connection)
                    
                    if not existing_keys_df.empty:
                        # DB에서 가져온 키도 None -> '' 처리하여 일관성 유지
                        for col in ['DeviceID', 'TrackingID']:
                            if col in existing_keys_df.columns:
                                existing_keys_df[col] = existing_keys_df[col].fillna('')
                        
                        # merge를 통해 DB에 없는 새로운 데이터만 필터링
                        df_merged = df.merge(
                            existing_keys_df, on=pk_cols, how='left', indicator=True
                        )
                        df_to_insert = df_merged[df_merged['_merge'] == 'left_only'].drop(columns='_merge')
                    else:
                        df_to_insert = df

                    if df_to_insert.empty:
                        # print("No new unique logs to add to the cache.")
                        return 0

                    # 4단계: 최종적으로 중복이 제거된 데이터만 DB에 추가
                    rows_affected = df_to_insert.to_sql(
                        LOGS_TABLE_NAME, connection, if_exists='append', index=False, chunksize=1000
                    )
                    return rows_affected if rows_affected is not None else 0
                
                except Exception as e:
                    print(f"Error during upsert to local cache: {e}. Transaction will be rolled back.")
                    raise
        return 0
    
    def read_all_logs_from_cache(self, limit=None):
        """로컬 캐시의 로그를 읽어옵니다. limit가 주어지면 최신 로그부터 해당 개수만큼 읽어옵니다."""
        try:
            query = f'SELECT * FROM {LOGS_TABLE_NAME}'
            if limit is not None:
                # NumericalTimeStamp는 로그의 시간 순서를 나타내는 정수형 타임스탬프라고 가정
                query += f' ORDER BY NumericalTimeStamp DESC LIMIT {limit}'
            return pd.read_sql(query, self.local_engine)
        except Exception as e:
            print(f"Error reading from local cache: {e}")
            return pd.DataFrame()
        
    def add_validation_history(self, scenario_name, status, message, involved_log_indices):
        """시나리오 분석 결과를 validation_history 테이블에 저장합니다."""
        try:
            serializable_logs = []
            for log_event in involved_log_indices:
                if isinstance(log_event, dict) and 'timestamp' in log_event:
                    event_copy = log_event.copy()
                    event_copy['timestamp'] = event_copy['timestamp'].isoformat()
                    serializable_logs.append(event_copy)
                else:
                    serializable_logs.append(log_event)

            with self.local_engine.connect() as connection:
                with connection.begin():
                    indices_json = json.dumps(serializable_logs, ensure_ascii=False)
                    stmt = text("""
                        INSERT INTO validation_history (run_timestamp, scenario_name, status, message, involved_log_indices)
                        VALUES (datetime('now', 'localtime'), :name, :status, :msg, :indices)
                    """)
                    connection.execute(stmt, {
                        "name": scenario_name, "status": status, "msg": message, "indices": indices_json
                    })
            print(f"Saved validation history for '{scenario_name}'.")
        except Exception as e:
            print(f"Error saving validation history: {e}")

    def get_validation_history_summary(self):
        """저장된 모든 분석 이력의 요약 목록을 반환합니다."""
        try:
            query = "SELECT run_id, run_timestamp, scenario_name, status, message FROM validation_history ORDER BY run_timestamp DESC"
            with self.local_engine.connect() as connection:
                return pd.read_sql(query, connection)
        except Exception as e:
            print(f"Error fetching validation history summary: {e}")
            return pd.DataFrame()

    def get_validation_history_detail(self, run_id):
        """특정 run_id에 해당하는 상세 분석 결과를 반환합니다."""
        try:
            query = "SELECT * FROM validation_history WHERE run_id = :id"
            with self.local_engine.connect() as connection:
                result = pd.read_sql(query, connection, params={"id": run_id}).iloc[0]
            
            report = result.to_dict()
            report['involved_logs'] = json.loads(report['involved_log_indices'])
            
            for log_event in report['involved_logs']:
                if isinstance(log_event, dict) and 'timestamp' in log_event:
                    log_event['timestamp'] = pd.to_datetime(log_event['timestamp'])
            return report
        except Exception as e:
            print(f"Error fetching validation history detail for run_id {run_id}: {e}")
            return None
