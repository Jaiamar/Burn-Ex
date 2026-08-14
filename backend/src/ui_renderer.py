"""
UI Renderer Module for Burn-Ex.
Renders real-time HUD, skeleton overlays, biomechanics metrics, calorie estimation,
and privacy badges with high visual fidelity.
"""

from typing import Dict, Any, Optional, Tuple, List
import cv2
import numpy as np

from src.config import (
    COLOR_BACKGROUND_DARK,
    COLOR_PANEL_BG,
    COLOR_ACCENT_CYAN,
    COLOR_SUCCESS_GREEN,
    COLOR_WARNING_YELLOW,
    COLOR_ERROR_RED,
    COLOR_TEXT_WHITE,
    COLOR_TEXT_MUTED,
    COLOR_JOINT_DEFAULT,
    COLOR_BONE_DEFAULT,
)


# Pose connectivity graph
SKELETON_CONNECTIONS = [
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"),
    ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"),
    ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
]


class UIRenderer:
    """
    Renders telemetry HUD, skeleton keypoints, and calorie metrics on the OpenCV frame.
    """

    def __init__(self) -> None:
        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def _draw_rounded_rect(
        self,
        img: np.ndarray,
        pt1: Tuple[int, int],
        pt2: Tuple[int, int],
        color: Tuple[int, int, int],
        radius: int = 12,
        alpha: float = 0.85,
    ) -> None:
        """Draws a sleek semi-transparent rounded rectangle overlay."""
        x1, y1 = pt1
        x2, y2 = pt2

        # Create overlay copy for alpha blending
        overlay = img.copy()

        # Draw main rectangle body
        cv2.rectangle(overlay, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(overlay, (x1, y1 + radius), (x2, y2 - radius), color, -1)

        # Draw 4 corner circles
        cv2.circle(overlay, (x1 + radius, y1 + radius), radius, color, -1)
        cv2.circle(overlay, (x2 - radius, y1 + radius), radius, color, -1)
        cv2.circle(overlay, (x1 + radius, y2 - radius), radius, color, -1)
        cv2.circle(overlay, (x2 - radius, y2 - radius), radius, color, -1)

        # Blend with original image
        cv2.addWeighted(overlay, alpha, img, 1.0 - alpha, 0, img)
        # Border stroke
        cv2.rectangle(img, (x1 + radius, y1), (x2 - radius, y1), COLOR_TEXT_MUTED, 1)
        cv2.rectangle(img, (x1 + radius, y2), (x2 - radius, y2), COLOR_TEXT_MUTED, 1)
        cv2.rectangle(img, (x1, y1 + radius), (x1, y2 - radius), COLOR_TEXT_MUTED, 1)
        cv2.rectangle(img, (x2, y1 + radius), (x2, y2 - radius), COLOR_TEXT_MUTED, 1)

    def draw_skeleton(
        self,
        frame: np.ndarray,
        landmarks: Optional[Dict[str, List[float]]],
        is_form_valid: bool = True,
        active_joint_name: str = "elbow"
    ) -> None:
        """
        Draws 33-point skeletal bones and nodes.
        Active joints are color-coded: Green (Valid form), Red (Flagged form).
        """
        if not landmarks:
            return

        h, w, _ = frame.shape

        # Draw bones
        for start_name, end_name in SKELETON_CONNECTIONS:
            if start_name in landmarks and end_name in landmarks:
                p1 = landmarks[start_name]
                p2 = landmarks[end_name]

                # Only draw if visibility is reasonable
                if p1[3] > 0.4 and p2[3] > 0.4:
                    pt1 = (int(p1[0] * w), int(p1[1] * h))
                    pt2 = (int(p2[0] * w), int(p2[1] * h))
                    cv2.line(frame, pt1, pt2, COLOR_BONE_DEFAULT, 2, cv2.LINE_AA)

        # Draw joint nodes
        for name, coords in landmarks.items():
            if coords[3] > 0.4:
                center = (int(coords[0] * w), int(coords[1] * h))
                
                # Check if this is an active or error-sensitive joint
                if active_joint_name in name or "spine" in name or "hip" in name:
                    node_color = COLOR_SUCCESS_GREEN if is_form_valid else COLOR_ERROR_RED
                    radius = 7
                else:
                    node_color = COLOR_JOINT_DEFAULT
                    radius = 4

                cv2.circle(frame, center, radius, node_color, -1, cv2.LINE_AA)
                cv2.circle(frame, center, radius + 1, (255, 255, 255), 1, cv2.LINE_AA)

    def render_hud(
        self,
        frame: np.ndarray,
        biomechanics_state: Dict[str, Any],
        duration_sec: float,
        predicted_kcal: Optional[Tuple[float, float, float]] = None,
        is_set_active: bool = True,
    ) -> np.ndarray:
        """
        Draws the complete Burn-Ex Heads-Up Display (HUD).
        """
        h, w, _ = frame.shape

        # 1. Top Privacy & Brand Header
        self._draw_rounded_rect(frame, (20, 15), (w - 20, 65), COLOR_PANEL_BG, radius=8, alpha=0.9)
        
        # Logo & App Title
        cv2.putText(frame, "BURN-EX", (35, 48), self.font, 0.85, COLOR_ACCENT_CYAN, 2, cv2.LINE_AA)
        cv2.putText(frame, "| AI ENERGY EXPENDITURE", (175, 48), self.font, 0.55, COLOR_TEXT_WHITE, 1, cv2.LINE_AA)

        # Privacy Badge
        privacy_text = "[LOCK] LOCAL PROCESSING - ZERO RAW VIDEO STORAGE"
        text_size = cv2.getTextSize(privacy_text, self.font, 0.45, 1)[0]
        cv2.putText(frame, privacy_text, (w - text_size[0] - 35, 48), self.font, 0.45, COLOR_SUCCESS_GREEN, 1, cv2.LINE_AA)

        # 2. Left Metrics HUD Card
        card_w = 320
        card_h = 360
        self._draw_rounded_rect(frame, (20, 80), (20 + card_w, 80 + card_h), COLOR_PANEL_BG, radius=10, alpha=0.88)

        # Exercise Badge
        ex_name = biomechanics_state.get("exercise_name", "Push-up").upper()
        cv2.putText(frame, f"EXERCISE: {ex_name}", (35, 115), self.font, 0.6, COLOR_ACCENT_CYAN, 2, cv2.LINE_AA)
        cv2.line(frame, (35, 125), (20 + card_w - 15, 125), (60, 60, 75), 1)

        # State & Repetitions
        state = biomechanics_state.get("current_state", "UP")
        state_color = COLOR_ACCENT_CYAN if state == "UP" else COLOR_WARNING_YELLOW
        cv2.putText(frame, "STAGE:", (35, 155), self.font, 0.5, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)
        cv2.putText(frame, state, (140, 155), self.font, 0.65, state_color, 2, cv2.LINE_AA)

        total_reps = biomechanics_state.get("total_reps", 0)
        valid_reps = biomechanics_state.get("valid_reps", 0)
        invalid_reps = biomechanics_state.get("invalid_reps", 0)

        cv2.putText(frame, "TOTAL REPS:", (35, 190), self.font, 0.5, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)
        cv2.putText(frame, str(total_reps), (160, 190), self.font, 0.7, COLOR_TEXT_WHITE, 2, cv2.LINE_AA)

        cv2.putText(frame, "VALID / INVALID:", (35, 220), self.font, 0.45, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)
        rep_ratio_text = f"{valid_reps} / {invalid_reps}"
        cv2.putText(frame, rep_ratio_text, (180, 220), self.font, 0.55, COLOR_SUCCESS_GREEN, 1, cv2.LINE_AA)

        # Form Quality & Angle
        form_pct = biomechanics_state.get("form_score_pct", 100.0)
        form_color = COLOR_SUCCESS_GREEN if form_pct >= 75.0 else (COLOR_WARNING_YELLOW if form_pct >= 50.0 else COLOR_ERROR_RED)
        cv2.putText(frame, "FORM SCORE:", (35, 255), self.font, 0.5, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)
        cv2.putText(frame, f"{form_pct:.1f}%", (160, 255), self.font, 0.6, form_color, 2, cv2.LINE_AA)

        current_angle = biomechanics_state.get("current_angle", 180.0)
        cv2.putText(frame, "JOINT ANGLE:", (35, 290), self.font, 0.5, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)
        cv2.putText(frame, f"{current_angle:.1f} deg", (160, 290), self.font, 0.55, COLOR_TEXT_WHITE, 1, cv2.LINE_AA)

        # Duration Timer
        mins = int(duration_sec // 60)
        secs = int(duration_sec % 60)
        cv2.putText(frame, "DURATION:", (35, 325), self.font, 0.5, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)
        cv2.putText(frame, f"{mins:02d}:{secs:02d}", (160, 325), self.font, 0.6, COLOR_TEXT_WHITE, 2, cv2.LINE_AA)

        # Avg ROM
        avg_rom = biomechanics_state.get("avg_rom", 0.0)
        cv2.putText(frame, "AVG ROM:", (35, 360), self.font, 0.5, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)
        cv2.putText(frame, f"{avg_rom:.1f} deg", (160, 360), self.font, 0.55, COLOR_TEXT_WHITE, 1, cv2.LINE_AA)

        # 3. Top-Right Calorie Panel
        cal_w = 340
        cal_h = 130
        cal_x = w - cal_w - 20
        self._draw_rounded_rect(frame, (cal_x, 80), (cal_x + cal_w, 80 + cal_h), COLOR_PANEL_BG, radius=10, alpha=0.88)
        
        cv2.putText(frame, "ENERGY EXPENDITURE", (cal_x + 15, 110), self.font, 0.55, COLOR_ACCENT_CYAN, 2, cv2.LINE_AA)
        cv2.line(frame, (cal_x + 15, 120), (cal_x + cal_w - 15, 120), (60, 60, 75), 1)

        if predicted_kcal is not None:
            lower, point, upper = predicted_kcal
            cal_str = f"{lower:.2f} - {upper:.2f} kcal"
            cv2.putText(frame, cal_str, (cal_x + 15, 160), self.font, 0.75, COLOR_SUCCESS_GREEN, 2, cv2.LINE_AA)
            cv2.putText(frame, f"Point Estimate: ~{point:.2f} kcal", (cal_x + 15, 190), self.font, 0.45, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)
        else:
            status_text = "CALCULATING ACTIVE SET..." if is_set_active else "PRESS [Q] TO INFER KCAL"
            cv2.putText(frame, status_text, (cal_x + 15, 165), self.font, 0.5, COLOR_WARNING_YELLOW, 1, cv2.LINE_AA)

        # 4. Form Error / Warning Card (Center Bottom if error exists)
        form_error = biomechanics_state.get("form_error")
        target_lost = biomechanics_state.get("target_lost", False)

        if target_lost:
            warn_w = 400
            warn_h = 50
            warn_x = (w - warn_w) // 2
            warn_y = h - 130
            self._draw_rounded_rect(frame, (warn_x, warn_y), (warn_x + warn_w, warn_y + warn_h), (20, 50, 100), radius=8, alpha=0.9)
            cv2.putText(frame, "[!] TARGET LOST - TRACKING PAUSED", (warn_x + 25, warn_y + 32), self.font, 0.55, COLOR_WARNING_YELLOW, 2, cv2.LINE_AA)
        elif form_error:
            warn_w = 440
            warn_h = 50
            warn_x = (w - warn_w) // 2
            warn_y = h - 130
            self._draw_rounded_rect(frame, (warn_x, warn_y), (warn_x + warn_w, warn_y + warn_h), (20, 20, 90), radius=8, alpha=0.9)
            cv2.putText(frame, f"[!] {form_error}", (warn_x + 25, warn_y + 32), self.font, 0.55, COLOR_ERROR_RED, 2, cv2.LINE_AA)

        # 5. Bottom Navigation & Hotkey Instructions
        self._draw_rounded_rect(frame, (20, h - 55), (w - 20, h - 15), COLOR_PANEL_BG, radius=8, alpha=0.9)
        controls_text = "[Q] Complete Set & Calculate Kcal  |  [R] Reset Counters  |  [ESC] Exit Program"
        cv2.putText(frame, controls_text, (35, h - 28), self.font, 0.48, COLOR_TEXT_MUTED, 1, cv2.LINE_AA)

        return frame
