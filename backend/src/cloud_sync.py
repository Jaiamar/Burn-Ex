"""
Firebase Cloud Sync and Local Leaderboard Caching Engine.
Saves session metrics in background threads and handles offline fallbacks dynamically.
"""

import sqlite3
import threading
import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import cv2 # For general imports if needed elsewhere
import numpy as np

# Firebase SDK imports (handled inside try-block to avoid import crashes if not installed)
firebase_app = None
db_client = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    
    key_path = Path("firebase-key.json")
    if key_path.exists():
        cred = credentials.Certificate(str(key_path))
        firebase_app = firebase_admin.initialize_app(cred)
        db_client = firestore.client()
        print("[Firebase] Initialized Firestore successfully.")
    else:
        print("[Firebase] Warning: 'firebase-key.json' not found. Operating in local SQLite mode.")
except Exception as e:
    print(f"[Firebase] Error initializing Admin SDK: {e}. Falling back to SQLite.")

# Setup SQLite Database for local cache and offline caching
DB_PATH = Path("data/leaderboard.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_local_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            athlete_alias TEXT PRIMARY KEY,
            total_kcal_burned REAL,
            global_form_score_avg REAL,
            total_valid_reps INTEGER,
            last_workout_timestamp TEXT,
            sync_pending INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_local_db()

def _push_local_sqlite(athlete_alias: str, kcal_burned: float, form_score: float, valid_reps: int) -> Dict[str, Any]:
    """Write/Update the session data in the local SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT total_kcal_burned, global_form_score_avg, total_valid_reps FROM leaderboard WHERE athlete_alias = ?", (athlete_alias,))
    row = cursor.fetchone()
    
    now_str = datetime.datetime.utcnow().isoformat()
    
    if row:
        old_kcal, old_form_avg, old_reps = row
        new_reps = old_reps + valid_reps
        
        # Running average of form score
        if new_reps > 0:
            new_form_avg = ((old_form_avg * old_reps) + (form_score * valid_reps)) / new_reps
        else:
            new_form_avg = form_score
            
        new_kcal = old_kcal + kcal_burned
        
        cursor.execute("""
            UPDATE leaderboard
            SET total_kcal_burned = ?, global_form_score_avg = ?, total_valid_reps = ?, last_workout_timestamp = ?, sync_pending = 1
            WHERE athlete_alias = ?
        """, (new_kcal, new_form_avg, new_reps, now_str, athlete_alias))
    else:
        new_kcal = kcal_burned
        new_form_avg = form_score
        new_reps = valid_reps
        cursor.execute("""
            INSERT INTO leaderboard (athlete_alias, total_kcal_burned, global_form_score_avg, total_valid_reps, last_workout_timestamp, sync_pending)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (athlete_alias, new_kcal, new_form_avg, new_reps, now_str))
        
    conn.commit()
    conn.close()
    
    return {
        "athlete_alias": athlete_alias,
        "total_kcal_burned": new_kcal,
        "global_form_score_avg": new_form_avg,
        "total_valid_reps": new_reps,
        "last_workout_timestamp": now_str
    }

def _sync_to_firebase(doc_data: Dict[str, Any]) -> bool:
    """Helper to push a document to Firebase Firestore. Returns True if successful."""
    global db_client
    if db_client is None:
        return False
    try:
        alias = doc_data["athlete_alias"]
        firebase_data = {
            "athlete_alias": doc_data["athlete_alias"],
            "total_kcal_burned": doc_data["total_kcal_burned"],
            "global_form_score_avg": doc_data["global_form_score_avg"],
            "total_valid_reps": doc_data["total_valid_reps"],
            "last_workout_timestamp": doc_data["last_workout_timestamp"]
        }
        db_client.collection("leaderboard").document(alias).set(firebase_data)
        return True
    except Exception as e:
        print(f"[Firebase Sync] Error pushing doc to Firestore: {e}")
        return False

def _background_sync_worker(athlete_alias: str, kcal_burned: float, form_score: float, valid_reps: int):
    # 1. Update SQLite
    updated_doc = _push_local_sqlite(athlete_alias, kcal_burned, form_score, valid_reps)
    
    # 2. Attempt Sync
    success = _sync_to_firebase(updated_doc)
    if success:
        # Mark as synced in SQLite
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE leaderboard SET sync_pending = 0 WHERE athlete_alias = ?", (athlete_alias,))
        conn.commit()
        conn.close()
        
    # 3. Retry other pending records
    _retry_pending_syncs()

def _retry_pending_syncs():
    global db_client
    if db_client is None:
        return
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT athlete_alias, total_kcal_burned, global_form_score_avg, total_valid_reps, last_workout_timestamp FROM leaderboard WHERE sync_pending = 1")
        pending = cursor.fetchall()
        conn.close()
        
        for row in pending:
            alias, kcal, form, reps, ts = row
            doc_data = {
                "athlete_alias": alias,
                "total_kcal_burned": kcal,
                "global_form_score_avg": form,
                "total_valid_reps": reps,
                "last_workout_timestamp": ts
            }
            if _sync_to_firebase(doc_data):
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("UPDATE leaderboard SET sync_pending = 0 WHERE athlete_alias = ?", (alias,))
                conn.commit()
                conn.close()
    except Exception as e:
        print(f"[Firebase Sync] Error retrying pending syncs: {e}")

def push_session_data(athlete_alias: str, kcal_burned: float, form_score: float, valid_reps: int) -> None:
    """
    Asynchronously push completed workout session data to Firebase and local DB.
    Never blocks the caller.
    """
    t = threading.Thread(
        target=_background_sync_worker,
        args=(athlete_alias, kcal_burned, form_score, valid_reps),
        daemon=True
    )
    t.start()

def get_leaderboard_data() -> List[Dict[str, Any]]:
    """
    Retrieve the top 10 users ranked by total_kcal_burned
    with a tie-breaker on global_form_score_avg.
    """
    # 1. Try Firebase first
    global db_client
    if db_client is not None:
        try:
            docs = db_client.collection("leaderboard").order_by(
                "total_kcal_burned", direction=firestore.Query.DESCENDING
            ).order_by(
                "global_form_score_avg", direction=firestore.Query.DESCENDING
            ).limit(10).get()
            
            leaderboard = []
            for doc in docs:
                leaderboard.append(doc.to_dict())
            
            # Update local SQLite with this fresh leaderboard so offline view is up to date
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            for entry in leaderboard:
                cursor.execute("""
                    INSERT INTO leaderboard (athlete_alias, total_kcal_burned, global_form_score_avg, total_valid_reps, last_workout_timestamp, sync_pending)
                    VALUES (?, ?, ?, ?, ?, 0)
                    ON CONFLICT(athlete_alias) DO UPDATE SET
                        total_kcal_burned = excluded.total_kcal_burned,
                        global_form_score_avg = excluded.global_form_score_avg,
                        total_valid_reps = excluded.total_valid_reps,
                        last_workout_timestamp = excluded.last_workout_timestamp,
                        sync_pending = 0
                """, (
                    entry["athlete_alias"],
                    entry["total_kcal_burned"],
                    entry["global_form_score_avg"],
                    entry["total_valid_reps"],
                    entry["last_workout_timestamp"]
                ))
            conn.commit()
            conn.close()
            
            return leaderboard
        except Exception as e:
            print(f"[Firebase] Error fetching leaderboard, falling back to local SQLite: {e}")
            
    # 2. SQLite Fallback
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT athlete_alias, total_kcal_burned, global_form_score_avg, total_valid_reps, last_workout_timestamp
            FROM leaderboard
            ORDER BY total_kcal_burned DESC, global_form_score_avg DESC
            LIMIT 10
        """)
        rows = cursor.fetchall()
        conn.close()
        
        leaderboard = []
        for r in rows:
            leaderboard.append({
                "athlete_alias": r[0],
                "total_kcal_burned": r[1],
                "global_form_score_avg": r[2],
                "total_valid_reps": r[3],
                "last_workout_timestamp": r[4]
            })
        return leaderboard
    except Exception as e:
        print(f"[SQLite] Error fetching leaderboard: {e}")
        return []
