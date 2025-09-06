import pandas as pd

class EventMatcher:
    """
    전략 패턴을 사용하여 이벤트 매칭 로직을 캡슐화하는 클래스.
    각 연산자는 별도의 '전략' 함수로 정의됩니다.
    """
    def __init__(self):
        # 각 연산자(전략)를 딕셔너리에 매핑합니다.
        # 새로운 연산자를 추가하려면 이 딕셔너리에 새 함수만 추가하면 됩니다.
        self._operators = {
            "contains": self._contains,
            "equals": self._equals,
            "starts with": self._starts_with,
            "ends with": self._ends_with,
        }

    def _contains(self, cell_value, check_value):
        return check_value in cell_value

    def _equals(self, cell_value, check_value):
        return check_value == cell_value

    def _starts_with(self, cell_value, check_value):
        return cell_value.startswith(check_value)

    def _ends_with(self, cell_value, check_value):
        return cell_value.endswith(check_value)

    def match(self, row, rule_group):
        """
        주어진 로그(row)가 규칙 그룹(rule_group)과 일치하는지 재귀적으로 확인합니다.
        """
        if not rule_group:
            return False

        # 복합 조건 그룹 처리
        if "logic" in rule_group:
            logic = rule_group.get("logic", "AND").upper()
            
            # 모든 하위 규칙에 대해 재귀적으로 match 함수 호출
            for sub_rule in rule_group.get("rules", []):
                result = self.match(row, sub_rule)
                
                if logic == "AND" and not result:
                    return False  # AND 그룹에서는 하나라도 False이면 즉시 False
                if logic == "OR" and result:
                    return True  # OR 그룹에서는 하나라도 True이면 즉시 True
            
            return True if logic == "AND" else False
        
        # 단일 조건 처리
        else:
            col, op, val = rule_group.get("column"), rule_group.get("operator"), rule_group.get("value")
            
            if not all([col, op, val is not None]) or col not in row.index or pd.isna(row[col]):
                return False
                
            cell_value = str(row[col]).lower()
            check_value = str(val).lower()
            
            # 딕셔너리에서 적절한 연산자(전략)를 찾아 실행
            if op in self._operators:
                return self._operators[op](cell_value, check_value)
            
            return False
