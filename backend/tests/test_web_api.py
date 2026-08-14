"""
Unit tests for FastAPI Web API endpoints.
"""

import unittest
from fastapi.testclient import TestClient
from api import app


class TestWebAPI(unittest.TestCase):
    """Test FastAPI Web API routes and controllers."""

    def setUp(self) -> None:
        self.client = TestClient(app)
        self.headers = {"Authorization": "Bearer mock-user-token-testuser"}

    def test_index_route(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"online", response.content)

    def test_profile_api(self) -> None:
        # GET Profile
        res = self.client.get("/api/profile", headers=self.headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["status"], "success")

        # POST Profile
        payload = {
            "name": "Marcus Kane",
            "weight_kg": 82.0,
            "height_cm": 182.0,
            "age": 30,
            "gender": "male",
            "fitness_goal": "hypertrophy",
        }
        res_post = self.client.post(
            "/api/profile",
            json=payload,
            headers=self.headers
        )
        self.assertEqual(res_post.status_code, 200)
        post_data = res_post.json()
        self.assertEqual(post_data["profile"]["name"], "Marcus Kane")
        self.assertEqual(post_data["profile"]["weight_kg"], 82.0)

    def test_telemetry_api(self) -> None:
        res = self.client.get("/api/telemetry")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("exercise_type", data)
        self.assertIn("total_reps", data)
        self.assertIn("form_score_pct", data)
        self.assertIn("burn_rate_kcal_min", data)

    def test_workout_lifecycle(self) -> None:
        # Start workout
        res_start = self.client.post(
            "/api/workout/start",
            json={"exercise": "squat"},
            headers=self.headers
        )
        self.assertEqual(res_start.status_code, 200)
        start_data = res_start.json()
        self.assertEqual(start_data["exercise"], "squat")

        # Toggle pause
        res_pause = self.client.post("/api/workout/pause", headers=self.headers)
        self.assertEqual(res_pause.status_code, 200)
        pause_data = res_pause.json()
        self.assertIn("is_paused", pause_data)

        # Reset workout
        res_reset = self.client.post("/api/workout/reset", headers=self.headers)
        self.assertEqual(res_reset.status_code, 200)
        reset_data = res_reset.json()
        self.assertEqual(reset_data["status"], "success")

        # End workout
        res_end = self.client.post("/api/workout/end", headers=self.headers)
        self.assertEqual(res_end.status_code, 200)
        end_data = res_end.json()
        self.assertEqual(end_data["status"], "success")
        self.assertIn("summary", end_data)
        self.assertIn("kcal_point", end_data["summary"])

    def test_history_and_export_api(self) -> None:
        # History API
        res_hist = self.client.get("/api/history", headers=self.headers)
        self.assertEqual(res_hist.status_code, 200)
        hist_data = res_hist.json()
        self.assertIn("sessions", hist_data)
        self.assertIn("stats", hist_data)

        # Export JSON
        res_json = self.client.get("/api/export?format=json", headers=self.headers)
        self.assertEqual(res_json.status_code, 200)

        # Export CSV
        res_csv = self.client.get("/api/export?format=csv", headers=self.headers)
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("text/csv", res_csv.headers["content-type"])


if __name__ == "__main__":
    unittest.main()
