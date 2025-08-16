import pandas as pd
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QStandardItemModel

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel

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
        self.update_model_data(self.original_data)
        return not self.original_data.empty

    def update_model_data(self, dataframe):
        self.source_model.update_data(dataframe)
        self.model_updated.emit(self.source_model)

    def clear_advanced_filter(self):
        self.update_model_data(self.original_data)

    def apply_advanced_filter(self, query_data):
        df = self.original_data.copy()
        
        if 'SystemDate' in df.columns:
            df['SystemDate_dt'] = pd.to_datetime(df['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce')

        final_mask = pd.Series(True, index=df.index) if query_data['logic'] == 'AND' else pd.Series(False, index=df.index)

        for cond in query_data['conditions']:
            column, op, value = cond['column'], cond['operator'], cond['value']
            if value == '' and not isinstance(value, (list, tuple)): continue

            mask = pd.Series(True, index=df.index)
            if column in ['SystemDate']:
                dt_value = pd.to_datetime(value.toPython()) if not isinstance(value, tuple) else None
                dt_value_from = pd.to_datetime(value[0].toPython()) if isinstance(value, tuple) else None
                dt_value_to = pd.to_datetime(value[1].toPython()) if isinstance(value, tuple) else None
                
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

            if query_data['logic'] == 'AND':
                final_mask &= mask
            else:
                final_mask |= mask
        
        self.update_model_data(self.original_data[final_mask])

    def get_trace_data(self, trace_id):
        df = self.original_data
        mask = df.apply(lambda r: r.astype(str).str.contains(trace_id, case=False, na=False).any(), axis=1)
        return df[mask]

    def get_scenario_data(self, trace_id):
        scenario_df = self.get_trace_data(trace_id)
        # Category 컬럼의 따옴표를 제거하고 비교
        com_logs = scenario_df[scenario_df['Category'].str.replace('"', '', regex=False) == 'Com'].sort_values(by='SystemDate')
        return com_logs