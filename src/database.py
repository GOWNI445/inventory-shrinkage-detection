"""SQLite persistence helper for generated CSV datasets."""
from pathlib import Path
import sqlite3
import pandas as pd

def load_csv_folder_to_sqlite(folder: str|Path, db_path: str|Path="data/inventory.db"):
    folder=Path(folder); db_path=Path(db_path)
    db_path.parent.mkdir(parents=True,exist_ok=True)
    tables=["stores","skus","employee_roles","shifts","opening_balances",
            "promotions","inventory_movements","cycle_counts","returns"]
    with sqlite3.connect(db_path) as conn:
        for name in tables:
            path=folder/f"{name}.csv"
            if path.exists():
                pd.read_csv(path).to_sql(name,conn,if_exists="replace",index=False,chunksize=50000)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mov_store_sku ON inventory_movements(store_id,sku_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_count_store_sku ON cycle_counts(store_id,sku_id)")
    return str(db_path)

def append_investigation_event(db_path, alert_id, assigned_to, finding, disposition):
    """Persist investigation state and append an immutable event record."""
    from datetime import datetime, timezone
    db_path=Path(db_path)
    db_path.parent.mkdir(parents=True,exist_ok=True)
    now=datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS Investigation (
            investigation_id TEXT PRIMARY KEY, alert_id TEXT NOT NULL,
            assigned_to TEXT NOT NULL, lifecycle_state TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS InvestigationEvent (
            event_id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL,
            event_type TEXT NOT NULL, event_payload TEXT NOT NULL,
            event_timestamp TEXT NOT NULL,
            FOREIGN KEY(investigation_id) REFERENCES Investigation(investigation_id))''')
        row=conn.execute("SELECT investigation_id FROM Investigation WHERE alert_id=? ORDER BY created_at LIMIT 1",(alert_id,)).fetchone()
        if row:
            investigation_id=row[0]
            conn.execute("UPDATE Investigation SET assigned_to=?, lifecycle_state=?, updated_at=? WHERE investigation_id=?",
                         (assigned_to, disposition, now, investigation_id))
        else:
            n=conn.execute("SELECT COUNT(*) FROM Investigation").fetchone()[0]+1
            investigation_id=f"INV-2026-{n:06d}"
            conn.execute("INSERT INTO Investigation VALUES (?,?,?,?,?,?)",
                         (investigation_id,alert_id,assigned_to,disposition,now,now))
        n_event=conn.execute("SELECT COUNT(*) FROM InvestigationEvent").fetchone()[0]+1
        event_id=f"IEV-2026-{n_event:08d}"
        payload=pd.Series({"assigned_to":assigned_to,"finding":finding,"disposition":disposition}).to_json()
        conn.execute("INSERT INTO InvestigationEvent VALUES (?,?,?,?,?)",
                     (event_id,investigation_id,"INVESTIGATION_UPDATED",payload,now))
    return {"investigation_id":investigation_id,"event_id":event_id,"event_timestamp":now}
