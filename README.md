# BURN-EX: Privacy-Preserving AI Energy Expenditure Tracker & Workout Studio

**Version:** 2.0 (Master Edition)  
**Target Environment:** Edge / Local Execution (Python 3.10+)  
**Core Paradigm:** Extract &rarr; Calculate &rarr; Infer &rarr; Render (*Zero Raw-Video Storage*)

---

## 1. Project Overview

**Burn-Ex** is an edge-computing AI system and workout studio that accurately estimates a user's physical energy expenditure (calories burned) during exercise sets. Traditional fitness trackers rely on static MET (Metabolic Equivalent of Task) duration timers that cannot distinguish between full-depth repetitions, slow controlled eccentrics, half-reps, or poor posture. 

Burn-Ex leverages real-time computer vision (MediaPipe) to track temporal biomechanical features—such as **Range of Motion (ROM)**, **repetition velocity/cadence**, and **form quality**—to output a **personalized energy expenditure calorie range** powered by XGBoost machine learning.

All computations are processed strictly in-memory on the edge with **zero raw-video storage**, ensuring absolute user privacy.

---

## 2. Web Studio & UX Features

### 🌟 1. Onboarding & Athlete Calibration (`/` -> Athlete Profile)
- Calibrates body weight (kg), height (cm), age, gender, and primary fitness goal (*Fat Loss*, *Hypertrophy*, *Posture / Rehab*, *Endurance*).
- Persists data locally in `data/user_profile.json` and updates the active metabolic calculation engine in real time.

### 🎥 2. Live Workout Studio (`/` -> Live Studio)
- **Two-Column Responsive Split Layout (60% Vision Canvas | 40% Telemetry Sidebar)**:
  - **Left Canvas**: Smooth video stream with neon-glowing MediaPipe skeleton overlays, real-time FPS counter, exercise selector (*Push-Up*, *Squat*, *Jumping Jack*), and active form alert banners (`FORM OPTIMAL`, `⚠️ SAGGING HIPS DETECTED`, `⚠️ TARGET LOST - PAUSED`).
  - **Right Telemetry Sidebar**:
    1. **Repetition Counter Widget**: Giant live count, valid vs. rejected sub-counter, state pill (`STATE: UP` / `STATE: DOWN`).
    2. **Biomechanics Gauge**: Animated SVG circular form score meter (%), instant joint angle readout & bar, average ROM readout & bar.
    3. **Metabolic Burn Rate**: Live instant calorie burn rate (`kcal/min`) and intensity tier (`LOW`, `MODERATE`, `HIGH`).
    4. **Control Bar**: Interactive **Pause/Resume** and **End Set & Analyze** buttons.

### 📊 3. Post-Workout Analytics Control Center (`/` -> Analytics Dashboard)
- **KPI Summary Row**: Total Estimated Expenditure (`X.XX - Y.YY kcal` with point estimate), Total Reps & Form Compliance %, Active Duration (`MM:SS`), Cadence (`reps/min`).
- **Interactive Visual Charts (Chart.js)**:
  - **Chart A (Repetition ROM Compliance)**: Line chart tracking ROM per rep against target baseline thresholds.
  - **Chart B (Historical Session Progress)**: Multi-axis combo chart tracking calories burned and form compliance across workout history.
- **Session Log Table**: Historical record of past workouts stored locally in SQLite (`data/workout_history.db`).
- **Export Data**: Direct 1-click export to **JSON** or **CSV**.

---

## 3. Directory Layout

```text
Burn-Ex/
├── data/
│   ├── raw_sessions.csv          # Local training dataset with biomechanical features
│   ├── reference_baselines.csv   # Standard MET baselines and exercise thresholds
│   ├── user_profile.json         # Athlete physical profile configuration
│   └── workout_history.db        # SQLite historical workout session database
├── models/
│   ├── burn_ex_xgboost.pkl       # Serialized trained XGBoost Regressor model
│   └── pose_landmarker_full.task # MediaPipe 3D Pose Landmarker model asset
├── src/
│   ├── __init__.py
│   ├── config.py                 # Hyperparameters, angle thresholds, exercise schemas & UI palette
│   ├── vision_pipeline.py        # MediaPipe camera integration with zero raw-video retention
│   ├── biomechanics.py           # Vector angle math, state machines & posture validation
│   ├── feature_extractor.py      # Aggregates temporal set metrics, instant burn rate (kcal/min)
│   ├── ml_engine.py              # XGBoost ML engine, MET physics calibration, confidence interval inference
│   ├── user_manager.py           # Athlete profile persistence & SQLite database logger
│   └── ui_renderer.py            # OpenCV HUD overlay renderer with neon cyber-aesthetic
├── static/
│   ├── css/
│   │   └── style.css             # Dark athletic & cyberpunk glassmorphism design system
│   └── js/
│       └── app.js                # SPA state controller, telemetry polling & Chart.js engine
├── templates/
│   └── index.html                # Responsive 3-screen SPA template (Onboarding, Studio, Dashboard)
├── tests/
│   ├── __init__.py
│   ├── test_biomechanics.py      # Unit tests for kinematics, state machines & ML inference
│   ├── test_user_manager.py      # Unit tests for profile persistence & SQLite logging
│   └── test_web_api.py           # Unit tests for Flask REST API endpoints & export
├── app.py                        # Flask Web Application & Video Feed Server
├── main.py                       # CLI & Web application entry point
├── requirements.txt              # Dependency specification
└── README.md                     # Project documentation
```

---

## 4. Quickstart Guide

### 1. Launch the Interactive Web Studio
```bash
python app.py
# or
python main.py --web
```
Open your browser at **`http://127.0.0.1:5000`**.

### 2. Standalone CLI OpenCV Mode
```bash
# Push-up tracking (webcam)
python main.py --exercise pushup --weight 75.0

# Squat tracking
python main.py --exercise squat --weight 70.0

# Jumping Jack tracking
python main.py --exercise jumping_jack --weight 80.0
```

### 3. Run Automated Unit Tests
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

---

## 5. Privacy Guarantee

- **Zero Raw-Video Storage**: Video frames captured from `cv2.VideoCapture` are processed in ephemeral memory and immediately discarded.
- **Local Edge Processing**: No landmark, biometric, or video data is ever sent to external cloud APIs or servers.
- **Graceful Target Loss**: If the user leaves the frame, the timer automatically pauses, retaining counts without crashing.
