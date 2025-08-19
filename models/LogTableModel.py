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
        
        if role == Qt.ItemDataRole.BackgroundRole or role == Qt.ItemDataRole.ForegroundRole:
            try:
                row_data = self._data.iloc[index.row()]
                for rule in self._highlighting_rules:
                    if rule.get("enabled", False) and self.check_rule(row_data, rule):
                        if role == Qt.ItemDataRole.BackgroundRole and rule.get("background"):
                            # ✅ 2. QtGui.QColor() 형태로 사용하여 참조 오류를 해결합니다.
                            return QtGui.QColor(rule["background"])
                        if role == Qt.ItemDataRole.ForegroundRole and rule.get("foreground"):
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
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return str(self._data.columns[section])
        return None

    def check_rule(self, row_data, rule):
        col = rule.get("column")
        op = rule.get("operator")
        val = rule.get("value")
        if not all([col, op, val]) or col not in row_data:
            return False
        
        cell_value = str(row_data[col]).lower()
        check_value = val.lower()

        if op == "contains":
            return check_value in cell_value
        elif op == "equals":
            return check_value == cell_value
        elif op == "starts with":
            return cell_value.startswith(check_value)
        elif op == "ends with":
            return cell_value.endswith(check_value)
        return False

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
            return self._data.at[row_index, col_name]
        return None