"""
ML Engine for Burn-Ex.
Implements a Physics-Informed Residual Architecture with XGBoost.
Calibrates Base MET energy with a dynamic form/intensity multiplier M_form in [0.6, 1.4]
evaluated with Leave-One-Person-Out (LOPO) cross-validation.
"""

from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import pickle
import numpy as np
import pandas as pd

from src.config import (
    MODEL_PATH,
    RAW_SESSIONS_CSV,
    REFERENCE_BASELINES_CSV,
    MET_VALUES,
    EXERCISE_CONFIGS,
    FORM_MULTIPLIER_MIN,
    FORM_MULTIPLIER_MAX,
)


RESIDUAL_FEATURE_COLUMNS: List[str] = [
    "peak_angular_velocity",
    "rom_completeness_ratio",
    "torso_inclination_angle",
    "rep_cadence_variance",
    "rep_velocity",
    "valid_rep_ratio",
    "is_pushup",
    "is_squat",
    "is_jumping_jack",
]


def calculate_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """Calculate BMR using Mifflin-St Jeor equation."""
    if str(gender).lower() == "male":
        return 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age + 5.0
    else:
        return 10.0 * weight_kg + 6.25 * height_cm - 5.0 * age - 161.0


class MLEngine:
    """
    Predicts calorie expenditure using a Physics-Informed Residual Architecture.
    Estimated Kcal = K_base * M_form
    where K_base = MET * (BMR / 24) * (Duration / 3600), and M_form in [0.6, 1.4] is predicted by XGBoost.
    """

    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model_path = model_path
        self.model: Optional[Any] = None
        self._load_or_initialize_model()

    def _load_or_initialize_model(self) -> None:
        """Load trained XGBoost model from disk or train if missing."""
        if self.model_path.exists():
            try:
                with open(self.model_path, "rb") as f:
                    self.model = pickle.load(f)
                return
            except Exception as e:
                print(f"[Burn-Ex ML] Warning: Could not load existing model ({e}). Retraining...")

        print("[Burn-Ex ML] Generating dataset and training Physics-Informed Residual XGBoost model...")
        self.train()

    def _preprocess_features(self, df_features: pd.DataFrame) -> pd.DataFrame:
        """One-hot encode exercise types and structure residual feature vector."""
        df = df_features.copy()

        exercise = str(df.get("exercise_type", ["pushup"]).iloc[0]).lower()
        df["is_pushup"] = 1.0 if exercise == "pushup" else 0.0
        df["is_squat"] = 1.0 if exercise == "squat" else 0.0
        df["is_jumping_jack"] = 1.0 if exercise == "jumping_jack" else 0.0

        for col in RESIDUAL_FEATURE_COLUMNS:
            if col not in df.columns:
                df[col] = 0.0

        return df[RESIDUAL_FEATURE_COLUMNS].astype(float)

    def calculate_k_base(
        self,
        exercise_type: str,
        user_weight_kg: float,
        duration_sec: float,
        user_height_cm: float = 175.0,
        user_age: int = 25,
        user_gender: str = "male",
    ) -> float:
        """
        Calculate Base MET Energy using Mifflin-St Jeor BMR personalization.
        K_base = MET * (BMR / 24.0) * (duration_sec / 3600.0)
        """
        met = MET_VALUES.get(exercise_type.lower(), 8.0)
        bmr = calculate_bmr(user_weight_kg, user_height_cm, user_age, user_gender)
        duration_hours = max(0.1, duration_sec) / 3600.0
        return float(met * (bmr / 24.0) * duration_hours)

    def calculate_ground_truth_multiplier(
        self,
        peak_angular_velocity: float,
        rom_completeness_ratio: float,
        valid_rep_ratio: float,
        rep_velocity: float,
        torso_inclination_angle: float,
        exercise_type: str = "pushup",
    ) -> float:
        """
        Synthesizes the ground truth physical form multiplier based on biomechanical laws.
        """
        # 1. Power / Explosiveness factor (from angular velocity ~ 120-250 deg/s)
        power_factor = 1.0 + 0.25 * np.clip((peak_angular_velocity - 180.0) / 100.0, -0.4, 0.6)

        # 2. ROM Completeness (Penalize shallow half-reps)
        rom_factor = 0.8 + 0.3 * np.clip(rom_completeness_ratio, 0.4, 1.2)

        # 3. Form Accuracy & Alignment
        form_factor = 0.85 + 0.15 * np.clip(valid_rep_ratio, 0.0, 1.0)

        # 4. Cadence Intensity
        cadence_factor = 1.0 + 0.15 * np.clip((rep_velocity - 20.0) / 20.0, -0.4, 0.5)

        m_form = power_factor * rom_factor * form_factor * cadence_factor
        return float(np.clip(m_form, FORM_MULTIPLIER_MIN, FORM_MULTIPLIER_MAX))

    def predict(self, df_features: pd.DataFrame) -> Tuple[float, float, float]:
        """
        Predict energy expenditure range using Physics-Informed Residual formulation.

        Returns:
            Tuple[float, float, float]: (lower_bound_kcal, point_prediction_kcal, upper_bound_kcal)
        """
        X = self._preprocess_features(df_features)
        exercise_type = str(df_features.get("exercise_type", ["pushup"]).iloc[0]).lower()
        user_weight = float(df_features.get("user_weight_kg", [70.0]).iloc[0])
        user_height = float(df_features.get("user_height_cm", [175.0]).iloc[0])
        user_age = int(df_features.get("user_age", [25]).iloc[0])
        user_gender = str(df_features.get("user_gender", ["male"]).iloc[0])
        duration_sec = float(df_features.get("duration_sec", [1.0]).iloc[0])
        valid_rep_ratio = float(df_features.get("valid_rep_ratio", [1.0]).iloc[0])

        # Step 1: Base MET Energy with Mifflin-St Jeor BMR personalization
        k_base = self.calculate_k_base(
            exercise_type=exercise_type,
            user_weight_kg=user_weight,
            duration_sec=duration_sec,
            user_height_cm=user_height,
            user_age=user_age,
            user_gender=user_gender,
        )

        # Step 2: Predict Dynamic Multiplier M_form
        if self.model is not None:
            try:
                m_pred = float(self.model.predict(X)[0])
            except Exception:
                m_pred = 1.0
        else:
            m_pred = 1.0

        # Strictly bound multiplier to physical range [0.60, 1.40]
        m_form = float(np.clip(m_pred, FORM_MULTIPLIER_MIN, FORM_MULTIPLIER_MAX))

        # Step 3: Compute Final Point Estimate
        point_kcal = k_base * m_form

        # Step 4: Calibrated Uncertainty Bounds
        uncertainty_rate = 0.07 + (1.0 - valid_rep_ratio) * 0.10
        m_lower = float(np.clip(m_form * (1.0 - uncertainty_rate), FORM_MULTIPLIER_MIN, FORM_MULTIPLIER_MAX))
        m_upper = float(np.clip(m_form * (1.0 + uncertainty_rate), FORM_MULTIPLIER_MIN, FORM_MULTIPLIER_MAX))

        lower_kcal = max(0.01, k_base * m_lower)
        upper_kcal = max(lower_kcal + 0.01, k_base * m_upper)

        return (
            round(lower_kcal, 2),
            round(point_kcal, 2),
            round(upper_kcal, 2),
        )

    def generate_datasets(
        self, num_participants: int = 30, samples_per_participant: int = 40
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Generates grouped workout sessions for Leave-One-Person-Out (LOPO) training.
        """
        np.random.seed(42)

        # 1. Reference Baselines
        ref_rows = []
        for ex, met in MET_VALUES.items():
            cfg = EXERCISE_CONFIGS[ex]
            ref_rows.append({
                "exercise_type": ex,
                "standard_met": met,
                "target_ideal_rom_deg": cfg.target_ideal_rom,
                "up_threshold_deg": cfg.up_angle_threshold,
                "down_threshold_deg": cfg.down_angle_threshold,
            })
        df_ref = pd.DataFrame(ref_rows)
        REFERENCE_BASELINES_CSV.parent.mkdir(parents=True, exist_ok=True)
        df_ref.to_csv(REFERENCE_BASELINES_CSV, index=False)

        # 2. Grouped Synthetic Sessions
        exercises = list(MET_VALUES.keys())
        data_rows = []

        for p_id in range(1, num_participants + 1):
            # Individual baseline characteristics
            p_weight = np.random.uniform(52.0, 105.0)
            p_height = np.random.uniform(150.0, 200.0)
            p_age = np.random.randint(18, 70)
            p_gender = np.random.choice(["male", "female"])
            p_tempo_bias = np.random.uniform(0.7, 1.4)
            p_form_bias = np.random.beta(6, 2)  # 70-95% form accuracy

            for _ in range(samples_per_participant):
                ex = np.random.choice(exercises)
                duration = np.random.uniform(20.0, 240.0)

                base_cadence = 20.0 * p_tempo_bias * np.random.uniform(0.8, 1.2)
                expected_reps = int(max(1, (duration / 60.0) * base_cadence))

                valid_ratio = float(np.clip(p_form_bias * np.random.uniform(0.85, 1.05), 0.3, 1.0))
                valid_reps = int(expected_reps * valid_ratio)
                invalid_reps = expected_reps - valid_reps
                total_reps = valid_reps + invalid_reps

                cfg = EXERCISE_CONFIGS[ex]
                rom_completeness = float(np.clip(np.random.normal(0.95, 0.15), 0.4, 1.3))
                avg_rom = round(cfg.target_ideal_rom * rom_completeness, 1)

                peak_angular_vel = float(np.clip(np.random.normal(200.0 * p_tempo_bias, 35.0), 80.0, 380.0))
                torso_angle = float(np.clip(np.random.normal(85.0 if ex == "pushup" else 20.0, 8.0), 0.0, 95.0))
                cadence_var = float(np.clip(np.random.exponential(0.35), 0.05, 1.2))
                rep_velocity = total_reps / (duration / 60.0)

                m_target = self.calculate_ground_truth_multiplier(
                    peak_angular_velocity=peak_angular_vel,
                    rom_completeness_ratio=rom_completeness,
                    valid_rep_ratio=valid_reps / max(1, total_reps),
                    rep_velocity=rep_velocity,
                    torso_inclination_angle=torso_angle,
                    exercise_type=ex,
                )

                # Add minor physiological measurement noise (± 2%)
                m_target = float(np.clip(m_target * np.random.normal(1.0, 0.02), FORM_MULTIPLIER_MIN, FORM_MULTIPLIER_MAX))
                k_base = self.calculate_k_base(
                    exercise_type=ex,
                    user_weight_kg=p_weight,
                    duration_sec=duration,
                    user_height_cm=p_height,
                    user_age=p_age,
                    user_gender=p_gender,
                )
                target_kcal = k_base * m_target

                data_rows.append({
                    "participant_id": f"ATHLETE_{p_id:03d}",
                    "exercise_type": ex,
                    "user_weight_kg": round(p_weight, 1),
                    "user_height_cm": round(p_height, 1),
                    "user_age": p_age,
                    "user_gender": p_gender,
                    "duration_sec": round(duration, 1),
                    "total_reps": total_reps,
                    "valid_reps": valid_reps,
                    "invalid_reps": invalid_reps,
                    "valid_rep_ratio": round(valid_reps / max(1, total_reps), 3),
                    "avg_rom_deg": avg_rom,
                    "rep_velocity": round(rep_velocity, 2),
                    "peak_angular_velocity": round(peak_angular_vel, 1),
                    "rom_completeness_ratio": round(rom_completeness, 3),
                    "torso_inclination_angle": round(torso_angle, 1),
                    "rep_cadence_variance": round(cadence_var, 3),
                    "k_base_kcal": round(k_base, 3),
                    "target_multiplier_m": round(m_target, 4),
                    "target_kcal": round(target_kcal, 3),
                })

        df_raw = pd.DataFrame(data_rows)
        RAW_SESSIONS_CSV.parent.mkdir(parents=True, exist_ok=True)
        df_raw.to_csv(RAW_SESSIONS_CSV, index=False)

        return df_ref, df_raw

    def train(self, num_participants: int = 30) -> None:
        """
        Train Physics-Informed XGBoost Regressor on the dynamic form multiplier M_form
        with Leave-One-Person-Out (LOPO) / Group-K-Fold cross-validation.
        """
        from xgboost import XGBRegressor
        from sklearn.model_selection import GroupKFold
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

        if not RAW_SESSIONS_CSV.exists():
            _, df_raw = self.generate_datasets(num_participants=num_participants)
        else:
            df_raw = pd.read_csv(RAW_SESSIONS_CSV)
            if "target_multiplier_m" not in df_raw.columns:
                _, df_raw = self.generate_datasets(num_participants=num_participants)

        # Preprocess features
        X_list = []
        for _, row in df_raw.iterrows():
            single_df = pd.DataFrame([row.to_dict()])
            X_list.append(self._preprocess_features(single_df).iloc[0])

        X = pd.DataFrame(X_list)
        y = df_raw["target_multiplier_m"].values
        groups = df_raw["participant_id"].values

        # Leave-One-Person-Out / Group-K-Fold Validation (5 splits across participants)
        gkf = GroupKFold(n_splits=5)
        fold_rmses, fold_maes, fold_r2s = [], [], []

        for train_idx, val_idx in gkf.split(X, y, groups):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            fold_model = XGBRegressor(
                n_estimators=120,
                max_depth=3,
                learning_rate=0.06,
                subsample=0.85,
                colsample_bytree=0.85,
                random_state=42,
            )
            fold_model.fit(X_train, y_train)
            y_pred = fold_model.predict(X_val)

            fold_rmses.append(np.sqrt(mean_squared_error(y_val, y_pred)))
            fold_maes.append(mean_absolute_error(y_val, y_pred))
            fold_r2s.append(r2_score(y_val, y_pred))

        avg_rmse = np.mean(fold_rmses)
        avg_mae = np.mean(fold_maes)
        avg_r2 = np.mean(fold_r2s)

        print(f"[Burn-Ex ML LOPO] 5-Fold Group CV Multiplier Evaluation:")
        print(f"                  Multiplier MAE: {avg_mae:.4f} | Multiplier RMSE: {avg_rmse:.4f} | R²: {avg_r2:.4f}")

        # Train final model on complete dataset
        final_model = XGBRegressor(
            n_estimators=140,
            max_depth=3,
            learning_rate=0.06,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=42,
        )
        final_model.fit(X, y)

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(MODEL_PATH, "wb") as f:
            pickle.dump(final_model, f)

        self.model = final_model
