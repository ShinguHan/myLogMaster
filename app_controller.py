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
    # ✅ Signal을 클래스 변수로 정의
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
        if not self.db_manager: 
            return
        
        print("Loading initial data from local cache...")
        cached_data = self.db_manager.read_all_logs_from_cache()
        if not cached_data.empty:
            self.original_data = cached_data
            if 'SystemDate' in self.original_data.columns and 'SystemDate_dt' not in self.original_data.columns:
                 self.original_data['SystemDate_dt'] = pd.to_datetime(self.original_data['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce')
            self.update_model_data(self.original_data)
            print(f"Loaded {len(cached_data)} rows from cache.")
        else:
            print("Local cache is empty.")

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
        self.model_updated.emit(self.source_model)  # emit() 사용

    def start_db_fetch(self, query_conditions):
        if self.fetch_thread and self.fetch_thread.isRunning():
            print("Fetch is already in progress.")
            return

        self.fetch_thread = OracleFetcherThread(self.connection_info, query_conditions)
        
        self.fetch_thread.data_fetched.connect(self.on_data_chunk_received)
        self.fetch_thread.finished.connect(self.on_fetch_finished)
        self.fetch_thread.progress.connect(self.fetch_progress)
        self.fetch_thread.error.connect(lambda e: self.fetch_progress.emit(f"Error: {e}"))

        self.fetch_thread.start()

    def on_data_chunk_received(self, df_chunk):
        print(f"Received a chunk of {len(df_chunk)} logs.")
        if self.db_manager:
            self.db_manager.upsert_logs_to_local_cache(df_chunk)
        self.load_data_from_cache()

    def on_fetch_finished(self):
        print("Fetch thread finished.")
        self.fetch_completed.emit()

    # 누락된 메서드 추가
    def run_analysis_script(self, script_code, dataframe):
        """
        스크립트 실행을 위한 메서드 (구현 필요)
        """
        try:
            # 여기에 스크립트 실행 로직을 구현하세요
            # 임시로 기본 AnalysisResult 반환
            return AnalysisResult()
        except Exception as e:
            print(f"Script execution error: {e}")
            return AnalysisResult()

    # 나머지 메서드들은 그대로 유지...
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

    # 나머지 메서드들도 동일하게 유지...
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