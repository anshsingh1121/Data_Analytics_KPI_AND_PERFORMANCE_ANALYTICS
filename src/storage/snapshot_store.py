import logging
import os
import sqlite3
import pandas as pd
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

class SnapshotStore:
    """Stores and retrieves data snapshots."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.index_db = os.path.join(data_dir, "snapshot_index.sqlite")
        os.makedirs(data_dir, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.index_db) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS snapshots (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    datatype TEXT,
                    filename TEXT,
                    record_count INTEGER,
                    is_demo INTEGER
                )
            ''')

    def save_snapshot(self, df: pd.DataFrame, datatype: str, is_demo: bool = False) -> str:
        """Saves a dataframe to a snapshot."""
        timestamp = datetime.now().isoformat()
        snap_id = f"{datatype}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Deduplicate columns if any duplicate exists to prevent PyArrow ValueError
        if df.columns.duplicated().any():
            dup_cols = list(df.columns[df.columns.duplicated()])
            logger.warning(f"Duplicate columns detected in {datatype} snapshot: {dup_cols}. Deduplicating...")
            df = df.loc[:, ~df.columns.duplicated()].copy()

        filename = f"{snap_id}.parquet"
        filepath = os.path.join(self.data_dir, filename)
        
        try:
            df.to_parquet(filepath, index=False)
        except Exception as e:
            logger.warning(f"Parquet save failed for {snap_id} ({e}), falling back to CSV format...")
            filename = f"{snap_id}.csv"
            filepath = os.path.join(self.data_dir, filename)
            df.to_csv(filepath, index=False)
        
        with sqlite3.connect(self.index_db) as conn:
            conn.execute(
                'INSERT INTO snapshots (id, timestamp, datatype, filename, record_count, is_demo) VALUES (?, ?, ?, ?, ?, ?)',
                (snap_id, timestamp, datatype, filename, len(df), int(is_demo))
            )
            
        logger.info(f"Saved snapshot {snap_id} with {len(df)} records.")
        return snap_id

    def load_snapshot(self, snap_id: str) -> Optional[pd.DataFrame]:
        """Loads a snapshot by ID."""
        with sqlite3.connect(self.index_db) as conn:
            cursor = conn.execute('SELECT filename FROM snapshots WHERE id = ?', (snap_id,))
            row = cursor.fetchone()
            
        if row:
            filepath = os.path.join(self.data_dir, row[0])
            if os.path.exists(filepath):
                if row[0].endswith('.parquet'):
                    return pd.read_parquet(filepath)
                else:
                    return pd.read_csv(filepath)
                
        logger.warning(f"Snapshot {snap_id} not found.")
        return None

    def list_snapshots(self, datatype: Optional[str] = None) -> List[Dict]:
        """Lists available snapshots."""
        query = 'SELECT * FROM snapshots'
        params = []
        if datatype:
            query += ' WHERE datatype = ?'
            params.append(datatype)
            
        with sqlite3.connect(self.index_db) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
