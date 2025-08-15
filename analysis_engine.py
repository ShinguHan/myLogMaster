import importlib
import os
import json # 추가
import re # 추가
from types import SimpleNamespace

class AnalysisEngine:
    def __init__(self):
        self.rules = self._discover_rules()
        print(f"Discovered rules: {list(self.rules.keys())}")
        self.state_profile = self._load_state_profile() # 상태 프로필 로드

    def _load_state_profile(self, profile_path="profile/state_profile.json"): # 신규 메서드
        """상태 정의 프로필을 로드합니다."""
        if not os.path.exists(profile_path):
            return None
        with open(profile_path, 'r') as f:
            return json.load(f)

    def _get_object_id(self, entry, log_source_def): # 신규 헬퍼 메서드
        """로그 항목에서 정의된 경로를 따라 객체 ID를 추출합니다."""
        source_type = log_source_def.get("source_type")
        
        if source_type == "json" and 'entry' in entry:
            # dpath 와 유사한 방식으로 경로를 탐색 (실제 구현 시 라이브러리 사용 고려)
            try:
                path_parts = log_source_def["identity_path"].split('.')
                value = entry['entry']
                for part in path_parts:
                    if isinstance(value, dict):
                        value = value.get(part)
                    elif isinstance(value, list) and part.endswith(']'):
                        index = int(part[part.find('[')+1:-1])
                        value = value[index]
                return value
            except (KeyError, IndexError, TypeError):
                return None

        elif source_type == "debug":
            # 정규표현식을 사용하여 AsciiData에서 ID 추출
            log_str = str(entry) # entry 전체를 문자열로 검색
            regex = log_source_def.get("identity_regex")
            if regex:
                match = re.search(regex, log_str)
                if match:
                    return match.group(1) # 첫 번째 캡처 그룹을 ID로 사용
        return None

    def _build_stateful_log(self, parsed_log_data): # 기능 고도화
        """파싱된 로그와 상태 프로필을 기반으로 상태 변화 이력을 추적합니다."""
        if not self.state_profile:
            return {}

        stateful_entries = []
        object_states = {} # 예: { "LHAE000336": "MOVE_REQUESTED" }

        # 모든 로그를 타임스탬프 순으로 정렬 (universal_parser가 timestamp 필드를 추가했다고 가정)
        all_logs = parsed_log_data.get('secs', []) + parsed_log_data.get('json', [])
        # 참고: debug_log는 현재 파서에서 timestamp 정보가 없어 정렬에서 제외. 필요시 파서 수정 필요.
        # all_logs.sort(key=lambda x: x.get('timestamp'))

        for entry in all_logs:
            for obj_def in self.state_profile.get("tracked_objects", []):
                obj_id = None
                for source_def in obj_def.get("log_sources", []):
                    obj_id = self._get_object_id(entry, source_def)
                    if obj_id:
                        break # ID를 찾으면 더 이상 다른 소스 정의를 확인하지 않음

                if obj_id:
                    # 객체의 현재 상태를 가져오거나 초기 상태로 설정
                    current_state = object_states.get(obj_id, obj_def["states"]["initial"])
                    new_state = current_state

                    # 상태 전이 규칙 확인
                    entry_str = json.dumps(entry)
                    for transition in obj_def["states"]["transitions"]:
                        if transition["trigger_log_contains"] in entry_str:
                            new_state = transition["new_state"]
                            break # 첫 번째 매칭되는 규칙으로 상태 변경

                    object_states[obj_id] = new_state
                    
                    # 로그 항목에 객체 ID와 상태 정보 추가
                    new_entry = entry.copy()
                    new_entry[obj_def["identity_key"]] = obj_id
                    new_entry['state'] = new_state
                    stateful_entries.append(new_entry)

        return {"stateful_log": stateful_entries}


    def _discover_rules(self):
        """Dynamically finds and imports all available rule plug-ins."""
        rules = {}
        rules_dir = "rules"
        if not os.path.isdir(rules_dir):
            return rules
            
        for filename in os.listdir(rules_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                rule_name = filename[:-3]
                try:
                    module = importlib.import_module(f"{rules_dir}.{rule_name}")
                    if hasattr(module, 'execute'):
                        rules[rule_name] = module.execute
                except ImportError as e:
                    print(f"Failed to import rule {rule_name}: {e}")
                    continue
        return rules

    def run(self, parsed_log_data, analysis_scenario):
        report = {"name": "Log Analysis", "result": "Pass", "duration": "N/A", "steps": []}
        
        stateful_log_data = self._build_stateful_log(parsed_log_data)
        
        log_data_bundle = {
            "secs": parsed_log_data.get('secs', []),
            "json": parsed_log_data.get('json', []),
            "stateful_log": stateful_log_data.get('stateful_log', [])
        }

        for step in analysis_scenario:
            action = step.get('action')
            if action in self.rules:
                rule_function = self.rules[action]
                result_obj = rule_function(log_data_bundle, step)
                
                step_result = result_obj.get("result", "Fail")
                step_details = result_obj.get("details", "No details provided.")
                
                if step_result != "Pass":
                    report['result'] = "Fail"
                
                report['steps'].append(f"- {action.upper()}: {step_result}\n  Details: {step_details}")
            else:
                report['result'] = "Fail"
                report['steps'].append(f"- {action.upper()}: Fail\n  Details: Rule '{action}' not found.")

        return report