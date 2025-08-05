import sqlite3
from datetime import datetime

DB_FILE = "test_history.db"

def initialize_database():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            scenario_name TEXT NOT NULL,
            result TEXT NOT NULL,
            duration TEXT,
            details TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_test_result(report):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO results (timestamp, scenario_name, result, duration, details)
        VALUES (?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        report.get('name', 'N/A'),
        report.get('result', 'Unknown'),
        report.get('duration', 'N/A'),
        "\n".join(report.get('steps', []))
    ))
    conn.commit()
    conn.close()

def get_all_results():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, scenario_name, result, duration FROM results ORDER BY id DESC")
    results = cursor.fetchall()
    conn.close()
    return results

def get_pass_fail_ratio():
    """Gets the count of Pass vs. Fail results."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT result, COUNT(*) FROM results GROUP BY result")
    results = cursor.fetchall()
    conn.close()
    return results

def get_daily_run_counts():
    """Gets the number of test runs per day."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # The SUBSTR function extracts the YYYY-MM-DD part of the timestamp
    cursor.execute("SELECT SUBSTR(timestamp, 1, 10), COUNT(*) FROM results GROUP BY SUBSTR(timestamp, 1, 10) ORDER BY SUBSTR(timestamp, 1, 10)")
    results = cursor.fetchall()
    conn.close()
    return results
