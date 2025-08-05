import sqlite3
from datetime import datetime

DB_FILE = "test_history.db"

def initialize_database():
    """Creates the results table if it doesn't exist."""
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
    """Saves a report dictionary to the database."""
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
    """Retrieves all results from the database, newest first."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, scenario_name, result, duration FROM results ORDER BY id DESC")
    results = cursor.fetchall()
    conn.close()
    return results
