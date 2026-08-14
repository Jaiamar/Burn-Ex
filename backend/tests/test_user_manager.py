"""
Unit tests for UserManager and SQLite workout session logging.
"""

import unittest
import tempfile
import json
from pathlib import Path

from src.user_manager import UserManager


class TestUserManager(unittest.TestCase):
    """Test user profile persistence and workout database operations."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profile_path = Path(self.temp_dir.name) / "test_user_profile.json"
        self.db_path = Path(self.temp_dir.name) / "test_workout_history.db"
        self.manager = UserManager(
            profile_path=self.profile_path,
            db_path=self.db_path,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_default_profile(self) -> None:
        profile = self.manager.get_profile()
        self.assertIn("name", profile)
        self.assertIn("weight_kg", profile)
        self.assertEqual(profile["weight_kg"], 70.0)

    def test_save_and_retrieve_profile(self) -> None:
        updated_data = {
            "name": "Sarah Connor",
            "weight_kg": 64.5,
            "height_cm": 168.0,
            "age": 29,
            "gender": "female",
            "fitness_goal": "hypertrophy",
        }
        saved = self.manager.save_profile(updated_data)
        self.assertEqual(saved["name"], "Sarah Connor")
        self.assertEqual(saved["weight_kg"], 64.5)

        retrieved = self.manager.get_profile()
        self.assertEqual(retrieved["name"], "Sarah Connor")
        self.assertEqual(retrieved["weight_kg"], 64.5)

    def test_record_and_query_sessions(self) -> None:
        # Record session 1
        session_id = self.manager.record_session(
            exercise_type="pushup",
            exercise_name="Push-up",
            duration_sec=45.0,
            total_reps=15,
            valid_reps=14,
            invalid_reps=1,
            valid_rep_ratio=0.933,
            avg_rom_deg=78.5,
            rep_velocity=20.0,
            form_score_pct=93.3,
            predicted_kcal=(3.85, 4.30, 4.75),
            rep_rom_history=[80.0, 78.0, 77.5],
        )
        self.assertIsInstance(session_id, int)
        self.assertGreater(session_id, 0)

        # Retrieve recent sessions
        sessions = self.manager.get_recent_sessions(limit=5)
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s["exercise_type"], "pushup")
        self.assertEqual(s["total_reps"], 15)
        self.assertEqual(s["valid_reps"], 14)
        self.assertEqual(s["kcal_point"], 4.30)
        self.assertEqual(s["rep_rom_data"], [80.0, 78.0, 77.5])

        # Check Aggregate Stats
        stats = self.manager.get_aggregate_stats()
        self.assertEqual(stats["total_workouts"], 1)
        self.assertEqual(stats["total_reps"], 15)
        self.assertEqual(stats["total_kcal_point"], 4.30)


if __name__ == "__main__":
    unittest.main()
