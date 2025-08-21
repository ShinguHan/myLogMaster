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

            # ✅ "Run All"일 때 (scenario_to_run=None), 비활성화된 시나리오는 건너뜀
            if scenario_to_run is None and not scenario.get("enabled", True):
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