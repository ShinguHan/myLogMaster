# shinguhan/mylogmaster/myLogMaster-main/models/LogTableModel.py

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex

class LogTableModel(QAbstractTableModel):
    def __init__(self, data=None):
        super().__init__()
        self._data = data if data is not None else pd.DataFrame()
        self._highlighted_rows = set()

    def rowCount(self, parent=QModelIndex()):
        return self._data.shape[0]

    def columnCount(self, parent=QModelIndex()):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
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

    # ✅ 이 부분이 추가되어야 합니다.
    def append_data(self, df_chunk):
        """모델의 끝에 새로운 데이터프레임 조각을 추가합니다."""
        if df_chunk is None or df_chunk.empty:
            return
            
        start_row = self.rowCount()
        end_row = start_row + len(df_chunk) - 1

        self.beginInsertRows(QModelIndex(), start_row, end_row)
        
        self._data = pd.concat([self._data, df_chunk], ignore_index=True)
        
        self.endInsertRows()

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