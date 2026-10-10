import logging
import sqlite3
import os
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class RunHistory:
    """Tracks pipeline executions."""

    def __init__(self, data_dir: str):
        self.db_path = os.path.join(data_dir, "run_history.sqlite")
        os.makedirs(data_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    start_time TEXT,
                    end_time TEXT,
                    status TEXT,
                    tasks_extracted INTEGER,
                    discrepancies_extracted INTEGER,
                    errors TEXT
                )
            ''')

    def start_run(self) -> str:
        run_id = datetime.now().strftime('run_%Y%m%d%H%M%S')
        start_time = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT INTO runs (run_id, start_time, status) VALUES (?, ?, ?)',
                (run_id, start_time, 'RUNNING')
            )
        return run_id

    def end_run(self, run_id: str, status: str, tasks: int = 0, disc: int = 0, errors: str = ""):
        end_time = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE runs 
                SET end_time = ?, status = ?, tasks_extracted = ?, discrepancies_extracted = ?, errors = ?
                WHERE run_id = ?
            ''', (end_time, status, tasks, disc, errors, run_id))

    def get_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('SELECT * FROM runs ORDER BY start_time DESC LIMIT ?', (limit,))
            return [dict(row) for row in cursor.fetchall()]
