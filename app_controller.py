# shinguhan/mylogmaster/myLogMaster-main/app_controller.py

import pandas as pd
import json
import os, re
from PySide6.QtCore import QObject, Signal, QDateTime, QTimer

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel
from analysis_result import AnalysisResult
from database_manager import DatabaseManager
from oracle_fetcher import OracleFetcherThread

CONFIG_FILE = 'config.json' # 💥 설정 파일 경로를 상수로 정의
FILTERS_FILE = 'filters.json'
SCENARIOS_DIR = 'scenarios'
HIGHLIGHTERS_FILE = 'highlighters.json' # ✅ 파일 경로 추가

class AppController(QObject):
    model_updated = Signal(LogTableModel)
    fetch_completed = Signal()
    fetch_progress = Signal(str)
        # ✅ 현재 행 개수를 전달할 새로운 신호
    row_count_updated = Signal(int)
        # ✅ 1. UI에 에러를 전달할 새로운 신호
    fetch_error = Signal(str)

    def __init__(self, app_mode, connection_name=None, connection_info=None):
        super().__init__()
        self.mode = app_mode
        self.connection_name = connection_name
        self.connection_info = connection_info
        self.original_data = pd.DataFrame()
        # ✅ 1. 모델 생성 시 최대 행 수를 전달합니다. (테스트를 위해 20000으로 설정)
        self.source_model = LogTableModel(max_rows=20000) 
        self.fetch_thread = None
        self.last_query_conditions = None # ✅ 조회 조건 저장할 변수 추가
                # ✅ 1. 대시보드 다이얼로그 참조를 저장할 변수 추가
        self.dashboard_dialog = None 
        self.current_theme = 'light' # ✅ 1. 현재 테마 저장 변수

                # ✅ 1. 데이터 업데이트를 위한 큐와 타이머 추가
        self._update_queue = []
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(200) # 200ms (0.2초) 마다 실행
        self._update_timer.timeout.connect(self._process_update_queue)

        self.config = self._load_config() # 💥 __init__에서 전체 설정을 로드
        self.highlighting_rules = self.load_highlighting_rules() # ✅ 시작 시 규칙 로드

        if self.mode == 'realtime':
            if self.connection_name:
                self.db_manager = DatabaseManager(self.connection_name)
                self.load_data_from_cache()
            else:
                print("Error: Realtime mode requires a connection name.")
                self.db_manager = None
        else:
            # 파일 모드에서는 'file_mode'라는 고정된 이름으로 DB 생성
            self.db_manager = DatabaseManager("file_mode")

    # 💥 변경점 1: 테마 관련 메소드 전체를 아래 코드로 교체합니다.
    def _load_config(self):
        """
        애플리케이션 시작 시 config.json에서 설정을 한 번만 로드합니다.
        파일이 없거나 손상된 경우 기본 설정을 반환합니다.
        """
        default_config = {'theme': 'light', 'visible_columns': []}
        if not os.path.exists(CONFIG_FILE):
            return default_config
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            print(f"Warning: Could not read {CONFIG_FILE}. Using default config.")
            return default_config
        
    def save_config(self):
        """현재 설정(self.config)을 config.json 파일에 저장합니다."""
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            print("Configuration saved successfully.")
        except Exception as e:
            print(f"Error saving configuration: {e}")
            
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
        # ✅ 모델 업데이트 시 하이라이트 규칙도 함께 적용
        self.source_model.set_highlighting_rules(self.highlighting_rules)
        self.model_updated.emit(self.source_model)

    # shinguhan/mylogmaster/myLogMaster-32ac0fde18fc7e07d5e70cee360ee943bd9507be/app_controller.py

    # shinguhan/mylogmaster/myLogMaster-32ac0fde18fc7e07d5e70cee360ee943bd9507be/app_controller.py

    def start_db_fetch(self, query_conditions):
        if self.fetch_thread and self.fetch_thread.isRunning():
            print("Fetch is already in progress.")
            return

        self.last_query_conditions = query_conditions
        
        # [수정] WHERE 절을 미리 만들지 않고, 조건 객체를 그대로 전달합니다.
        # where_clause, params = self._build_where_clause(query_conditions)

        if self.db_manager:
            self.db_manager.clear_logs_from_cache()

        self.source_model.update_data(pd.DataFrame())
        self.original_data = pd.DataFrame()

        # [수정] OracleFetcherThread에 조건 객체를 통째로 전달하고, self를 parent로 지정합니다.
        self.fetch_thread = OracleFetcherThread(self.connection_info, query_conditions, parent=self)
        
        self.fetch_thread.data_fetched.connect(self.append_data_chunk)
        self.fetch_thread.finished.connect(self.on_fetch_finished)
        self.fetch_thread.progress.connect(self.fetch_progress)
        self.fetch_thread.error.connect(self._handle_fetch_error)

        if self.dashboard_dialog and self.dashboard_dialog.isVisible():
            self.dashboard_dialog.start_updates()

        self._update_timer.start()
        self.fetch_thread.start()


    # ✅ 2. append_data_chunk 메소드에 original_data 잘라내는 로직 추가
    def append_data_chunk(self, df_chunk):
        """받은 데이터 조각을 바로 처리하지 않고 큐에 추가합니다."""
        if not df_chunk.empty:
            self._update_queue.append(df_chunk)

    def on_fetch_finished(self):
        """데이터 수신이 완료/중단/에러 발생 후 공통으로 호출됩니다."""
        # 마지막 남은 데이터를 처리
        if self._update_queue:
            self._process_update_queue()
        
        print("Fetch thread finished.")
        if self._update_timer.isActive():
            self._update_timer.stop()

        # ✅ 3. 작업 완료 시에도 대시보드 업데이트 중지 명령
        if self.dashboard_dialog and self.dashboard_dialog.isVisible():
            self.dashboard_dialog.stop_updates()
            
        self.fetch_completed.emit()

        # ✅ 데이터 조회가 성공적으로 끝났을 때만 이력을 저장합니다.
        if self.db_manager and self.last_query_conditions:
            start_time = self.last_query_conditions.get('start_time', '')
            end_time = self.last_query_conditions.get('end_time', '')
            # start_time, end_time을 제외한 나머지 조건을 filters로 간주
            filters = {k: v for k, v in self.last_query_conditions.items() if k not in ['start_time', 'end_time']}
            self.db_manager.add_fetch_history(start_time, end_time, filters)
        
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

    # shinguhan/mylogmaster/myLogMaster-main/app_controller.py

    # shinguhan/mylogmaster/myLogMaster-main/app_controller.py

    # shinguhan/mylogmaster/myLogMaster-main/app_controller.py

    def run_scenario_validation(self, scenario_to_run=None):
        if self.original_data.empty:
            return [] # 텍스트 대신 빈 리스트 반환
        scenarios = self.load_all_scenarios()
        if "Error" in scenarios:
            return [{"scenario_name": "Error", "status": "FAIL", "message": scenarios['Error']['description']}]

        all_completed_scenarios = []
        df = self.original_data.sort_values(by='SystemDate_dt').reset_index()

        for name, scenario in scenarios.items():
            if (scenario_to_run and name != scenario_to_run) or \
               (scenario_to_run is None and not scenario.get("enabled", True)):
                continue

            active_scenarios = {}
            completed_scenarios = []
            context_keys = list(scenario.get("context_extractors", {}).keys())

            for index, row in df.iterrows():
                current_time = row['SystemDate_dt']
                current_row_context = self._extract_context(row, scenario.get("context_extractors", {}))

                # --- 1. 타임아웃 및 이벤트 매칭 검사 ---
                finished_keys = []
                for key, state in active_scenarios.items():
                    if context_keys and any(k in current_row_context for k in context_keys):
                        context_match = all(state['context'].get(k) == current_row_context.get(k) for k in context_keys if k in current_row_context)
                        if not context_match: continue
                    
                    if state['current_step'] >= len(state['steps']): continue
                    step_definition = state['steps'][state['current_step']]
                    
                    # --- [복원] 타임아웃 검사 ---
                    if 'max_delay_seconds' in step_definition:
                        time_limit = pd.Timedelta(seconds=step_definition['max_delay_seconds'])
                        if current_time > state['last_event_time'] + time_limit:
                            if step_definition.get('optional', False):
                                state['current_step'] += 1
                                if state['current_step'] >= len(state['steps']):
                                    state['status'] = 'SUCCESS'; state['message'] = 'Completed (last optional step timed out).'; completed_scenarios.append(state); finished_keys.append(key)
                                continue
                            else:
                                state['status'] = 'FAIL'; state['message'] = f"Timeout at Step {state['current_step'] + 1}: {step_definition.get('name', 'N/A')}"; completed_scenarios.append(state); finished_keys.append(key)
                                continue
                    
                    # --- [복원] 이벤트 매칭 (Optional, Unordered 등) ---
                    step_matched = False
                    if step_definition.get('optional', False) and (state['current_step'] + 1) < len(state['steps']):
                        next_step_definition = state['steps'][state['current_step'] + 1]
                        if self._match_event(row, next_step_definition.get('event_match', {})):
                            state['current_step'] += 1; step_definition = next_step_definition
                    
                    if 'unordered_group' in step_definition:
                        found_event_name = None
                        for event_in_group in state.get('unordered_events', []):
                            if self._match_event(row, event_in_group['event_match']):
                                found_event_name = event_in_group['name']; break
                        if found_event_name:
                            state['unordered_events'] = [e for e in state['unordered_events'] if e['name'] != found_event_name]
                            if not state['unordered_events']: state['current_step'] += 1
                            step_matched = True
                    elif self._match_event(row, step_definition.get('event_match', {})):
                        state['current_step'] += 1
                        step_matched = True

                    # ✅ [수정] 단계 성공 시, 상세 딕셔너리를 저장하도록 변경
                    if step_matched:
                        state['last_event_time'] = current_time
                        step_name = step_definition.get('name', f"Step {state['current_step']}")
                        state['involved_logs'].append({
                            "step_name": step_name,
                            "log_index": int(row['index']),
                            "timestamp": row['SystemDate_dt']
                        })

                    if state['current_step'] >= len(state['steps']):
                        state['status'] = 'SUCCESS'; state['message'] = 'Scenario completed successfully.'; completed_scenarios.append(state); finished_keys.append(key)

                for key in finished_keys: del active_scenarios[key]

                # --- 2. 새로운 시나리오 시작(Trigger) 검사 ---
                if self._match_event(row, scenario.get('trigger_event', {})):
                    trigger_context = self._extract_context(row, scenario.get("context_extractors", {}))
                    key = None
                    if context_keys:
                        if trigger_context and all(k in trigger_context for k in context_keys):
                            key = tuple(trigger_context[k] for k in context_keys)
                    else: key = row['index']

                    if key is not None and key not in active_scenarios:
                        new_state = {
                            'context': trigger_context,
                            'steps': list(scenario['steps']),
                            'start_time': current_time,
                            'last_event_time': current_time,
                            'current_step': 0,
                            'status': 'IN_PROGRESS',
                            'scenario_name': name,
                            # ✅ [수정] involved_logs에 상세 딕셔너리를 저장하도록 변경
                            'involved_logs': [{"step_name": "Trigger", "log_index": int(row['index']), "timestamp": row['SystemDate_dt']}]
                        }
                        if 'unordered_group' in new_state['steps'][0]:
                            new_state['unordered_events'] = list(new_state['steps'][0]['unordered_group'])
                        active_scenarios[key] = new_state
            
            # --- 3. 최종 결과 처리 ---
            for key, state in active_scenarios.items():
                state['status'] = 'INCOMPLETE'; state['message'] = f"Scenario stopped at step {state['current_step'] + 1}."; completed_scenarios.append(state)
            
            all_completed_scenarios.extend(completed_scenarios)

        if self.db_manager:
            for report in all_completed_scenarios:
                self.db_manager.add_validation_history(
                    scenario_name=report['scenario_name'],
                    status=report['status'],
                    message=report.get('message', ''),
                    involved_log_indices=report.get('involved_logs', [])
                )
        
        return all_completed_scenarios

    # shinguhan/mylogmaster/myLogMaster-main/app_controller.py

    def _match_event(self, row, rule_group):
        """
        단순 조건과 복합 조건(AND/OR) 모두를 재귀적으로 처리하는
        새롭고 안정적인 이벤트 매칭 함수입니다.
        """
        if not rule_group:
            return False

        # 'logic' 키가 있으면 복합 조건 그룹으로 처리
        if "logic" in rule_group:
            logic = rule_group.get("logic", "AND").upper()
            
            # 모든 하위 규칙(rules)에 대해 재귀적으로 _match_event 호출
            for sub_rule in rule_group.get("rules", []):
                result = self._match_event(row, sub_rule)
                
                if logic == "AND" and not result:
                    return False # AND 그룹에서는 하나라도 False이면 즉시 False
                if logic == "OR" and result:
                    return True # OR 그룹에서는 하나라도 True이면 즉시 True
            
            # 루프가 끝났을 때의 최종 결과
            return True if logic == "AND" else False
        
        # 'logic' 키가 없으면 단일 조건으로 처리
        else:
            col = rule_group.get("column")
            op = rule_group.get("operator")
            val = rule_group.get("value")
            
            # 규칙의 필수 요소가 없거나, 로그에 해당 컬럼이 없으면 False
            if not all([col, op, val is not None]) or col not in row.index or pd.isna(row[col]):
                return False
                
            cell_value = str(row[col]).lower()
            check_value = str(val).lower()
            
            if op == "contains":
                return check_value in cell_value
            elif op == "equals":
                return check_value == cell_value
            elif op == "starts with":
                return cell_value.startswith(check_value)
            elif op == "ends with":
                return cell_value.endswith(check_value)
            else:
                return False

    def load_all_scenarios(self):
        all_scenarios = {}
        if not os.path.exists(SCENARIOS_DIR):
            return {"Error": {"description": f"'{SCENARIOS_DIR}' directory not found."}}
        
        for filename in sorted(os.listdir(SCENARIOS_DIR)):
            if filename.endswith(".json"):
                filepath = os.path.join(SCENARIOS_DIR, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        scenarios_in_file = json.load(f)
                        # ✅ 각 시나리오에 원본 파일 이름을 '_source_file' 키로 추가합니다.
                        for name, details in scenarios_in_file.items():
                            details['_source_file'] = filename
                            all_scenarios[name] = details
                except (json.JSONDecodeError, Exception) as e:
                    print(f"Warning: Could not parse {filename}: {e}")
        return all_scenarios
    
    def get_scenario_names(self):
        scenarios = self.load_all_scenarios()
        # ✅ "enabled"가 false가 아닌 시나리오의 이름만 리스트로 반환
        return [name for name, details in scenarios.items() if details.get("enabled", True)]
    
    # ✅ 3. 타이머가 호출할 새로운 메소드
    def _process_update_queue(self):
        """큐에 쌓인 데이터 조각들을 한 번에 처리합니다."""
        if not self._update_queue:
            return

        # 큐에 있는 모든 데이터 조각을 하나로 합침
        combined_chunk = pd.concat(self._update_queue, ignore_index=True)
        self._update_queue.clear()

        print(f"Processing a combined chunk of {len(combined_chunk)} logs.")

        if 'SystemDate' in combined_chunk.columns and 'SystemDate_dt' not in combined_chunk.columns:
            combined_chunk['SystemDate_dt'] = pd.to_datetime(combined_chunk['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce')

        self.original_data = pd.concat([self.original_data, combined_chunk], ignore_index=True)
        self.source_model.append_data(combined_chunk)
        
        current_model_rows = self.source_model.rowCount()
        if len(self.original_data) > current_model_rows:
            self.original_data = self.original_data.tail(current_model_rows).reset_index(drop=True)

        if self.db_manager:
            self.db_manager.upsert_logs_to_local_cache(combined_chunk)
        
        # UI에 현재 총 행 수를 알림
        self.row_count_updated.emit(self.source_model.rowCount())

                # ✅ 2. 대시보드가 열려있으면, 업데이트 신호를 보냄
        if self.dashboard_dialog and self.dashboard_dialog.isVisible():
            # 전체 original_data를 넘겨주어 대시보드가 항상 최신 상태를 반영하게 함
            self.dashboard_dialog.update_dashboard(self.original_data)

        # ✅ 3. UI의 취소 요청을 처리할 새로운 메소드
    def cancel_db_fetch(self):
        """실행 중인 데이터 fetch 스레드를 중지시킵니다."""
        if self.fetch_thread and self.fetch_thread.isRunning():
            self.fetch_thread.stop()
            # finished 신호가 올 때까지 기다리지 않고, UI는 즉시 반응하도록 합니다.
            # 스레드는 내부적으로 멈추고 on_fetch_finished를 호출하여 정리할 것입니다.
    
    # ✅ 4. 스레드의 에러를 받아 UI에 전달하는 새로운 슬롯
    def _handle_fetch_error(self, error_message):
        """Fetcher 스레드에서 발생한 에러를 처리합니다."""
        print(f"Controller caught error: {error_message}")
        self.fetch_error.emit(error_message)

               # ✅ 2. 에러 발생 시에도 대시보드 업데이트 중지 명령
        if self.dashboard_dialog and self.dashboard_dialog.isVisible():
            self.dashboard_dialog.stop_updates()

        # 에러 발생 시에도 타이머는 중지해야 합니다.
        if self._update_timer.isActive():
            self._update_timer.stop()

        # ✅ 2. 테마 설정을 위한 새로운 메소드들
    def set_current_theme(self, theme_name):
        """메모리에 현재 테마를 업데이트하고, 즉시 파일에 저장합니다."""
        self.config['theme'] = theme_name
        self.save_config() # 💥 테마 변경 시 즉시 저장

    def get_current_theme(self):
        """메모리에 저장된 현재 테마를 반환합니다."""
        return self.config.get('theme', 'light')
    
        # ✅ 하이라이트 규칙을 위한 새로운 메소드들
    def load_highlighting_rules(self):
        if not os.path.exists(HIGHLIGHTERS_FILE):
            return []
        try:
            with open(HIGHLIGHTERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return []

    def apply_new_highlighting_rules(self):
        self.highlighting_rules = self.load_highlighting_rules()
        self.source_model.set_highlighting_rules(self.highlighting_rules)

        # ✅ 아래 메소드를 클래스 맨 끝에 추가해주세요.
    def save_log_to_csv(self, dataframe, file_path):
        """데이터프레임을 지정된 경로의 CSV 파일로 저장합니다."""
        try:
            # utf-8-sig 인코딩은 Excel에서 한글이 깨지지 않도록 보장합니다.
            dataframe.to_csv(file_path, index=False, encoding='utf-8-sig')
            return True, f"Successfully saved to {os.path.basename(file_path)}"
        except Exception as e:
            print(f"Error saving to CSV: {e}")
            return False, f"Could not save file: {e}"
        
    # ✅ 3. 아래의 두 메소드를 클래스 맨 끝에 새로 추가해주세요.
    def _build_where_clause(self, query_conditions):
        """QueryConditionsDialog에서 받은 조건으로 WHERE 절과 파라미터를 생성합니다."""
        clauses = []
        params = {}
        
        # 시간 조건 추가 (Oracle DATE 형식에 맞게 변환)
        params['p_start_time'] = pd.to_datetime(query_conditions['start_time']).strftime('%Y-%m-%d %H:%M:%S')
        params['p_end_time'] = pd.to_datetime(query_conditions['end_time']).strftime('%Y-%m-%d %H:%M:%S')
        clauses.append("SystemDate BETWEEN TO_DATE(:p_start_time, 'YYYY-MM-DD HH24:MI:SS') AND TO_DATE(:p_end_time, 'YYYY-MM-DD HH24:MI:SS')")
        
        # 고급 필터 조건 추가
        adv_filter = query_conditions.get('advanced_filter')
        if adv_filter and adv_filter.get('rules'):
            adv_clause, adv_params = self._parse_filter_group(adv_filter)
            if adv_clause:
                clauses.append(adv_clause)
                params.update(adv_params)
        
        return " AND ".join(clauses), params

    def _parse_filter_group(self, group, param_index=0):
        """재귀적으로 필터 그룹을 파싱하여 SQL 조건문과 파라미터를 만듭니다."""
        clauses = []
        params = {}
        logic = f" {group.get('logic', 'AND')} "
        
        for rule in group.get('rules', []):
            if "logic" in rule: # 하위 그룹인 경우
                sub_clause, sub_params = self._parse_filter_group(rule, param_index)
                if sub_clause:
                    clauses.append(f"({sub_clause})")
                    params.update(sub_params)
                    param_index += len(sub_params)
            else: # 실제 규칙인 경우
                col = rule.get('column')
                op = rule.get('operator')
                val = rule.get('value')
                
                if not all([col, op, val]): continue
                
                param_name = f"p{param_index}"
                
                # 연산자에 맞는 SQL 구문 생성
                if op == 'Contains':
                    clauses.append(f"INSTR({col}, :{param_name}) > 0")
                    params[param_name] = val
                elif op == 'Does Not Contain':
                    clauses.append(f"INSTR({col}, :{param_name}) = 0")
                    params[param_name] = val
                elif op == 'Equals':
                    clauses.append(f"{col} = :{param_name}")
                    params[param_name] = val
                elif op == 'Not Equals':
                    clauses.append(f"{col} != :{param_name}")
                    params[param_name] = val
                elif op == 'Matches Regex': # Oracle REGEXP_LIKE 사용
                    clauses.append(f"REGEXP_LIKE({col}, :{param_name})")
                    params[param_name] = val

                param_index += 1
                
        return logic.join(clauses), params
    
    def _extract_context(self, row, extractors):
        """정의된 여러 추출기 규칙에 따라 로그(row)에서 컨텍스트 값을 찾아냅니다."""
        context_data = {}
        for context_name, rules in extractors.items():
            found_value = None
            for rule in rules:
                if "from_column" in rule:
                    val = row.get(rule["from_column"])
                    if pd.notna(val) and str(val).strip():
                        found_value = str(val)
                        break
                elif "from_regex" in rule:
                    source_col = rule["from_regex"].get("column")
                    pattern = rule["from_regex"].get("pattern")
                    source_text = str(row.get(source_col, ''))
                    match = re.search(pattern, source_text)
                    if match:
                        found_value = match.group(1) # 첫 번째 괄호 그룹을 추출
                        break
            if found_value:
                context_data[context_name] = found_value
        return context_data
    
        # ✅ 아래 두 메소드를 클래스 맨 끝에 추가해주세요.
    def get_history_summary(self):
        if self.db_manager:
            return self.db_manager.get_validation_history_summary()
        return pd.DataFrame()

    def get_history_detail(self, run_id):
        if self.db_manager:
            return self.db_manager.get_validation_history_detail(run_id)
        return None
    
    def _load_initial_theme(self):
        """
        애플리케이션 시작 시 config.json에서 테마 설정을 한 번만 로드합니다.
        """
        config_path = 'config.json'
        theme_to_load = 'light'  # 기본값
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    theme_to_load = config.get('theme', 'light')
            except (json.JSONDecodeError, KeyError):
                print("Warning: Could not read theme from config.json. Defaulting to 'light'.")
                pass
        self.current_theme = theme_to_load

    # 💥 변경점 1: 하이라이트 규칙 관리 메소드를 컨트롤러에 추가
    def _load_highlighting_rules(self):
        """하이라이트 규칙을 파일에서 로드합니다."""
        if not os.path.exists(HIGHLIGHTERS_FILE):
            return []
        try:
            with open(HIGHLIGHTERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            print(f"Warning: Could not read {HIGHLIGHTERS_FILE}. Using empty rules.")
            return []

    def _save_highlighting_rules(self):
        """현재 하이라이트 규칙을 파일에 저장합니다."""
        try:
            with open(HIGHLIGHTERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.highlighting_rules, f, indent=4, ensure_ascii=False)
            print("Highlighting rules saved successfully.")
        except Exception as e:
            print(f"Error saving highlighting rules: {e}")

    def get_highlighting_rules(self):
        """다이얼로그에 전달할 규칙 데이터의 복사본을 반환합니다."""
        return [dict(rule) for rule in self.highlighting_rules]
    
    def set_and_save_highlighting_rules(self, new_rules):
        """새로운 규칙을 적용, 저장하고 모델을 업데이트합니다."""
        self.highlighting_rules = new_rules
        self._save_highlighting_rules()
        self.source_model.set_highlighting_rules(self.highlighting_rules)
        print("New highlighting rules applied.")