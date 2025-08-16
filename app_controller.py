import pandas as pd
import json
import os
from PySide6.QtCore import QObject, Signal, QDateTime

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel

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
                if column in ['SystemDate']:
                    # QDateTime이 아닌 ISO 문자열로 넘어온 값을 처리
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
        if not os.path.exists(FILTERS_FILE):
            return {}
        try:
            with open(FILTERS_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    def save_filter(self, name, query_data):
        filters = self.load_filters()
        if query_data: # 비어있지 않은 쿼리만 저장
            filters[name] = query_data
            with open(FILTERS_FILE, 'w') as f:
                json.dump(filters, f, indent=4)

    def get_trace_data(self, trace_id):
        df = self.original_data
        mask = df.apply(lambda r: r.astype(str).str.contains(trace_id, case=False, na=False).any(), axis=1)
        return df[mask]

    def get_scenario_data(self, trace_id):
        scenario_df = self.get_trace_data(trace_id)
        com_logs = scenario_df[scenario_df['Category'].str.replace('"', '', regex=False) == 'Com'].sort_values(by='SystemDate')
        return com_logs