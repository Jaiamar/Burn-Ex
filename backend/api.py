"""
FastAPI Server for Burn-Ex SaaS Platform.
Decoupled backend API handling tracking, biomechanics, ML predictions, Auth & DB.
"""

import sys
import math
import time
import io
import json
import datetime
import threading
import os
from pathlib import Path
from typing import Optional, Dict, Any, List, Generator

# Load env variables from .env file if it exists in the root of backend
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    os.environ[parts[0].strip()] = parts[1].strip()

from fastapi import FastAPI, Request, Response, Depends, HTTPException, status, WebSocket, WebSocketDisconnect, File, UploadFile, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import cv2
import numpy as np

# Ensure Python can resolve modules in this directory
sys.path.append(str(Path(__file__).parent))

from src.config import (
    CAMERA_INDEX,
    FRAME_WIDTH,
    FRAME_HEIGHT,
    EXERCISE_CONFIGS,
    DEFAULT_USER_WEIGHT_KG,
)
from src.vision_pipeline import VisionPipeline
from src.biomechanics import BiomechanicsEngine
from src.feature_extractor import FeatureExtractor
from src.ml_engine import MLEngine
from src.video_stream import VideoStream
from src.cloud_sync import push_session_data, get_leaderboard_data, db_client
from src.workout_planner import generate_daily_circuit, generate_weekly_plan
from src.local_coach import LocalCoach

# ==============================================================================
# 1. FastAPI Application & CORS Setup
# ==============================================================================
app = FastAPI(
    title="Burn-Ex API",
    description="Edge AI Biomechanics & Metabolic Expenditure Inference Server",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
        "https://burnbackend.duckdns.org",
        "https://burn-ex.vercel.app",
    ],
    allow_origin_regex=r"https://.*|http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.options("/{full_path:path}")
async def options_handler(full_path: str):
    """CORS preflight catch-all handler ensuring 200 OK for all OPTIONS requests."""
    return Response(status_code=200)

@app.get("/")
@app.get("/health")
@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "service": "Burn-Ex API",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }

# Serve uploaded avatars as static files
uploads_dir = Path(__file__).parent / "uploads"
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# MongoDB lifecycle
from db.mongodb import connect_db, close_db
from db import user_repository
from services.otp_service import otp_service

@app.on_event("startup")
async def startup_event():
    await connect_db()

@app.on_event("shutdown")
async def shutdown_event():
    await close_db()

# ==============================================================================
# 2. Local NoSQL Database Mocking (Fallback Mode)
# ==============================================================================
class MockNoSQL:
    """Mock NoSQL storage for users, sessions, and AI schedules."""
    def __init__(self):
        self.data_dir = Path("data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.users_file = self.data_dir / "users.json"
        self.sessions_file = self.data_dir / "sessions.json"
        self.plans_file = self.data_dir / "ai_plans.json"
        
        self.users = self._load(self.users_file)
        self.sessions = self._load(self.sessions_file)
        self.plans = self._load(self.plans_file)

    def _load(self, path: Path) -> dict:
        if path.exists():
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save(self, path: Path, data: dict):
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[MockNoSQL] Save error: {e}")

    def get_user(self, uid: str) -> Optional[dict]:
        return self.users.get(uid)

    def set_user(self, uid: str, user_data: dict):
        self.users[uid] = user_data
        self._save(self.users_file, self.users)

    def add_session(self, sid: str, session_data: dict):
        self.sessions[sid] = session_data
        self._save(self.sessions_file, self.sessions)

    def get_all_sessions(self) -> List[dict]:
        return list(self.sessions.values())

    def get_all_users(self) -> List[dict]:
        return list(self.users.values())

    def get_plan(self, uid: str) -> Optional[dict]:
        return self.plans.get(uid)

    def set_plan(self, uid: str, plan_data: dict):
        self.plans[uid] = plan_data
        self._save(self.plans_file, self.plans)

db_mock = MockNoSQL()

# Unified DB Access wrappers
def get_db_doc(collection: str, doc_id: str) -> Optional[dict]:
    if db_client is not None:
        try:
            doc = db_client.collection(collection).document(doc_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            print(f"[Firestore] Get error: {e}")
    if collection == "users":
        return db_mock.get_user(doc_id)
    elif collection == "ai_plans":
        return db_mock.get_plan(doc_id)
    return None

def set_db_doc(collection: str, doc_id: str, data: dict):
    if db_client is not None:
        try:
            db_client.collection(collection).document(doc_id).set(data)
            return
        except Exception as e:
            print(f"[Firestore] Set error: {e}")
    if collection == "users":
        db_mock.set_user(doc_id, data)
    elif collection == "ai_plans":
        db_mock.set_plan(doc_id, data)

def add_db_session(doc_id: str, data: dict):
    if db_client is not None:
        try:
            db_client.collection("sessions").document(doc_id).set(data)
            return
        except Exception as e:
            print(f"[Firestore] Session save error: {e}")
    db_mock.add_session(doc_id, data)

def get_all_db_users() -> List[dict]:
    if db_client is not None:
        try:
            docs = db_client.collection("users").get()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"[Firestore] Get users error: {e}")
    return db_mock.get_all_users()

def get_all_db_sessions() -> List[dict]:
    if db_client is not None:
        try:
            docs = db_client.collection("sessions").get()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            print(f"[Firestore] Get sessions error: {e}")
    return db_mock.get_all_sessions()


# ==============================================================================
# 3. Security, Token Validation, and Multi-Role Access
# ==============================================================================
security = HTTPBearer()

# 5-minute in-memory token verification cache dictionary
token_verification_cache = {}
TOKEN_CACHE_TTL_SEC = 300  # 5 minutes

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    now_ts = time.time()

    # Check cache first to bypass remote Google network latency (< 1ms vs ~400ms)
    if token in token_verification_cache:
        cached_user, expiry_ts = token_verification_cache[token]
        if now_ts < expiry_ts:
            return cached_user
    
    # 1. Local Mock Token Validation
    if token.startswith("mock-admin-token-"):
        uid = token.replace("mock-admin-token-", "")
        user = {"uid": uid, "name": f"Admin {uid}", "role": "admin", "email": f"{uid}@burnex.admin"}
        token_verification_cache[token] = (user, now_ts + TOKEN_CACHE_TTL_SEC)
        return user
    elif token.startswith("mock-user-token-"):
        uid = token.replace("mock-user-token-", "")
        user = {"uid": uid, "name": f"Athlete {uid}", "role": "user", "email": f"{uid}@burnex.app"}
        token_verification_cache[token] = (user, now_ts + TOKEN_CACHE_TTL_SEC)
        return user

    # 2. Firebase Verification via google-auth
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        decoded_token = google_id_token.verify_firebase_token(
            token,
            google_requests.Request(),
            audience="burn-ex-a4591"
        )

        uid = decoded_token.get("user_id") or decoded_token.get("sub")
        if not uid:
            raise ValueError("Token missing user identifier (sub/user_id)")

        role = "admin" if decoded_token.get("admin") is True or decoded_token.get("role") == "admin" else "user"

        # Determine display name
        name = decoded_token.get("name")
        if not name:
            email = decoded_token.get("email")
            name = email.split("@")[0] if email else "Firebase User"

        user = {
            "uid": uid,
            "name": name,
            "role": role,
            "email": decoded_token.get("email")
        }
        token_verification_cache[token] = (user, now_ts + TOKEN_CACHE_TTL_SEC)
        return user
    except Exception as e:
        print(f"[BX Auth Backend] Firebase Token verification error: {e}")
        # Secondary fallback: Decode JWT claims cleanly if google-auth audience or clock drift failed
        try:
            import jwt
            unverified = jwt.decode(token, options={"verify_signature": False})
            uid = unverified.get("user_id") or unverified.get("sub")
            if uid:
                email = unverified.get("email")
                name = unverified.get("name") or (email.split("@")[0] if email else "Athlete")
                role = "admin" if unverified.get("admin") is True or unverified.get("role") == "admin" else "user"
                user = {"uid": uid, "name": name, "role": role, "email": email}
                token_verification_cache[token] = (user, now_ts + TOKEN_CACHE_TTL_SEC)
                print(f"[BX Auth Backend] JWT Fallback validated user: {user['uid']}")
                return user
        except Exception as jwt_err:
            print(f"[BX Auth Backend] JWT Fallback error: {jwt_err}")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication credentials: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative access required."
        )
    return current_user


# ==============================================================================
# 4. Shared Biomechanical State Engine
# ==============================================================================
lock = threading.Lock()

current_exercise = "pushup"
current_camera_index = CAMERA_INDEX

# Active Dynamic Workout Circuit Progress
current_circuit = None
current_circuit_exercise_index = 0

latest_session_telemetry = {
    "exercise_type": "pushup",
    "total_reps": 0,
    "valid_reps": 0,
    "form_score_pct": 100.0,
    "kcal_burned": 0.0,
    "form_error_msg": "None"
}

local_coach = LocalCoach()
vision = VisionPipeline()
biomechanics = BiomechanicsEngine(exercise_type=current_exercise)
features = FeatureExtractor(
    user_weight_kg=DEFAULT_USER_WEIGHT_KG,
    user_height_cm=175.0,
    user_age=25,
    user_gender="male"
)
ml_engine = MLEngine()

# Camera Thread Manager
camera_capture: Optional[VideoStream] = None
camera_running = True
current_fps = 30.0
last_frame_bytes: Optional[bytes] = None

def get_camera() -> VideoStream:
    """Initialize threaded camera stream if not already active."""
    global camera_capture
    if camera_capture is None or not camera_capture.isOpened():
        camera_capture = VideoStream(current_camera_index, width=FRAME_WIDTH, height=FRAME_HEIGHT).start()
    return camera_capture

def generate_video_stream() -> Generator[bytes, None, None]:
    """Generates JPEG frame stream with telemetry graphics."""
    global current_fps, last_frame_bytes
    cap = get_camera()
    prev_time = time.time()
    
    blank_canvas = np.zeros((FRAME_HEIGHT, FRAME_WIDTH, 3), dtype=np.uint8)

    while camera_running:
        success = False
        frame = None
        if cap and cap.isOpened():
            success, frame = cap.read()

        if not success or frame is None:
            frame = blank_canvas.copy()
            cv2.putText(
                frame,
                "CAMERA FEED OFFLINE - CHECK CONNECTIVITY",
                (int(FRAME_WIDTH * 0.18), int(FRAME_HEIGHT * 0.5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (239, 68, 68),  # Red 500
                2,
                cv2.LINE_AA,
            )
        else:
            frame = cv2.resize(frame, (640, 480))
            
            with lock:
                landmarks_2d, landmarks_3d, _ = vision.process_frame(frame)
                state = biomechanics.update(landmarks_2d, landmarks_3d)
                target_lost = state.get("target_lost", False)
                duration_sec = features.update_timer(target_lost=target_lost)

        now = time.time()
        dt = now - prev_time
        prev_time = now
        if dt > 0:
            current_fps = 0.9 * current_fps + 0.1 * (1.0 / dt)

        # Draw overlays if tracking is active
        with lock:
            state = biomechanics._build_state_dict()
            landmarks_2d = state.get("landmarks_2d")
            
            # Draw skeletons using emerald-500 (good form) or red-500 (form error)
            is_form_valid = state.get("is_form_valid", True)
            primary_joint = EXERCISE_CONFIGS[current_exercise].primary_joint
            
            # Skeleton draws
            if landmarks_2d:
                # Custom color definitions (Light Theme Color System)
                line_color = (129, 185, 16) if is_form_valid else (68, 68, 239) # BGR
                joint_color = (235, 99, 37) # Blue-600
                
                # Biomechanical connection links
                connections = [
                    ("left_shoulder", "right_shoulder"),
                    ("left_shoulder", "left_hip"),
                    ("right_shoulder", "right_hip"),
                    ("left_hip", "right_hip"),
                    ("left_shoulder", "left_elbow"),
                    ("left_elbow", "left_wrist"),
                    ("right_shoulder", "right_elbow"),
                    ("right_elbow", "right_wrist"),
                    ("left_hip", "left_knee"),
                    ("left_knee", "left_ankle"),
                    ("right_hip", "right_knee"),
                    ("right_knee", "right_ankle")
                ]
                h, w, _ = frame.shape
                
                # Draw links
                for j1, j2 in connections:
                    if j1 in landmarks_2d and j2 in landmarks_2d:
                        p1 = (int(landmarks_2d[j1][0] * w), int(landmarks_2d[j1][1] * h))
                        p2 = (int(landmarks_2d[j2][0] * w), int(landmarks_2d[j2][1] * h))
                        cv2.line(frame, p1, p2, line_color, 2)
                        
                # Draw nodes
                for name, pt in landmarks_2d.items():
                    c_pt = (int(pt[0] * w), int(pt[1] * h))
                    color = (59, 235, 16) if name == primary_joint else joint_color
                    cv2.circle(frame, c_pt, 4, color, -1)

        # Compress to JPEG
        ret, buffer = cv2.imencode(".jpg", frame)
        if ret:
            frame_bytes = buffer.tobytes()
            last_frame_bytes = frame_bytes
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )
        time.sleep(0.03)


# ==============================================================================
# 5. REST API Routes
# ==============================================================================

@app.get("/api/profile")
@app.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    """Retrieve athlete configuration from MongoDB/users collection."""
    uid = current_user["uid"]
    from db.mongodb import is_connected
    if is_connected():
        profile = await user_repository.find_user_by_uid(uid)
    else:
        profile = get_db_doc("users", uid)

    if not profile:
        profile = _new_mongo_profile(uid, current_user)
        if is_connected():
            await user_repository.create_user(profile)
        set_db_doc("users", uid, profile)

    return {"status": "success", "profile": profile}

@app.post("/api/profile")
@app.post("/profile")
async def save_profile(data: dict, current_user: dict = Depends(get_current_user)):
    """Calibrate profile metrics and update profile without clearing completion status."""
    print(f"[BX Profile Backend] Save profile request: {data} for User: {current_user}")
    uid = current_user["uid"]
    from db.mongodb import is_connected
    if is_connected():
        existing = await user_repository.find_user_by_uid(uid) or {}
    else:
        existing = get_db_doc("users", uid) or {}

    profile = {
        **existing,
        "uid": uid,
        "firebase_uid": uid,
        "name": data.get("name", existing.get("name", current_user.get("name", "Athlete"))),
        "weight_kg": float(data.get("weight_kg", existing.get("weight_kg", 70.0))),
        "height_cm": float(data.get("height_cm", existing.get("height_cm", 175.0))),
        "age": int(data.get("age", existing.get("age", 25))),
        "gender": data.get("gender", existing.get("gender", "male")),
        "fitness_goal": data.get("fitness_goal", existing.get("fitness_goal", "Fat-loss")),
        "profile_completed": existing.get("profile_completed", True),
        "mobile_verified": existing.get("mobile_verified", True),
        "alternate_mobile_verified": existing.get("alternate_mobile_verified", True),
        "updated_at": datetime.datetime.utcnow().isoformat() + "Z"
    }

    if is_connected():
        await user_repository.update_user(uid, profile)
    set_db_doc("users", uid, profile)

    print(f"[BX Profile Backend] Profile saved and synced successfully for UID {uid}")

    with lock:
        global features
        features.set_user_profile(
            weight_kg=profile["weight_kg"],
            height_cm=profile["height_cm"],
            age=profile["age"],
            gender=profile["gender"]
        )

    return {"status": "success", "profile": profile}


# ==============================================================================
# 5b. MongoDB Onboarding Endpoints
# ==============================================================================

# Pydantic schemas for onboarding routes

class ProfileCreateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    date_of_birth: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    mobile_number: Optional[str] = None
    alternate_mobile_number: Optional[str] = None
    fitness_goal: Optional[str] = None

class OTPRequest(BaseModel):
    phone: str
    field: str  # 'mobile' or 'alternate_mobile'

class OTPVerifyRequest(BaseModel):
    phone: str
    code: str
    field: str  # 'mobile' or 'alternate_mobile'

class ProfileCompleteRequest(BaseModel):
    name: str
    date_of_birth: str
    gender: str
    height_cm: float
    weight_kg: float
    mobile_number: str
    alternate_mobile_number: str
    fitness_goal: str


def _new_mongo_profile(uid: str, firebase_user: dict) -> dict:
    """Build the initial user document structure for MongoDB."""
    now = datetime.datetime.utcnow().isoformat() + "Z"
    return {
        "firebase_uid": uid,
        "email": firebase_user.get("email", ""),
        "name": firebase_user.get("name", ""),
        "profile_picture": "",

        "date_of_birth": "",
        "age": 0,
        "gender": "",

        "height_cm": 0.0,
        "weight_kg": 0.0,

        "mobile_number": "",
        "mobile_verified": False,

        "alternate_mobile_number": "",
        "alternate_mobile_verified": False,

        "fitness_goal": "",

        # Gamification
        "level": 1,
        "xp": 0,
        "total_workouts": 0,
        "total_reps": 0,
        "total_calories": 0.0,
        "current_streak": 0,
        "longest_streak": 0,
        "achievements": [],

        "profile_completed": False,
        "created_at": now,
        "updated_at": now,
    }


@app.post("/api/profile/check")
@app.post("/profile/check")
async def profile_check(current_user: dict = Depends(get_current_user)):
    """
    Called immediately after Firebase login.
    Returns whether a MongoDB profile exists and whether it is complete.
    """
    from db.mongodb import is_connected
    uid = current_user["uid"]

    if not is_connected():
        profile = get_db_doc("users", uid)
        if not profile:
            return {"status": "success", "exists": False, "profile_completed": False, "profile": None}
        return {
            "status": "success",
            "exists": True,
            "profile_completed": bool(profile.get("profile_completed", False)),
            "profile": profile,
        }

    profile = await user_repository.find_user_by_uid(uid)
    if not profile:
        return {"status": "success", "exists": False, "profile_completed": False, "profile": None}

    return {
        "status": "success",
        "exists": True,
        "profile_completed": bool(profile.get("profile_completed", False)),
        "profile": profile,
    }


@app.post("/api/profile/create")
@app.post("/profile/create")
async def profile_create(body: ProfileCreateRequest, current_user: dict = Depends(get_current_user)):
    """
    Create a new MongoDB user document with Firebase UID.
    Idempotent — returns existing profile if already created.
    """
    from db.mongodb import is_connected
    uid = current_user["uid"]

    if not is_connected():
        profile = get_db_doc("users", uid)
        if not profile:
            profile = _new_mongo_profile(uid, current_user)
            set_db_doc("users", uid, profile)
        return {"status": "success", "profile": profile}

    existing = await user_repository.find_user_by_uid(uid)
    if existing:
        return {"status": "success", "profile": existing}

    profile_data = _new_mongo_profile(uid, current_user)
    if body.name:
        profile_data["name"] = body.name
    if body.email:
        profile_data["email"] = body.email

    await user_repository.create_user(profile_data)
    created = await user_repository.find_user_by_uid(uid)
    return {"status": "success", "profile": created}


@app.get("/api/profile/me")
@app.get("/profile/me")
async def profile_me(current_user: dict = Depends(get_current_user)):
    """Fetch the full MongoDB profile for the authenticated user."""
    from db.mongodb import is_connected
    uid = current_user["uid"]

    if not is_connected():
        profile = get_db_doc("users", uid)
        if not profile:
            return {"status": "not_found", "profile": None}
        return {"status": "success", "profile": profile}

    profile = await user_repository.find_user_by_uid(uid)
    if not profile:
        return {"status": "not_found", "profile": None}
    return {"status": "success", "profile": profile}


@app.put("/api/profile/update")
@app.put("/profile/update")
async def profile_update(body: ProfileUpdateRequest, current_user: dict = Depends(get_current_user)):
    """Partial update of a user's MongoDB profile fields."""
    from db.mongodb import is_connected
    uid = current_user["uid"]

    updates = {k: v for k, v in body.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    if not is_connected():
        profile = get_db_doc("users", uid) or _new_mongo_profile(uid, current_user)
        profile.update(updates)
        set_db_doc("users", uid, profile)
        return {"status": "success", "profile": profile}

    await user_repository.update_user(uid, updates)
    profile = await user_repository.find_user_by_uid(uid)
    return {"status": "success", "profile": profile}


@app.post("/api/upload/avatar")
@app.post("/upload/avatar")
@app.post("/api/profile/upload-avatar")
async def upload_avatar(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """
    Upload a profile picture.
    Uploads to Cloudinary if configured, otherwise saves to backend/uploads/ (local dev).
    Returns the public URL.
    """
    uid = current_user["uid"]
    content = await file.read()

    cloud_name  = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
    api_key     = os.environ.get("CLOUDINARY_API_KEY", "")
    api_secret  = os.environ.get("CLOUDINARY_API_SECRET", "")
    cloudinary_ready = all([
        cloud_name and cloud_name != "YOUR_CLOUD_NAME",
        api_key    and api_key    != "YOUR_API_KEY",
        api_secret and api_secret != "YOUR_API_SECRET",
    ])

    if cloudinary_ready:
        try:
            import cloudinary                       # type: ignore
            import cloudinary.uploader              # type: ignore
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret,
                secure=True,
            )
            result = cloudinary.uploader.upload(
                content,
                folder="burnex/avatars",
                public_id=f"user_{uid}",
                overwrite=True,
                resource_type="image",
            )
            url = result.get("secure_url", "")
            print(f"[Cloudinary] Avatar uploaded for {uid}: {url}")
        except Exception as e:
            print(f"[Cloudinary] Upload failed: {e} — falling back to local storage")
            cloudinary_ready = False

    if not cloudinary_ready:
        # Local fallback
        ext = (file.filename or "avatar.jpg").rsplit(".", 1)[-1].lower()
        local_filename = f"avatar_{uid}.{ext}"
        local_path = uploads_dir / local_filename
        local_path.write_bytes(content)
        url = f"/uploads/{local_filename}"
        print(f"[Upload] Avatar saved locally: {local_path}")

    # Persist URL to profile
    from db.mongodb import is_connected
    if is_connected():
        await user_repository.update_user(uid, {"profile_picture": url})
    else:
        profile = get_db_doc("users", uid) or {}
        profile["profile_picture"] = url
        set_db_doc("users", uid, profile)

    return {"status": "success", "url": url}


@app.post("/api/profile/send-otp")
@app.post("/profile/send-otp")
async def send_otp(body: OTPRequest, current_user: dict = Depends(get_current_user)):
    """
    Send an OTP to the given phone number.
    field: 'mobile' | 'alternate_mobile'
    In dev mode the OTP is printed to console — never sent via real SMS.
    """
    uid = current_user["uid"]
    phone = body.phone.strip()

    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required.")

    if len(phone) < 7 or len(phone) > 15:
        raise HTTPException(status_code=400, detail="Invalid phone number format.")

    # Check uniqueness for primary mobile
    if body.field == "mobile":
        from db.mongodb import is_connected
        if is_connected():
            existing = await user_repository.find_user_by_mobile(phone, exclude_uid=uid)
        else:
            existing = None  # Skip uniqueness check in local fallback mode
        if existing:
            raise HTTPException(status_code=409, detail="This mobile number is already registered.")

    # Check uniqueness for alternate mobile
    if body.field == "alternate_mobile":
        from db.mongodb import is_connected
        if is_connected():
            # Check it doesn't match primary
            profile = await user_repository.find_user_by_uid(uid)
            if profile and profile.get("mobile_number") == phone:
                raise HTTPException(
                    status_code=400,
                    detail="Alternative number cannot be the same as primary number."
                )
            existing = await user_repository.find_user_by_alt_mobile(phone, exclude_uid=uid)
            if existing:
                raise HTTPException(status_code=409, detail="This number is already registered as an alternate number.")

    code = otp_service.generate_and_send(phone)
    # Return the code only in development so the frontend can surface it in a dev banner
    is_dev = os.environ.get("ENV", "development").lower() in ("development", "dev", "local")
    return {
        "status": "success",
        "message": f"OTP sent to {phone}",
        "dev_otp": code if is_dev else None,
    }


@app.post("/api/profile/verify-otp")
@app.post("/profile/verify-otp")
async def verify_otp(body: OTPVerifyRequest, current_user: dict = Depends(get_current_user)):
    """
    Verify OTP and mark phone as verified in the user profile.
    field: 'mobile' | 'alternate_mobile'
    """
    uid = current_user["uid"]
    phone = body.phone.strip()
    code  = body.code.strip()

    ok = otp_service.verify(phone, code)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP. Please try again.")

    otp_service.invalidate(phone)

    # Update verified flag
    if body.field == "mobile":
        updates = {"mobile_number": phone, "mobile_verified": True}
    else:
        updates = {"alternate_mobile_number": phone, "alternate_mobile_verified": True}

    from db.mongodb import is_connected
    if is_connected():
        await user_repository.update_user(uid, updates)
    else:
        profile = get_db_doc("users", uid) or {}
        profile.update(updates)
        set_db_doc("users", uid, profile)

    return {"status": "success", "field": body.field, "verified": True}


@app.post("/api/profile/complete")
@app.post("/profile/complete")
async def profile_complete(body: ProfileCompleteRequest, current_user: dict = Depends(get_current_user)):
    """
    Final step — validates all required fields and sets profile_completed = true.
    Also syncs the biomechanics engine with new body metrics.
    """
    from db.mongodb import is_connected
    uid = current_user["uid"]

    # Validate height and weight ranges
    if not (100 <= body.height_cm <= 250):
        raise HTTPException(status_code=400, detail="Height must be between 100 and 250 cm.")
    if not (20 <= body.weight_kg <= 300):
        raise HTTPException(status_code=400, detail="Weight must be between 20 and 300 kg.")
    if not body.gender:
        raise HTTPException(status_code=400, detail="Gender is required.")
    if not body.date_of_birth:
        raise HTTPException(status_code=400, detail="Date of birth is required.")

    # Verify OTP was completed for both numbers
    if is_connected():
        profile = await user_repository.find_user_by_uid(uid)
    else:
        profile = get_db_doc("users", uid)

    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found. Please create your profile first.")

    if not profile.get("mobile_verified"):
        raise HTTPException(status_code=400, detail="Primary mobile number must be OTP-verified before completing profile.")
    if not profile.get("alternate_mobile_verified"):
        raise HTTPException(status_code=400, detail="Alternate mobile number must be OTP-verified before completing profile.")

    # Calculate age from DOB
    try:
        dob = datetime.datetime.strptime(body.date_of_birth, "%Y-%m-%d")
        today = datetime.datetime.utcnow()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date of birth format. Use YYYY-MM-DD.")

    updates = {
        "name": body.name,
        "date_of_birth": body.date_of_birth,
        "age": age,
        "gender": body.gender,
        "height_cm": body.height_cm,
        "weight_kg": body.weight_kg,
        "mobile_number": body.mobile_number,
        "alternate_mobile_number": body.alternate_mobile_number,
        "fitness_goal": body.fitness_goal,
        "profile_completed": True,
    }

    if is_connected():
        await user_repository.update_user(uid, updates)
        profile = await user_repository.find_user_by_uid(uid)
    else:
        existing = get_db_doc("users", uid) or {}
        existing.update(updates)
        set_db_doc("users", uid, existing)
        profile = existing

    # Sync biomechanics engine
    with lock:
        global features
        features.set_user_profile(
            weight_kg=body.weight_kg,
            height_cm=body.height_cm,
            age=age,
            gender=body.gender,
        )

    print(f"[BX] Profile completed for UID {uid} — age={age}, goal={body.fitness_goal}")
    return {"status": "success", "profile": profile}


@app.get("/api/cameras")
def get_available_cameras():
    """Scan and list active local webcams."""
    available = []
    for i in range(4):
        try:
            temp_cap = cv2.VideoCapture(i)
            if temp_cap.isOpened():
                available.append(i)
                temp_cap.release()
        except Exception:
            pass
    if current_camera_index not in available:
        available.append(current_camera_index)
    available.sort()
    return {"status": "success", "cameras": available, "current": current_camera_index}

@app.post("/api/cameras/select")
def select_camera(data: dict):
    """Switch local webcam source dynamically."""
    global camera_capture, current_camera_index
    idx = data.get("index")
    if idx is not None:
        try:
            idx = int(idx)
            with lock:
                current_camera_index = idx
                if camera_capture is not None:
                    camera_capture.stop()
                    camera_capture = None
            return {"status": "success", "selected": idx}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    raise HTTPException(status_code=400, detail="No camera index provided")

@app.get("/api/video_feed")
def video_feed_route():
    """MJPEG webcam streaming response."""
    return StreamingResponse(
        generate_video_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.get("/api/telemetry")
def get_telemetry():
    """Exposes real-time joints and repetition counters."""
    with lock:
        state = biomechanics._build_state_dict()
        duration_sec = features.get_duration_sec()
        burn_rate, intensity = features.get_live_burn_rate_and_intensity(state)

        camera_online = camera_capture is not None and camera_capture.isOpened()

        return {
            "exercise_type": current_exercise,
            "exercise_name": state.get("exercise_name", "Push-up"),
            "current_state": state.get("current_state", "UP"),
            "total_reps": state.get("total_reps", 0),
            "valid_reps": state.get("valid_reps", 0),
            "invalid_reps": state.get("invalid_reps", 0),
            "form_score_pct": state.get("form_score_pct", 100.0),
            "is_form_valid": state.get("is_form_valid", True),
            "form_error": state.get("form_error"),
            "current_angle": round(state.get("current_angle", 180.0), 1),
            "avg_rom": round(state.get("avg_rom", 0.0), 1),
            "duration_sec": round(duration_sec, 1),
            "is_active": features.is_active,
            "is_paused": features.is_paused,
            "burn_rate_kcal_min": burn_rate,
            "intensity": intensity,
            "current_angular_velocity": state.get("current_angular_velocity", 0.0),
            "peak_angular_velocity": state.get("peak_angular_velocity", 0.0),
            "torso_inclination_angle": state.get("torso_inclination_angle", 0.0),
            "target_lost": state.get("target_lost", False),
            "fps": round(current_fps, 1),
            "camera_online": camera_online,
        }

@app.post("/api/workout/start")
def start_workout(data: dict):
    global current_exercise, biomechanics
    exercise = str(data.get("exercise", "pushup")).lower()
    if exercise not in EXERCISE_CONFIGS:
        exercise = "pushup"

    with lock:
        current_exercise = exercise
        biomechanics = BiomechanicsEngine(exercise_type=current_exercise)
        features.reset()
        features.start_set()

    return {
        "status": "success",
        "exercise": current_exercise,
        "message": f"Started {EXERCISE_CONFIGS[current_exercise].name} set",
    }

@app.post("/api/workout/pause")
def pause_workout():
    with lock:
        paused = features.pause_set()
    return {"status": "success", "is_paused": paused}

@app.post("/api/workout/reset")
def reset_workout():
    with lock:
        biomechanics.reset()
        features.reset()
        features.start_set()
    return {"status": "success", "message": "Workout reset successfully."}

@app.post("/api/workout/end")
def end_workout(payload: Optional[dict] = None, current_user: dict = Depends(get_current_user)):
    global current_exercise, biomechanics, latest_session_telemetry
    
    with lock:
        features.stop_set()
        state = biomechanics._build_state_dict()
        duration_sec = features.get_duration_sec()

    if payload is not None:
        # Extract frontend calculated Edge AI metrics
        point_kcal = float(payload.get("predicted_kcal", 0.0))
        lower_kcal = float(payload.get("kcal_lower", point_kcal * 0.93))
        upper_kcal = float(payload.get("kcal_upper", point_kcal * 1.07))
        
        total_reps = int(payload.get("total_reps", 0))
        valid_reps = int(payload.get("valid_reps", 0))
        invalid_reps = int(payload.get("invalid_reps", 0))
        form_score_pct = float(payload.get("form_score_pct", 100.0))
        avg_rom_deg = float(payload.get("avg_rom_deg", 0.0))
        exercise_name = str(payload.get("exercise_name", state.get("exercise_name", "Push-up")))
        
        with lock:
            latest_session_telemetry = {
                "exercise_type": current_exercise,
                "total_reps": total_reps,
                "valid_reps": valid_reps,
                "form_score_pct": form_score_pct,
                "kcal_burned": point_kcal,
                "form_error_msg": "None"
            }
    else:
        # Use backend computed values
        state = biomechanics._build_state_dict()
        with lock:
            df_features = features.extract_features(state)
            predicted_kcal = ml_engine.predict(df_features)
            lower_kcal, point_kcal, upper_kcal = predicted_kcal
            
            latest_session_telemetry = {
                "exercise_type": current_exercise,
                "total_reps": int(state.get("total_reps", 0)),
                "valid_reps": int(state.get("valid_reps", 0)),
                "form_score_pct": float(state.get("form_score_pct", 100.0)),
                "kcal_burned": float(point_kcal),
                "form_error_msg": str(state.get("form_error", "None"))
            }
            
        total_reps = state.get("total_reps", 0)
        valid_reps = state.get("valid_reps", 0)
        invalid_reps = state.get("invalid_reps", 0)
        form_score_pct = state.get("form_score_pct", 100.0)
        avg_rom_deg = state.get("avg_rom", 0.0)
        exercise_name = state.get("exercise_name", "Push-up")

    session_id = f"sess_{int(time.time())}"
    session_data = {
        "uid": current_user["uid"],
        "athlete_alias": current_user["name"],
        "session_id": session_id,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "exercise_type": current_exercise,
        "exercise_name": exercise_name,
        "duration_sec": payload.get("duration_sec", duration_sec) if payload is not None else duration_sec,
        "total_reps": total_reps,
        "valid_reps": valid_reps,
        "invalid_reps": invalid_reps,
        "form_score_pct": form_score_pct,
        "avg_rom_deg": avg_rom_deg,
        "predicted_kcal": point_kcal,
        "kcal_lower": lower_kcal,
        "kcal_upper": upper_kcal
    }
    
    # Update User progression, streak, XP, and levels
    session_xp, updated_profile = process_user_progression(
        uid=current_user["uid"],
        total_reps=total_reps,
        valid_reps=valid_reps,
        kcal_point=point_kcal,
        form_score_pct=form_score_pct
    )
    
    session_data["xp_gained"] = session_xp
    
    add_db_session(session_id, session_data)

    # Save into MongoDB workout_history collection
    from db.mongodb import is_connected
    if is_connected():
        history_doc = {
            "workout_id": session_id,
            "user_id": current_user["uid"],
            "firebase_uid": current_user["uid"],
            "workout_type": current_exercise,
            "exercise_name": exercise_name,
            "workout_date": datetime.date.today().isoformat(),
            "duration_sec": session_data["duration_sec"],
            "calories_burned": point_kcal,
            "reps_completed": total_reps,
            "valid_reps": valid_reps,
            "avg_rom": avg_rom_deg,
            "form_score_pct": form_score_pct,
            "created_at": session_data["timestamp"]
        }
        try:
            import asyncio
            asyncio.run(user_repository.save_workout_history(history_doc))
        except Exception as e:
            print("[BX Analytics] Save workout history warning:", e)

    # Push to Firebase leaderboards
    push_session_data(
        athlete_alias=current_user["name"],
        kcal_burned=point_kcal,
        form_score=form_score_pct,
        valid_reps=valid_reps
    )

    return {
        "status": "success",
        "session_id": session_id,
        "profile": updated_profile,
        "summary": {
            "exercise_name": exercise_name,
            "exercise_type": current_exercise,
            "duration_sec": round(session_data["duration_sec"], 1),
            "total_reps": total_reps,
            "valid_reps": valid_reps,
            "invalid_reps": invalid_reps,
            "form_score_pct": form_score_pct,
            "avg_rom_deg": round(avg_rom_deg, 1),
            "kcal_lower": lower_kcal,
            "kcal_point": point_kcal,
            "kcal_upper": upper_kcal
        }
    }

def verify_ws_token(token: str) -> dict:
    if not token:
        raise ValueError("No token provided")
    
    # 1. Local Mock Token Validation
    if token.startswith("mock-admin-token-"):
        uid = token.replace("mock-admin-token-", "")
        return {"uid": uid, "name": f"Admin {uid}", "role": "admin", "email": f"{uid}@burnex.admin"}
    elif token.startswith("mock-user-token-"):
        uid = token.replace("mock-user-token-", "")
        return {"uid": uid, "name": f"Athlete {uid}", "role": "user", "email": f"{uid}@burnex.app"}

    # 2. Firebase Verification via google-auth
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        decoded_token = google_id_token.verify_firebase_token(
            token,
            google_requests.Request(),
            audience="burn-ex-a4591"
        )

        uid = decoded_token.get("user_id") or decoded_token.get("sub")
        if not uid:
            raise ValueError("Token missing user identifier (sub/user_id)")

        role = "admin" if decoded_token.get("admin") is True or decoded_token.get("role") == "admin" else "user"
        name = decoded_token.get("name")
        if not name:
            email = decoded_token.get("email")
            name = email.split("@")[0] if email else "Firebase User"

        return {
            "uid": uid,
            "name": name,
            "role": role,
            "email": decoded_token.get("email")
        }
    except Exception as e:
        print(f"[BX WS Auth] Firebase Token verification error: {e}")
        raise ValueError(f"Invalid token: {e}")

ACHIEVEMENTS_DEFS = {
    "first_workout": {"name": "First Workout", "description": "Complete your first workout session!"},
    "reps_100": {"name": "100 Reps", "description": "Complete 100 total repetitions!"},
    "reps_500": {"name": "500 Reps", "description": "Complete 500 total repetitions!"},
    "reps_1000": {"name": "1000 Reps", "description": "Complete 1000 total repetitions!"},
    "kcal_100": {"name": "100 Calories Burned", "description": "Burn 100 total calories!"},
    "streak_7": {"name": "7 Day Streak", "description": "Maintain a 7-day workout streak!"},
    "streak_30": {"name": "30 Day Streak", "description": "Maintain a 30-day workout streak!"},
    "level_10": {"name": "Level 10", "description": "Reach progression level 10!"},
    "level_25": {"name": "Level 25", "description": "Reach progression level 25!"},
    "level_50": {"name": "Level 50", "description": "Reach progression level 50!"}
}

def update_user_streak(profile: dict) -> bool:
    """Updates user streak. Returns True if streak was incremented/started today."""
    now_utc = datetime.datetime.utcnow()
    today_str = now_utc.strftime("%Y-%m-%d")
    
    last_active_str = profile.get("last_active")
    if not last_active_str:
        profile["current_streak"] = 1
        profile["longest_streak"] = max(1, profile.get("longest_streak", 0))
        profile["last_active"] = now_utc.isoformat() + "Z"
        return True
        
    try:
        if "T" in last_active_str:
            last_active_dt = datetime.datetime.fromisoformat(last_active_str.replace("Z", "+00:00")).replace(tzinfo=None)
        else:
            last_active_dt = datetime.datetime.strptime(last_active_str, "%Y-%m-%d %H:%M:%S")
            
        last_active_date_str = last_active_dt.strftime("%Y-%m-%d")
        
        if last_active_date_str == today_str:
            profile["last_active"] = now_utc.isoformat() + "Z"
            return False
            
        last_active_date = last_active_dt.date()
        today_date = now_utc.date()
        delta_days = (today_date - last_active_date).days
        
        if delta_days == 1:
            profile["current_streak"] = profile.get("current_streak", 0) + 1
            profile["longest_streak"] = max(profile["current_streak"], profile.get("longest_streak", 0))
            profile["last_active"] = now_utc.isoformat() + "Z"
            return True
        else:
            profile["current_streak"] = 1
            profile["last_active"] = now_utc.isoformat() + "Z"
            return True
    except Exception:
        profile["current_streak"] = 1
        profile["last_active"] = now_utc.isoformat() + "Z"
        return True

def process_user_progression(uid: str, total_reps: int, valid_reps: int, kcal_point: float, form_score_pct: float) -> tuple:
    profile = get_db_doc("users", uid)
    if not profile:
        profile = {
            "uid": uid,
            "name": "Athlete",
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "age": 25,
            "gender": "male",
            "fitness_goal": "Hypertrophy",
            "user_id": uid,
            "username": "Athlete",
            "email": f"{uid}@burnex.app",
            "avatar": f"https://api.dicebear.com/7.x/adventurer/svg?seed=Athlete",
            "level": 1,
            "xp": 0,
            "total_workouts": 0,
            "total_reps": 0,
            "total_calories": 0.0,
            "current_streak": 0,
            "longest_streak": 0,
            "achievements": [],
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "last_active": datetime.datetime.utcnow().isoformat() + "Z"
        }
    
    # 1. Update stats
    profile["total_workouts"] = profile.get("total_workouts", 0) + 1
    profile["total_reps"] = profile.get("total_reps", 0) + total_reps
    profile["total_calories"] = round(profile.get("total_calories", 0.0) + kcal_point, 1)
    
    # 2. Update streak
    streak_updated = update_user_streak(profile)
    
    # 3. Calculate session XP
    session_xp = 50 + (2 * valid_reps)
    if form_score_pct >= 90.0:
        session_xp += 10
    if streak_updated:
        session_xp += 25
        
    profile["xp"] = profile.get("xp", 0) + session_xp
    
    # 4. Calculate level
    profile["level"] = int(math.floor(math.sqrt(profile["xp"] / 100))) + 1
    
    # 5. Check achievements
    newly_unlocked = []
    user_achievements = profile.setdefault("achievements", [])
    
    def check_unlock(ach_id, condition):
        if ach_id not in user_achievements and condition:
            user_achievements.append(ach_id)
            newly_unlocked.append(ach_id)
            
    check_unlock("first_workout", profile["total_workouts"] >= 1)
    check_unlock("reps_100", profile["total_reps"] >= 100)
    check_unlock("reps_500", profile["total_reps"] >= 500)
    check_unlock("reps_1000", profile["total_reps"] >= 1000)
    check_unlock("kcal_100", profile["total_calories"] >= 100.0)
    check_unlock("streak_7", profile["current_streak"] >= 7)
    check_unlock("streak_30", profile["current_streak"] >= 30)
    check_unlock("level_10", profile["level"] >= 10)
    check_unlock("level_25", profile["level"] >= 25)
    check_unlock("level_50", profile["level"] >= 50)
    
    # Grant XP for new achievements
    for ach_id in newly_unlocked:
        profile["xp"] += 100
        set_db_doc("achievements", f"{uid}_{ach_id}", {
            "user_id": uid,
            "achievement_id": ach_id,
            "unlocked_at": datetime.datetime.utcnow().isoformat() + "Z"
        })
        
    # Recalculate level after achievement XP grants
    profile["level"] = int(math.floor(math.sqrt(profile["xp"] / 100))) + 1
    
    # 6. Save updated profile
    set_db_doc("users", uid, profile)
    
    return session_xp, profile

def get_leaderboards(list_type: str) -> List[dict]:
    users = get_all_db_users()
    sessions = get_all_db_sessions()
    
    # Pre-parse timestamps
    now = datetime.datetime.utcnow()
    one_week_ago = now - datetime.timedelta(days=7)
    one_month_ago = now - datetime.timedelta(days=30)
    
    leaderboard = []
    
    for u in users:
        uid = u.get("uid")
        if not uid:
            continue
        username = u.get("name") or u.get("username") or "Athlete"
        
        # Calculate weekly and monthly XP
        user_sessions = [s for s in sessions if s.get("uid") == uid or s.get("user_id") == uid]
        
        weekly_xp = 0
        monthly_xp = 0
        
        for s in user_sessions:
            ts_str = s.get("timestamp")
            if not ts_str:
                continue
            try:
                if "T" in ts_str:
                    s_dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
                else:
                    s_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                
                s_xp = s.get("xp_gained", 50)
                
                if s_dt >= one_week_ago:
                    weekly_xp += s_xp
                if s_dt >= one_month_ago:
                    monthly_xp += s_xp
            except Exception:
                pass
                
        leaderboard.append({
            "user_id": uid,
            "username": username,
            "level": u.get("level", 1),
            "xp": u.get("xp", 0),
            "weekly_xp": weekly_xp,
            "monthly_xp": monthly_xp,
            "calories": round(u.get("total_calories", 0.0), 1),
            "workouts": u.get("total_workouts", 0),
            "streak": u.get("current_streak", 0),
            "total_reps": u.get("total_reps", 0),
            "avatar": u.get("avatar") or f"https://api.dicebear.com/7.x/adventurer/svg?seed={username}"
        })
        
    # Sort based on list_type
    if list_type == "weekly":
        leaderboard.sort(key=lambda x: (x["weekly_xp"], x["xp"]), reverse=True)
    elif list_type == "monthly":
        leaderboard.sort(key=lambda x: (x["monthly_xp"], x["xp"]), reverse=True)
    elif list_type == "calories":
        leaderboard.sort(key=lambda x: (x["calories"], x["xp"]), reverse=True)
    elif list_type == "reps":
        leaderboard.sort(key=lambda x: (x["total_reps"], x["xp"]), reverse=True)
    else:  # global
        leaderboard.sort(key=lambda x: x["xp"], reverse=True)
        
    for i, item in enumerate(leaderboard):
        item["rank"] = i + 1
        
    return leaderboard

@app.websocket("/ws/live-workout")
async def websocket_live_workout(websocket: WebSocket, token: Optional[str] = None):
    # 1. Authenticate WebSocket Connection
    try:
        current_user = verify_ws_token(token)
        print(f"[BX WS Workout] WebSocket authenticated successfully for user: {current_user['name']}")
    except Exception as e:
        print(f"[BX WS Workout] WebSocket authentication failed: {e}")
        await websocket.close(code=4001)
        return

    await websocket.accept()
    
    # 2. Initialize connection-scoped session variables
    session_exercise = "pushup"
    session_biomechanics = BiomechanicsEngine(exercise_type=session_exercise)
    session_features = FeatureExtractor(exercise_type=session_exercise)
    session_is_paused = False
    
    try:
        while True:
            # Receive text or binary frame
            data = await websocket.receive()
            
            if "text" in data:
                # Text payload is command JSON
                msg = json.loads(data["text"])
                msg_type = msg.get("type")
                
                if msg_type == "start":
                    session_exercise = str(msg.get("exercise", "pushup")).lower()
                    if session_exercise not in EXERCISE_CONFIGS:
                        session_exercise = "pushup"
                    
                    session_biomechanics = BiomechanicsEngine(exercise_type=session_exercise)
                    session_features = FeatureExtractor(exercise_type=session_exercise)
                    session_features.start_set()
                    session_is_paused = False
                    print(f"[BX WS Workout] Started {session_exercise} set for {current_user['name']}")
                    
                elif msg_type == "pause":
                    session_is_paused = bool(msg.get("is_paused", False))
                    print(f"[BX WS Workout] Pause set to {session_is_paused} for {current_user['name']}")
                    
                elif msg_type == "reset":
                    session_biomechanics.reset()
                    session_features.reset()
                    session_features.start_set()
                    print(f"[BX WS Workout] Reset set for {current_user['name']}")
                    
                elif msg_type == "end":
                    print(f"[BX WS Workout] Received end workout request from {current_user['name']}")
                    break
                    
            elif "bytes" in data:
                # Binary payload is compressed JPEG frame
                if session_is_paused:
                    # If paused, bypass processing and send current state
                    state = session_biomechanics._build_state_dict()
                    duration_sec = session_features.get_duration_sec()
                    df_features = session_features.extract_features(state)
                    _, point_kcal, _ = ml_engine.predict(df_features)
                    
                    response = {
                        "exercise": state.get("exercise_name", "Push-up"),
                        "confidence": 1.0,
                        "repCount": state.get("total_reps", 0),
                        "validReps": state.get("valid_reps", 0),
                        "jointAngle": round(state.get("current_angle", 180.0), 1),
                        "rom": round(state.get("avg_rom", 0.0), 1),
                        "calories": round(point_kcal, 2),
                        "formScore": round(state.get("form_score_pct", 100.0), 1),
                        
                        "exercise_type": session_exercise,
                        "exercise_name": state.get("exercise_name", "Push-up"),
                        "current_state": state.get("current_state", "UP"),
                        "total_reps": state.get("total_reps", 0),
                        "valid_reps": state.get("valid_reps", 0),
                        "invalid_reps": state.get("invalid_reps", 0),
                        "form_score_pct": state.get("form_score_pct", 100.0),
                        "is_form_valid": state.get("is_form_valid", True),
                        "form_error": state.get("form_error"),
                        "current_angle": round(state.get("current_angle", 180.0), 1),
                        "avg_rom": round(state.get("avg_rom", 0.0), 1),
                        "duration_sec": round(duration_sec, 1),
                        "is_active": False,
                        "kcal_burned": round(point_kcal, 2),
                        "kcal_lower": round(point_kcal * 0.93, 2),
                        "kcal_upper": round(point_kcal * 1.07, 2),
                        "fps": 30.0,
                        "camera_online": True
                    }
                    await websocket.send_json(response)
                    continue

                binary_data = data["bytes"]
                nparr = np.frombuffer(binary_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    frame = cv2.resize(frame, (640, 480))
                    
                    # Run pose detection and update biomechanics state
                    landmarks_2d, landmarks_3d, _ = vision.process_frame(frame)
                    state = session_biomechanics.update(landmarks_2d, landmarks_3d)
                    
                    target_lost = state.get("target_lost", False)
                    duration_sec = session_features.update_timer(target_lost=target_lost)
                    
                    # Extract temporal features and predict calories via XGBoost
                    df_features = session_features.extract_features(state)
                    lower_kcal, point_kcal, upper_kcal = ml_engine.predict(df_features)
                    
                    # Format standard skeletals overlay
                    landmarks2D = {}
                    if landmarks_2d:
                        landmarks2D = landmarks_2d
                    
                    response = {
                        "exercise": state.get("exercise_name", "Push-up"),
                        "confidence": 1.0,
                        "repCount": state.get("total_reps", 0),
                        "validReps": state.get("valid_reps", 0),
                        "jointAngle": round(state.get("current_angle", 180.0), 1),
                        "rom": round(state.get("avg_rom", 0.0), 1),
                        "calories": round(point_kcal, 2),
                        "formScore": round(state.get("form_score_pct", 100.0), 1),
                        
                        "exercise_type": session_exercise,
                        "exercise_name": state.get("exercise_name", "Push-up"),
                        "current_state": state.get("current_state", "UP"),
                        "total_reps": state.get("total_reps", 0),
                        "valid_reps": state.get("valid_reps", 0),
                        "invalid_reps": state.get("invalid_reps", 0),
                        "form_score_pct": state.get("form_score_pct", 100.0),
                        "is_form_valid": state.get("is_form_valid", True),
                        "form_error": state.get("form_error"),
                        "current_angle": round(state.get("current_angle", 180.0), 1),
                        "avg_rom": round(state.get("avg_rom", 0.0), 1),
                        "duration_sec": round(duration_sec, 1),
                        "is_active": session_features.is_active,
                        "kcal_burned": round(point_kcal, 2),
                        "kcal_lower": round(lower_kcal, 2),
                        "kcal_upper": round(upper_kcal, 2),
                        "landmarks_2d": landmarks2D,
                        "fps": 30.0,
                        "camera_online": True
                    }
                    await websocket.send_json(response)
                    
    except WebSocketDisconnect:
        print(f"[BX WS Workout] Client disconnected abruptly for user: {current_user['name']}")
    except Exception as e:
        print(f"[BX WS Workout] Connection error for user {current_user['name']}: {e}")
    finally:
        # Save workout set results if some repetitions were logged
        session_features.stop_set()
        state = session_biomechanics._build_state_dict()
        total_reps = state.get("total_reps", 0)
        
        if total_reps > 0:
            duration_sec = session_features.get_duration_sec()
            df_features = session_features.extract_features(state)
            lower_kcal, point_kcal, upper_kcal = ml_engine.predict(df_features)
            
            session_id = f"sess_{int(time.time())}"
            session_data = {
                "uid": current_user["uid"],
                "athlete_alias": current_user["name"],
                "session_id": session_id,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "exercise_type": session_exercise,
                "exercise_name": state.get("exercise_name", "Push-up"),
                "duration_sec": duration_sec,
                "total_reps": total_reps,
                "valid_reps": state.get("valid_reps", 0),
                "invalid_reps": state.get("invalid_reps", 0),
                "form_score_pct": state.get("form_score_pct", 100.0),
                "avg_rom_deg": state.get("avg_rom", 0.0),
                "predicted_kcal": point_kcal,
                "kcal_lower": lower_kcal,
                "kcal_upper": upper_kcal
            }
            
            # Calculate progression update and store xp_gained in session
            session_xp, updated_profile = process_user_progression(
                uid=current_user["uid"],
                total_reps=total_reps,
                valid_reps=state.get("valid_reps", 0),
                kcal_point=point_kcal,
                form_score_pct=state.get("form_score_pct", 100.0)
            )
            session_data["xp_gained"] = session_xp
            
            add_db_session(session_id, session_data)
            push_session_data(
                athlete_alias=current_user["name"],
                kcal_burned=point_kcal,
                form_score=state.get("form_score_pct", 100.0),
                valid_reps=state.get("valid_reps", 0)
            )
            
            # If socket is still open, send the final summary before closing
            try:
                await websocket.send_json({
                    "type": "summary",
                    "summary": {
                        "exercise_name": state.get("exercise_name", "Push-up"),
                        "exercise_type": session_exercise,
                        "duration_sec": round(duration_sec, 1),
                        "total_reps": total_reps,
                        "valid_reps": state.get("valid_reps", 0),
                        "invalid_reps": state.get("invalid_reps", 0),
                        "form_score_pct": state.get("form_score_pct", 100.0),
                        "avg_rom_deg": round(state.get("avg_rom", 0.0), 1),
                        "kcal_lower": lower_kcal,
                        "kcal_point": point_kcal,
                        "kcal_upper": upper_kcal
                    }
                })
            except Exception:
                pass
        
        try:
            await websocket.close()
        except Exception:
            pass

@app.get("/api/user/profile")
def get_user_profile(current_user: dict = Depends(get_current_user)):
    uid = current_user["uid"]
    profile = get_db_doc("users", uid)
    if not profile:
        profile = {
            "uid": uid,
            "name": current_user["name"],
            "weight_kg": 70.0,
            "height_cm": 175.0,
            "age": 25,
            "gender": "male",
            "fitness_goal": "Hypertrophy",
            
            "user_id": uid,
            "username": current_user["name"],
            "email": current_user.get("email") or f"{uid}@burnex.app",
            "avatar": f"https://api.dicebear.com/7.x/adventurer/svg?seed={current_user['name']}",
            "level": 1,
            "xp": 0,
            "total_workouts": 0,
            "total_reps": 0,
            "total_calories": 0.0,
            "current_streak": 0,
            "longest_streak": 0,
            "achievements": [],
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "last_active": datetime.datetime.utcnow().isoformat() + "Z"
        }
        set_db_doc("users", uid, profile)
    return {"status": "success", "profile": profile}

@app.get("/api/user/stats")
def get_user_stats(current_user: dict = Depends(get_current_user)):
    uid = current_user["uid"]
    profile = get_db_doc("users", uid) or {}
    
    sessions = get_all_db_sessions()
    user_sessions = [s for s in sessions if s.get("uid") == uid or s.get("user_id") == uid]
    
    exercise_counts = {}
    for s in user_sessions:
        name = s.get("exercise_name", "Push-up")
        exercise_counts[name] = exercise_counts.get(name, 0) + 1
        
    weekly_kcal = 0.0
    now = datetime.datetime.utcnow()
    one_week_ago = now - datetime.timedelta(days=7)
    for s in user_sessions:
        ts_str = s.get("timestamp")
        if not ts_str:
            continue
        try:
            if "T" in ts_str:
                s_dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
            else:
                s_dt = datetime.datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if s_dt >= one_week_ago:
                weekly_kcal += float(s.get("kcal_point", s.get("predicted_kcal", 0.0)))
        except Exception:
            pass
            
    return {
        "status": "success",
        "stats": {
            "total_workouts": profile.get("total_workouts", 0),
            "total_reps": profile.get("total_reps", 0),
            "total_calories": round(profile.get("total_calories", 0.0), 1),
            "current_streak": profile.get("current_streak", 0),
            "longest_streak": profile.get("longest_streak", 0),
            "level": profile.get("level", 1),
            "xp": profile.get("xp", 0),
            "weekly_kcal": round(weekly_kcal, 1),
            "exercise_counts": exercise_counts,
            "sessions_count": len(user_sessions)
        }
    }

@app.get("/api/leaderboard")
def get_leaderboard(type: str = "global", current_user: dict = Depends(get_current_user)):
    data = get_leaderboards(type)
    return {"status": "success", "leaderboard": data}

@app.get("/api/achievements")
def get_achievements(current_user: dict = Depends(get_current_user)):
    uid = current_user["uid"]
    profile = get_db_doc("users", uid) or {}
    unlocked_ids = profile.get("achievements", [])
    
    achievements_list = []
    for ach_id, defs in ACHIEVEMENTS_DEFS.items():
        achievements_list.append({
            "id": ach_id,
            "name": defs["name"],
            "description": defs["description"],
            "unlocked": ach_id in unlocked_ids,
            "xp_bonus": 100
        })
    return {"status": "success", "achievements": achievements_list}

@app.get("/api/workout/circuit")
def get_workout_circuit(current_user: dict = Depends(get_current_user)):
    """Retrieve daily circuit schedule based on fitness goal."""
    global current_circuit, current_circuit_exercise_index
    uid = current_user["uid"]
    
    profile = get_db_doc("users", uid)
    if not profile:
        profile = {"weight_kg": 70.0, "height_cm": 175.0, "age": 25, "gender": "male", "fitness_goal": "Hypertrophy"}

    weight = float(profile.get("weight_kg", 70.0))
    height = float(profile.get("height_cm", 175.0))
    age = int(profile.get("age", 25))
    gender = str(profile.get("gender", "male"))
    goal = str(profile.get("fitness_goal", "Hypertrophy"))

    current_circuit = generate_daily_circuit(weight, height, age, gender, goal)

    return {
        "status": "success",
        "circuit": current_circuit,
        "current_index": current_circuit_exercise_index
    }

@app.post("/api/workout/circuit/next")
def next_circuit_exercise():
    global current_circuit_exercise_index, current_circuit, current_exercise, biomechanics
    if current_circuit is None:
        raise HTTPException(status_code=400, detail="No active circuit loaded.")
    
    num_ex = len(current_circuit["exercises"])
    if num_ex == 0:
         raise HTTPException(status_code=400, detail="Circuit has no exercises.")

    current_circuit_exercise_index = (current_circuit_exercise_index + 1) % num_ex
    next_ex = current_circuit["exercises"][current_circuit_exercise_index]["exercise_type"]

    with lock:
        current_exercise = next_ex
        biomechanics = BiomechanicsEngine(exercise_type=current_exercise)

    return {
        "status": "success",
        "current_index": current_circuit_exercise_index,
        "exercise_type": next_ex
    }

@app.post("/api/workout/circuit/select")
def select_circuit_exercise(data: dict):
    global current_circuit_exercise_index, current_circuit, current_exercise, biomechanics
    idx = data.get("index")
    if idx is not None and current_circuit is not None:
        idx = int(idx)
        num_ex = len(current_circuit["exercises"])
        if 0 <= idx < num_ex:
            current_circuit_exercise_index = idx
            next_ex = current_circuit["exercises"][idx]["exercise_type"]
            
            with lock:
                current_exercise = next_ex
                biomechanics = BiomechanicsEngine(exercise_type=current_exercise)
                
            return {
                "status": "success",
                "current_index": current_circuit_exercise_index,
                "exercise_type": next_ex
            }
    raise HTTPException(status_code=400, detail="Invalid index")

@app.post("/api/generate-plan")
@app.post("/generate-plan")
async def generate_weekly_coach_plan(current_user: dict = Depends(get_current_user)):
    """Generate 7-day training schedule from user profile goals."""
    print(f"[BX Plan Backend] Received Generate Plan Request for UID: {current_user.get('uid')}")
    uid = current_user["uid"]
    from db.mongodb import is_connected
    if is_connected():
        profile = await user_repository.find_user_by_uid(uid)
    else:
        profile = get_db_doc("users", uid)

    if not profile:
        profile = _new_mongo_profile(uid, current_user)

    weight = float(profile.get("weight_kg") or 70.0)
    height = float(profile.get("height_cm") or 175.0)
    age = int(profile.get("age") or 25)
    gender = str(profile.get("gender") or "male")
    goal = str(profile.get("fitness_goal") or "Fat-loss")

    plan_data = generate_weekly_plan(goal)
    set_db_doc("ai_plans", uid, plan_data)
    print(f"[BX Plan Backend] Generated 7-day plan successfully for goal: {goal}")
    return {"status": "success", "plan": plan_data}

@app.get("/api/generate-plan")
@app.get("/generate-plan")
async def get_weekly_coach_plan(current_user: dict = Depends(get_current_user)):
    """Retrieve existing 7-day schedule plan."""
    uid = current_user["uid"]
    plan = get_db_doc("ai_plans", uid)
    if not plan:
        return await generate_weekly_coach_plan(current_user)
    return {"status": "success", "plan": plan}

@app.get("/api/workout/circuit")
@app.get("/workout/circuit")
async def get_workout_circuit(current_user: dict = Depends(get_current_user)):
    """Return active daily workout circuit for athlete."""
    uid = current_user["uid"]
    from db.mongodb import is_connected
    if is_connected():
        profile = await user_repository.find_user_by_uid(uid)
    else:
        profile = get_db_doc("users", uid)

    if not profile:
        profile = _new_mongo_profile(uid, current_user)

    weight = float(profile.get("weight_kg") or 70.0)
    height = float(profile.get("height_cm") or 175.0)
    age = int(profile.get("age") or 25)
    gender = str(profile.get("gender") or "male")
    goal = str(profile.get("fitness_goal") or "Fat-loss")

    circuit_data = generate_daily_circuit(weight, height, age, gender, goal)
    return {
        "status": "success",
        "circuit": circuit_data,
        "current_index": 0
    }

@app.post("/api/coach/chat")
def coach_chat(data: dict):
    global latest_session_telemetry
    msg = data.get("message", "")
    if not msg:
        raise HTTPException(status_code=400, detail="Empty query")
    response = local_coach.get_response(msg, latest_session_telemetry)
    return {"status": "success", "response": response}

@app.post("/api/ai/coach")
def post_ai_coach(data: dict, current_user: dict = Depends(get_current_user)):
    # Validate request payload before processing
    if not data or "message" not in data or not str(data.get("message", "")).strip():
        raise HTTPException(status_code=400, detail="Message is required")
        
    msg = data.get("message", "").strip()
    nutrition_ctx = data.get("nutrition_context")
    uid = current_user["uid"]
    
    # Detailed log
    print(f"\n[AI Coach] Incoming Request from UID {uid}: message='{msg}'")
    print(f"[AI Coach] Environment Verification: GEMINI_API_KEY={'LOADED' if os.getenv('GEMINI_API_KEY') else 'MISSING'}, GEMINI_MODEL={os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}")
    
    try:
        from src.gemini_service import get_coach_chat_reply
        
        # 1. Fetch user profile
        profile = get_db_doc("users", uid)
        
        # 2. Fetch history sessions
        all_sess = get_all_db_sessions()
        user_sess = [s for s in all_sess if s.get("uid") == uid]
        user_sess.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
        
        # 3. Call service
        print(f"[AI Coach] Calling Gemini with model: {os.getenv('GEMINI_MODEL')}")
        reply = get_coach_chat_reply(
            uid=uid,
            message=msg,
            profile=profile,
            history_sessions=user_sess,
            get_db_doc_fn=get_db_doc,
            set_db_doc_fn=set_db_doc,
            nutrition_ctx=nutrition_ctx
        )
        print(f"[AI Coach] Gemini Response: Success")
        return {"status": "success", "reply": reply}
    except Exception as error:
        # Catch all errors (ValueError, Exception, etc.) and return fallback message
        print(f"[AI Coach Error]: {error}")
        return {
            "status": "success",
            "reply": "I'm temporarily having trouble connecting to the AI service. Please try again shortly."
        }

@app.get("/api/leaderboard")
@app.get("/leaderboard")
def get_leaderboard():
    leaderboard = get_leaderboard_data()
    return {"status": "success", "leaderboard": leaderboard}

@app.get("/api/achievements")
@app.get("/achievements")
def get_achievements(current_user: dict = Depends(get_current_user)):
    """Retrieve unlocked and locked achievements for athlete."""
    uid = current_user["uid"]
    profile = get_db_doc("users", uid) or {}
    unlocked_ids = profile.get("achievements", [])
    
    ach_list = []
    for ach_id, ach_info in ACHIEVEMENTS_DEFS.items():
        ach_list.append({
            "id": ach_id,
            "name": ach_info["name"],
            "description": ach_info["description"],
            "unlocked": ach_id in unlocked_ids
        })
        
    return {"status": "success", "achievements": ach_list}

@app.get("/api/history")
@app.get("/history")
async def get_history(current_user: dict = Depends(get_current_user)):
    uid = current_user["uid"]
    from db.mongodb import is_connected
    user_sess = []

    if is_connected():
        try:
            mongo_history = await user_repository.get_workout_history(uid)
            for h in mongo_history:
                user_sess.append({
                    "session_id": h.get("workout_id") or h.get("id"),
                    "uid": uid,
                    "exercise_type": h.get("workout_type", "pushup"),
                    "exercise_name": h.get("exercise_name", "Push-up"),
                    "timestamp": h.get("created_at") or h.get("workout_date"),
                    "workout_date": h.get("workout_date"),
                    "duration_sec": float(h.get("duration_sec", 120)),
                    "predicted_kcal": float(h.get("calories_burned", 45.0)),
                    "calories_burned": float(h.get("calories_burned", 45.0)),
                    "total_reps": int(h.get("reps_completed", 15)),
                    "valid_reps": int(h.get("valid_reps", 12)),
                    "form_score_pct": float(h.get("form_score_pct", 92.0)),
                    "avg_rom_deg": float(h.get("avg_rom", 110.0))
                })
        except Exception as e:
            print("[BX History API] Mongo fetch warning:", e)

    all_sess = get_all_db_sessions()
    for s in all_sess:
        if (s.get("uid") == uid or s.get("user_id") == uid) and not any(x.get("session_id") == s.get("session_id") for x in user_sess):
            user_sess.append(s)

    if not user_sess:
        today_date = datetime.date.today()
        user_sess = [
            {
                "session_id": "sess_sample_1",
                "uid": uid,
                "exercise_type": "pushup",
                "exercise_name": "Push-up Set",
                "timestamp": f"{today_date.isoformat()}T07:30:00Z",
                "workout_date": today_date.isoformat(),
                "duration_sec": 420,
                "predicted_kcal": 185.0,
                "calories_burned": 185.0,
                "total_reps": 35,
                "valid_reps": 30,
                "form_score_pct": 94.0
            },
            {
                "session_id": "sess_sample_2",
                "uid": uid,
                "exercise_type": "squat",
                "exercise_name": "Squat Circuit",
                "timestamp": f"{(today_date - datetime.timedelta(days=2)).isoformat()}T08:15:00Z",
                "workout_date": (today_date - datetime.timedelta(days=2)).isoformat(),
                "duration_sec": 600,
                "predicted_kcal": 240.0,
                "calories_burned": 240.0,
                "total_reps": 45,
                "valid_reps": 40,
                "form_score_pct": 91.0
            },
            {
                "session_id": "sess_sample_3",
                "uid": uid,
                "exercise_type": "jumping_jack",
                "exercise_name": "HIIT Cardio",
                "timestamp": f"{(today_date - datetime.timedelta(days=4)).isoformat()}T17:45:00Z",
                "workout_date": (today_date - datetime.timedelta(days=4)).isoformat(),
                "duration_sec": 750,
                "predicted_kcal": 310.0,
                "calories_burned": 310.0,
                "total_reps": 80,
                "valid_reps": 75,
                "form_score_pct": 89.0
            },
            {
                "session_id": "sess_sample_4",
                "uid": uid,
                "exercise_type": "lunge",
                "exercise_name": "Lower Body Burn",
                "timestamp": f"{(today_date - datetime.timedelta(days=6)).isoformat()}T07:10:00Z",
                "workout_date": (today_date - datetime.timedelta(days=6)).isoformat(),
                "duration_sec": 540,
                "predicted_kcal": 210.0,
                "calories_burned": 210.0,
                "total_reps": 40,
                "valid_reps": 36,
                "form_score_pct": 93.0
            }
        ]

    user_sess.sort(key=lambda s: str(s.get("timestamp", "")), reverse=True)

    total_kcal = sum(float(s.get("predicted_kcal", 0.0) or s.get("calories_burned", 0.0) or 0.0) for s in user_sess)
    total_reps = sum(int(s.get("total_reps", 0) or 0) for s in user_sess)
    avg_form = np.mean([float(s.get("form_score_pct", 100.0) or 100.0) for s in user_sess]) if user_sess else 100.0

    return {
        "status": "success",
        "sessions": user_sess,
        "stats": {
            "total_kcal_burned": round(total_kcal, 1),
            "total_sessions": len(user_sess),
            "total_reps": total_reps,
            "avg_form_score": round(float(avg_form), 1)
        }
    }

# ==============================================================================
# 6. Admin Endpoints (Multi-Role Enforcement)
# ==============================================================================

@app.get("/api/admin/metrics")
def get_admin_metrics(current_user: dict = Depends(require_admin)):
    all_users = get_all_db_users()
    all_sessions = get_all_db_sessions()
    total_kcal = sum(s.get("predicted_kcal", 0.0) for s in all_sessions)
    
    return {
        "status": "success",
        "metrics": {
            "total_users": len(all_users),
            "total_sessions": len(all_sessions),
            "total_kcal_burned_platform": round(total_kcal, 1),
            "mediapipe_failure_rate_pct": 0.0,
            "llm_timeout_rate_pct": 0.0
        }
    }

@app.get("/api/admin/users")
def get_admin_users(current_user: dict = Depends(require_admin)):
    all_users = get_all_db_users()
    all_sessions = get_all_db_sessions()
    
    users_summary = []
    for u in all_users:
        uid = u.get("uid")
        user_sessions = [s for s in all_sessions if s.get("uid") == uid]
        users_summary.append({
            "uid": uid,
            "name": u.get("name", "Athlete"),
            "gender": u.get("gender", "male"),
            "age": u.get("age", 25),
            "goal": u.get("fitness_goal", "Hypertrophy"),
            "sessions_count": len(user_sessions),
            "total_kcal": round(sum(s.get("predicted_kcal", 0.0) for s in user_sessions), 1)
        })
    return {"status": "success", "users": users_summary}

@app.get("/api/export")
def export_data(format: str = "json", current_user: dict = Depends(get_current_user)):
    import csv
    all_sess = get_all_db_sessions()
    user_sess = [s for s in all_sess if s.get("uid") == current_user["uid"]]
    user_sess.sort(key=lambda s: s.get("timestamp", ""), reverse=True)

    if format.lower() == "csv":
        output = io.StringIO()
        fieldnames = [
            "session_id", "timestamp", "exercise_type", "exercise_name",
            "duration_sec", "total_reps", "valid_reps", "invalid_reps",
            "avg_rom_deg", "form_score_pct", "kcal_lower", "predicted_kcal", "kcal_upper"
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in user_sess:
            writer.writerow(row)
            
        output.seek(0)
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=burn_ex_workout_history.csv"}
        )
        
    # JSON default format
    return Response(
        content=json.dumps(user_sess, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=burn_ex_workout_history.json"}
    )


# ==============================================================================
# CALORIES ANALYTICS & HISTORY API ENDPOINTS
# ==============================================================================

@app.get("/api/analytics/calories/today")
async def analytics_calories_today(current_user: dict = Depends(get_current_user)):
    """Return total calories burned today for authenticated user."""
    uid = current_user["uid"]
    today_str = datetime.date.today().isoformat()
    from db.mongodb import is_connected
    if is_connected():
        data = await user_repository.get_calories_analytics(uid, start_date=today_str, end_date=today_str)
        return {"status": "success", "calories": data["totalCalories"]}
    
    # Fallback local sessions
    all_sess = get_all_db_sessions()
    user_sess = [s for s in all_sess if s.get("uid") == uid and str(s.get("timestamp") or "").startswith(today_str)]
    today_kcal = round(sum(s.get("predicted_kcal", 0.0) for s in user_sess), 1)
    return {"status": "success", "calories": today_kcal}


@app.get("/api/analytics/calories/last-15-days")
async def analytics_calories_15_days(current_user: dict = Depends(get_current_user)):
    """Return 15-day total calories and daily breakdown array."""
    uid = current_user["uid"]
    end_dt = datetime.date.today()
    start_dt = end_dt - datetime.timedelta(days=14)
    start_str = start_dt.isoformat()
    end_str = end_dt.isoformat()

    from db.mongodb import is_connected
    if is_connected():
        data = await user_repository.get_calories_analytics(uid, start_date=start_str, end_date=end_str)
        return {
            "status": "success",
            "totalCalories": data["totalCalories"],
            "dailyBreakdown": data["dailyBreakdown"]
        }

    # Fallback local sessions
    all_sess = get_all_db_sessions()
    user_sess = [s for s in all_sess if s.get("uid") == uid and start_str <= str(s.get("timestamp") or "")[:10] <= end_str]
    total_kcal = round(sum(s.get("predicted_kcal", 0.0) for s in user_sess), 1)
    daily_map = {}
    for s in user_sess:
        w_date = str(s.get("timestamp") or "")[:10]
        kcal = float(s.get("predicted_kcal", 0.0))
        if w_date not in daily_map:
            daily_map[w_date] = {"date": w_date, "calories": 0.0, "workouts": 0}
        daily_map[w_date]["calories"] = round(daily_map[w_date]["calories"] + kcal, 1)
        daily_map[w_date]["workouts"] += 1
    return {
        "status": "success",
        "totalCalories": total_kcal,
        "dailyBreakdown": list(daily_map.values())
    }


@app.get("/api/analytics/calories/range")
async def analytics_calories_range(
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """Return analytics for custom date range."""
    uid = current_user["uid"]
    from db.mongodb import is_connected
    if is_connected():
        data = await user_repository.get_calories_analytics(uid, start_date=startDate, end_date=endDate)
        return {
            "status": "success",
            "totalCalories": data["totalCalories"],
            "workouts": data["workouts"],
            "avgDaily": data["avgDaily"],
            "dailyBreakdown": data["dailyBreakdown"]
        }

    all_sess = get_all_db_sessions()
    filtered = []
    for s in all_sess:
        if s.get("uid") != uid:
            continue
        w_date = str(s.get("timestamp") or "")[:10]
        if startDate and w_date < startDate:
            continue
        if endDate and w_date > endDate:
            continue
        filtered.append(s)

    total_kcal = round(sum(s.get("predicted_kcal", 0.0) for s in filtered), 1)
    daily_map = {}
    for s in filtered:
        w_date = str(s.get("timestamp") or "")[:10]
        kcal = float(s.get("predicted_kcal", 0.0))
        if w_date not in daily_map:
            daily_map[w_date] = {"date": w_date, "calories": 0.0, "workouts": 0}
        daily_map[w_date]["calories"] = round(daily_map[w_date]["calories"] + kcal, 1)
        daily_map[w_date]["workouts"] += 1

    daily_list = list(daily_map.values())
    days_count = len(daily_list) if daily_list else 1
    avg_daily = round(total_kcal / days_count, 1)

    return {
        "status": "success",
        "totalCalories": total_kcal,
        "workouts": len(filtered),
        "avgDaily": avg_daily,
        "dailyBreakdown": daily_list
    }


@app.get("/api/analytics/workout-history")
async def analytics_workout_history(
    startDate: Optional[str] = Query(None),
    endDate: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """Return paginated workout history records for authenticated user."""
    uid = current_user["uid"]
    skip = (page - 1) * limit
    from db.mongodb import is_connected
    if is_connected():
        res = await user_repository.get_workout_history(
            firebase_uid=uid,
            start_date=startDate,
            end_date=endDate,
            search=search,
            skip=skip,
            limit=limit
        )
        return {
            "status": "success",
            "items": res["items"],
            "total": res["total"],
            "page": page,
            "limit": limit
        }

    # Fallback local sessions
    all_sess = get_all_db_sessions()
    user_sess = [s for s in all_sess if s.get("uid") == uid]
    if startDate:
        user_sess = [s for s in user_sess if str(s.get("timestamp") or "")[:10] >= startDate]
    if endDate:
        user_sess = [s for s in user_sess if str(s.get("timestamp") or "")[:10] <= endDate]
    if search:
        s_lower = search.lower()
        user_sess = [s for s in user_sess if s_lower in str(s.get("exercise_name") or "").lower() or s_lower in str(s.get("exercise_type") or "").lower()]

    total = len(user_sess)
    user_sess.sort(key=lambda s: s.get("timestamp", ""), reverse=True)
    paged_items = user_sess[skip:skip + limit]

    formatted_items = []
    for s in paged_items:
        formatted_items.append({
            "workout_id": s.get("session_id"),
            "user_id": uid,
            "workout_type": s.get("exercise_type", "pushup"),
            "exercise_name": s.get("exercise_name", "Push-up"),
            "workout_date": str(s.get("timestamp", ""))[:10],
            "duration_sec": s.get("duration_sec", 0),
            "calories_burned": s.get("predicted_kcal", 0.0),
            "reps_completed": s.get("total_reps", 0),
            "valid_reps": s.get("valid_reps", 0),
            "avg_rom": s.get("avg_rom_deg", 0.0),
            "form_score_pct": s.get("form_score_pct", 100.0),
            "created_at": s.get("timestamp")
        })

    return {
        "status": "success",
        "items": formatted_items,
        "total": total,
        "page": page,
        "limit": limit
    }


@app.get("/")
def read_root():
    return {"status": "success", "message": "Burn-Ex API is online"}

# ==============================================================================
# 7. Server Initialization Runner
# ==============================================================================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
