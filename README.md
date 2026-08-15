# Burn-Ex — AI-Powered Personalized Fitness Intelligence

> **Move Better. Burn Smarter.**

Burn-Ex is an **AI-powered, privacy-focused fitness platform** that goes beyond traditional calorie counters and simple repetition tracking.

Instead of treating every repetition equally, Burn-Ex analyzes **how the user actually moves**. Using computer vision, biomechanical feature extraction, signal processing, and a custom-trained machine-learning model, the platform estimates exercise intensity and personalized energy expenditure from real movement telemetry.

---

## 🚀 Why Burn-Ex?

Traditional fitness applications often rely on generalized formulas:

```text
Calories ≈ Weight × Time × Generic Activity Factor
```

This creates a major limitation.

Two users can perform the same number of repetitions while using very different:

* Range of Motion
* Movement speed
* Joint velocity
* Exercise form
* Body positioning
* Movement intensity

Yet a conventional system may treat them almost identically.

### Burn-Ex takes a different approach.

```text
                  ┌──────────────────────┐
                  │     User Camera      │
                  └──────────┬───────────┘
                             ↓
                  ┌──────────────────────┐
                  │  Pose Estimation     │
                  │     MediaPipe        │
                  └──────────┬───────────┘
                             ↓
                  ┌──────────────────────┐
                  │ EMA Signal Filtering │
                  └──────────┬───────────┘
                             ↓
                  ┌──────────────────────┐
                  │ Biomechanical        │
                  │ Feature Extraction   │
                  └──────────┬───────────┘
                             ↓
                  ┌──────────────────────┐
                  │ Trained ML Model     │
                  │      XGBoost         │
                  └──────────┬───────────┘
                             ↓
             ┌───────────────┴────────────────┐
             ↓                                ↓
      Form / Rep Analysis              Energy Estimation
             ↓                                ↓
             └───────────────┬────────────────┘
                             ↓
                  ┌──────────────────────┐
                  │   Burn-Ex Dashboard │
                  └──────────────────────┘
```

---

# ✨ Core Features

## 🧠 AI-Powered Movement Analysis

Burn-Ex uses computer vision to understand exercise movement rather than simply counting time.

The system analyzes movement telemetry such as:

* Joint angles
* Range of Motion (ROM)
* Joint velocity
* Movement tempo
* Torso inclination
* Exercise phase
* Form quality
* Repetition validity
* Movement intensity

---

## 🦴 Real-Time Pose Estimation

Burn-Ex uses **MediaPipe Pose** to extract human body landmarks from the camera feed.

The pipeline works with pose landmarks to understand the user's body position and movement.

The system can derive biomechanical measurements such as:

```text
Shoulder Angle
Elbow Angle
Hip Angle
Knee Angle
Torso Inclination
Range of Motion
Joint Velocity
```

This allows Burn-Ex to understand **how the exercise is being performed**, rather than simply detecting that movement occurred.

---

## 📐 Biomechanical Analysis

A major part of Burn-Ex is converting raw pose data into meaningful movement telemetry.

For example, during a push-up:

```text
Shoulder
    │
    │
Elbow ───────── Wrist
    │
    │
   Hip
```

The system can monitor the changing joint angles throughout the repetition.

A simplified movement cycle can be represented as:

```text
Starting Position
       ↓
     Descent
       ↓
   Bottom Position
       ↓
     Ascent
       ↓
  Starting Position
       ↓
   Valid Rep
```

This allows Burn-Ex to distinguish between:

```text
Deep controlled push-up
        vs.
Shallow half repetition
```

---

# 📊 EMA Signal Processing

Camera-based landmark coordinates naturally contain noise and jitter.

Raw coordinates can look conceptually like:

```text
100
102
98
104
99
105
101
```

Directly calculating velocity from this signal can produce unstable results.

Burn-Ex therefore applies an **Exponential Moving Average (EMA)** filter to smooth the landmark signal before calculating movement features.

Conceptually:

```text
Raw Camera Data
       ↓
   EMA Filter
       ↓
Smoothed Coordinates
       ↓
Velocity / ROM / Angles
```

The EMA provides a balance between:

* Responsiveness
* Stability
* Noise reduction

This is particularly important for real-time joint velocity calculations.

---

# 🔄 Intelligent Rep Detection

Burn-Ex does not simply count every detected movement as a repetition.

A **state-machine / debouncing approach** is used to identify exercise phases and reduce false positives.

For example, a push-up may use thresholds conceptually similar to:

```text
< 80°  → Bottom State

80° ─────────────── 160°

> 160° → Top State
```

The system requires the movement to transition through the appropriate states before registering a complete repetition.

This helps prevent:

* Micro-movements
* Camera jitter
* Partial repetitions
* Repeated frame triggers
* Accidental rep counts

---

# 🤖 Physics-Informed Machine Learning

One of the key design decisions in Burn-Ex is that the ML model does **not blindly predict calories from scratch**.

Instead, Burn-Ex follows a hybrid approach.

### Stage 1 — Baseline

A physiological baseline is calculated using user information and workout duration.

Conceptually:

```text
User Profile
    +
Weight
    +
Duration
    +
Exercise Context
    ↓
Baseline Energy Estimate
```

### Stage 2 — Movement Intelligence

The trained ML model analyzes movement telemetry such as:

```text
Range of Motion
Joint Velocity
Movement Intensity
Torso Inclination
Exercise Characteristics
```

The model then estimates an intensity adjustment.

Conceptually:

```text
Baseline Energy
       ×
Movement Intensity Multiplier
       ↓
Personalized Energy Estimate
```

This creates a **physics-informed residual approach** rather than allowing an unconstrained model to generate arbitrary calorie values.

---

# 🌳 XGBoost-Based Prediction

Burn-Ex uses a custom-trained machine-learning model based on **XGBoost** for movement/intensity-related prediction.

Instead of feeding raw images directly into the model, Burn-Ex first converts movement into structured numerical telemetry.

Example feature vector:

```text
[
    joint_angle,
    range_of_motion,
    joint_velocity,
    torso_inclination,
    movement_duration,
    exercise_phase,
    ...
]
```

The model learns relationships between these movement characteristics and the target output from the project's training data.

### Why XGBoost?

XGBoost is well suited for structured/tabular data such as biomechanical telemetry because it can model nonlinear relationships between multiple movement features.

---

# 🧪 Custom / Self-Generated Dataset

Burn-Ex is designed around a **self-generated training dataset** rather than relying on an external fitness-calorie API as the source of its predictions.

The dataset is generated around the project's own movement and telemetry pipeline.

The general workflow is:

```text
Exercise Performance
        ↓
Pose Landmarks
        ↓
Biomechanical Features
        ↓
Telemetry Dataset
        ↓
Data Cleaning
        ↓
Feature Engineering
        ↓
Model Training
        ↓
Validation
        ↓
Trained Burn-Ex Model
```

This allows the project to maintain control over:

* Feature definitions
* Data generation
* Preprocessing
* Training
* Model inference
* Evaluation

The production application uses the trained model rather than requesting calorie predictions from a third-party fitness API.

---

# 🔥 Live Studio

The **Live Studio** is the core real-time AI component of Burn-Ex.

Users can perform an exercise in front of their camera while Burn-Ex analyzes the movement.

### Live Dashboard

The interface provides real-time information including:

| Metric            | Description                           |
| ----------------- | ------------------------------------- |
| Completed Reps    | Total detected repetitions            |
| Valid Reps        | Repetitions meeting movement criteria |
| Faulty Reps       | Repetitions failing form criteria     |
| Joint Angle       | Current biomechanical joint angle     |
| Average ROM       | Range of Motion measurement           |
| Torso Inclination | Current torso positioning             |
| Joint Velocity    | Movement velocity                     |
| Form Score        | Estimated movement quality            |
| Burn Rate         | Estimated kcal/min                    |
| Total Calories    | Estimated session energy expenditure  |
| FPS               | Real-time processing performance      |

---

# 🎥 Real-Time Pipeline

The Live Studio follows this pipeline:

```text
             Webcam
                │
                ▼
       Video Frame Capture
                │
                ▼
        MediaPipe Pose
                │
                ▼
       3D Pose Landmarks
                │
                ▼
          EMA Filtering
                │
                ▼
      Feature Extraction
                │
       ┌────────┼─────────┐
       ▼        ▼         ▼
      ROM    Velocity   Angles
       │        │         │
       └────────┼─────────┘
                ▼
        Movement Telemetry
                │
                ▼
        Trained ML Model
                │
       ┌────────┴─────────┐
       ▼                  ▼
   Form Analysis      Energy Model
       │                  │
       └────────┬─────────┘
                ▼
         FastAPI Backend
                │
                ▼
         React Frontend
                │
                ▼
        Live Studio UI
```

---

# 🏋️ Personalized Workouts

Burn-Ex is designed as a complete fitness platform rather than a single calorie calculator.

The workout module provides personalized training based on the user's profile and goals.

Potential personalization factors include:

* Fitness goal
* Experience level
* Body measurements
* Workout history
* Previous performance
* Exercise performance
* Progress trends

The system can organize workouts into structured sessions rather than presenting an unorganized exercise list.

---

# 📈 Progress Tracking

Burn-Ex stores historical workout information so users can monitor their development over time.

Progress can include:

```text
Workout History
       ↓
Performance Trends
       ↓
Rep Improvements
       ↓
Form Improvements
       ↓
Energy Expenditure
       ↓
Long-Term Progress
```

Users can compare previous sessions and observe changes in their performance.

---

# 🥗 Personalized Indian Nutrition

The Nutrition module is designed around the user's fitness objective.

For example:

### Weight Loss

The system can prioritize meals such as:

* Vegetable-based breakfasts
* Idli with suitable sides
* Vegetable upma
* High-protein meals
* Dal-based dishes
* Vegetable curries
* Controlled rice portions
* Fruits and other appropriate snacks

### Weight Gain

The recommendations can shift toward more energy-dense meals containing:

* Rice-based meals
* Paneer
* Eggs
* Milk
* Curd
* Nuts
* Peanut-based foods
* Higher-calorie traditional meals

The nutrition system is intended to provide **Indian-style meal recommendations** rather than relying exclusively on Western food databases.

---

# 🤖 AI Coach

Burn-Ex includes an AI fitness assistant designed to answer user questions about:

* Exercise technique
* Workout planning
* Recovery
* Nutrition
* Fitness concepts
* Form improvement
* Training questions
* Burn-Ex metrics

The AI Coach is a **separate AI subsystem** from the Live Studio ML model.

```text
                    BURN-EX AI
                        │
             ┌──────────┴──────────┐
             ↓                     ↓
       Live Studio              AI Coach
             │                     │
     Custom ML Pipeline         Gemini API
             │                     │
     Movement Analysis        User Questions
```

Camera frames are **not sent to Gemini for movement analysis**.

The computer-vision pipeline remains responsible for Live Studio inference.

---

# 🔐 Privacy-First Architecture

Privacy is a core design principle of Burn-Ex.

The system is designed to minimize unnecessary external processing of fitness and camera data.

The architecture separates:

```text
Camera / Biomechanics
        ↓
Burn-Ex ML Pipeline
        ↓
Local / Application Processing
```

from:

```text
User Question
        ↓
AI Coach
        ↓
Gemini API
```

Camera data should not be sent to external generative-AI services for pose analysis.

> **Your workout should remain your data.**

---

# 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────┐
│                    BURN-EX                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────┐       ┌─────────────────────┐ │
│  │ React Frontend  │       │   FastAPI Backend   │ │
│  │                 │◄─────►│                     │ │
│  │ • Dashboard     │       │ • REST APIs         │ │
│  │ • Live Studio   │       │ • Inference         │ │
│  │ • Workouts      │       │ • Pose Processing   │ │
│  │ • Progress      │       │ • ML Prediction    │ │
│  │ • Nutrition     │       │ • User Data        │ │
│  │ • AI Coach      │       │                     │ │
│  └────────┬────────┘       └──────────┬──────────┘ │
│           │                           │            │
│           │                           ▼            │
│           │                  ┌─────────────────┐  │
│           │                  │  ML Model Layer │  │
│           │                  │                 │  │
│           │                  │ • XGBoost       │  │
│           │                  │ • MediaPipe     │  │
│           │                  │ • EMA Filter    │  │
│           │                  │ • Features      │  │
│           │                  └─────────────────┘  │
│           │                                       │
│           ▼                                       │
│    ┌───────────────┐                              │
│    │ Camera Input  │                              │
│    └───────────────┘                              │
│                                                   │
└───────────────────────────────────────────────────┘
```

---

# 📁 Project Structure

```text
Burn-Ex/
│
├── .github/
│   └── workflows/
│       └── deploy.yml
│
├── backend/
│   │
│   ├── data/
│   │   └── # Training / application data
│   │
│   ├── models/
│   │   └── # Trained ML models and model artifacts
│   │
│   ├── src/
│   │   ├── # Pose processing
│   │   ├── # Feature extraction
│   │   ├── # Signal processing
│   │   ├── # ML inference
│   │   └── # Application services
│   │
│   ├── tests/
│   │   └── # Backend tests
│   │
│   ├── .env
│   ├── .env.example
│   ├── api.py
│   ├── main.py
│   └── requirements.txt
│
├── frontend/
│   └── # React application
│
├── .gitignore
├── LICENSE
├── README.md
└── Burn-Ex.txt
```

> The exact internal files may evolve as the project develops. The important architectural separation is between the React frontend, FastAPI backend, model artifacts, data, and application services.

---

# 🛠️ Technology Stack

## Frontend

* React
* JavaScript / TypeScript depending on implementation
* Modern responsive UI
* Real-time dashboard components

## Backend

* Python
* FastAPI
* Uvicorn
* REST APIs
* Real-time communication where required

## Computer Vision

* MediaPipe
* Pose landmark extraction
* Biomechanical analysis
* 3D/world landmark processing where supported

## Signal Processing

* Exponential Moving Average (EMA)
* Movement smoothing
* Velocity estimation
* State-machine based repetition detection

## Machine Learning

* XGBoost
* Custom-trained dataset
* Feature engineering
* Physics-informed prediction strategy

## AI Assistant

* Gemini API

## Database / Authentication

* Application authentication
* MongoDB-backed user/application data where configured

---

# ⚙️ Installation

## 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/Burn-Ex.git
cd Burn-Ex
```

---

## 2. Backend Setup

Navigate to the backend:

```bash
cd backend
```

Create a virtual environment:

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# 🔑 Environment Configuration

Create:

```text
backend/.env
```

using:

```text
backend/.env.example
```

as the template.

Example:

```env
DATABASE_URL=your_database_connection
GEMINI_API_KEY=your_gemini_api_key
JWT_SECRET=your_secure_secret
```

Use the actual environment variables expected by the implementation.

### ⚠️ Never commit secrets

Do **not** commit:

```text
.env
firebase-key.json
API keys
database credentials
private model credentials
JWT secrets
```

The `.env` file should remain in `.gitignore`.

---

# ▶️ Running the Backend

From:

```text
backend/
```

run:

```bash
uvicorn main:app --reload --port 8000
```

The backend should become available at:

```text
http://127.0.0.1:8000
```

API documentation is normally available through FastAPI at:

```text
http://127.0.0.1:8000/docs
```

---

# ▶️ Running the Frontend

Open another terminal:

```bash
cd frontend
```

Install dependencies:

```bash
npm install
```

Start the development server:

```bash
npm run dev
```

The frontend should normally be available at:

```text
http://localhost:5174
```

---

# 🧪 Development Workflow

A typical development workflow is:

```text
1. Start MongoDB / configured database
             ↓
2. Start FastAPI
             ↓
3. Load trained model
             ↓
4. Start React
             ↓
5. Login
             ↓
6. Open Live Studio
             ↓
7. Enable camera
             ↓
8. Select exercise
             ↓
9. Start workout
             ↓
10. Real-time inference
             ↓
11. Store workout result
             ↓
12. Display progress
```

---

# 🧠 Model Inference Workflow

Burn-Ex separates model training from production inference.

### Training

```text
Self-Generated Dataset
        ↓
Data Cleaning
        ↓
Feature Engineering
        ↓
Train / Validation Split
        ↓
XGBoost Training
        ↓
Model Evaluation
        ↓
Model Artifact
```

### Production

```text
Camera
   ↓
Pose Detection
   ↓
EMA
   ↓
Feature Extraction
   ↓
Pre-trained Model
   ↓
Prediction
```

The production application should **not retrain the model every time the application starts**.

---

# 📊 Example Live Inference

A hypothetical push-up session might produce:

```text
Exercise             Push-Up

FPS                  29.8

Completed Reps       15
Valid Reps           13
Faulty Reps           2

Joint Angle          142°
Average ROM           79°
Torso Inclination      8°

Form Score            91%

Burn Rate             7.3 kcal/min
Total Calories       34.8 kcal
```

These values are intended to represent the type of telemetry produced by the system; actual values depend on the user's movement and model inference.

---

# 🔬 Engineering Principles

Burn-Ex follows several important engineering principles.

### 1. No fake AI

The Live Studio should never use random or hard-coded values for model outputs.

### 2. Model-first inference

The frontend visualizes model output instead of pretending to perform ML itself.

### 3. Physics-informed prediction

The ML model works alongside a physiological baseline instead of being treated as an unconstrained calorie oracle.

### 4. Signal processing before prediction

Raw pose coordinates are filtered before calculating movement features.

### 5. Real-time architecture

The Live Studio is designed for continuous inference rather than post-workout analysis only.

### 6. Separation of AI responsibilities

```text
Computer Vision + ML
        ↓
Movement Intelligence

Gemini
        ↓
Conversational Intelligence
```

### 7. Privacy by design

Camera-based movement analysis should remain within the application's controlled processing pipeline.

---

# 🧩 Planned Roadmap

Burn-Ex is being developed toward a complete AI fitness ecosystem.

### Phase 1 — Core Intelligence

* [x] Pose estimation
* [x] Biomechanical feature extraction
* [x] EMA filtering
* [x] Rep detection
* [x] Form analysis
* [x] Custom ML model
* [x] Energy estimation

### Phase 2 — Fitness Platform

* [x] User authentication
* [x] User profiles
* [x] Workout dashboard
* [x] Progress tracking
* [x] Nutrition planning
* [x] AI Coach
* [x] Live Studio

### Phase 3 — Advanced Intelligence

* [ ] More exercise models
* [ ] Improved personalized calibration
* [ ] Long-term performance modeling
* [ ] Adaptive workout generation
* [ ] Advanced movement-quality scoring
* [ ] Personalized recovery insights
* [ ] More comprehensive nutrition tracking

### Phase 4 — Production

* [ ] Model optimization
* [ ] Automated testing
* [ ] Production monitoring
* [ ] Performance benchmarking
* [ ] Scalable deployment
* [ ] Comprehensive security hardening

---

# 🎯 What Makes Burn-Ex Different?

| Traditional Fitness App          | Burn-Ex                              |
| -------------------------------- | ------------------------------------ |
| Counts repetitions               | Analyzes repetitions                 |
| Measures time                    | Measures movement                    |
| Generic calorie formulas         | Personalized energy estimation       |
| Limited form analysis            | Biomechanical form analysis          |
| Static workout tracking          | Real-time movement intelligence      |
| Generic recommendations          | Personalized fitness ecosystem       |
| External fitness data dependency | Custom movement dataset              |
| Camera as optional input         | Camera-powered movement intelligence |
| Post-workout insights            | Real-time feedback                   |

---

# 🧪 Testing

Backend tests are maintained under:

```text
backend/tests/
```

Run the test suite using the project's configured testing framework.

For a Python/pytest setup:

```bash
pytest
```

Recommended testing areas include:

* Authentication
* API endpoints
* Model loading
* Feature extraction
* Pose processing
* Rep counting
* EMA filtering
* Energy estimation
* Database operations
* Live inference
* Frontend/backend integration

---

# 🔒 Security

Before deploying Burn-Ex:

* Never commit API keys.
* Never commit `.env`.
* Never commit private credentials.
* Validate user input.
* Protect authenticated endpoints.
* Configure CORS appropriately.
* Use HTTPS in production.
* Secure database credentials.
* Validate uploaded/requested data.
* Apply appropriate rate limiting to external AI APIs.

For Gemini:

```text
Frontend
   ❌
   │
   │ Do not expose secret API key
   │
Backend
   ↓
Gemini API
```

The Gemini API key should be stored server-side whenever the architecture supports it.

---

# 🤝 Contributing

Contributions are welcome.

### Development process

```bash
git checkout -b feature/your-feature
```

Make your changes, test them, and commit:

```bash
git add .
git commit -m "feat: add your feature"
```

Push the branch:

```bash
git push origin feature/your-feature
```

Then create a Pull Request.

### Recommended commit format

```text
feat: add squat analysis
fix: resolve live inference connection
refactor: improve pose feature extraction
docs: update installation guide
test: add rep counting tests
perf: optimize frame processing
```

---

# 📜 License

This project is distributed under the license specified in the repository's `LICENSE` file.

---

# 👨‍💻 Project

**Burn-Ex — AI-Powered Fitness Intelligence**

> **Move Better. Burn Smarter.**

Built with:

```text
Computer Vision
        +
Biomechanics
        +
Signal Processing
        +
Machine Learning
        +
Generative AI
        +
Personalized Fitness
```

The goal is simple:

> **Don't just count the movement. Understand the movement.**

---

## ⭐ If You Find This Project Interesting

Give the repository a ⭐ and follow the development of Burn-Ex as it evolves from an AI-powered exercise analyzer into a complete personalized fitness platform.

```text
┌──────────────────────────────────────────────┐
│                                              │
│                  BURN-EX                     │
│                                              │
│          MOVE BETTER. BURN SMARTER.          │
│                                              │
│     Computer Vision • ML • Fitness AI        │
│                                              │
└──────────────────────────────────────────────┘
```
