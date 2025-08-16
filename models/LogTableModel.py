from PySide6.QtCore import QAbstractTableModel, Qt
from PySide6.QtGui import QColor # ⭐️ QColor 임포트
import pandas as pd

class LogTableModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        self._data = data if data is not None else pd.DataFrame()
        # ⭐️ 하이라이트 정보를 저장할 딕셔너리
        self.highlights = {} # {row_index: (message, color_str)}

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()

        # ⭐️ 1. 배경색 역할(BackgroundRole) 처리
        if role == Qt.ItemDataRole.BackgroundRole:
            if row in self.highlights:
                color_str = self.highlights[row][1]
                return QColor(color_str)
        
        # ⭐️ 2. 툴팁 역할(ToolTipRole) 처리 (마우스 호버 시 메시지 표시)
        if role == Qt.ItemDataRole.ToolTipRole:
            if row in self.highlights:
                message = self.highlights[row][0]
                return message

        if role == Qt.ItemDataRole.DisplayRole:
            try:
                value = self._data.iloc[row, index.column()]
                return str(value)
            except IndexError:
                return None
        return None

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return str(self._data.columns[section])
        return None

    def update_data(self, new_data):
        self.beginResetModel()
        if isinstance(new_data, list):
            self._data = pd.DataFrame(new_data)
        elif isinstance(new_data, pd.DataFrame):
             self._data = new_data
        else:
             self._data = pd.DataFrame()
        self.endResetModel()
    
    def get_data_by_col_name(self, row_index, column_name):
        if self._data.empty: return None
        try:
            col_index = self._data.columns.get_loc(column_name)
            return self._data.iloc[row_index, col_index]
        except (KeyError, IndexError):
            return None

    # ⭐️ 3. 하이라이트 정보를 설정하고 뷰를 갱신하는 메서드
    def set_highlights(self, markers):
        self.beginResetModel() # 데이터 변경 시작을 알림
        self.highlights.clear()
        for row_index, message, color in markers:
            # 원본 DataFrame의 인덱스를 사용하여 저장
            if row_index in self._data.index:
                # 실제 모델의 행 번호로 변환
                model_row = self._data.index.get_loc(row_index)
                self.highlights[model_row] = (message, color)
        self.endResetModel() # 데이터 변경 완료를 알림

    # ⭐️ 4. 하이라이트 정보를 초기화하는 메서드
    def clear_highlights(self):
        self.beginResetModel()
        self.highlights.clear()
        self.endResetModel()