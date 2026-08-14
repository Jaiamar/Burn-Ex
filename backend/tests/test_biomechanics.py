"""
Unit tests for Burn-Ex Biomechanics, Debounced State Machine, EMA Smoother, and Physics-Informed ML Engine.
"""

import unittest
import numpy as np
import pandas as pd

from src.vision_pipeline import LandmarkSmoother
from src.biomechanics import (
    calculate_angle,
    calculate_angle_3d,
    calculate_torso_inclination,
    BiomechanicsEngine,
)
from src.feature_extractor import FeatureExtractor
from src.ml_engine import MLEngine
from src.config import FORM_MULTIPLIER_MIN, FORM_MULTIPLIER_MAX


class TestLandmarkSmoother(unittest.TestCase):
    """Test Exponential Moving Average (EMA) Coordinate Filter."""

    def test_ema_smoothing(self) -> None:
        smoother = LandmarkSmoother(alpha=0.35)
        raw1 = {"left_elbow": [1.0, 1.0, 0.0, 0.9]}
        res1 = smoother.smooth(raw1)
        self.assertEqual(res1["left_elbow"], [1.0, 1.0, 0.0, 0.9])

        # Step with noise: target is 2.0
        raw2 = {"left_elbow": [2.0, 2.0, 0.0, 0.9]}
        res2 = smoother.smooth(raw2)
        # Expected: 0.35 * 2.0 + 0.65 * 1.0 = 1.35
        self.assertAlmostEqual(res2["left_elbow"][0], 1.35, places=3)
        self.assertAlmostEqual(res2["left_elbow"][1], 1.35, places=3)


class Test3DAngleAndKinematics(unittest.TestCase):
    """Test 3D geometric angle and torso inclination math."""

    def test_3d_right_angle(self) -> None:
        a = [0.0, 1.0, 0.0]
        b = [0.0, 0.0, 0.0]
        c = [1.0, 0.0, 0.0]
        angle = calculate_angle_3d(a, b, c)
        self.assertAlmostEqual(angle, 90.0, places=2)

    def test_3d_straight_line(self) -> None:
        a = [0.0, 1.0, 0.0]
        b = [0.0, 0.0, 0.0]
        c = [0.0, -1.0, 0.0]
        angle = calculate_angle_3d(a, b, c)
        self.assertAlmostEqual(angle, 180.0, places=2)

    def test_torso_inclination(self) -> None:
        # Vertical standing posture (Hip at 0.5, 0.8; Shoulder at 0.5, 0.2)
        hip = [0.5, 0.8, 0.0]
        sh_upright = [0.5, 0.2, 0.0]
        inc_upright = calculate_torso_inclination(hip, sh_upright)
        self.assertAlmostEqual(inc_upright, 0.0, places=1)

        # Horizontal plank posture (Hip at 0.8, 0.5; Shoulder at 0.2, 0.5)
        sh_plank = [0.2, 0.8, 0.0]
        inc_plank = calculate_torso_inclination(hip, sh_plank)
        self.assertAlmostEqual(inc_plank, 90.0, places=1)


class TestDebouncedBiomechanicsEngine(unittest.TestCase):
    """Test state machine debounce buffer and hysteresis rep counting."""

    def _create_mock_landmarks(
        self,
        elbow_angle_deg: float = 170.0,
        spine_angle_deg: float = 170.0,
    ) -> dict:
        el = [0.5, 0.5, 0.0, 0.95]
        sh = [0.5, 0.2, 0.0, 0.95]
        elbow_rad = np.radians(180.0 - elbow_angle_deg)
        wr = [
            float(0.5 + 0.3 * np.sin(elbow_rad)),
            float(0.5 + 0.3 * np.cos(elbow_rad)),
            0.0,
            0.95,
        ]

        hip = [0.5, 0.5, 0.0, 0.95]
        spine_rad = np.radians(180.0 - spine_angle_deg)
        ank = [
            float(0.5 + 0.3 * np.sin(spine_rad)),
            float(0.5 + 0.3 * np.cos(spine_rad)),
            0.0,
            0.95,
        ]

        return {
            "left_shoulder": sh,
            "left_elbow": el,
            "left_wrist": wr,
            "right_shoulder": sh,
            "right_elbow": el,
            "right_wrist": wr,
            "left_hip": hip,
            "right_hip": hip,
            "left_knee": [0.5, 0.65, 0.0, 0.95],
            "right_knee": [0.5, 0.65, 0.0, 0.95],
            "left_ankle": ank,
            "right_ankle": ank,
        }

    def test_debounce_blocks_rapid_micro_pauses(self) -> None:
        """Micro-pauses / rapid angle flips (<300ms) must NOT increment reps."""
        engine = BiomechanicsEngine(exercise_type="pushup", min_hold_time_sec=0.30)
        t = 1000.0

        # Start UP at t = 1000.0
        lm_up = self._create_mock_landmarks(elbow_angle_deg=170.0)
        engine.update(lm_up, custom_time=t)
        self.assertEqual(engine.current_state, "UP")

        # 50 ms later: sudden angle dip to 70 deg (< 80 deg) -> Should be REJECTED by debounce!
        lm_down = self._create_mock_landmarks(elbow_angle_deg=70.0)
        engine.update(lm_down, custom_time=t + 0.05)
        self.assertEqual(engine.current_state, "UP")  # Still UP, blocked!

        # 350 ms later (hold time met): State transitions to DOWN
        engine.update(lm_down, custom_time=t + 0.35)
        self.assertEqual(engine.current_state, "DOWN")

        # 50 ms after DOWN: micro-bounce to 170 deg -> Should be REJECTED!
        engine.update(lm_up, custom_time=t + 0.40)
        self.assertEqual(engine.current_state, "DOWN")  # Still DOWN
        self.assertEqual(engine.total_reps, 0)

        # 350 ms after DOWN: return to UP -> Completes 1 valid rep
        engine.update(lm_up, custom_time=t + 0.75)
        self.assertEqual(engine.current_state, "UP")
        self.assertEqual(engine.valid_reps, 1)

    def test_hysteresis_boundaries(self) -> None:
        """Angles in buffer zone (85-155 deg) must NOT trigger premature state flip."""
        engine = BiomechanicsEngine(exercise_type="pushup", min_hold_time_sec=0.30)
        t = 1000.0

        lm_up = self._create_mock_landmarks(elbow_angle_deg=170.0)
        engine.update(lm_up, custom_time=t)

        # Angle drops to 85 deg (below 90, but NOT below strict 80 deg threshold)
        lm_buffer = self._create_mock_landmarks(elbow_angle_deg=85.0)
        engine.update(lm_buffer, custom_time=t + 0.5)
        self.assertEqual(engine.current_state, "UP")  # Must stay UP


class TestAdvancedFeatureExtractor(unittest.TestCase):
    """Test advanced kinematic and physics feature engineering."""

    def test_feature_schema(self) -> None:
        extractor = FeatureExtractor(user_weight_kg=75.0)
        extractor.start_set()
        extractor.elapsed_time_sec = 45.0

        mock_state = {
            "exercise_type": "pushup",
            "total_reps": 12,
            "valid_reps": 10,
            "avg_rom": 88.0,
            "peak_angular_velocity": 210.5,
            "torso_inclination_angle": 86.0,
            "rep_cadence_variance": 0.28,
            "is_form_valid": True,
        }

        df = extractor.extract_features(mock_state)
        self.assertEqual(df["peak_angular_velocity"].iloc[0], 210.5)
        self.assertAlmostEqual(df["rom_completeness_ratio"].iloc[0], 88.0 / 110.0, places=2)
        self.assertEqual(df["torso_inclination_angle"].iloc[0], 86.0)
        self.assertEqual(df["rep_cadence_variance"].iloc[0], 0.28)


class TestPhysicsResidualMLEngine(unittest.TestCase):
    """Test Physics-Informed Residual calorie model and bounds."""

    def test_bmr_calculation(self) -> None:
        from src.ml_engine import calculate_bmr
        # Male: 10 * 80 + 6.25 * 175 - 5 * 25 + 5 = 800 + 1093.75 - 125 + 5 = 1773.75
        bmr_male = calculate_bmr(80.0, 175.0, 25, "male")
        self.assertAlmostEqual(bmr_male, 1773.75, places=2)

        # Female: 10 * 60 + 6.25 * 160 - 5 * 30 - 161 = 600 + 1000 - 150 - 161 = 1289.0
        bmr_female = calculate_bmr(60.0, 160.0, 30, "female")
        self.assertAlmostEqual(bmr_female, 1289.0, places=2)

    def test_physics_residual_bounds(self) -> None:
        engine = MLEngine()

        # Weight: 80kg, Duration: 60s (1 min), Push-up MET = 8.0
        mock_features = pd.DataFrame([{
            "exercise_type": "pushup",
            "user_weight_kg": 80.0,
            "user_height_cm": 175.0,
            "user_age": 25,
            "user_gender": "male",
            "duration_sec": 60.0,
            "total_reps": 20,
            "valid_rep_ratio": 0.95,
            "avg_rom_deg": 95.0,
            "rep_velocity": 20.0,
            "peak_angular_velocity": 220.0,
            "rom_completeness_ratio": 0.95 / 1.1,
            "torso_inclination_angle": 85.0,
            "rep_cadence_variance": 0.15,
        }])

        lower, point, upper = engine.predict(mock_features)
        k_base = engine.calculate_k_base("pushup", 80.0, 60.0, 175.0, 25, "male")

        # Point estimate must be strictly within K_base * [0.60, 1.40]
        self.assertGreaterEqual(point, k_base * FORM_MULTIPLIER_MIN - 0.05)
        self.assertLessEqual(point, k_base * FORM_MULTIPLIER_MAX + 0.05)
        self.assertLessEqual(lower, point)
        self.assertLessEqual(point, upper)


if __name__ == "__main__":
    unittest.main()
