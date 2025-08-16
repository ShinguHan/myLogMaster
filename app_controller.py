import pandas as pd
import json
import os
from PySide6.QtCore import QObject, Signal, QDateTime
import io
import sys
from contextlib import redirect_stdout

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel
from analysis_result import AnalysisResult # ⭐️ 새로 만든 클래스 임포트

FILTERS_FILE = 'filters.json'

class AppController(QObject):
    model_updated = Signal(LogTableModel)

    def __init__(self):
        super().__init__()
        # ⭐️ 1. 마스터 원본 데이터를 보관하는 변수
        self.original_data = pd.DataFrame()
        self.source_model = LogTableModel()

    def load_log_file(self, filepath):
        # ⭐️ 2. 이 메서드에서만 self.original_data에 쓰기 작업을 수행합니다.
        profile = {
            'column_mapping': {'Category': 'Category', 'AsciiData': 'AsciiData', 'BinaryData': 'BinaryData'},
            'type_rules': [{'value': 'Com', 'type': 'secs'}, {'value': 'Info', 'type': 'json'}]
        }
        parsed_data = parse_log_with_profile(filepath, profile)
        self.original_data = pd.DataFrame(parsed_data)
        
        if 'SystemDate' in self.original_data.columns:
            # 원본 데이터에 날짜/시간 변환 컬럼을 미리 추가해 둡니다.
            self.original_data['SystemDate_dt'] = pd.to_datetime(
                self.original_data['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce'
            )
        
        # UI에 원본 데이터 전체를 표시하며 시작
        self.update_model_data(self.original_data)
        return not self.original_data.empty

    def update_model_data(self, dataframe):
        """UI에 표시될 모델의 데이터만 업데이트합니다. 원본은 건드리지 않습니다."""
        self.source_model.update_data(dataframe)
        self.model_updated.emit(self.source_model)

    def clear_advanced_filter(self):
        """UI를 다시 원본 데이터로 되돌립니다."""
        print("Filter cleared. Restoring original data.")
        self.update_model_data(self.original_data)

    def apply_advanced_filter(self, query_data):
        if not query_data or not query_data.get('rules'):
            self.clear_advanced_filter()
            return
            
        try:
            # ⭐️ 3. 필터링을 수행할 때, 항상 self.original_data를 대상으로 합니다.
            print("Applying advanced filter on original data...")
            final_mask = self._build_mask_recursive(query_data, self.original_data)
            
            # 필터링된 '결과(복사본)'를 UI에 업데이트합니다.
            self.update_model_data(self.original_data[final_mask])
        except Exception as e:
            print(f"Error applying filter: {e}")
            self.update_model_data(self.original_data) # 에러 발생 시 원본으로 복원

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
                    
                    # 미리 변환해 둔 'SystemDate_dt' 컬럼을 사용
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
            with open(FILTERS_FILE, 'r') as f: return json.load(f)
        except json.JSONDecodeError: return {}

    def save_filter(self, name, query_data):
        filters = self.load_filters()
        if query_data:
            filters[name] = query_data
            with open(FILTERS_FILE, 'w') as f: json.dump(filters, f, indent=4)

    def get_trace_data(self, trace_id):
        df = self.original_data
        mask = df.apply(lambda r: r.astype(str).str.contains(trace_id, case=False, na=False).any(), axis=1)
        return df[mask]

    def get_scenario_data(self, trace_id):
        scenario_df = self.get_trace_data(trace_id)
        com_logs = scenario_df[scenario_df['Category'].str.replace('"', '', regex=False) == 'Com'].sort_values(by='SystemDate')
        return com_logs
    
    def run_analysis_script(self, script_code, logs_df):
        stdout_capture = io.StringIO()
        result = AnalysisResult() # ⭐️ AnalysisResult 객체 생성

        try:
            script_namespace = {}
            with redirect_stdout(stdout_capture):
                exec(script_code, globals(), script_namespace)

            analyze_func = script_namespace.get('analyze')

            if not callable(analyze_func):
                result.set_summary("Error: 'analyze(logs, result)' function not found in the script.")
                return result
            
            # ⭐️ 이제 result 객체를 함께 전달
            return_value = analyze_func(logs_df, result)
            
            # 스크립트의 return 값이 있으면 요약에 추가
            if return_value:
                summary = f"--- Return Value ---\n{return_value}"
                if result.summary:
                    result.summary = f"{result.summary}\n{summary}"
                else:
                    result.set_summary(summary)

        except Exception as e:
            result.set_summary(f"--- SCRIPT ERROR ---\n{type(e).__name__}: {e}")
        
        finally:
            # 캡처된 print 출력을 result 객체에 저장
            result.captured_output = stdout_capture.getvalue()
            return result