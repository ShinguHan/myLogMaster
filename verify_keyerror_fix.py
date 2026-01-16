import pandas as pd
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex


# Mocking the model for testing
class MockLogTableModel:
    def __init__(self, data):
        self._data = data

    def get_data_by_col_name(self, row_index, col_name):
        if col_name in self._data.columns and 0 <= row_index < len(self._data):
            # The fix: using iloc for position-based access
            return self._data.iloc[row_index][col_name]
        return None


# Test data with non-continuous index (simulating filtered DataFrame)
data = [
    {"TrackingID": "ID1", "Val": "A"},
    {"TrackingID": "ID2", "Val": "B"},
    {"TrackingID": "ID3", "Val": "C"},
]
df = pd.DataFrame(data)
# Filter to simulate a view where index labels are not 0, 1, 2...
filtered_df = df[df["TrackingID"] != "ID2"].copy()
# filtered_df index is [0, 2]

model = MockLogTableModel(filtered_df)

# Test 1: Access row 0 (ID1)
# Position 0 is label 0
val1 = model.get_data_by_col_name(0, "TrackingID")
assert val1 == "ID1"
print("Test 1 Passed: Accessing position 0 returns ID1")

# Test 2: Access row 1 (ID3)
# Position 1 is label 2
# If using .at[1, 'TrackingID'], it would raise KeyError because label 1 doesn't exist.
# If using .iloc[1]['TrackingID'], it returns ID3.
val2 = model.get_data_by_col_name(1, "TrackingID")
assert val2 == "ID3"
print("Test 2 Passed: Accessing position 1 returns ID3 (Fixes KeyError)")

print("Verification Successful!")
