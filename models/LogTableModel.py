from PySide6.QtCore import QAbstractTableModel, Qt
import pandas as pd

class LogTableModel(QAbstractTableModel):
    """
    Pandas DataFrame을 Qt TableView에 연결하기 위한 데이터 모델 클래스
    """
    def __init__(self, data=None):
        super().__init__()
        self._data = data if data is not None else pd.DataFrame()

    def rowCount(self, parent=None):
        return self._data.shape[0]

    def columnCount(self, parent=None):
        return self._data.shape[1]

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            try:
                value = self._data.iloc[index.row(), index.column()]
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
    
    # ⭐️ 이 함수가 누락되어 에러가 발생했습니다.
    def get_data_by_col_name(self, row_index, column_name):
        """행 인덱스와 컬럼 이름으로 특정 셀의 데이터를 가져옵니다."""
        if self._data.empty:
            return None
        try:
            # get_loc은 컬럼 이름으로 정수 인덱스를 찾아줍니다.
            col_index = self._data.columns.get_loc(column_name)
            return self._data.iloc[row_index, col_index]
        except (KeyError, IndexError):
            # 해당 컬럼이 없거나 행 인덱스가 범위를 벗어난 경우
            return None