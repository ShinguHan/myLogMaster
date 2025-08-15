import importlib
import os
from types import SimpleNamespace

class AnalysisEngine:
    def __init__(self):
        self.rules = self._discover_rules()
        print(f"Discovered rules: {list(self.rules.keys())}")

    def _discover_rules(self):
        """Dynamically finds and imports all available rule plug-ins."""
        rules = {}
        rules_dir = "rules"
        # Ensure the rules directory exists
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
        """
        Executes an analysis scenario by dispatching tasks to the correct rule plug-ins.
        """
        report = {"name": "Log Analysis", "result": "Pass", "duration": "N/A", "steps": []}
        
        # --- Pre-computation Pass ---
        stateful_secs_log = []
        current_process_state = "IDLE"
        for entry in parsed_log_data.get('secs', []):
            # Simplified state logic
            if entry.get('msg') == 'S6F11':
                current_process_state = "PROCESSING"
            new_entry = entry.copy()
            new_entry['state'] = current_process_state
            stateful_secs_log.append(new_entry)
        
        log_data_bundle = {
            "secs": parsed_log_data.get('secs', []),
            "json": parsed_log_data.get('json', []),
            "stateful_secs": stateful_secs_log
        }

        # --- Rule Execution Pass ---
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
