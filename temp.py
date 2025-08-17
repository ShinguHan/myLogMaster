import pandas as pd
import json
import os
from PySide6.QtCore import QObject, Signal, QDateTime

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel
from analysis_result import AnalysisResult

FILTERS_FILE = 'filters.json'
SCENARIOS_DIR = 'scenarios'

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
                        # ... (이전과 동일한 날짜 처리 로직)
                        pass
                    else:
                        # ... (이전과 동일한 텍스트 처리 로직)
                        pass
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

    # ... (get_trace_data, get_scenario_data 메서드는 이전과 동일)

    def run_scenario_validation(self, scenario_to_run=None):
        # ⭐️ 엣지 케이스 방어: 검증할 원본 데이터가 없으면 즉시 반환
        if self.original_data.empty:
            return "오류: 로그 데이터가 없습니다."

        # ⭐️ 구체적인 예외 처리
        try:
            scenarios = self.load_all_scenarios()
            if "Error" in scenarios:
                return f"오류: {scenarios['Error']['description']}"
        except Exception as e:
            return f"오류: 시나리오 파일을 로드하는 중 에러 발생\n{e}"

        # ... (이하 검증 로직은 이전과 동일)