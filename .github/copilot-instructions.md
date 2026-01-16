# myLogMaster - AI Coding Agent Guide

## Project Overview

**myLogMaster** is a specialized PySide6/Qt6 desktop application for analyzing complex process logs (CSV format), particularly SECS/GEM and MES communication logs. It provides parsing, filtering, scenario validation, and custom analysis capabilities.

**Key Architectural Pattern:** MVC with separation of concerns:
- **Models** (`models/LogTableModel.py`): Qt table model wrapping pandas DataFrames
- **Controllers** (`app_controller.py`): Core business logic, signals/slots coordination
- **Views** (`main_window.py`, `widgets/`, `dialogs/`): PySide6 UI components

## Critical Architecture Decisions

### 1. File-Mode Pipeline
- Application launches in **file mode** (`app_mode='file'`) via `ModeSelectionDialog`
- CSV files loaded and parsed through `universal_parser.parse_log_with_profile()`
- All operations work on in-memory pandas DataFrames—no database dependencies

**Why:** Simplified, fast, self-contained for log analysis without external DB requirements.

### 2. Signal-Based Threading for File Parsing
- Large CSV parsing runs in separate thread to keep UI responsive
- Signals emit (`data_fetched`, `finished`, `progress`, `error`)
- Main thread batches updates via `_update_queue` and `QTimer` (200ms intervals)
- Prevents Qt model thrashing during incremental loads

**Why:** Smooth UI responsiveness even on large files; users can filter/scroll while data loads.

### 3. Query Conditions as Unified Data Structure
All filtering logic flows through a single `query_conditions` dict:
```python
{
    "analysis_mode": "time_range",
    "time_from", "time_to",
    "filter_groups": {...},  # Nested AND/OR logic tree
    "script": "python code",
    "scenario_rules": [...]
}
```
Passed from `QueryBuilderDialog` → `AppController` → DataFrame filtering logic.

**Why:** Single source of truth prevents state sync bugs across filter/validation components.

### 4. Scenario-Based Validation Engine
Located in `analysis_result.py`: Scenarios (JSON files in `scenarios/`) define normal process flows with:
- `trigger_event`: Starting condition (e.g., S1F13 SECS message)
- `steps`: Sequential expected events with max_delay_seconds
- Validation produces detailed failure reports

Used via `analysis_result.run_validation()` after data is loaded.

## Data Flow Patterns

### Log Parsing Pipeline
1. **File Loading**: `universal_parser.parse_log_with_profile()` reads CSV with custom profile
2. **SECS-II Body Decoding**: `_parse_body_recursive()` converts binary SECS format to structured data
3. **DataFrame Creation**: Parsed logs wrapped in pandas DataFrame
4. **Model Binding**: DataFrame → `LogTableModel` → Qt TableView

### Filtering Chain
1. Query Builder creates condition tree
2. `EventMatcher.match(row, rule_group)` recursively evaluates AND/OR rules (Strategy pattern)
3. DataFrame filtered via pandas boolean indexing
4. Highlighting rules applied post-filter in model's `data()` method

## Key Files & Their Responsibilities

| File | Purpose |
|------|---------|
| `app_controller.py` | Central orchestrator: file loading, signal coordination, filter execution |
| `universal_parser.py` | SECS/GEM binary parsing, multi-line CSV handling, generator-based for memory efficiency |
| `models/LogTableModel.py` | Qt table model; applies highlighting rules via `check_rule()` method |
| `dialogs/QueryBuilderDialog.py` | Complex nested AND/OR condition builder with tree widget UI |
| `dialogs/ScriptEditorDialog.py` | Python script execution sandbox; APIs: `logs`, `result.add_marker()`, `result.show_dataframe()` |
| `analysis_result.py` | Scenario validation engine, result aggregation, marker tracking |
| `utils/event_matcher.py` | Reusable Strategy pattern for event matching; extensible operator dict |

## Common Workflows

### Adding a New Filter Operator
1. Add method to `EventMatcher._operators` dict (e.g., `"regex": self._regex`)
2. Define matching function: `def _regex(self, cell_value, check_value)`
3. UI updates automatically in `ConditionWidget.py` via operator dropdown

### Implementing a Custom Analysis Script
Scripts in `ScriptEditorDialog` receive:
- `logs`: filtered pandas DataFrame
- `result`: object with methods:
  - `result.add_marker(row_index, label, color)` - highlight row
  - `result.show_dataframe(df, title)` - display new data window
  - `result.set_summary(text)` - final report text

### Extending Scenario Validation
1. Add JSON file to `scenarios/` with structure: `{scenario_name: {trigger_event, steps, enabled}}`
2. Steps use `EventMatcher` operators (e.g., `{"column": "ParsedBody", "equals": "S1F14"}`
3. Validation runs in `analysis_result.py` via `run_validation(logs, selected_scenarios)`

## Configuration & Data Files

- `config.json`: UI state (window size, selected columns, theme)
- `filters.json`: Saved advanced query filters (user-created)
- `query_templates.json`: Reusable condition snippets
- `query_presets.json`: Quick-access filter presets
- `highlighters.json`: Highlighting rule definitions
- `themes/*.qss`: Qt stylesheets (dark, light, dracula, solarized)

## Common Pitfalls

1. **Thread Safety**: Don't modify `self.original_data` from parser thread—use signals only
2. **Model Updates**: Always call `self.source_model.layoutChanged.emit()` after DataFrame changes
3. **Query Conditions Structure**: Must match expected keys or filtering fails silently
4. **Scenario JSON Syntax**: "enabled" flag ignored; check logic in `analysis_result.py`
5. **CSV Header Detection**: Expects quoted column names; `universal_parser.py` line ~30 searches for ALL required headers in one line

## Testing & Debugging

- **verify_keyerror_fix.py**: Regression test suite
- **LogScripts/IDRead.py**: Utility for ID extraction
- Add print statements in file parsing logic to debug CSV header issues
- Use `pd.read_csv()` in isolation to test parser profiles before integration
