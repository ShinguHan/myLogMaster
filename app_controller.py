import pandas as pd
import json
import os
import re
from PySide6.QtCore import QObject, Signal, QTimer

from universal_parser import parse_log_with_profile
from models.LogTableModel import LogTableModel
from analysis_result import AnalysisResult
from database_manager import DatabaseManager
from oracle_fetcher import OracleFetcherThread
from utils.event_matcher import EventMatcher # 💥 변경점: EventMatcher 임포트

FILTERS_FILE = 'filters.json'
SCENARIOS_DIR = 'scenarios'

class AppController(QObject):
    model_updated = Signal(LogTableModel)
    fetch_completed = Signal()
    fetch_progress = Signal(str)
    row_count_updated = Signal(int)
    fetch_error = Signal(str)

    def __init__(self, app_mode, connection_name=None, connection_info=None):
        super().__init__()
        self.mode = app_mode
        self.connection_name = connection_name
        self.connection_info = connection_info
        self.original_data = pd.DataFrame()
        self.source_model = LogTableModel(max_rows=20000)
        self.fetch_thread = None
        self.last_query_conditions = None
        self.dashboard_dialog = None
        
        self.config = {}
        self._load_config()

        self._update_queue = []
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(200)
        self._update_timer.timeout.connect(self._process_update_queue)

        self.highlighting_rules = self._load_highlighting_rules()
        
        # 💥 변경점: EventMatcher 인스턴스 생성
        self.event_matcher = EventMatcher()

        if self.mode == 'realtime':
            if self.connection_name:
                self.db_manager = DatabaseManager(self.connection_name)
                self.load_data_from_cache()
            else:
                self.db_manager = None
        else:
            self.db_manager = DatabaseManager("file_mode")
            
    def _load_config(self):
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            else:
                self.config = {'theme': 'light', 'visible_columns': []}
        except (json.JSONDecodeError, Exception):
            self.config = {'theme': 'light', 'visible_columns': []}

    def save_config(self):
        try:
            with open('config.json', 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get_current_theme(self):
        return self.config.get('theme', 'light')

    def set_current_theme(self, theme_name):
        self.config['theme'] = theme_name
        self.save_config()

    def _load_highlighting_rules(self):
        try:
            if os.path.exists('highlighters.json'):
                with open('highlighters.json', 'r', encoding='utf-8') as f:
                    return json.load(f)
        except (json.JSONDecodeError, Exception):
            pass
        return []

    def _save_highlighting_rules(self):
        try:
            with open('highlighters.json', 'w', encoding='utf-8') as f:
                json.dump(self.highlighting_rules, f, indent=4)
        except Exception as e:
            print(f"Error saving highlighting rules: {e}")

    def get_highlighting_rules(self):
        return self.highlighting_rules.copy()

    def set_and_save_highlighting_rules(self, new_rules):
        self.highlighting_rules = new_rules
        self._save_highlighting_rules()
        self.source_model.set_highlighting_rules(self.highlighting_rules)

    def load_data_from_cache(self):
        if not self.db_manager: 
            self.update_model_data(pd.DataFrame())
            return
        
        cached_data = self.db_manager.read_all_logs_from_cache()
        
        if not cached_data.empty:
            self.original_data = cached_data
            if 'SystemDate' in self.original_data.columns and 'SystemDate_dt' not in self.original_data.columns:
                 self.original_data['SystemDate_dt'] = pd.to_datetime(self.original_data['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce')
        else:
            self.original_data = pd.DataFrame()
        
        self.update_model_data(self.original_data)

    def load_log_file(self, filepath):
        try:
            parsed_data = parse_log_with_profile(filepath, self._get_profile())
            if not parsed_data:
                return False
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
        self.source_model.set_highlighting_rules(self.highlighting_rules)
        self.model_updated.emit(self.source_model)

    def start_db_fetch(self, query_conditions):
        if self.fetch_thread and self.fetch_thread.isRunning():
            return

        self.last_query_conditions = query_conditions
        
        if self.db_manager:
            self.db_manager.clear_logs_from_cache()

        self.source_model.update_data(pd.DataFrame())
        self.original_data = pd.DataFrame()

        self.fetch_thread = OracleFetcherThread(self.connection_info, query_conditions, parent=self)
        
        self.fetch_thread.data_fetched.connect(self.append_data_chunk)
        self.fetch_thread.finished.connect(self.on_fetch_finished)
        self.fetch_thread.progress.connect(self.fetch_progress)
        self.fetch_thread.error.connect(self._handle_fetch_error)

        if self.dashboard_dialog and self.dashboard_dialog.isVisible():
            self.dashboard_dialog.start_updates()

        self._update_timer.start()
        self.fetch_thread.start()

    def append_data_chunk(self, df_chunk):
        if not df_chunk.empty:
            self._update_queue.append(df_chunk)

    def on_fetch_finished(self):
        if self._update_queue:
            self._process_update_queue()
        
        if self._update_timer.isActive():
            self._update_timer.stop()

        if self.dashboard_dialog and self.dashboard_dialog.isVisible():
            self.dashboard_dialog.stop_updates()
            
        self.fetch_completed.emit()

        if self.db_manager and self.last_query_conditions:
            start_time = self.last_query_conditions.get('start_time', '')
            end_time = self.last_query_conditions.get('end_time', '')
            filters = {k: v for k, v in self.last_query_conditions.items() if k not in ['start_time', 'end_time']}
            self.db_manager.add_fetch_history(start_time, end_time, filters)
        
    def run_analysis_script(self, script_code, dataframe):
        result_obj = AnalysisResult()
        try:
            # `exec` can be dangerous. Ensure script source is trusted.
            # A safer approach might involve a restricted execution environment.
            exec_globals = {
                'logs': dataframe,
                'result': result_obj,
                'pd': pd 
            }
            exec(script_code, exec_globals)
        except Exception as e:
            result_obj.set_summary(f"Script execution failed:\n{e}")
            print(f"Script execution error: {e}")
        return result_obj

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
                    series = df[column].astype(str)
                    if op == 'Contains': mask = series.str.contains(value, case=False, na=False)
                    elif op == 'Does Not Contain': mask = ~series.str.contains(value, case=False, na=False)
                    elif op == 'Equals': mask = series == value
                    elif op == 'Not Equals': mask = series != value
                    elif op == 'Matches Regex': mask = series.str.match(value, na=False)
                    masks.append(mask)
                except KeyError:
                    continue

        if not masks:
            return pd.Series(True, index=df.index)

        return pd.concat(masks, axis=1).all(axis=1) if query_group['logic'] == 'AND' else pd.concat(masks, axis=1).any(axis=1)

    def load_filters(self):
        try:
            if not os.path.exists(FILTERS_FILE): return {}
            with open(FILTERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
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
        if self.original_data.empty: return []
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

                finished_keys = []
                for key, state in active_scenarios.items():
                    context_match = all(state['context'].get(k) == current_row_context.get(k) for k in context_keys if k in current_row_context) if context_keys else True
                    if not context_match: continue
                    
                    if state['current_step'] >= len(state['steps']): continue
                    step_definition = state['steps'][state['current_step']]
                    
                    step_matched = self._match_event(row, step_definition.get('event_match', {}))

                    if step_matched:
                        state['last_event_time'] = current_time
                        state['involved_logs'].append({"step_name": step_definition.get('name', f"Step {state['current_step']+1}"), "log_index": int(row['index']), "timestamp": row['SystemDate_dt']})
                        state['current_step'] += 1

                    if state['current_step'] >= len(state['steps']):
                        state['status'] = 'SUCCESS'; state['message'] = 'Scenario completed successfully.'
                        completed_scenarios.append(state); finished_keys.append(key)

                for key in finished_keys: del active_scenarios[key]

                if self._match_event(row, scenario.get('trigger_event', {})):
                    trigger_context = self._extract_context(row, scenario.get("context_extractors", {}))
                    key = tuple(trigger_context[k] for k in context_keys) if context_keys and all(k in trigger_context for k in context_keys) else row['index']

                    if key not in active_scenarios:
                        active_scenarios[key] = {
                            'context': trigger_context, 'steps': list(scenario['steps']),
                            'start_time': current_time, 'last_event_time': current_time,
                            'current_step': 0, 'status': 'IN_PROGRESS', 'scenario_name': name,
                            'involved_logs': [{"step_name": "Trigger", "log_index": int(row['index']), "timestamp": row['SystemDate_dt']}]
                        }
            
            for key, state in active_scenarios.items():
                state['status'] = 'INCOMPLETE'; state['message'] = f"Scenario stopped at step {state['current_step'] + 1}."
                completed_scenarios.append(state)
            
            all_completed_scenarios.extend(completed_scenarios)

        if self.db_manager:
            for report in all_completed_scenarios:
                self.db_manager.add_validation_history(
                    scenario_name=report['scenario_name'], status=report['status'],
                    message=report.get('message', ''), involved_log_indices=report.get('involved_logs', [])
                )
        
        return all_completed_scenarios

    # 💥 변경점: 복잡한 로직이 EventMatcher로 위임되어 코드가 극도로 단순해짐
    def _match_event(self, row, rule_group):
        """이벤트가 규칙과 일치하는지 확인합니다. (EventMatcher에 위임)"""
        return self.event_matcher.match(row, rule_group)

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
                        for name, details in scenarios_in_file.items():
                            details['_source_file'] = filename
                            all_scenarios[name] = details
                except Exception as e:
                    print(f"Warning: Could not parse {filename}: {e}")
        return all_scenarios
    
    def get_scenario_names(self):
        scenarios = self.load_all_scenarios()
        return [name for name, details in scenarios.items() if details.get("enabled", True)]
    
    def _process_update_queue(self):
        if not self._update_queue: return

        combined_chunk = pd.concat(self._update_queue, ignore_index=True)
        self._update_queue.clear()

        if 'SystemDate' in combined_chunk.columns and 'SystemDate_dt' not in combined_chunk.columns:
            combined_chunk['SystemDate_dt'] = pd.to_datetime(combined_chunk['SystemDate'], format='%d-%b-%Y %H:%M:%S:%f', errors='coerce')

        self.original_data = pd.concat([self.original_data, combined_chunk], ignore_index=True)
        self.source_model.append_data(combined_chunk)
        
        current_model_rows = self.source_model.rowCount()
        if len(self.original_data) > current_model_rows:
            self.original_data = self.original_data.tail(current_model_rows).reset_index(drop=True)

        if self.db_manager:
            self.db_manager.upsert_logs_to_local_cache(combined_chunk)
        
        self.row_count_updated.emit(self.source_model.rowCount())

        if self.dashboard_dialog and self.dashboard_dialog.isVisible():
            self.dashboard_dialog.update_dashboard(self.original_data)

    def cancel_db_fetch(self):
        if self.fetch_thread and self.fetch_thread.isRunning():
            self.fetch_thread.stop()
    
    def _handle_fetch_error(self, error_message):
        self.fetch_error.emit(error_message)
        if self.dashboard_dialog and self.dashboard_dialog.isVisible():
            self.dashboard_dialog.stop_updates()
        if self._update_timer.isActive():
            self._update_timer.stop()

    def save_log_to_csv(self, dataframe, file_path):
        try:
            dataframe.to_csv(file_path, index=False, encoding='utf-8-sig')
            return True, f"Successfully saved to {os.path.basename(file_path)}"
        except Exception as e:
            return False, f"Could not save file: {e}"
        
    def _build_where_clause(self, query_conditions):
        clauses = []
        params = {}
        
        params['p_start_time'] = pd.to_datetime(query_conditions['start_time']).strftime('%Y-%m-%d %H:%M:%S')
        params['p_end_time'] = pd.to_datetime(query_conditions['end_time']).strftime('%Y-%m-%d %H:%M:%S')
        clauses.append("SystemDate BETWEEN TO_DATE(:p_start_time, 'YYYY-MM-DD HH24:MI:SS') AND TO_DATE(:p_end_time, 'YYYY-MM-DD HH24:MI:SS')")
        
        adv_filter = query_conditions.get('advanced_filter')
        if adv_filter and adv_filter.get('rules'):
            adv_clause, adv_params = self._parse_filter_group(adv_filter)
            if adv_clause:
                clauses.append(f"({adv_clause})")
                params.update(adv_params)
        
        return " AND ".join(clauses), params

    def _parse_filter_group(self, group, param_index=0):
        clauses = []
        params = {}
        logic = f" {group.get('logic', 'AND')} "
        
        for rule in group.get('rules', []):
            if "logic" in rule:
                sub_clause, sub_params = self._parse_filter_group(rule, param_index)
                if sub_clause:
                    clauses.append(f"({sub_clause})")
                    params.update(sub_params)
                    param_index += len(sub_params)
            else:
                col, op, val = rule.get('column'), rule.get('operator'), rule.get('value')
                if not all([col, op, val]): continue
                param_name = f"p{param_index}"
                
                op_map = {
                    'Contains': "INSTR({col}, :{p}) > 0", 'Does Not Contain': "INSTR({col}, :{p}) = 0",
                    'Equals': "{col} = :{p}", 'Not Equals': "{col} != :{p}",
                    'Matches Regex': "REGEXP_LIKE({col}, :{p})"
                }
                if op in op_map:
                    clauses.append(op_map[op].format(col=col, p=param_name))
                    params[param_name] = val
                    param_index += 1
                
        return logic.join(clauses), params
    
    def _extract_context(self, row, extractors):
        context_data = {}
        for context_name, rules in extractors.items():
            for rule in rules:
                if "from_column" in rule:
                    val = row.get(rule["from_column"])
                    if pd.notna(val) and str(val).strip():
                        context_data[context_name] = str(val); break
                elif "from_regex" in rule:
                    source_col, pattern = rule["from_regex"].get("column"), rule["from_regex"].get("pattern")
                    match = re.search(pattern, str(row.get(source_col, '')))
                    if match:
                        context_data[context_name] = match.group(1); break
        return context_data
    
    def get_history_summary(self):
        return self.db_manager.get_validation_history_summary() if self.db_manager else pd.DataFrame()

    def get_history_detail(self, run_id):
        return self.db_manager.get_validation_history_detail(run_id) if self.db_manager else None

