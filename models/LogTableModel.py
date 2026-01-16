import pandas as pd
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex

# ✅ 1. QColor를 더 안정적으로 참조하기 위해 QtGui 모듈 전체를 임포트합니다.
from PySide6 import QtGui


class LogTableModel(QAbstractTableModel):
    def __init__(self, data=None, max_rows=100000):
        super().__init__()
        self._data = data if data is not None else pd.DataFrame()
        self._highlighting_rules = []
        self.max_rows = max_rows

    def rowCount(self, parent=QModelIndex()):
        return self._data.shape[0]

    def columnCount(self, parent=QModelIndex()):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if (
            role == Qt.ItemDataRole.BackgroundRole
            or role == Qt.ItemDataRole.ForegroundRole
        ):
            try:
                row_data = self._data.iloc[index.row()]
                for rule in self._highlighting_rules:
                    if rule.get("enabled", False) and self.check_rule(row_data, rule):
                        if role == Qt.ItemDataRole.BackgroundRole and rule.get(
                            "background"
                        ):
                            # ✅ 2. QtGui.QColor() 형태로 사용하여 참조 오류를 해결합니다.
                            return QtGui.QColor(rule["background"])
                        if role == Qt.ItemDataRole.ForegroundRole and rule.get(
                            "foreground"
                        ):
                            return QtGui.QColor(rule["foreground"])
            except IndexError:
                # 데이터가 실시간으로 변경될 때 발생할 수 있는 인덱스 오류를 방지
                return None
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            try:
                return str(self._data.iloc[index.row(), index.column()])
            except IndexError:
                return None
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return str(self._data.columns[section])
        return None

    # shinguhan/mylogmaster/myLogMaster-main/models/LogTableModel.py

    def check_rule(self, row_data, rule):
        # ✅ 규칙에 포함된 모든 'conditions'를 순회
        for condition in rule.get("conditions", []):
            col = condition.get("column")
            op = condition.get("operator")
            val = condition.get("value")

            if not all([col, op, val]) or col not in row_data:
                return False  # 조건이 불완전하면 규칙 불일치

            cell_value = str(row_data[col]).lower()
            check_value = val.lower()

            match = False
            if op == "contains":
                match = check_value in cell_value
            elif op == "equals":
                match = check_value == cell_value
            elif op == "starts with":
                match = (
                    check_value == cell_value
                )  # This looks like a bug in original code, but I'll keep it for now or fix it?
                # Actually, original code was: match = cell_value.startswith(check_value)
                # Let me check Step 362 again.
                # 71:                 match = cell_value.startswith(check_value)
                # Ah, I see. I'll use the original code.

            # Wait, let me re-copy from Step 362 carefully.

    def check_rule(self, row_data, rule):
        # ✅ 규칙에 포함된 모든 'conditions'를 순회
        for condition in rule.get("conditions", []):
            col = condition.get("column")
            op = condition.get("operator")
            val = condition.get("value")

            if not all([col, op, val]) or col not in row_data:
                return False  # 조건이 불완전하면 규칙 불일치

            cell_value = str(row_data[col]).lower()
            check_value = val.lower()

            match = False
            if op == "contains":
                match = check_value in cell_value
            elif op == "equals":
                match = check_value == cell_value
            elif op == "starts with":
                match = cell_value.startswith(check_value)
            elif op == "ends with":
                match = cell_value.endswith(check_value)

            # ✅ AND 조건이므로, 하나라도 거짓이면 즉시 False 반환
            if not match:
                return False

        # 모든 조건을 통과했으면 True 반환
        return True

    def set_highlighting_rules(self, rules):
        self.beginResetModel()
        self._highlighting_rules = [r for r in rules if r.get("enabled")]
        self.endResetModel()

    def update_data(self, data):
        self.beginResetModel()
        self._data = data.copy() if data is not None else pd.DataFrame()
        self.endResetModel()

    def append_data(self, df_chunk):
        if df_chunk is None or df_chunk.empty:
            return

        start_row = self.rowCount()
        end_row = start_row + len(df_chunk) - 1

        self.beginInsertRows(QModelIndex(), start_row, end_row)
        self._data = pd.concat([self._data, df_chunk], ignore_index=True)
        self.endInsertRows()

        overflow = self.rowCount() - self.max_rows
        if overflow > 0:
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            self._data = self._data.iloc[overflow:].reset_index(drop=True)
            self.endRemoveRows()

    def get_data_by_col_name(self, row_index, col_name):
        if col_name in self._data.columns and 0 <= row_index < len(self._data):
            # ✅ iloc를 사용하여 위치 기반으로 접근합니다. (KeyError 방지)
            return self._data.iloc[row_index][col_name]
        return None

        # ✅ 아래 메소드를 새로 추가해주세요.

    def clear_highlights(self):
        """적용된 모든 하이라이트 규칙을 제거하고 뷰를 갱신합니다."""
        if not self._highlighting_rules:
            return  # 지울 하이라이트가 없으면 아무것도 하지 않음

        self.beginResetModel()
        self._highlighting_rules = []
        self.endResetModel()
