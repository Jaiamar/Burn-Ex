"""
Feature Extractor Module for Burn-Ex.
Aggregates rich biomechanical, kinetic, and temporal features over a workout set.
"""

import time
from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

from src.config import (
    DEFAULT_USER_WEIGHT_KG,
    MET_VALUES,
    EXERCISE_CONFIGS,
)


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """Calculate BMR using Mifflin-St Jeor equation."""
    if str(gender).lower() == "male":
        return 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age + 5.0
    else:
        return 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age - 161.0


class FeatureExtractor:
    """
    Tracks and aggregates temporal, kinematic, and power metrics across an active set.
    """

    def __init__(
        self,
        user_weight_kg: float = DEFAULT_USER_WEIGHT_KG,
        user_height_cm: float = 175.0,
        user_age: int = 25,
        user_gender: str = "male",
    ) -> None:
        self.user_weight_kg: float = float(user_weight_kg)
        self.user_height_cm: float = float(user_height_cm)
        self.user_age: int = int(user_age)
        self.user_gender: str = str(user_gender).lower()
        self.start_time: Optional[float] = None
        self.elapsed_time_sec: float = 0.0
        self.is_active: bool = False
        self.is_paused: bool = False
        self._last_tick_time: Optional[float] = None

    def set_user_weight(self, weight_kg: float) -> None:
        """Update user body weight (legacy/compatibility method)."""
        self.user_weight_kg = max(20.0, float(weight_kg))

    def set_user_profile(
        self, weight_kg: float, height_cm: float, age: int, gender: str
    ) -> None:
        """Update full athlete physical profile for customized BMR mapping."""
        self.user_weight_kg = max(20.0, float(weight_kg))
        self.user_height_cm = max(100.0, float(height_cm))
        self.user_age = max(1, int(age))
        self.user_gender = str(gender).lower()

    def start_set(self) -> None:
        """Start or restart set tracking timer."""
        self.start_time = time.time()
        self._last_tick_time = self.start_time
        self.elapsed_time_sec = 0.0
        self.is_active = True
        self.is_paused = False

    def pause_set(self) -> bool:
        """Toggle pause state. Returns True if now paused, False if active."""
        if not self.is_active:
            return False
        self.is_paused = not self.is_paused
        if not self.is_paused:
            self._last_tick_time = time.time()
        return self.is_paused

    def update_timer(self, target_lost: bool = False) -> float:
        """
        Increment elapsed active time, pausing if tracking target is lost or paused.
        """
        if not self.is_active:
            return self.elapsed_time_sec

        now = time.time()
        if self._last_tick_time is None:
            self._last_tick_time = now

        dt = now - self._last_tick_time
        self._last_tick_time = now

        if not target_lost and not self.is_paused:
            self.elapsed_time_sec += dt

        return self.elapsed_time_sec

    def stop_set(self) -> None:
        """Stop the active set."""
        self.is_active = False
        self.is_paused = False
        self._last_tick_time = None

    def reset(self) -> None:
        """Reset all timers and session metrics."""
        self.start_time = None
        self.elapsed_time_sec = 0.0
        self.is_active = False
        self.is_paused = False
        self._last_tick_time = None

    def extract_features(self, biomechanics_state: Dict[str, Any]) -> pd.DataFrame:
        """
        Extract rich biomechanical and physics feature dataframe for ML inference.
        """
        total_reps = int(biomechanics_state.get("total_reps", 0))
        valid_reps = int(biomechanics_state.get("valid_reps", 0))
        avg_rom = float(biomechanics_state.get("avg_rom", 0.0))
        exercise_type = str(biomechanics_state.get("exercise_type", "pushup")).lower()

        # Valid rep ratio
        if total_reps > 0:
            valid_rep_ratio = float(valid_reps / total_reps)
        else:
            valid_rep_ratio = 1.0 if biomechanics_state.get("is_form_valid", True) else 0.0

        # Duration in seconds (at least 0.1s)
        duration_sec = max(0.1, float(self.elapsed_time_sec))

        # Rep velocity: reps per minute
        rep_velocity = float(total_reps / (duration_sec / 60.0))

        # Kinematic features
        cfg = EXERCISE_CONFIGS.get(exercise_type)
        target_ideal_rom = cfg.target_ideal_rom if cfg else 110.0
        rom_completeness_ratio = float(np.clip(avg_rom / target_ideal_rom, 0.0, 1.5)) if avg_rom > 0 else 1.0

        peak_angular_velocity = float(biomechanics_state.get("peak_angular_velocity", 0.0))
        torso_inclination_angle = float(biomechanics_state.get("torso_inclination_angle", 0.0))
        rep_cadence_variance = float(biomechanics_state.get("rep_cadence_variance", 0.0))

        feature_dict: Dict[str, Any] = {
            "exercise_type": exercise_type,
            "user_weight_kg": self.user_weight_kg,
            "user_height_cm": self.user_height_cm,
            "user_age": self.user_age,
            "user_gender": self.user_gender,
            "duration_sec": duration_sec,
            "total_reps": total_reps,
            "valid_rep_ratio": valid_rep_ratio,
            "avg_rom_deg": avg_rom,
            "rep_velocity": rep_velocity,
            "peak_angular_velocity": peak_angular_velocity,
            "rom_completeness_ratio": rom_completeness_ratio,
            "torso_inclination_angle": torso_inclination_angle,
            "rep_cadence_variance": rep_cadence_variance,
        }

        return pd.DataFrame([feature_dict])

    def get_live_burn_rate_and_intensity(
        self, biomechanics_state: Dict[str, Any]
    ) -> Tuple[float, str]:
        """
        Calculate instantaneous calorie burn rate (kcal/min) and intensity tier.
        Uses Mifflin-St Jeor BMR personalization for high metabolic accuracy.
        """
        if not self.is_active or self.is_paused:
            return 0.0, "IDLE"

        duration_sec = max(1.0, float(self.elapsed_time_sec))
        total_reps = int(biomechanics_state.get("total_reps", 0))
        valid_reps = int(biomechanics_state.get("valid_reps", 0))
        exercise = str(biomechanics_state.get("exercise_type", "pushup")).lower()

        rep_rate = total_reps / (duration_sec / 60.0) if duration_sec > 3.0 else 15.0
        met = MET_VALUES.get(exercise, 8.0)

        # Baseline kcal/min using Mifflin-St Jeor BMR: (MET * (BMR / 24)) / 60
        bmr = calculate_bmr(self.user_weight_kg, self.user_height_cm, self.user_age, self.user_gender)
        base_kcal_min = (met * (bmr / 24.0)) / 60.0

        # Dynamic kinetic modifier based on cadence & ROM completeness
        cfg = EXERCISE_CONFIGS.get(exercise)
        target_rom = cfg.target_ideal_rom if cfg else 110.0
        avg_rom = float(biomechanics_state.get("avg_rom", target_rom))
        rom_ratio = np.clip(avg_rom / target_rom, 0.5, 1.3) if avg_rom > 0 else 1.0

        intensity_factor = 1.0 + 0.3 * np.clip((rep_rate - 20.0) / 20.0, -0.5, 1.0)
        valid_ratio = valid_reps / max(1, total_reps) if total_reps > 0 else 1.0
        form_factor = 0.85 + 0.15 * valid_ratio

        live_kcal_min = base_kcal_min * intensity_factor * rom_ratio * form_factor

        # Determine intensity tier
        if rep_rate < 12.0:
            intensity = "LOW"
        elif rep_rate <= 24.0:
            intensity = "MODERATE"
        else:
            intensity = "HIGH"

        return float(round(live_kcal_min, 2)), intensity

    def get_duration_sec(self) -> float:
        """Get current active elapsed duration in seconds."""
        return float(self.elapsed_time_sec)
