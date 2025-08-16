import pandas as pd
import json
import os
from PySide6.QtCore import QObject, Signal, QDateTime

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel
from analysis_result import AnalysisResult

FILTERS_FILE = 'filters.json'

class AppController(QObject):
    model_updated = Signal(LogTableModel)

    def __init__(self):
        super().__init__()
        self.original_data = pd.DataFrame()
        self.source_model = LogTableModel()

    def load_log_file(self, filepath):
        profile = {
            'column_mapping': {'Category': 'Category', 'AsciiData': 'AsciiData', 'BinaryData': 'BinaryData'},
            'type_rules': [{'value': 'Com', 'type': 'secs'}, {'value': 'Info', 'type': 'json'}]
        }
        parsed_data = parse_log_with_profile(filepath, profile)
        self.original_data = pd.DataFrame(parsed_data)
        
        # ⭐️ 시나리오 검증 시 시간 비교 성능을 위해 datetime 객체 컬럼을 미리 생성합니다.
        if 'SystemDate' in self.original_data.columns:
            self.original_data['SystemDate_dt'] = pd.to_datetime(self.original_data['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce')
        
        self.update_model_data(self.original_data)
        return not self.original_data.empty

    def update_model_data(self, dataframe):
        self.source_model.update_data(dataframe)
        self.model_updated.emit(self.source_model)

    def clear_advanced_filter(self):
        self.update_model_data(self.original_data)

    def apply_advanced_filter(self, query_data):
        if not query_data or not query_data.get('rules'):
            self.clear_advanced_filter()
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
                mask = pd.Series(True, index=df.index)
                
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

        if not masks:
            return pd.Series(True, index=df.index)

        if query_group['logic'] == 'AND':
            return pd.concat(masks, axis=1).all(axis=1)
        else:
            return pd.concat(masks, axis=1).any(axis=1)

    def load_filters(self):
        if not os.path.exists(FILTERS_FILE): return {}
        try:
            with open(FILTERS_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except json.JSONDecodeError: return {}

    def save_filter(self, name, query_data):
        filters = self.load_filters()
        if query_data:
            filters[name] = query_data
            with open(FILTERS_FILE, 'w', encoding='utf-8') as f: json.dump(filters, f, indent=4)

    def get_trace_data(self, trace_id):
        df = self.original_data
        mask = df.apply(lambda r: r.astype(str).str.contains(trace_id, case=False, na=False).any(), axis=1)
        return df[mask]

    def get_scenario_data(self, trace_id):
        scenario_df = self.get_trace_data(trace_id)
        com_logs = scenario_df[scenario_df['Category'].str.replace('"', '', regex=False) == 'Com'].sort_values(by='SystemDate')
        return com_logs

    # ⭐️ --- 시나리오 검증 엔진 --- ⭐️
    def run_scenario_validation(self):
        if self.original_data.empty:
            return "오류: 로그 데이터가 없습니다."

        try:
            with open('scenarios.json', 'r', encoding='utf-8') as f:
                scenarios = json.load(f)
        except FileNotFoundError:
            return "오류: 'scenarios.json' 파일을 찾을 수 없습니다."
        except json.JSONDecodeError:
            return "오류: 'scenarios.json' 파일의 형식이 잘못되었습니다."

        results = ["=== 시나리오 검증 결과 ==="]
        df = self.original_data.sort_values(by='SystemDate_dt').reset_index(drop=True)

        for name, scenario in scenarios.items():
            trigger_rule = scenario['trigger_event']
            trigger_indices = self._find_event_indices(df, trigger_rule)
            
            success_count = 0
            # ⭐️ 실패 정보를 상세히 기록할 리스트
            failures = [] 

            if not trigger_indices.any():
                results.append(f"[{name}]: 시작 이벤트를 찾을 수 없습니다.")
                continue

            for idx in trigger_indices:
                first_step = scenario['steps'][0]
                time_limit = first_step['max_delay_seconds']
                trigger_time = df.loc[idx, 'SystemDate_dt']
                
                search_df = df.loc[idx + 1:]
                time_bound = trigger_time + pd.Timedelta(seconds=time_limit)
                search_df = search_df[search_df['SystemDate_dt'] <= time_bound]

                found_indices = self._find_event_indices(search_df, first_step['event_match'])

                if not found_indices.empty:
                    success_count += 1
                else:
                    # ⭐️ 실패 시, 단순 카운트가 아닌 상세 정보 기록
                    failures.append({
                        "trigger_row": idx,
                        "trigger_time": str(trigger_time),
                        "expected_step": first_step['name']
                    })
            
            # 최종 결과 리포트 생성
            summary = f"[{name}]: {len(trigger_indices)}회 시작 -> Step 1 성공: {success_count}회, 실패: {len(failures)}회"
            results.append(summary)
            if failures:
                results.append("  [실패 상세 정보 (최대 3건)]")
                for fail in failures[:3]:
                    results.append(f"    - Trigger at row {fail['trigger_row']} ({fail['trigger_time']}), Expected: '{fail['expected_step']}'")

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