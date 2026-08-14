"""
User Profile & Workout History Management for Burn-Ex.
Handles local athlete profile calibration (data/user_profile.json)
and SQLite workout session recording (data/workout_history.db).
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Generator

from src.config import DATA_DIR, DEFAULT_USER_WEIGHT_KG


USER_PROFILE_PATH: Path = DATA_DIR / "user_profile.json"
WORKOUT_DB_PATH: Path = DATA_DIR / "workout_history.db"


class UserManager:
    """
    Manages athlete profile persistence and historical workout database logging.
    """

    def __init__(
        self,
        profile_path: Path = USER_PROFILE_PATH,
        db_path: Path = WORKOUT_DB_PATH,
    ) -> None:
        self.profile_path = profile_path
        self.db_path = db_path
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager guaranteeing connection closure on all platforms."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize SQLite workout history schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workout_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    exercise_type TEXT NOT NULL,
                    exercise_name TEXT NOT NULL,
                    duration_sec REAL NOT NULL,
                    total_reps INTEGER NOT NULL,
                    valid_reps INTEGER NOT NULL,
                    invalid_reps INTEGER NOT NULL,
                    valid_rep_ratio REAL NOT NULL,
                    avg_rom_deg REAL NOT NULL,
                    rep_velocity REAL NOT NULL,
                    form_score_pct REAL NOT NULL,
                    kcal_lower REAL NOT NULL,
                    kcal_point REAL NOT NULL,
                    kcal_upper REAL NOT NULL,
                    rep_rom_data TEXT
                )
            """)

    def get_profile(self) -> Dict[str, Any]:
        """Load athlete profile from JSON or return calibrated defaults."""
        if self.profile_path.exists():
            try:
                with open(self.profile_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[Burn-Ex User] Warning: Could not read profile ({e}). Using defaults.")

        default_profile: Dict[str, Any] = {
            "name": "Alex Mercer",
            "weight_kg": DEFAULT_USER_WEIGHT_KG,
            "height_cm": 175.0,
            "age": 26,
            "gender": "male",
            "fitness_goal": "fat_loss",
            "updated_at": datetime.now().isoformat(),
        }
        self.save_profile(default_profile)
        return default_profile

    def save_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save athlete profile to JSON."""
        profile: Dict[str, Any] = {
            "name": str(profile_data.get("name", "Athlete")).strip() or "Athlete",
            "weight_kg": float(profile_data.get("weight_kg", DEFAULT_USER_WEIGHT_KG)),
            "height_cm": float(profile_data.get("height_cm", 175.0)),
            "age": int(profile_data.get("age", 25)),
            "gender": str(profile_data.get("gender", "male")),
            "fitness_goal": str(profile_data.get("fitness_goal", "fat_loss")),
            "updated_at": datetime.now().isoformat(),
        }
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
        return profile

    def record_session(
        self,
        exercise_type: str,
        exercise_name: str,
        duration_sec: float,
        total_reps: int,
        valid_reps: int,
        invalid_reps: int,
        valid_rep_ratio: float,
        avg_rom_deg: float,
        rep_velocity: float,
        form_score_pct: float,
        predicted_kcal: tuple,
        rep_rom_history: Optional[List[float]] = None,
    ) -> int:
        """
        Records a completed workout session in the SQLite database.
        Returns the inserted session ID.
        """
        lower_kcal, point_kcal, upper_kcal = predicted_kcal
        rom_json = json.dumps(rep_rom_history if rep_rom_history else [])
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO workout_sessions (
                    timestamp, exercise_type, exercise_name, duration_sec,
                    total_reps, valid_reps, invalid_reps, valid_rep_ratio,
                    avg_rom_deg, rep_velocity, form_score_pct,
                    kcal_lower, kcal_point, kcal_upper, rep_rom_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                timestamp, exercise_type, exercise_name, round(duration_sec, 2),
                total_reps, valid_reps, invalid_reps, round(valid_rep_ratio, 3),
                round(avg_rom_deg, 2), round(rep_velocity, 2), round(form_score_pct, 1),
                round(lower_kcal, 2), round(point_kcal, 2), round(upper_kcal, 2),
                rom_json
            ))
            return int(cursor.lastrowid)

    def get_recent_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve recent workout history records."""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM workout_sessions
                ORDER BY id DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            results = []
            for row in rows:
                item = dict(row)
                try:
                    item["rep_rom_data"] = json.loads(item.get("rep_rom_data", "[]"))
                except Exception:
                    item["rep_rom_data"] = []
                results.append(item)
            return results

    def get_aggregate_stats(self) -> Dict[str, Any]:
        """Compute all-time workout stats."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_workouts,
                    SUM(total_reps) as total_reps,
                    SUM(duration_sec) as total_duration_sec,
                    SUM(kcal_point) as total_kcal_point,
                    AVG(form_score_pct) as avg_form_score
                FROM workout_sessions
            """)
            row = cursor.fetchone()
            return {
                "total_workouts": row[0] or 0,
                "total_reps": row[1] or 0,
                "total_duration_sec": row[2] or 0.0,
                "total_kcal_point": round(row[3] or 0.0, 2),
                "avg_form_score": round(row[4] or 100.0, 1),
            }
