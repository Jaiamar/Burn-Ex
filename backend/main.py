"""
Burn-Ex: Privacy-Preserving AI Energy Expenditure Tracker
Main Application Entry Point.
"""

import sys
import argparse
import time
from typing import Optional, Tuple
import cv2
import numpy as np

from src.config import (
    CAMERA_INDEX,
    DEFAULT_USER_WEIGHT_KG,
    EXERCISE_CONFIGS,
    FRAME_WIDTH,
    FRAME_HEIGHT,
)
from src.vision_pipeline import VisionPipeline
from src.biomechanics import BiomechanicsEngine
from src.feature_extractor import FeatureExtractor
from src.ml_engine import MLEngine
from src.ui_renderer import UIRenderer
from src.video_stream import VideoStream


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Burn-Ex: Privacy-Preserving AI Energy Expenditure Tracker"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="Launch the interactive Web Studio & Dashboard UI on http://127.0.0.1:5000",
    )
    parser.add_argument(
        "--exercise",
        type=str,
        default="pushup",
        choices=["pushup", "squat", "jumping_jack"],
        help="Exercise type to track in CLI mode (default: pushup)",
    )
    parser.add_argument(
        "--weight",
        type=float,
        default=DEFAULT_USER_WEIGHT_KG,
        help=f"User body weight in kilograms (default: {DEFAULT_USER_WEIGHT_KG})",
    )
    parser.add_argument(
        "--camera",
        type=int,
        default=CAMERA_INDEX,
        help="Camera device index for cv2.VideoCapture (default: 0)",
    )
    parser.add_argument(
        "--video",
        type=str,
        default=None,
        help="Optional path to a video file instead of live camera",
    )
    parser.add_argument(
        "--train",
        action="store_true",
        help="Generate synthetic datasets and train/retrain the XGBoost model",
    )
    parser.add_argument(
        "--headless-test",
        action="store_true",
        help="Run non-interactive headless test loop for automated verification",
    )
    return parser.parse_args()


def run_pipeline(
    exercise_type: str,
    user_weight_kg: float,
    camera_index: int = CAMERA_INDEX,
    video_path: Optional[str] = None,
    headless_test: bool = False,
) -> None:
    """
    Main loop executing the Burn-Ex computer vision & biomechanics pipeline.
    """
    print("=" * 60)
    print("  BURN-EX: Privacy-Preserving AI Energy Expenditure Tracker")
    print("  Zero Raw-Video Retention | Edge Biomechanical Inference")
    print("=" * 60)
    print(f"[*] Exercise: {exercise_type.upper()} | User Weight: {user_weight_kg} kg")

    # 1. Initialize Subsystems
    print("[*] Initializing MediaPipe Vision Pipeline...")
    vision = VisionPipeline()

    print(f"[*] Initializing Biomechanics Engine ({exercise_type})...")
    biomechanics = BiomechanicsEngine(exercise_type=exercise_type)

    print("[*] Initializing Feature Extractor...")
    features = FeatureExtractor(user_weight_kg=user_weight_kg)
    features.start_set()

    print("[*] Loading ML Engine & XGBoost Regressor...")
    ml_engine = MLEngine()

    renderer = UIRenderer()

    # 2. Open Video Capture Source
    if headless_test:
        print("[*] Running in headless test mode...")
        dummy_frames = [
            np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)
            for _ in range(30)
        ]
        for idx, frame in enumerate(dummy_frames):
            landmarks_2d, landmarks_3d, _ = vision.process_frame(frame)
            state = biomechanics.update(landmarks_2d, landmarks_3d)
            duration = features.update_timer(target_lost=state.get("target_lost", False))
            _ = renderer.render_hud(frame, state, duration, predicted_kcal=None)

        df_feat = features.extract_features(biomechanics.update(None))
        pred = ml_engine.predict(df_feat)
        print(f"[+] Headless test successful! Prediction: {pred[0]} - {pred[2]} kcal")
        vision.close()
        return

    video_source = video_path if video_path else camera_index
    print(f"[*] Opening video capture source: {video_source} ...")
    if video_path:
        cap = VideoStream(video_source).start()
    else:
        cap = VideoStream(video_source, width=FRAME_WIDTH, height=FRAME_HEIGHT).start()

    if not cap.isOpened():
        print(f"[!] Error: Unable to open video capture source ({video_source}).")
        print("    If you don't have a connected webcam, pass a video with --video <path> or run tests.")
        vision.close()
        return

    window_name = "Burn-Ex: Privacy-Preserving AI Energy Tracker"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, FRAME_WIDTH, FRAME_HEIGHT)

    predicted_kcal: Optional[Tuple[float, float, float]] = None
    is_set_active: bool = True

    try:
        while cap.isOpened():
            success, frame = cap.read()
            if not success or frame is None:
                if video_path:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(0.03)
                    continue
                else:
                    print("[!] Video stream ended or camera disconnected.")
                    break

            frame = cv2.resize(frame, (640, 480))
            landmarks_2d, landmarks_3d, raw_results = vision.process_frame(frame)
            state = biomechanics.update(landmarks_2d, landmarks_3d)
            target_lost = state.get("target_lost", False)
            duration_sec = features.update_timer(target_lost=target_lost)

            primary_joint = EXERCISE_CONFIGS[exercise_type].primary_joint
            renderer.draw_skeleton(
                frame,
                landmarks_2d,
                is_form_valid=state.get("is_form_valid", True),
                active_joint_name=primary_joint,
            )

            hud_frame = renderer.render_hud(
                frame,
                biomechanics_state=state,
                duration_sec=duration_sec,
                predicted_kcal=predicted_kcal,
                is_set_active=is_set_active,
            )

            cv2.imshow(window_name, hud_frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q") or key == ord("Q"):
                print("\n[*] Completing active set and calculating energy expenditure...")
                features.stop_set()
                is_set_active = False

                df_features = features.extract_features(state)
                predicted_kcal = ml_engine.predict(df_features)

                lower, point, upper = predicted_kcal
                print(f"[+] Total Reps: {state['total_reps']} (Valid: {state['valid_reps']}, Invalid: {state['invalid_reps']})")
                print(f"[+] Duration: {duration_sec:.1f}s | Avg ROM: {state['avg_rom']:.1f}°")
                print(f"[+] ESTIMATED ENERGY EXPENDITURE: {lower:.2f} - {upper:.2f} kcal (Point: ~{point:.2f} kcal)\n")

            elif key == ord("r") or key == ord("R"):
                print("[*] Resetting session metrics for new set...")
                biomechanics.reset()
                features.reset()
                features.start_set()
                predicted_kcal = None
                is_set_active = True

            elif key == 27:
                print("[*] Exiting Burn-Ex...")
                break

    finally:
        vision.close()
        cap.release()
        cv2.destroyAllWindows()
        print("[*] Shutdown complete. All temporary video buffers purged.")


def main() -> None:
    args = parse_arguments()

    if args.web:
        print("[*] Starting Burn-Ex Web Studio & Analytics Platform...")
        from app import app
        app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
        return

    if args.train:
        print("[*] Generating reference datasets and training XGBoost model...")
        ml_engine = MLEngine()
        ml_engine.train()
        print("[+] Training completed successfully.")
        if not args.headless_test and not args.video:
            return

    run_pipeline(
        exercise_type=args.exercise,
        user_weight_kg=args.weight,
        camera_index=args.camera,
        video_path=args.video,
        headless_test=args.headless_test,
    )


if __name__ == "__main__":
    main()
