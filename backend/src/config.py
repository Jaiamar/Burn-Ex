"""
Configuration and constants for Burn-Ex.
Includes physics parameters, hysteresis thresholds, EMA smoothing rates, and MET baselines.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Tuple


# Base Project Paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = BASE_DIR / "data"
MODELS_DIR: Path = BASE_DIR / "models"
MODEL_PATH: Path = MODELS_DIR / "burn_ex_xgboost.pkl"
RAW_SESSIONS_CSV: Path = DATA_DIR / "raw_sessions.csv"
REFERENCE_BASELINES_CSV: Path = DATA_DIR / "reference_baselines.csv"
USER_PROFILE_PATH: Path = DATA_DIR / "user_profile.json"
WORKOUT_DB_PATH: Path = DATA_DIR / "workout_history.db"

# Make sure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Vision and Tracking Settings
CAMERA_INDEX: int = 1
TARGET_FPS: int = 30
FRAME_WIDTH: int = 1280
FRAME_HEIGHT: int = 720
MIN_DETECTION_CONFIDENCE: float = 0.5
MIN_TRACKING_CONFIDENCE: float = 0.5
MODEL_COMPLEXITY: int = 0

# Coordinate Smoothing & Debouncing
EMA_SMOOTHING_ALPHA: float = 0.35
MIN_STATE_HOLD_TIME_SEC: float = 0.30  # 300 ms debounce buffer

# Default User Metrics
DEFAULT_USER_WEIGHT_KG: float = 70.0

# MET (Metabolic Equivalent of Task) Standard Reference Baselines
MET_VALUES: Dict[str, float] = {
    "pushup": 8.0,
    "squat": 6.5,
    "jumping_jack": 8.0,
}

# Exercise Biomechanical Thresholds & Configurations
@dataclass
class ExerciseThresholds:
    name: str
    primary_joint: str
    up_angle_threshold: float
    down_angle_threshold: float
    min_rom: float
    target_ideal_rom: float
    form_rules: Dict[str, Any] = field(default_factory=dict)


EXERCISE_CONFIGS: Dict[str, ExerciseThresholds] = {
    "pushup": ExerciseThresholds(
        name="Push-up",
        primary_joint="elbow",
        up_angle_threshold=160.0,
        down_angle_threshold=80.0,    # Strict hysteresis buffer: < 80 deg
        min_rom=45.0,
        target_ideal_rom=110.0,       # Ideal full-depth ROM
        form_rules={
            "spine_min_angle": 150.0,
            "spine_max_angle": 180.0,
            "error_msg": "SAGGING HIPS DETECTED",
        },
    ),
    "squat": ExerciseThresholds(
        name="Squat",
        primary_joint="knee",
        up_angle_threshold=165.0,
        down_angle_threshold=90.0,    # Strict hysteresis: < 90 deg
        min_rom=50.0,
        target_ideal_rom=110.0,
        form_rules={
            "torso_min_angle": 70.0,
            "error_msg": "CHEST TOO LOW / SAGGING FORM",
        },
    ),
    "jumping_jack": ExerciseThresholds(
        name="Jumping Jack",
        primary_joint="shoulder",
        up_angle_threshold=145.0,
        down_angle_threshold=45.0,
        min_rom=60.0,
        target_ideal_rom=120.0,
        form_rules={
            "arm_sync_threshold": 30.0,
            "error_msg": "ASYMMETRIC ARM EXTENSION",
        },
    ),
}

# Physics-Informed Multiplier Bounds
FORM_MULTIPLIER_MIN: float = 0.60
FORM_MULTIPLIER_MAX: float = 1.40

# UI Styling and Palette (Dark Cyber-Aesthetic)
COLOR_BACKGROUND_DARK: Tuple[int, int, int] = (18, 18, 22)
COLOR_PANEL_BG: Tuple[int, int, int] = (28, 28, 36)
COLOR_ACCENT_CYAN: Tuple[int, int, int] = (255, 208, 0)
COLOR_SUCCESS_GREEN: Tuple[int, int, int] = (74, 222, 128)
COLOR_WARNING_YELLOW: Tuple[int, int, int] = (42, 193, 255)
COLOR_ERROR_RED: Tuple[int, int, int] = (68, 68, 239)
COLOR_TEXT_WHITE: Tuple[int, int, int] = (245, 245, 245)
COLOR_TEXT_MUTED: Tuple[int, int, int] = (160, 160, 175)
COLOR_JOINT_DEFAULT: Tuple[int, int, int] = (230, 180, 50)
COLOR_BONE_DEFAULT: Tuple[int, int, int] = (100, 200, 240)
