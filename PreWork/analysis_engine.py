import importlib
import os
import json
import re
from types import SimpleNamespace

class AnalysisEngine:
    def __init__(self):
        self.rules = self._discover_rules()
        print(f"[ENGINE] Discovered rules: {list(self.rules.keys())}")
        self.state_profile = self._load_state_profile()

    def _load_state_profile(self, profile_path="profile/state_profile.json"):
        print(f"[ENGINE] Attempting to load state profile from: {profile_path}")
        if not os.path.exists(profile_path):
            print(f"[ENGINE] State profile not found.")
            return None
        with open(profile_path, 'r') as f:
            profile = json.load(f)
            print("[ENGINE] State profile loaded successfully.")
            return profile

    def _get_object_id(self, entry, log_source_def):
        source_type = log_source_def.get("source_type")
        
        # --- JSON 로그 ID 추출 ---
        if source_type == "json":
            # universal_parser가 {'entry': json_data} 형태로 저장하므로, 실제 데이터에 접근
            json_data = entry.get('entry')
            if not json_data:
                return None
            
            try:
                path_parts = log_source_def["identity_path"].split('.')
                value = json_data
                print(f"  [ID_EXTRACT|json] Start path search: {log_source_def['identity_path']}")
                
                for part in path_parts:
                    if value is None:
                        print(f"    [ID_EXTRACT|json] Path search failed, value is None.")
                        return None
                    
                    if '[' in part and part.endswith(']'):
                        key = part.split('[')[0]
                        index = int(part.split('[')[1][:-1])
                        
                        print(f"    [ID_EXTRACT|json] Accessing list '{key}' at index '{index}'...")
                        list_value = value.get(key)
                        if isinstance(list_value, list) and len(list_value) > index:
                            value = list_value[index]
                        else:
                            print(f"    [ID_EXTRACT|json] Failed to access list.")
                            return None
                    else:
                        print(f"    [ID_EXTRACT|json] Accessing key '{part}'...")
                        value = value.get(part)
                
                print(f"  [ID_EXTRACT|json] Found ID: {value}")
                return value
            except (KeyError, IndexError, TypeError, AttributeError, ValueError) as e:
                print(f"  [ID_EXTRACT|json] Exception during path search: {e}")
                return None

        # --- DEBUG/TEXT 로그 ID 추출 ---
        elif source_type == "debug":
            log_str = str(entry) # entry 전체를 문자열로 검색
            regex = log_source_def.get("identity_regex")
            if regex:
                match = re.search(regex, log_str)
                if match:
                    obj_id = match.group(1)
                    print(f"  [ID_EXTRACT|debug] Regex found ID: {obj_id}")
                    return obj_id
        return None

    def _build_stateful_log(self, parsed_log_data):
        if not self.state_profile:
            return {}

        print("\n--- [ENGINE] Building Stateful Log ---")
        stateful_entries = []
        object_states = {} 

        all_logs = parsed_log_data.get('all_logs', []) # universal_parser가 통합 로그를 제공한다고 가정
        if not all_logs: # 임시 호환성 코드
            all_logs = parsed_log_data.get('secs', []) + parsed_log_data.get('json', [])

        for i, entry in enumerate(all_logs):
            print(f"\n[ENGINE|{i+1}] Processing log entry: {str(entry)[:150]}...")

            for obj_def in self.state_profile.get("tracked_objects", []):
                obj_id = None
                for source_def in obj_def.get("log_sources", []):
                    obj_id = self._get_object_id(entry, source_def)
                    if obj_id:
                        break
                
                if obj_id:
                    print(f"  [STATE] Found object '{obj_id}' in log.")
                    current_state = object_states.get(obj_id, obj_def["states"]["initial"])
                    new_state = current_state

                    entry_str = str(entry)
                    for transition in obj_def["states"]["transitions"]:
                        if transition["trigger_log_contains"] in entry_str:
                            new_state = transition["new_state"]
                            print(f"  [STATE] State transition for '{obj_id}': '{current_state}' -> '{new_state}' (Trigger: '{transition['trigger_log_contains']}')")
                            break

                    object_states[obj_id] = new_state
                    
                    new_entry = entry.copy()
                    new_entry[obj_def["identity_key"]] = obj_id
                    new_entry['state'] = new_state
                    stateful_entries.append(new_entry)

        print("--- [ENGINE] Finished Building Stateful Log ---\n")
        return {"stateful_log": stateful_entries}

    def run(self, parsed_log_data, analysis_scenario):
        report = {"name": "Log Analysis", "result": "Pass", "duration": "N/A", "steps": []}
        
        stateful_log_data = self._build_stateful_log(parsed_log_data)
        
        log_data_bundle = {
            "secs": parsed_log_data.get('secs', []),
            "json": parsed_log_data.get('json', []),
            "stateful_log": stateful_log_data.get('stateful_log', [])
        }

        print("--- [ENGINE] Running Analysis Scenario ---")
        for i, step in enumerate(analysis_scenario):
            action = step.get('action')
            print(f"[ENGINE|Step {i+1}] Executing action: '{action}'")
            if action in self.rules:
                rule_function = self.rules[action]
                result_obj = rule_function(log_data_bundle, step)
                
                step_result = result_obj.get("result", "Fail")
                step_details = result_obj.get("details", "No details provided.")
                
                if step_result != "Pass":
                    report['result'] = "Fail"
                
                report['steps'].append(f"- {action.upper()}: {step_result}\n  Details: {step_details}")
                print(f"  [ENGINE|Step {i+1}] Result: {step_result}")
            else:
                report['result'] = "Fail"
                report['steps'].append(f"- {action.upper()}: Fail\n  Details: Rule '{action}' not found.")
        print("--- [ENGINE] Finished Analysis Scenario ---")

        return report