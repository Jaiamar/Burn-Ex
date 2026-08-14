"""
Biomechanics and Exercise State Machine for Burn-Ex.
Calculates 3D joint angles, maintains a debounced hysteresis state machine,
tracks torso inclination, and computes peak angular velocities.
"""

import time
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from src.config import EXERCISE_CONFIGS, ExerciseThresholds, MIN_STATE_HOLD_TIME_SEC


def calculate_angle(
    a: Tuple[float, float],
    b: Tuple[float, float],
    c: Tuple[float, float]
) -> float:
    """
    Calculate the 2D interior angle at joint 'b' given coordinates of points a, b, c.
    Uses np.arctan2 to guarantee accurate angles in degrees [0, 180].
    """
    a_arr = np.array(a[:2], dtype=np.float64)
    b_arr = np.array(b[:2], dtype=np.float64)
    c_arr = np.array(c[:2], dtype=np.float64)

    radians = np.arctan2(c_arr[1] - b_arr[1], c_arr[0] - b_arr[0]) - \
              np.arctan2(a_arr[1] - b_arr[1], a_arr[0] - b_arr[0])
    
    angle = np.abs(radians * 180.0 / np.pi)

    if angle > 180.0:
        angle = 360.0 - angle

    return float(angle)


def calculate_angle_3d(
    a: List[float],
    b: List[float],
    c: List[float]
) -> float:
    """
    Calculate 3D joint angle at vertex b using Euclidean dot product.
    Supports metric 3D world landmarks (x, y, z in meters).
    """
    v1 = np.array(a[:3], dtype=np.float64) - np.array(b[:3], dtype=np.float64)
    v2 = np.array(c[:3], dtype=np.float64) - np.array(b[:3], dtype=np.float64)

    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)

    if norm_v1 < 1e-6 or norm_v2 < 1e-6:
        return 180.0

    cosine = np.dot(v1, v2) / (norm_v1 * norm_v2)
    cosine = np.clip(cosine, -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine))
    return float(angle)


def calculate_torso_inclination(
    hip: List[float],
    shoulder: List[float]
) -> float:
    """
    Calculates angle of the torso (Hip -> Shoulder vector) relative to the vertical axis.
    0 deg = Perfectly vertical standing/upright posture.
    90 deg = Horizontal push-up plank posture.
    """
    dx = shoulder[0] - hip[0]
    dy = shoulder[1] - hip[1]  # In image coords, y increases downwards

    # Angle relative to vertical (dx=0, dy=-1)
    norm = np.hypot(dx, dy)
    if norm < 1e-6:
        return 0.0

    # Vertical vector pointing up is (0, -1)
    cos_theta = (-dy) / norm
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    angle = np.degrees(np.arccos(cos_theta))
    return float(angle)


class BiomechanicsEngine:
    """
    Analyzes biomechanical motion and maintains a debounced state machine.
    Prevents false repetitions via hysteresis angle buffers and minimum hold times.
    """

    def __init__(
        self,
        exercise_type: str = "pushup",
        min_hold_time_sec: float = MIN_STATE_HOLD_TIME_SEC,
    ) -> None:
        self.exercise_type: str = exercise_type.lower()
        if self.exercise_type not in EXERCISE_CONFIGS:
            self.exercise_type = "pushup"

        self.config: ExerciseThresholds = EXERCISE_CONFIGS[self.exercise_type]
        self.min_hold_time_sec: float = float(min_hold_time_sec)

        # State Machine Variables
        self.current_state: str = "UP" if self.exercise_type != "jumping_jack" else "DOWN"
        self.last_state_change_time: float = time.time()
        self.rep_start_time: float = time.time()

        self.valid_reps: int = 0
        self.invalid_reps: int = 0
        self.total_reps: int = 0

        # Motion & Kinematic Tracking
        self.current_angle: float = 180.0
        self.previous_angle: float = 180.0
        self.last_angle_time: float = time.time()

        self.min_rep_angle: float = 180.0
        self.max_rep_angle: float = 0.0
        self.rep_rom_history: List[float] = []
        self.rep_durations: List[float] = []

        # Advanced Biomechanical Metrics
        self.current_angular_velocity: float = 0.0
        self.peak_angular_velocity: float = 0.0
        self.rep_peak_angular_velocity: float = 0.0
        self.torso_inclination: float = 0.0

        # Form Validation
        self.is_form_valid: bool = True
        self.current_form_error: Optional[str] = None
        self.current_rep_had_form_error: bool = False
        self.target_lost: bool = False

        self.angles: Dict[str, float] = {}

    def reset(self) -> None:
        """Reset counters and state machines for a new workout set."""
        now = time.time()
        self.current_state = "UP" if self.exercise_type != "jumping_jack" else "DOWN"
        self.last_state_change_time = now
        self.rep_start_time = now

        self.valid_reps = 0
        self.invalid_reps = 0
        self.total_reps = 0

        self.current_angle = 180.0
        self.previous_angle = 180.0
        self.last_angle_time = now

        self.min_rep_angle = 180.0
        self.max_rep_angle = 0.0
        self.rep_rom_history.clear()
        self.rep_durations.clear()

        self.current_angular_velocity = 0.0
        self.peak_angular_velocity = 0.0
        self.rep_peak_angular_velocity = 0.0
        self.torso_inclination = 0.0

        self.is_form_valid = True
        self.current_form_error = None
        self.current_rep_had_form_error = False
        self.target_lost = False
        self.angles.clear()

    def update(
        self,
        landmarks: Optional[Dict[str, List[float]]],
        landmarks_3d: Optional[Dict[str, List[float]]] = None,
        custom_time: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Process current frame landmarks and advance state machine.
        """
        if landmarks is None:
            self.target_lost = True
            self.is_form_valid = False
            self.current_form_error = "MOVE INTO FRAME — full body not detected"
            return self._build_state_dict()

        # Check if critical landmarks are present and have sufficient visibility
        required_landmarks = ["left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"]
        missing_or_low_vis = False
        for lm_name in required_landmarks:
            if lm_name not in landmarks:
                missing_or_low_vis = True
                break
            # Visibility score is at index 3
            if len(landmarks[lm_name]) > 3 and landmarks[lm_name][3] < 0.45:
                missing_or_low_vis = True
                break

        if missing_or_low_vis:
            self.target_lost = False
            self.is_form_valid = False
            self.current_form_error = "MOVE INTO FRAME — make sure your full body is visible"
            return self._build_state_dict()

        self.target_lost = False
        now = custom_time if custom_time is not None else time.time()

        if self.last_state_change_time is None or self.last_state_change_time > now:
            self.last_state_change_time = now
            self.rep_start_time = now
            self.last_angle_time = now

        # Update angular velocity
        dt = max(0.001, now - self.last_angle_time)
        self.last_angle_time = now

        # Use 3D landmarks if available for superior depth accuracy
        calc_lms = landmarks_3d if landmarks_3d is not None else landmarks

        if self.exercise_type == "pushup":
            self._update_pushup(calc_lms, now, dt)
        elif self.exercise_type == "squat":
            self._update_squat(calc_lms, now, dt)
        elif self.exercise_type == "jumping_jack":
            self._update_jumping_jack(calc_lms, now, dt)

        return self._build_state_dict()

    def _get_best_side_points(
        self,
        landmarks: Dict[str, List[float]],
        joint_names: Tuple[str, str, str]
    ) -> Tuple[List[float], List[float], List[float], str]:
        """Selects left or right side based on higher landmark visibility."""
        prefix_left = [f"left_{name}" for name in joint_names]
        prefix_right = [f"right_{name}" for name in joint_names]

        left_vis = np.mean([landmarks[k][3] for k in prefix_left if k in landmarks])
        right_vis = np.mean([landmarks[k][3] for k in prefix_right if k in landmarks])

        side = "left" if left_vis >= right_vis else "right"
        active_keys = prefix_left if side == "left" else prefix_right

        p1 = landmarks[active_keys[0]]
        p2 = landmarks[active_keys[1]]
        p3 = landmarks[active_keys[2]]

        return p1, p2, p3, side

    def _track_angular_velocity(self, new_angle: float, dt: float) -> None:
        """Calculate and track instantaneous and peak angular velocity."""
        d_theta = abs(new_angle - self.previous_angle)
        self.previous_angle = new_angle
        ang_vel = d_theta / dt
        self.current_angular_velocity = float(ang_vel)
        self.rep_peak_angular_velocity = max(self.rep_peak_angular_velocity, ang_vel)
        self.peak_angular_velocity = max(self.peak_angular_velocity, ang_vel)

    def _update_pushup(
        self, landmarks: Dict[str, List[float]], now: float, dt: float
    ) -> None:
        """Push-up state machine with strict debounced hysteresis."""
        # 1. Elbow angle (Elbow vertex between Shoulder and Wrist)
        p_sh, p_el, p_wr, side = self._get_best_side_points(
            landmarks, ("shoulder", "elbow", "wrist")
        )
        elbow_angle = calculate_angle_3d(p_sh, p_el, p_wr) if len(p_sh) >= 3 else calculate_angle(p_sh, p_el, p_wr)
        self.current_angle = elbow_angle
        self.angles["elbow"] = elbow_angle
        self._track_angular_velocity(elbow_angle, dt)

        self.min_rep_angle = min(self.min_rep_angle, elbow_angle)
        self.max_rep_angle = max(self.max_rep_angle, elbow_angle)

        # 2. Form check: Spine alignment (Shoulder - Hip - Ankle)
        p_sh_spine, p_hip_spine, p_ank_spine, _ = self._get_best_side_points(
            landmarks, ("shoulder", "hip", "ankle")
        )
        spine_angle = calculate_angle_3d(p_sh_spine, p_hip_spine, p_ank_spine) if len(p_sh_spine) >= 3 else calculate_angle(p_sh_spine, p_hip_spine, p_ank_spine)
        self.angles["spine"] = spine_angle

        # Torso inclination
        self.torso_inclination = calculate_torso_inclination(p_hip_spine, p_sh_spine)

        spine_min = self.config.form_rules.get("spine_min_angle", 150.0)
        spine_max = self.config.form_rules.get("spine_max_angle", 180.0)

        if spine_angle < spine_min or spine_angle > spine_max + 15.0:
            self.is_form_valid = False
            self.current_form_error = "ADJUST FORM — maintain a more stable torso"
            self.current_rep_had_form_error = True
        elif self.current_state == "DOWN" and elbow_angle > 105.0:
            self.is_form_valid = False
            self.current_form_error = "ADJUST FORM — increase your range of motion"
        else:
            self.is_form_valid = True
            self.current_form_error = None

        # 3. Debounced Hysteresis State Machine
        up_thresh = self.config.up_angle_threshold      # > 160 deg
        down_thresh = self.config.down_angle_threshold  # < 80 deg (strict)
        time_in_state = now - self.last_state_change_time

        if self.current_state == "UP":
            # Strict DOWN condition with minimum hold time debounce
            if elbow_angle < down_thresh and time_in_state >= self.min_hold_time_sec:
                self.current_state = "DOWN"
                self.last_state_change_time = now
        elif self.current_state == "DOWN":
            # Strict UP return condition with minimum hold time debounce
            if elbow_angle > up_thresh and time_in_state >= self.min_hold_time_sec:
                rep_duration = now - self.rep_start_time
                self.rep_durations.append(max(0.3, rep_duration))
                self.rep_start_time = now

                rom = max(0.0, self.max_rep_angle - self.min_rep_angle)
                self.rep_rom_history.append(rom)

                if not self.current_rep_had_form_error and rom >= self.config.min_rom:
                    self.valid_reps += 1
                else:
                    self.invalid_reps += 1

                self.total_reps = self.valid_reps + self.invalid_reps
                self.current_state = "UP"
                self.last_state_change_time = now

                # Reset rep bounds & flags
                self.min_rep_angle = 180.0
                self.max_rep_angle = 0.0
                self.rep_peak_angular_velocity = 0.0
                self.current_rep_had_form_error = False

    def _update_squat(
        self, landmarks: Dict[str, List[float]], now: float, dt: float
    ) -> None:
        """Squat state machine with strict debounced hysteresis."""
        p_hip, p_knee, p_ank, side = self._get_best_side_points(
            landmarks, ("hip", "knee", "ankle")
        )
        knee_angle = calculate_angle_3d(p_hip, p_knee, p_ank) if len(p_hip) >= 3 else calculate_angle(p_hip, p_knee, p_ank)
        self.current_angle = knee_angle
        self.angles["knee"] = knee_angle
        self._track_angular_velocity(knee_angle, dt)

        self.min_rep_angle = min(self.min_rep_angle, knee_angle)
        self.max_rep_angle = max(self.max_rep_angle, knee_angle)

        # Torso inclination
        p_sh, p_hip_t, _, _ = self._get_best_side_points(landmarks, ("shoulder", "hip", "knee"))
        self.torso_inclination = calculate_torso_inclination(p_hip_t, p_sh)

        torso_min = self.config.form_rules.get("torso_min_angle", 70.0)
        # Check posture
        p_sh_t, p_hip_v, p_knee_v, _ = self._get_best_side_points(landmarks, ("shoulder", "hip", "knee"))
        torso_angle = calculate_angle_3d(p_sh_t, p_hip_v, p_knee_v) if len(p_sh_t) >= 3 else calculate_angle(p_sh_t, p_hip_v, p_knee_v)
        self.angles["torso"] = torso_angle

        # Check knee caving (knee valgus)
        knee_caving = False
        if "left_knee" in landmarks and "right_knee" in landmarks and "left_hip" in landmarks and "right_hip" in landmarks:
            knee_dist = abs(landmarks["left_knee"][0] - landmarks["right_knee"][0])
            hip_dist = abs(landmarks["left_hip"][0] - landmarks["right_hip"][0])
            if knee_dist < 0.8 * hip_dist:
                knee_caving = True

        if torso_angle < torso_min:
            self.is_form_valid = False
            self.current_form_error = "ADJUST FORM — maintain a more stable torso"
            self.current_rep_had_form_error = True
        elif knee_caving:
            self.is_form_valid = False
            self.current_form_error = "ADJUST FORM — adjust knee alignment"
            self.current_rep_had_form_error = True
        elif self.current_state == "DOWN" and knee_angle > 115.0:
            self.is_form_valid = False
            self.current_form_error = "ADJUST FORM — increase your range of motion"
        else:
            self.is_form_valid = True
            self.current_form_error = None

        # Debounced Hysteresis
        up_thresh = self.config.up_angle_threshold      # > 165 deg
        down_thresh = self.config.down_angle_threshold  # < 90 deg
        time_in_state = now - self.last_state_change_time

        if self.current_state == "UP":
            if knee_angle < down_thresh and time_in_state >= self.min_hold_time_sec:
                self.current_state = "DOWN"
                self.last_state_change_time = now
        elif self.current_state == "DOWN":
            if knee_angle > up_thresh and time_in_state >= self.min_hold_time_sec:
                rep_duration = now - self.rep_start_time
                self.rep_durations.append(max(0.3, rep_duration))
                self.rep_start_time = now

                rom = max(0.0, self.max_rep_angle - self.min_rep_angle)
                self.rep_rom_history.append(rom)

                if not self.current_rep_had_form_error and rom >= self.config.min_rom:
                    self.valid_reps += 1
                else:
                    self.invalid_reps += 1

                self.total_reps = self.valid_reps + self.invalid_reps
                self.current_state = "UP"
                self.last_state_change_time = now

                self.min_rep_angle = 180.0
                self.max_rep_angle = 0.0
                self.rep_peak_angular_velocity = 0.0
                self.current_rep_had_form_error = False

    def _update_jumping_jack(
        self, landmarks: Dict[str, List[float]], now: float, dt: float
    ) -> None:
        """Jumping Jack state machine with bilateral arm tracking & debounce."""
        left_arm = calculate_angle(
            (landmarks["left_hip"][0], landmarks["left_hip"][1]),
            (landmarks["left_shoulder"][0], landmarks["left_shoulder"][1]),
            (landmarks["left_wrist"][0], landmarks["left_wrist"][1]),
        )
        right_arm = calculate_angle(
            (landmarks["right_hip"][0], landmarks["right_hip"][1]),
            (landmarks["right_shoulder"][0], landmarks["right_shoulder"][1]),
            (landmarks["right_wrist"][0], landmarks["right_wrist"][1]),
        )

        avg_arm_angle = (left_arm + right_arm) / 2.0
        self.current_angle = avg_arm_angle
        self.angles["shoulder"] = avg_arm_angle
        self._track_angular_velocity(avg_arm_angle, dt)

        self.min_rep_angle = min(self.min_rep_angle, avg_arm_angle)
        self.max_rep_angle = max(self.max_rep_angle, avg_arm_angle)

        # Symmetry check
        arm_diff = abs(left_arm - right_arm)
        sync_thresh = self.config.form_rules.get("arm_sync_threshold", 30.0)
        if arm_diff > sync_thresh:
            self.is_form_valid = False
            self.current_form_error = "ADJUST FORM — adjust arm alignment"
            self.current_rep_had_form_error = True
        else:
            self.is_form_valid = True
            self.current_form_error = None

        up_thresh = self.config.up_angle_threshold      # > 145 deg (overhead)
        down_thresh = self.config.down_angle_threshold  # < 40 deg (at side)
        time_in_state = now - self.last_state_change_time

        if self.current_state == "DOWN":
            if avg_arm_angle > up_thresh and time_in_state >= self.min_hold_time_sec:
                self.current_state = "UP"
                self.last_state_change_time = now
        elif self.current_state == "UP":
            if avg_arm_angle < down_thresh and time_in_state >= self.min_hold_time_sec:
                rep_duration = now - self.rep_start_time
                self.rep_durations.append(max(0.3, rep_duration))
                self.rep_start_time = now

                rom = max(0.0, self.max_rep_angle - self.min_rep_angle)
                self.rep_rom_history.append(rom)

                if not self.current_rep_had_form_error and rom >= self.config.min_rom:
                    self.valid_reps += 1
                else:
                    self.invalid_reps += 1

                self.total_reps = self.valid_reps + self.invalid_reps
                self.current_state = "DOWN"
                self.last_state_change_time = now

                self.min_rep_angle = 180.0
                self.max_rep_angle = 0.0
                self.rep_peak_angular_velocity = 0.0
                self.current_rep_had_form_error = False

    def get_form_score_percentage(self) -> float:
        """Calculate percentage of valid reps / total reps."""
        if self.total_reps == 0:
            return 100.0 if self.is_form_valid else 0.0
        return float((self.valid_reps / self.total_reps) * 100.0)

    def get_average_rom(self) -> float:
        """Calculate average ROM from completed reps."""
        if not self.rep_rom_history:
            return 0.0
        return float(np.mean(self.rep_rom_history))

    def get_rep_cadence_variance(self) -> float:
        """Compute standard deviation of repetition durations (seconds)."""
        if len(self.rep_durations) < 2:
            return 0.0
        return float(np.std(self.rep_durations))

    def _build_state_dict(self) -> Dict[str, Any]:
        """Construct comprehensive state summary dictionary."""
        return {
            "exercise_type": self.exercise_type,
            "exercise_name": self.config.name,
            "current_state": self.current_state,
            "valid_reps": self.valid_reps,
            "invalid_reps": self.invalid_reps,
            "total_reps": self.total_reps,
            "current_angle": self.current_angle,
            "is_form_valid": self.is_form_valid,
            "form_error": self.current_form_error,
            "form_score_pct": self.get_form_score_percentage(),
            "avg_rom": self.get_average_rom(),
            "rep_rom_history": list(self.rep_rom_history),
            "target_lost": self.target_lost,
            "angles": self.angles,
            "current_angular_velocity": round(self.current_angular_velocity, 1),
            "peak_angular_velocity": round(self.peak_angular_velocity, 1),
            "torso_inclination_angle": round(self.torso_inclination, 1),
            "rep_cadence_variance": round(self.get_rep_cadence_variance(), 3),
        }
