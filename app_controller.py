# shinguhan/mylogmaster/myLogMaster-main/app_controller.py

import pandas as pd
import json
import os
from PySide6.QtCore import QObject, Signal, QDateTime

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel
from analysis_result import AnalysisResult
from database_manager import DatabaseManager
from oracle_fetcher import OracleFetcherThread

FILTERS_FILE = 'filters.json'
SCENARIOS_DIR = 'scenarios'

class AppController(QObject):
    model_updated = Signal(LogTableModel)
    fetch_completed = Signal()
    fetch_progress = Signal(str)

    def __init__(self, app_mode, connection_name=None, connection_info=None):
        super().__init__()
        self.mode = app_mode
        self.connection_name = connection_name
        self.connection_info = connection_info
        self.original_data = pd.DataFrame()
        self.source_model = LogTableModel()
        self.fetch_thread = None

        if self.mode == 'realtime':
            if self.connection_name:
                self.db_manager = DatabaseManager(self.connection_name)
                self.load_data_from_cache()
            else:
                print("Error: Realtime mode requires a connection name.")
                self.db_manager = None
        else:
            self.db_manager = None

    def load_data_from_cache(self):
        """로컬 캐시에서 데이터를 로드하고, 데이터 유무와 상관없이 항상 UI에 모델을 업데이트하도록 신호를 보냅니다."""
        if not self.db_manager: 
            self.update_model_data(pd.DataFrame()) # DB 매니저가 없을 때도 초기 모델 전송
            return
        
        print("Loading initial data from local cache...")
        cached_data = self.db_manager.read_all_logs_from_cache()
        
        if not cached_data.empty:
            self.original_data = cached_data
            if 'SystemDate' in self.original_data.columns and 'SystemDate_dt' not in self.original_data.columns:
                 self.original_data['SystemDate_dt'] = pd.to_datetime(self.original_data['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce')
            print(f"Loaded {len(cached_data)} rows from cache.")
        else:
            self.original_data = pd.DataFrame() # 캐시가 비었으면 빈 데이터프레임으로 초기화
            print("Local cache is empty.")
        
        # ✅ 데이터가 있든 없든, 무조건 UI에 모델을 설정하라는 신호를 보냅니다.
        self.update_model_data(self.original_data)

    
    def load_log_file(self, filepath):
        try:
            parsed_data = parse_log_with_profile(filepath, self._get_profile())
            self.original_data = pd.DataFrame(parsed_data)
            
            if 'SystemDate' in self.original_data.columns:
                self.original_data['SystemDate_dt'] = pd.to_datetime(
                    self.original_data['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce'
                )
            
            self.update_model_data(self.original_data)
            return not self.original_data.empty
        except Exception as e:
            print(f"Error loading or parsing file: {e}")
            self.original_data = pd.DataFrame()
            self.update_model_data(self.original_data)
            return False

    def _get_profile(self):
        return {
            'column_mapping': {'Category': 'Category', 'AsciiData': 'AsciiData', 'BinaryData': 'BinaryData'},
            'type_rules': [{'value': 'Com', 'type': 'secs'}, {'value': 'Info', 'type': 'json'}]
        }
    def update_model_data(self, dataframe):
        self.source_model.update_data(dataframe)
        self.model_updated.emit(self.source_model)

    def start_db_fetch(self, query_conditions):
        if self.fetch_thread and self.fetch_thread.isRunning():
            print("Fetch is already in progress.")
            return

        # 💡 1. 데이터 가져오기를 시작하기 전, 기존 모델의 데이터를 초기화합니다.
        self.source_model.update_data(pd.DataFrame())
        self.original_data = pd.DataFrame() # 원본 데이터도 초기화

        self.fetch_thread = OracleFetcherThread(self.connection_info, query_conditions)
        
        # 💡 2. data_fetched 신호를 append_data_chunk 슬롯에 연결합니다.
        self.fetch_thread.data_fetched.connect(self.append_data_chunk)
        self.fetch_thread.finished.connect(self.on_fetch_finished)
        self.fetch_thread.progress.connect(self.fetch_progress)
        self.fetch_thread.error.connect(lambda e: self.fetch_progress.emit(f"Error: {e}"))

        self.fetch_thread.start()

    # 💡 3. 데이터를 점진적으로 추가하는 새로운 메소드
    def append_data_chunk(self, df_chunk):
        """받은 데이터 조각을 기존 모델에 추가하고 UI를 업데이트합니다."""
        print(f"Received and appending a chunk of {len(df_chunk)} logs.")
        
        if df_chunk.empty: return

        if 'SystemDate' in df_chunk.columns and 'SystemDate_dt' not in df_chunk.columns:
            df_chunk['SystemDate_dt'] = pd.to_datetime(df_chunk['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce')

        # 원본 데이터에도 추가
        self.original_data = pd.concat([self.original_data, df_chunk], ignore_index=True)
        
        # 모델에 데이터 추가 (UI 업데이트 신호는 모델 내부에서 발생)
        self.source_model.append_data(df_chunk)
        
        # 로컬 캐시에 저장
        if self.db_manager:
            self.db_manager.upsert_logs_to_local_cache(df_chunk)

    def on_fetch_finished(self):
        print("Fetch thread finished.")
        self.fetch_completed.emit()
        # 전체 데이터가 로드된 후 필터링이나 다른 작업을 수행할 수 있습니다.
        # 예: self.apply_advanced_filter(self.last_query_data)
        
    # ... (load_log_file, run_analysis_script 등 나머지 코드는 동일)     
    def run_analysis_script(self, script_code, dataframe):
        try:
            # 여기에 스크립트 실행 로직을 구현하세요
            # 임시로 기본 AnalysisResult 반환
            return AnalysisResult()
        except Exception as e:
            print(f"Script execution error: {e}")
            return AnalysisResult()

    def clear_advanced_filter(self):
        self.update_model_data(self.original_data)

    def apply_advanced_filter(self, query_data):
        if not query_data or not query_data.get('rules'):
            self.clear_advanced_filter()
            return
            
        if self.original_data.empty:
            return

        try:
            final_mask = self._build_mask_recursive(query_data, self.original_data)
            self.update_model_data(self.original_data[final_mask])
        except Exception as e:
            print(f"Error applying filter: {e}")
            self.update_model_data(self.original_data)

    def _build_mask_recursive(self, query_group, df):
        masks = []
        for rule in query_group.get('rules', []):
            if 'logic' in rule: 
                masks.append(self._build_mask_recursive(rule, df))
            else: 
                column, op, value = rule['column'], rule['operator'], rule['value']
                if not all([column, op]): continue

                mask = pd.Series(True, index=df.index)
                try:
                    if column == 'SystemDate':
                        dt_value = pd.to_datetime(value) if not isinstance(value, tuple) else None
                        dt_value_from = pd.to_datetime(value[0]) if isinstance(value, tuple) else None
                        dt_value_to = pd.to_datetime(value[1]) if isinstance(value, tuple) else None
                        
                        if op == 'is after': mask = df[f'{column}_dt'] > dt_value
                        elif op == 'is before': mask = df[f'{column}_dt'] < dt_value
                        elif op == 'is between': mask = (df[f'{column}_dt'] >= dt_value_from) & (df[f'{column}_dt'] <= dt_value_to)
                    else:
                        series = df[column].astype(str)
                        if op == 'Contains': mask = series.str.contains(value, case=False, na=False)
                        elif op == 'Does Not Contain': mask = ~series.str.contains(value, case=False, na=False)
                        elif op == 'Equals': mask = series == value
                        elif op == 'Not Equals': mask = series != value
                        elif op == 'Matches Regex': mask = series.str.match(value, na=False)
                    masks.append(mask)
                except KeyError:
                    print(f"Warning: Column '{column}' not found for filtering. Skipping rule.")
                    continue

        if not masks:
            return pd.Series(True, index=df.index)

        if query_group['logic'] == 'AND':
            return pd.concat(masks, axis=1).all(axis=1)
        else:
            return pd.concat(masks, axis=1).any(axis=1)

    def load_filters(self):
        try:
            if not os.path.exists(FILTERS_FILE): return {}
            with open(FILTERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse '{FILTERS_FILE}'. It may be corrupted.")
            return {}
        except Exception as e:
            print(f"Error loading filters: {e}")
            return {}

    def save_filter(self, name, query_data):
        try:
            filters = self.load_filters()
            if query_data:
                filters[name] = query_data
                with open(FILTERS_FILE, 'w', encoding='utf-8') as f: 
                    json.dump(filters, f, indent=4)
        except Exception as e:
            print(f"Error saving filter '{name}': {e}")
    
    def get_trace_data(self, trace_id):
        df = self.original_data
        mask = df.apply(lambda r: r.astype(str).str.contains(trace_id, case=False, na=False).any(), axis=1)
        return df[mask]

    def get_scenario_data(self, trace_id):
        scenario_df = self.get_trace_data(trace_id)
        com_logs = scenario_df[scenario_df['Category'].str.replace('"', '', regex=False) == 'Com'].sort_values(by='SystemDate')
        return com_logs

    def run_scenario_validation(self, scenario_to_run=None):
        if self.original_data.empty:
            return "오류: 로그 데이터가 없습니다."

        scenarios = self.load_all_scenarios()
        if "Error" in scenarios:
            return f"오류: {scenarios['Error']['description']}"

        results = ["=== 시나리오 검증 결과 ==="]
        df = self.original_data.sort_values(by='SystemDate_dt').reset_index()

        for name, scenario in scenarios.items():
            if scenario_to_run and name != scenario_to_run:
                continue
            
            active_scenarios = {}
            completed_scenarios = []
            key_columns = scenario.get('key_columns', [])

            for index, row in df.iterrows():
                current_time = row['SystemDate_dt']
                
                timed_out_keys = []
                for key, state in active_scenarios.items():
                    time_limit = scenario['steps'][state['current_step']]['max_delay_seconds']
                    if current_time > state['last_event_time'] + pd.Timedelta(seconds=time_limit):
                        state['status'] = 'FAIL'
                        state['message'] = f"Timeout at Step {state['current_step']+1}: {scenario['steps'][state['current_step']]['name']}"
                        completed_scenarios.append(state)
                        timed_out_keys.append(key)
                for key in timed_out_keys:
                    del active_scenarios[key]

                progressed_keys = []
                for key, state in active_scenarios.items():
                    next_step_rule = scenario['steps'][state['current_step']]['event_match']
                    if self._match_event(row, next_step_rule):
                        state['events'].append(row.to_dict())
                        state['current_step'] += 1
                        state['last_event_time'] = current_time
                        
                        if state['current_step'] >= len(scenario['steps']):
                            state['status'] = 'SUCCESS'
                            state['message'] = 'Scenario completed successfully.'
                            completed_scenarios.append(state)
                            progressed_keys.append(key)
                for key in progressed_keys:
                    del active_scenarios[key]

                trigger_rule = scenario['trigger_event']
                if self._match_event(row, trigger_rule):
                    key = tuple(row[k] for k in key_columns) if key_columns else index
                    if key not in active_scenarios:
                        active_scenarios[key] = {
                            'scenario_name': name,
                            'start_index': index,
                            'start_time': current_time,
                            'last_event_time': current_time,
                            'current_step': 0,
                            'status': 'IN_PROGRESS',
                            'message': '',
                            'events': [row.to_dict()]
                        }

            for key, state in active_scenarios.items():
                state['status'] = 'INCOMPLETE'
                state['message'] = f"Scenario did not complete. Stopped at step {state['current_step']+1}."
                completed_scenarios.append(state)

            success_count = sum(1 for s in completed_scenarios if s['status'] == 'SUCCESS')
            fail_count = sum(1 for s in completed_scenarios if s['status'] == 'FAIL')
            incomplete_count = sum(1 for s in completed_scenarios if s['status'] == 'INCOMPLETE')

            results.append(f"\n[{name}]: 총 {len(completed_scenarios)}건 시도 -> 성공: {success_count}, 실패: {fail_count}, 미완료: {incomplete_count}")
            if fail_count > 0:
                results.append("  [실패 상세 정보 (최대 3건)]")
                fail_cases = [s for s in completed_scenarios if s['status'] == 'FAIL']
                for fail in fail_cases[:3]:
                    results.append(f"    - Trigger at row {fail['start_index']} ({fail['start_time']}), Reason: {fail['message']}")
        
        return "\n".join(results)

    def _match_event(self, row, rule):
        col = rule.get('column')
        if not col or col not in row or pd.isna(row[col]):
            return False
        
        row_val = str(row[col]).replace('"', '')
        
        if 'contains' in rule:
            return rule['contains'] in row_val
        if 'equals' in rule:
            return rule['equals'] == row_val
        return False

    def load_all_scenarios(self):
        all_scenarios = {}
        if not os.path.exists(SCENARIOS_DIR):
            return {"Error": {"description": f"'{SCENARIOS_DIR}' directory not found."}}
        
        for filename in sorted(os.listdir(SCENARIOS_DIR)):
            if filename.endswith(".json"):
                filepath = os.path.join(SCENARIOS_DIR, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    try:
                        scenarios = json.load(f)
                        all_scenarios.update(scenarios)
                    except json.JSONDecodeError:
                        print(f"Warning: Could not parse {filename}")
        return all_scenarios
    
    def get_scenario_names(self):
        return list(self.load_all_scenarios().keys())