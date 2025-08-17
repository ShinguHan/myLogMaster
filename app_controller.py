import pandas as pd
import json
import os
from PySide6.QtCore import QObject, Signal, QDateTime

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel
from analysis_result import AnalysisResult

FILTERS_FILE = 'filters.json'
SCENARIOS_DIR = 'scenarios' # ⭐️ 시나리오 디렉토리 경로 상수 추가

class AppController(QObject):
    model_updated = Signal(LogTableModel)

    def __init__(self):
        super().__init__()
        self.original_data = pd.DataFrame()
        self.source_model = LogTableModel()

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
            # 파일 로딩/파싱 중 발생하는 모든 에러는 여기서 처리
            print(f"Error loading or parsing file: {e}")
            self.original_data = pd.DataFrame() # 데이터 초기화
            self.update_model_data(self.original_data)
            return False

    def _get_profile(self):
        """파싱을 위한 프로파일을 반환합니다."""
        return {
            'column_mapping': {'Category': 'Category', 'AsciiData': 'AsciiData', 'BinaryData': 'BinaryData'},
            'type_rules': [{'value': 'Com', 'type': 'secs'}, {'value': 'Info', 'type': 'json'}]
        }

    def update_model_data(self, dataframe):
        self.source_model.update_data(dataframe)
        self.model_updated.emit(self.source_model)

    def clear_advanced_filter(self):
        self.update_model_data(self.original_data)

    def apply_advanced_filter(self, query_data):
        if not query_data or not query_data.get('rules'):
            self.clear_advanced_filter()
            return
            
        # ⭐️ 엣지 케이스 방어: 필터링할 원본 데이터가 없으면 실행하지 않음
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
                # ⭐️ 엣지 케이스 방어: 룰에 필요한 키가 없으면 건너뜀
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
        # ⭐️ 구체적인 예외 처리
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

    # ⭐️ --- 시나리오 검증 엔진 (상태 머신 업그레이드) --- ⭐️
    # ⭐️ --- 이 메서드 전체를 아래 내용으로 교체합니다 --- ⭐️
    def run_scenario_validation(self, scenario_to_run=None):
        """scenarios 폴더를 읽어 정의된 시나리오들을 상태 머신으로 검증합니다."""
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
            
            # --- 상태 머신 초기화 ---
            active_scenarios = {}  # {key: state}
            completed_scenarios = [] # {status, events, message}
            key_columns = scenario.get('key_columns', [])

            # --- 로그 파일 전체 순회 ---
            for index, row in df.iterrows():
                current_time = row['SystemDate_dt']
                
                # 1. 타임아웃 검사
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

                # 2. 상태 전이 (다음 단계 진행) 검사
                progressed_keys = []
                for key, state in active_scenarios.items():
                    # 현재 상태에서 다음으로 기대되는 단계를 확인
                    next_step_rule = scenario['steps'][state['current_step']]['event_match']
                    if self._match_event(row, next_step_rule):
                        state['events'].append(row.to_dict())
                        state['current_step'] += 1
                        state['last_event_time'] = current_time
                        
                        # 시나리오의 모든 단계를 통과했는지 확인
                        if state['current_step'] >= len(scenario['steps']):
                            state['status'] = 'SUCCESS'
                            state['message'] = 'Scenario completed successfully.'
                            completed_scenarios.append(state)
                            progressed_keys.append(key)
                for key in progressed_keys:
                    del active_scenarios[key]

                # 3. 새로운 트리거 감지 (기존에 진행 중인 시나리오가 아닐 경우에만)
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

            # 로그 파일 순회가 끝난 후, 아직 진행 중인 시나리오 처리
            for key, state in active_scenarios.items():
                state['status'] = 'INCOMPLETE'
                state['message'] = f"Scenario did not complete. Stopped at step {state['current_step']+1}."
                completed_scenarios.append(state)

            # --- 결과 리포트 생성 ---
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

    def _find_event_indices(self, df, rule):
        if df.empty:
            return pd.Index([])
        mask = df.apply(lambda row: self._match_event(row, rule), axis=1)
        return df[mask].index
    
    # ⭐️ scenarios.json을 직접 읽는 대신, 폴더 전체를 읽는 헬퍼 메서드 추가
    def load_all_scenarios(self):
        """'scenarios' 폴더 내의 모든 .json 파일을 읽어 하나로 합칩니다."""
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
    
    # ⭐️ UI가 시나리오 목록을 쉽게 가져갈 수 있도록 메서드 추가
    def get_scenario_names(self):
        return list(self.load_all_scenarios().keys())