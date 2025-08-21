# shinguhan/mylogmaster/myLogMaster-main/app_controller.py

import pandas as pd
import json
import os
from PySide6.QtCore import QObject, Signal, QDateTime, QTimer

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel
from analysis_result import AnalysisResult
from database_manager import DatabaseManager
from oracle_fetcher import OracleFetcherThread

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

        self.highlighting_rules = self.load_highlighting_rules() # ✅ 시작 시 규칙 로드

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
        # ✅ 모델 업데이트 시 하이라이트 규칙도 함께 적용
        self.source_model.set_highlighting_rules(self.highlighting_rules)
        self.model_updated.emit(self.source_model)

    def start_db_fetch(self, query_conditions):
        if self.fetch_thread and self.fetch_thread.isRunning():
            print("Fetch is already in progress.")
            return

        # ✅ 현재 조회 조건을 인스턴스 변수에 저장
        self.last_query_conditions = query_conditions

                # ✅ 1. 고급 필터 조건을 SQL WHERE 절로 변환
        where_clause, params = self._build_where_clause(query_conditions)
        print(f"Generated WHERE clause: {where_clause}")
        print(f"Parameters: {params}")

        if self.db_manager:
            self.db_manager.clear_logs_from_cache()

        self.source_model.update_data(pd.DataFrame())
        self.original_data = pd.DataFrame() 

        # ✅ 2. 생성된 WHERE 절과 파라미터를 Fetcher 스레드에 전달
        self.fetch_thread = OracleFetcherThread(self.connection_info, where_clause, params)
        
        self.fetch_thread.data_fetched.connect(self.append_data_chunk)
        self.fetch_thread.finished.connect(self.on_fetch_finished)
                # ✅ 2. 스레드의 error 신호를 컨트롤러 내부 슬롯에 연결
        self.fetch_thread.error.connect(self._handle_fetch_error)

                # ✅ 1. 대시보드가 열려있으면, 업데이트 시작 명령
        if self.dashboard_dialog and self.dashboard_dialog.isVisible():
            self.dashboard_dialog.start_updates()

        # ✅ 2. 타이머 시작
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

    def run_scenario_validation(self, scenario_to_run=None):
        """
        모든 고급 문법(시간제한 없음, 순서 없는 그룹, 선택적 단계)을 지원하는
        최종 버전의 시나리오 분석 엔진입니다.
        """
        if self.original_data.empty:
            return "오류: 로그 데이터가 없습니다."

        scenarios = self.load_all_scenarios()
        if "Error" in scenarios:
            return f"오류: {scenarios['Error']['description']}"

        results = ["=== 시나리오 검증 결과 ==="]
        # 분석의 기준이 되는 로그 데이터를 시간순으로 정렬합니다.
        df = self.original_data.sort_values(by='SystemDate_dt').reset_index()

        # --- 각 시나리오별로 분석을 수행 ---
        for name, scenario in scenarios.items():
            # 특정 시나리오만 실행하는 경우 필터링
            if scenario_to_run and name != scenario_to_run:
                continue
            # 'Run All'일 때 비활성화된 시나리오는 건너뜀
            if scenario_to_run is None and not scenario.get("enabled", True):
                continue

            # --- 시나리오별 상태 변수 초기화 ---
            # active_scenarios: 현재 진행 중인 시나리오들의 상태를 저장하는 '관제탑'
            # key_columns(예: TrackingID)를 기준으로 각 시나리오의 진행 상태를 추적합니다.
            active_scenarios = {}
            completed_scenarios = [] # 성공 또는 실패로 완료된 시나리오들을 보관

            # --- 전체 로그를 한 줄씩 순회하며 분석 시작 ---
            for index, row in df.iterrows():
                current_time = row['SystemDate_dt']
                
                # --- 1. 타임아웃 검사: 현재 진행중인 시나리오들이 시간 초과는 아닌지 먼저 확인 ---
                timed_out_keys = []
                for key, state in active_scenarios.items():
                    current_step_index = state['current_step']
                    step_definition = scenario['steps'][current_step_index]
                    
                    # 1a. 시간 제한이 있는 단계만 검사
                    if 'max_delay_seconds' in step_definition:
                        time_limit = pd.Timedelta(seconds=step_definition['max_delay_seconds'])
                        if current_time > state['last_event_time'] + time_limit:
                            # 1b. 시간 초과! 하지만 이 단계가 '선택 사항(optional)'인지 확인
                            if step_definition.get('optional', False):
                                # 'optional' 단계가 타임아웃되면, 실패가 아니라 "건너뛴 것"으로 간주.
                                # 다음 단계로 넘어가서 계속 분석을 진행합니다.
                                state['current_step'] += 1
                                # last_event_time은 그대로 유지 (건너뛰었으므로 시간 기준은 이전 이벤트)
                                if state['current_step'] >= len(scenario['steps']):
                                    # 만약 마지막 단계가 optional이고 타임아웃됐다면 성공으로 처리
                                    state['status'] = 'SUCCESS'
                                    state['message'] = 'Scenario completed (last optional step timed out).'
                                    completed_scenarios.append(state)
                                    timed_out_keys.append(key)
                            else:
                                # 'optional'이 아닌 단계가 타임아웃되면 최종 실패.
                                state['status'] = 'FAIL'
                                state['message'] = f"Timeout at Step {current_step_index + 1}: {step_definition.get('name', 'N/A')}"
                                completed_scenarios.append(state)
                                timed_out_keys.append(key)
                # 실패/완료된 시나리오는 관제탑에서 제거
                for key in timed_out_keys:
                    del active_scenarios[key]

                # --- 2. 이벤트 매칭 검사: 현재 로그가 진행중인 시나리오의 다음 단계 조건과 맞는지 확인 ---
                progressed_keys = []
                for key, state in active_scenarios.items():
                    # 2a. 'optional' 단계 건너뛰기 로직:
                    # 현재 로그가 optional인 현 단계를 만족시키진 않지만, 그 다음 단계를 만족시키는 경우
                    current_step_index = state['current_step']
                    step_definition = scenario['steps'][current_step_index]
                    if step_definition.get('optional', False) and (current_step_index + 1) < len(scenario['steps']):
                        next_step_definition = scenario['steps'][current_step_index + 1]
                        if self._match_event(row, next_step_definition.get('event_match', {})):
                            # optional 단계를 건너뛰고 바로 다음 단계부터 진행
                            state['current_step'] += 1
                            step_definition = next_step_definition # 이제부터는 다음 단계를 기준으로 검사
                    
                    # 2b. 순서 없는 그룹('unordered_group') 처리
                    if 'unordered_group' in step_definition:
                        # 아직 찾지 못한 이벤트 목록(state['unordered_events'])을 순회
                        found_event_name = None
                        for event_in_group in state['unordered_events']:
                            if self._match_event(row, event_in_group['event_match']):
                                found_event_name = event_in_group['name']
                                break
                        
                        if found_event_name:
                            # 그룹 내 이벤트를 찾았다면, 찾아야 할 목록에서 제거
                            state['unordered_events'] = [e for e in state['unordered_events'] if e['name'] != found_event_name]
                            state['last_event_time'] = current_time # 그룹 내 이벤트가 발생했으므로 시간 갱신
                            
                            # 만약 목록의 모든 이벤트를 다 찾았다면, 이 그룹은 성공!
                            if not state['unordered_events']:
                                state['current_step'] += 1 # 다음 단계로 이동
                    
                    # 2c. 일반(순서 있는) 단계 처리
                    elif self._match_event(row, step_definition.get('event_match', {})):
                        state['current_step'] += 1
                        state['last_event_time'] = current_time

                    # 2d. 시나리오 최종 성공 여부 판단
                    if state['current_step'] >= len(scenario['steps']):
                        state['status'] = 'SUCCESS'
                        state['message'] = 'Scenario completed successfully.'
                        completed_scenarios.append(state)
                        progressed_keys.append(key)
                # 성공한 시나리오는 관제탑에서 제거
                for key in progressed_keys:
                    del active_scenarios[key]

                # --- 3. 새로운 시나리오 시작(Trigger) 검사 ---
                trigger_rule = scenario.get('trigger_event', {})
                if self._match_event(row, trigger_rule):
                    key_columns = scenario.get('key_columns', [])
                    # key_columns가 비어있으면 로그의 고유 인덱스를 key로 사용
                    key = tuple(row[k] for k in key_columns) if key_columns else row['index']
                    
                    # 이미 동일한 key로 진행중인 시나리오가 없다면, 새로 시작
                    if key not in active_scenarios:
                        new_state = {
                            'start_time': current_time,
                            'last_event_time': current_time,
                            'current_step': 0,
                            'status': 'IN_PROGRESS',
                        }
                        # 만약 첫 단계가 'unordered_group'이라면, 찾아야 할 이벤트 목록을 미리 생성
                        if 'unordered_group' in scenario['steps'][0]:
                            new_state['unordered_events'] = list(scenario['steps'][0]['unordered_group'])
                        
                        active_scenarios[key] = new_state

            # --- 로그 순회가 끝난 후, 아직 완료되지 않은 시나리오들을 처리 ---
            for key, state in active_scenarios.items():
                state['status'] = 'INCOMPLETE'
                state['message'] = f"Scenario did not complete. Stopped at step {state['current_step'] + 1}."
                completed_scenarios.append(state)

            # --- 최종 결과 리포트 생성 ---
            success_count = sum(1 for s in completed_scenarios if s['status'] == 'SUCCESS')
            fail_count = sum(1 for s in completed_scenarios if s['status'] == 'FAIL')
            incomplete_count = sum(1 for s in completed_scenarios if s['status'] == 'INCOMPLETE')

            results.append(f"\n[{name}]: 총 {len(completed_scenarios)}건 시도 -> 성공: {success_count}, 실패: {fail_count}, 미완료: {incomplete_count}")
            # ... (실패 상세 정보 출력)
        
        return "\n".join(results)

    def _match_event(self, row, rule_group):
        """복합적인 AND/OR 조건을 재귀적으로 검사하여 이벤트 일치 여부를 판단합니다."""
        # 이전 버전과의 호환성을 위해, logic 키가 없으면 단일 규칙으로 간주
        if "logic" not in rule_group:
            # 단일 규칙 처리 (이전 로직)
            col = rule_group.get('column')
            if not col or col not in row or pd.isna(row[col]): return False
            row_val = str(row[col]).replace('"', '')
            if 'contains' in rule_group: return rule_group['contains'] in row_val
            if 'equals' in rule_group: return rule_group['equals'] == row_val
            return False

        # --- 새로운 복합 규칙 처리 ---
        logic = rule_group.get("logic", "AND").upper()
        
        for sub_rule in rule_group.get("rules", []):
            # 하위 그룹(AND/OR)인 경우, 재귀 호출
            if "logic" in sub_rule:
                result = self._match_event(row, sub_rule)
            # 개별 규칙인 경우
            else:
                col = sub_rule.get("column")
                op = sub_rule.get("operator")
                val = sub_rule.get("value")
                
                if not all([col, op, val]) or col not in row.index:
                    result = False
                else:
                    cell_value = str(row[col]).lower()
                    check_value = val.lower()
                    
                    if op == "contains": result = check_value in cell_value
                    elif op == "equals": result = check_value == cell_value
                    # (향후 starts with, ends with 등 연산자 추가 가능)
                    else: result = False
            
            # 논리 연산 적용
            if logic == "AND" and not result:
                return False # AND 조건에서는 하나라도 거짓이면 즉시 실패
            if logic == "OR" and result:
                return True # OR 조건에서는 하나라도 참이면 즉시 성공
        
        # 루프가 끝난 후 최종 결과 반환
        return True if logic == "AND" else False

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
        self.current_theme = theme_name

    def get_current_theme(self):
        # 시작 시 config.json에서 로드한 값을 반영하기 위해 추가
        config_path = 'config.json'
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.current_theme = config.get('theme', 'light')
            except (json.JSONDecodeError, KeyError):
                pass
        return self.current_theme
    
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