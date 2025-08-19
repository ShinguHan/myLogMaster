# shinguhan/mylogmaster/myLogMaster-main/models/LogTableModel.py

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from PySide6.QtGui import QColor # ✅ QColor 임포트

class LogTableModel(QAbstractTableModel):
    # ✅ 1. 생성자에 max_rows 파라미터 추가
    def __init__(self, data=None, max_rows=100000):
        super().__init__()
        self._data = data if data is not None else pd.DataFrame()
        self._highlighted_rows = set()
        self.max_rows = max_rows # 최대 행 수 저장
          # ✅ 1. 하이라이트 규칙을 저장할 변수 추가
        self._highlighting_rules = []

    def rowCount(self, parent=QModelIndex()):
        return self._data.shape[0]

    def columnCount(self, parent=QModelIndex()):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        
                # ✅ 2. 배경색과 글자색을 결정하는 로직 추가
        if role == Qt.ItemDataRole.BackgroundRole or role == Qt.ItemDataRole.ForegroundRole:
            row_data = self._data.iloc[index.row()]
            for rule in self._highlighting_rules:
                if rule.get("enabled", False) and self.check_rule(row_data, rule):
                    if role == Qt.ItemDataRole.BackgroundRole and rule.get("background"):
                        return QColor(rule["background"])
                    if role == Qt.ItemDataRole.ForegroundRole and rule.get("foreground"):
                        return QColor(rule["foreground"])
            return None # 규칙에 맞지 않으면 기본값 사용
        
        if role == Qt.ItemDataRole.DisplayRole:
            try:
                return str(self._data.iloc[index.row(), index.column()])
            except IndexError:
                return None
        elif role == Qt.ItemDataRole.BackgroundRole:
            if index.row() in self._highlighted_rows:
                from PySide6.QtGui import QColor
                return QColor(Qt.GlobalColor.yellow)
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])
            if orientation == Qt.Orientation.Vertical:
                return str(self._data.index[section])
        return None

    def update_data(self, data):
        """모델의 데이터를 새로운 데이터프레임으로 완전히 교체합니다."""
        self.beginResetModel()
        self._data = data.copy() if data is not None else pd.DataFrame()
        self.endResetModel()

    # ✅ 2. append_data 메소드에 오래된 데이터 삭제 로직 추가
    def append_data(self, df_chunk):
        """모델의 끝에 새로운 데이터 조각을 추가하고, 최대 행 수를 초과하면 오래된 데이터를 삭제합니다."""
        if df_chunk is None or df_chunk.empty:
            return
            
        start_row = self.rowCount()
        end_row = start_row + len(df_chunk) - 1

        self.beginInsertRows(QModelIndex(), start_row, end_row)
        self._data = pd.concat([self._data, df_chunk], ignore_index=True)
        self.endInsertRows()

        # 최대 행 수를 초과했는지 확인
        overflow = self.rowCount() - self.max_rows
        if overflow > 0:
            # 오래된 데이터를 삭제한다고 View에 알림
            self.beginRemoveRows(QModelIndex(), 0, overflow - 1)
            # 데이터프레임의 맨 위에서 overflow 개수만큼 행을 삭제
            self._data = self._data.iloc[overflow:].reset_index(drop=True)
            self.endRemoveRows()

    def get_data_by_col_name(self, row_index, col_name):
        if col_name in self._data.columns and 0 <= row_index < len(self._data):
            return self._data.at[row_index, col_name]
        return None

    def set_highlights(self, markers):
        self.beginResetModel()
        self._highlighted_rows.clear()
        for marker in markers:
            if 0 <= marker.row_index < len(self._data):
                 self._highlighted_rows.add(marker.row_index)
        self.endResetModel()

    def clear_highlights(self):
        if self._highlighted_rows:
            self.beginResetModel()
            self._highlighted_rows.clear()
            self.endResetModel()
    
     # ✅ 3. 규칙이 현재 행에 맞는지 확인하는 헬퍼 메소드
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

    # ✅ 4. 외부에서 규칙을 설정하고 테이블을 새로고침하는 메소드
    def set_highlighting_rules(self, rules):
        self.beginResetModel()
        self._highlighting_rules = [r for r in rules if r.get("enabled")]
        self.endResetModel()