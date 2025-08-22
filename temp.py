# shinguhan/mylogmaster/myLogMaster-main/app_controller.py

    def run_scenario_validation(self, scenario_to_run=None):
        """
        'branch_on_event'를 포함한 모든 고급 문법을 지원하는 최종 버전의 시나리오 분석 엔진입니다.
        """
        if self.original_data.empty: return "오류: 로그 데이터가 없습니다."
        scenarios = self.load_all_scenarios()
        if "Error" in scenarios: return f"오류: {scenarios['Error']['description']}"

        results = ["=== 시나리오 검증 결과 ==="]
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

                # --- 1. 타임아웃 및 이벤트 매칭 검사 ---
                finished_keys = []
                for key, state in active_scenarios.items():
                    context_match = all(state['context'].get(k) == current_row_context.get(k) for k in context_keys if k in current_row_context)
                    if not context_match: continue
                    if state['current_step'] >= len(state['steps']): continue
                        
                    step_definition = state['steps'][state['current_step']]

                    # --- 1a. 타임아웃 검사 ---
                    if 'max_delay_seconds' in step_definition:
                        time_limit = pd.Timedelta(seconds=step_definition['max_delay_seconds'])
                        if current_time > state['last_event_time'] + time_limit:
                            if step_definition.get('optional', False):
                                state['current_step'] += 1
                                if state['current_step'] >= len(state['steps']):
                                    state['status'] = 'SUCCESS'; completed_scenarios.append(state); finished_keys.append(key)
                                continue
                            else:
                                state['status'] = 'FAIL'; state['message'] = f"Timeout at Step {state['current_step'] + 1}: {step_definition.get('name', 'N/A')}"; completed_scenarios.append(state); finished_keys.append(key)
                                continue
                    
                    # --- 1b. 분기(Branch) 이벤트 처리 ---
                    if 'branch_on_event' in step_definition:
                        branch_rule = step_definition['branch_on_event']
                        if self._match_event(row, branch_rule.get('event_match', {})):
                            branch_value_context = self._extract_context(row, {'branch_key': branch_rule.get('extract_value_from', [])})
                            branch_key = branch_value_context.get('branch_key')
                            new_steps = branch_rule.get('cases', {}).get(branch_key)
                            if new_steps is not None:
                                # 현재 state의 남은 steps를 새로운 분기 steps로 교체
                                current_steps_so_far = state['steps'][:state['current_step']]
                                state['steps'] = current_steps_so_far + new_steps
                                state['last_event_time'] = current_time
                                # 다음 루프에서 새로운 steps의 첫 단계를 검사하도록 current_step은 그대로 둠
                            else:
                                state['status'] = 'FAIL'; state['message'] = f"Branching failed: No case for value '{branch_key}'"; completed_scenarios.append(state); finished_keys.append(key)
                        continue # 분기 이벤트 처리는 여기서 마무리하고 다음 로그로

                    # --- 1c. 일반, Optional, Unordered 그룹 이벤트 처리 ---
                    if step_definition.get('optional', False) and (state['current_step'] + 1) < len(state['steps']):
                        next_step_definition = state['steps'][state['current_step'] + 1]
                        if self._match_event(row, next_step_definition.get('event_match', {})):
                            state['current_step'] += 1; step_definition = next_step_definition
                    
                    # ✅ [수정] 'pass'로 비어있던 'unordered_group' 로직을 복원합니다.
                    if 'unordered_group' in step_definition:
                        found_event_name = None
                        for event_in_group in state.get('unordered_events', []):
                            if self._match_event(row, event_in_group['event_match']):
                                found_event_name = event_in_group['name']
                                break
                        if found_event_name:
                            state['unordered_events'] = [e for e in state['unordered_events'] if e['name'] != found_event_name]
                            state['last_event_time'] = current_time
                            if not state['unordered_events']:
                                state['current_step'] += 1
                    
                    elif self._match_event(row, step_definition.get('event_match', {})):
                        state['current_step'] += 1
                        state['last_event_time'] = current_time

                    if state['current_step'] >= len(state['steps']):
                        state['status'] = 'SUCCESS'; state['message'] = 'Scenario completed successfully.'; completed_scenarios.append(state); finished_keys.append(key)

                for key in finished_keys: del active_scenarios[key]

                # --- 2. 새로운 시나리오 시작(Trigger) 검사 ---
                if self._match_event(row, scenario.get('trigger_event', {})):
                    trigger_context = self._extract_context(row, scenario.get("context_extractors", {}))
                    if trigger_context and all(k in trigger_context for k in context_keys):
                        key = tuple(trigger_context[k] for k in context_keys)
                        if key not in active_scenarios:
                            new_state = {
                                'context': trigger_context,
                                'steps': list(scenario['steps']),
                                'start_time': current_time,
                                'last_event_time': current_time,
                                'current_step': 0, 'status': 'IN_PROGRESS'
                            }
                            # 첫 단계가 unordered_group이면 찾아야 할 이벤트 목록을 미리 생성
                            if 'unordered_group' in new_state['steps'][0]:
                                new_state['unordered_events'] = list(new_state['steps'][0]['unordered_group'])
                            active_scenarios[key] = new_state
            
            # --- 3. 최종 결과 처리 ---
            for key, state in active_scenarios.items():
                state['status'] = 'INCOMPLETE'; state['message'] = f"Scenario stopped at step {state['current_step'] + 1}."; completed_scenarios.append(state)
            
            success = sum(1 for s in completed_scenarios if s['status'] == 'SUCCESS')
            fail = sum(1 for s in completed_scenarios if s['status'] == 'FAIL')
            incomplete = sum(1 for s in completed_scenarios if s['status'] == 'INCOMPLETE')
            results.append(f"\n[{name}]: 총 {len(completed_scenarios)}건 시도 -> 성공: {success}, 실패: {fail}, 미완료: {incomplete}")

        return "\n".join(results)