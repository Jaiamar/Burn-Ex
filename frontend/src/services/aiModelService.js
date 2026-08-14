/**
 * src/services/aiModelService.js
 * Burn-Ex — Local Edge AI Inference Service (TensorFlow.js + MediaPipe)
 * 
 * Handles client-side model loading, pose estimation, feature extraction,
 * real-time exercise classification, rep counting, and form tracking.
 */

let customModel = null;
let poseDetector = null;
let localStream = null;
let modelLoadingPromise = null;

// Hysteresis & State Machine configurations matching backend/src/config.py
export const EXERCISE_CONFIGS = {
  pushup: {
    name: "Push-Up",
    primaryJoint: "elbow",
    upThreshold: 160.0,
    downThreshold: 95.0,
    minRom: 45.0,
    idealRom: 110.0,
    met: 8.0,
  },
  squat: {
    name: "Squat",
    primaryJoint: "knee",
    upThreshold: 165.0,
    downThreshold: 100.0,
    minRom: 50.0,
    idealRom: 110.0,
    met: 6.5,
  },
  jumping_jack: {
    name: "Jumping Jack",
    primaryJoint: "shoulder",
    upThreshold: 130.0,
    downThreshold: 50.0,
    minRom: 60.0,
    idealRom: 120.0,
    met: 8.0,
  },
  lunge: {
    name: "Lunge",
    primaryJoint: "knee",
    upThreshold: 160.0,
    downThreshold: 100.0,
    minRom: 45.0,
    idealRom: 110.0,
    met: 6.0,
  },
  plank: {
    name: "Plank",
    primaryJoint: "spine",
    upThreshold: 175.0,
    downThreshold: 150.0,
    minRom: 0.0,
    idealRom: 180.0,
    met: 3.8,
  },
  burpee: {
    name: "Burpee",
    primaryJoint: "knee",
    upThreshold: 165.0,
    downThreshold: 95.0,
    minRom: 50.0,
    idealRom: 110.0,
    met: 10.0,
  }
};

// Internal Session State
let sessionState = {
  exercise_type: "pushup",
  exercise_name: "Push-up",
  current_state: "UP", // UP/DOWN
  total_reps: 0,
  valid_reps: 0,
  invalid_reps: 0,
  form_score_pct: 100.0,
  is_form_valid: true,
  form_error: null,
  current_angle: 180.0,
  avg_rom: 0.0,
  duration_sec: 0.0,
  is_active: false,
  kcal_burned: 0.0,
  kcal_lower: 0.0,
  kcal_upper: 0.0,
  
  // Buffers
  startTime: null,
  lastStateChangeTime: 0,
  currentRepHadError: false,
  minRepAngle: 180.0,
  maxRepAngle: 0.0,
  romHistory: [],
  plankHoldTimer: 0,
  lastPlankSecond: 0,
};

// ─── Mifflin-St Jeor Calorie Personalization ───────────────────────────────
export function calculateBmr(weight, height, age, gender) {
  const w = parseFloat(weight) || 70.0;
  const h = parseFloat(height) || 175.0;
  const a = parseInt(age) || 25;
  const g = String(gender).toLowerCase();
  
  if (g === "male") {
    return 10.0 * w + 6.25 * h - 5.0 * a + 5.0;
  } else {
    return 10.0 * w + 6.25 * h - 5.0 * a - 161.0;
  }
}

export function calculateCalories(exerciseType, bmr, durationSec, validRepRatio = 1.0) {
  const cfg = EXERCISE_CONFIGS[exerciseType] || { met: 4.0 };
  const durationHours = Math.max(0.1, durationSec) / 3600.0;
  const baseKcal = cfg.met * (bmr / 24.0) * durationHours;
  
  // Form accuracy intensity modifier (from 0.8 to 1.2)
  const formMultiplier = 0.8 + 0.4 * validRepRatio;
  return baseKcal * formMultiplier;
}

// ─── 3D Euclidean Joint Angle Mathematics ────────────────────────────────────
export function calculateAngle3D(a, b, c) {
  if (!a || !b || !c) return 180.0;

  // Keypoints3D coordinates are in meters (x, y, z)
  const v1 = [a.x - b.x, a.y - b.y, a.z - b.z];
  const v2 = [c.x - b.x, c.y - b.y, c.z - b.z];

  const norm1 = Math.sqrt(v1[0]*v1[0] + v1[1]*v1[1] + v1[2]*v1[2]);
  const norm2 = Math.sqrt(v2[0]*v2[0] + v2[1]*v2[1] + v2[2]*v2[2]);

  if (norm1 < 1e-6 || norm2 < 1e-6) return 180.0;

  const dot = v1[0]*v2[0] + v1[1]*v2[1] + v1[2]*v2[2];
  const cosine = Math.max(-1.0, Math.min(1.0, dot / (norm1 * norm2)));
  const angleRad = Math.acos(cosine);
  return (angleRad * 180.0) / Math.PI;
}

export function calculateTorsoInclination(hip, shoulder) {
  if (!hip || !shoulder) return 0.0;
  const dx = shoulder.x - hip.x;
  const dy = shoulder.y - hip.y;
  
  const norm = Math.hypot(dx, dy);
  if (norm < 1e-6) return 0.0;
  
  // y points downwards in image/viewport coordinates, vertical is up (0, -1)
  const cosTheta = (-dy) / norm;
  const cosine = Math.max(-1.0, Math.min(1.0, cosTheta));
  return (Math.acos(cosine) * 180.0) / Math.PI;
}

// ─── Initialize Pose Detection ──────────────────────────────────────────────
export async function initializeDetector() {
  if (poseDetector) return poseDetector;
  if (!window.poseDetection) {
    throw new Error("TensorFlow.js pose-detection CDN scripts are not loaded yet.");
  }
  
  console.log("[BX AI Service] Creating BlazePose detector instance...");
  poseDetector = await window.poseDetection.createDetector(
    window.poseDetection.SupportedModels.BlazePose,
    {
      runtime: 'mediapipe',
      solutionPath: 'https://cdn.jsdelivr.net/npm/@mediapipe/pose',
      modelComplexity: 1
    }
  );
  console.log("[BX AI Service] BlazePose detector initialized.");
  return poseDetector;
}

// ─── Load Custom TFJS Classification Model ──────────────────────────────────
export async function loadModel() {
  if (customModel) return customModel;
  if (modelLoadingPromise) return modelLoadingPromise;

  if (!window.tf) {
    throw new Error("TensorFlow.js CDN is not loaded yet.");
  }

  modelLoadingPromise = (async () => {
    try {
      console.log("[BX AI Service] Attempting to load custom trained TFJS model from /models/model.json...");
      // In Vite projects, files placed in public/models/ are served under /models/
      customModel = await window.tf.loadLayersModel('/models/model.json');
      console.log("[BX AI Service] Custom classification model loaded successfully!");
      return customModel;
    } catch (err) {
      console.warn("[BX AI Service] Custom model file not found or failed to load. Operating in high-fidelity biomechanical fallback mode.", err.message);
      customModel = null;
      return null;
    }
  })();

  return modelLoadingPromise;
}

// ─── Local Webcam Controller ───────────────────────────────────────────────
export async function startLocalWebcam(videoElement) {
  if (localStream) {
    stopLocalWebcam();
  }
  console.log("[BX AI Service] Starting local camera device feed...");
  localStream = await navigator.mediaDevices.getUserMedia({
    video: { width: 640, height: 480, frameRate: { ideal: 30 } },
    audio: false
  });
  if (videoElement) {
    videoElement.srcObject = localStream;
  }
  return localStream;
}

export function stopLocalWebcam() {
  if (localStream) {
    console.log("[BX AI Service] Releasing local camera device...");
    localStream.getTracks().forEach(track => track.stop());
    localStream = null;
  }
}

// ─── Session Initialization ───────────────────────────────────────────────
export function startSet(exerciseType) {
  const now = Date.now();
  const titleMap = {
    pushup: "Push-up",
    squat: "Squat",
    jumping_jack: "Jumping Jack",
    lunge: "Lunge",
    plank: "Plank",
    burpee: "Burpee"
  };

  sessionState = {
    exercise_type: exerciseType,
    exercise_name: titleMap[exerciseType] || "Push-up",
    current_state: exerciseType === "jumping_jack" ? "DOWN" : "UP",
    total_reps: 0,
    valid_reps: 0,
    invalid_reps: 0,
    form_score_pct: 100.0,
    is_form_valid: true,
    form_error: null,
    current_angle: 180.0,
    avg_rom: 0.0,
    duration_sec: 0.0,
    is_active: true,
    kcal_burned: 0.0,
    kcal_lower: 0.0,
    kcal_upper: 0.0,
    
    startTime: now,
    lastStateChangeTime: now,
    currentRepHadError: false,
    minRepAngle: 180.0,
    maxRepAngle: 0.0,
    romHistory: [],
    plankHoldTimer: 0,
    lastPlankSecond: 0,
  };
}

export function resetSetCounters() {
  const now = Date.now();
  sessionState.total_reps = 0;
  sessionState.valid_reps = 0;
  sessionState.invalid_reps = 0;
  sessionState.form_score_pct = 100.0;
  sessionState.is_form_valid = true;
  sessionState.form_error = null;
  sessionState.startTime = now;
  sessionState.lastStateChangeTime = now;
  sessionState.romHistory = [];
  sessionState.kcal_burned = 0.0;
  sessionState.kcal_lower = 0.0;
  sessionState.kcal_upper = 0.0;
}

export function getSessionSummary() {
  return {
    exercise_name: sessionState.exercise_name,
    duration_sec: sessionState.duration_sec,
    total_reps: sessionState.total_reps,
    valid_reps: sessionState.valid_reps,
    invalid_reps: sessionState.invalid_reps,
    form_score_pct: sessionState.form_score_pct,
    avg_rom_deg: sessionState.avg_rom,
    predicted_kcal: sessionState.kcal_burned,
    kcal_lower: sessionState.kcal_lower,
    kcal_upper: sessionState.kcal_upper
  };
}

// ─── Real-Time Inference Frame Processing ────────────────────────────────────
export async function predictFrame(videoElement, userProfile) {
  if (!poseDetector) return null;
  
  // 1. Estimate poses
  const poses = await poseDetector.estimatePoses(videoElement, {
    maxPoses: 1,
    flipHorizontal: false
  });
  
  if (!poses || poses.length === 0) {
    return { ...sessionState, camera_online: true, target_lost: true };
  }
  
  const keypoints3D = poses[0].keypoints3D;
  const keypoints2D = poses[0].keypoints;
  
  // Extract key coordinates (MediaPipe landmarks)
  const lElbow = keypoints3D[13];
  const rElbow = keypoints3D[14];
  const lWrist = keypoints3D[15];
  const rWrist = keypoints3D[16];
  const lShoulder = keypoints3D[11];
  const rShoulder = keypoints3D[12];
  const lHip = keypoints3D[23];
  const rHip = keypoints3D[24];
  const lKnee = keypoints3D[25];
  const rKnee = keypoints3D[26];
  const lAnkle = keypoints3D[27];
  const rAnkle = keypoints3D[28];
  
  // Compute joint angles in 3D (meters space)
  const leftElbowAngle = calculateAngle3D(lShoulder, lElbow, lWrist);
  const rightElbowAngle = calculateAngle3D(rShoulder, rElbow, rWrist);
  const leftKneeAngle = calculateAngle3D(lHip, lKnee, lAnkle);
  const rightKneeAngle = calculateAngle3D(rHip, rKnee, rAnkle);
  const leftHipAngle = calculateAngle3D(lShoulder, lHip, lKnee);
  const rightHipAngle = calculateAngle3D(rShoulder, rHip, rKnee);
  const leftShoulderAngle = calculateAngle3D(lElbow, lShoulder, lHip);
  const rightShoulderAngle = calculateAngle3D(rElbow, rShoulder, rHip);
  
  const spineAngle = calculateAngle3D(lShoulder, lHip, lAnkle);
  const torsoInclination = calculateTorsoInclination(lHip, lShoulder);
  
  // 2. Feature Vector representation
  const featureVector = [
    leftElbowAngle, rightElbowAngle,
    leftKneeAngle, rightKneeAngle,
    leftHipAngle, rightHipAngle,
    leftShoulderAngle, rightShoulderAngle,
    torsoInclination
  ];
  
  // 3. AI Exercise Classification (Auto-recognition)
  let classifiedExercise = sessionState.exercise_type;
  let confidenceScore = 1.0;
  
  if (customModel && window.tf) {
    window.tf.tidy(() => {
      try {
        const tensor = window.tf.tensor2d([featureVector]);
        const prediction = customModel.predict(tensor);
        const predictionData = prediction.dataSync();
        
        // Probability order: ['pushup', 'squat', 'jumping_jack', 'lunge', 'plank', 'burpee']
        const classes = ['pushup', 'squat', 'jumping_jack', 'lunge', 'plank', 'burpee'];
        const maxIdx = predictionData.indexOf(Math.max(...predictionData));
        if (predictionData[maxIdx] > 0.65) {
          classifiedExercise = classes[maxIdx];
          confidenceScore = predictionData[maxIdx];
        }
      } catch (err) {
        console.error("[BX AI Inference] Model run error:", err);
      }
    });
  } else {
    // Biomechanical Fallback Auto-Classifier
    if (torsoInclination > 65.0) {
      // Horizontal exercises
      if (Math.abs(leftElbowAngle - rightElbowAngle) > 30) {
        classifiedExercise = "pushup"; // Asymmetry or movement
      } else if (leftElbowAngle < 120.0 || rightElbowAngle < 120.0) {
        classifiedExercise = "pushup";
      } else {
        classifiedExercise = "plank";
      }
    } else {
      // Upright exercises
      if (leftShoulderAngle > 110.0 || rightShoulderAngle > 110.0) {
        classifiedExercise = "jumping_jack";
      } else if (leftKneeAngle < 120.0 || rightKneeAngle < 120.0) {
        if (Math.abs(leftKneeAngle - rightKneeAngle) > 35) {
          classifiedExercise = "lunge";
        } else {
          classifiedExercise = "squat";
        }
      }
    }
  }

  // 4. Update timer
  if (sessionState.is_active && sessionState.startTime) {
    sessionState.duration_sec = (Date.now() - sessionState.startTime) / 1000.0;
  }
  
  // 5. Repetition State Machine logic
  const now = Date.now();
  const cfg = EXERCISE_CONFIGS[sessionState.exercise_type] || EXERCISE_CONFIGS.pushup;
  let angleToTrack = 180.0;
  
  if (sessionState.exercise_type === "pushup") {
    angleToTrack = (leftElbowAngle + rightElbowAngle) / 2.0;
  } else if (sessionState.exercise_type === "squat") {
    angleToTrack = (leftKneeAngle + rightKneeAngle) / 2.0;
  } else if (sessionState.exercise_type === "jumping_jack") {
    angleToTrack = (leftShoulderAngle + rightShoulderAngle) / 2.0;
  } else if (sessionState.exercise_type === "lunge") {
    angleToTrack = Math.min(leftKneeAngle, rightKneeAngle);
  } else if (sessionState.exercise_type === "plank") {
    angleToTrack = spineAngle;
  } else if (sessionState.exercise_type === "burpee") {
    angleToTrack = (leftKneeAngle + rightKneeAngle) / 2.0;
  }
  
  sessionState.current_angle = angleToTrack;
  sessionState.minRepAngle = Math.min(sessionState.minRepAngle, angleToTrack);
  sessionState.maxRepAngle = Math.max(sessionState.maxRepAngle, angleToTrack);
  
  // Hysteresis Rep Counters
  const holdTime = (now - sessionState.lastStateChangeTime) / 1000.0;
  
  if (sessionState.exercise_type === "plank") {
    // Plank holds logic (every 1 second held is a valid count)
    const torsoValid = torsoInclination > 65.0;
    const hipValid = spineAngle > 145.0 && spineAngle < 185.0;
    
    if (torsoValid && hipValid) {
      sessionState.is_form_valid = true;
      sessionState.form_error = null;
      
      const currentSecond = Math.floor(sessionState.duration_sec);
      if (currentSecond > sessionState.lastPlankSecond) {
        sessionState.lastPlankSecond = currentSecond;
        sessionState.valid_reps++;
        sessionState.total_reps++;
      }
    } else {
      sessionState.is_form_valid = false;
      sessionState.form_error = hipValid ? "CHEST OUT OF PLANK ANGLE" : "SAGGING HIPS DETECTED";
      
      const currentSecond = Math.floor(sessionState.duration_sec);
      if (currentSecond > sessionState.lastPlankSecond) {
        sessionState.lastPlankSecond = currentSecond;
        sessionState.invalid_reps++;
        sessionState.total_reps++;
      }
    }
  } else {
    // Dynamic rep counters (Pushup, Squat, Lunge, Jumping Jack, Burpee)
    if (sessionState.current_state === "UP") {
      // Transition downward
      if (angleToTrack < cfg.downThreshold && holdTime > 0.3) {
        sessionState.current_state = "DOWN";
        sessionState.lastStateChangeTime = now;
        sessionState.currentRepHadError = false;
        
        // Evaluate posture forms during descent
        if (sessionState.exercise_type === "pushup" && spineAngle < 145.0) {
          sessionState.currentRepHadError = true;
          sessionState.is_form_valid = false;
          sessionState.form_error = "SAGGING HIPS DETECTED";
        } else if (sessionState.exercise_type === "squat" && torsoInclination > 65.0) {
          sessionState.currentRepHadError = true;
          sessionState.is_form_valid = false;
          sessionState.form_error = "CHEST TOO LOW / SAGGING FORM";
        } else {
          sessionState.is_form_valid = true;
          sessionState.form_error = null;
        }
      }
    } else if (sessionState.current_state === "DOWN") {
      // Transition upward
      if (angleToTrack > cfg.upThreshold && holdTime > 0.3) {
        sessionState.current_state = "UP";
        sessionState.lastStateChangeTime = now;
        
        const repRom = sessionState.maxRepAngle - sessionState.minRepAngle;
        sessionState.total_reps++;
        
        if (repRom >= cfg.minRom && !sessionState.currentRepHadError) {
          sessionState.valid_reps++;
          sessionState.romHistory.push(repRom);
          sessionState.is_form_valid = true;
          sessionState.form_error = null;
        } else {
          sessionState.invalid_reps++;
          sessionState.is_form_valid = false;
          if (repRom < cfg.minRom) {
            sessionState.form_error = "SHALLOW DEPTH DETECTED";
          }
        }
        
        // Reset min/max buffers
        sessionState.minRepAngle = 180.0;
        sessionState.maxRepAngle = 0.0;
      }
    }
  }
  
  // Calculate average ROM
  if (sessionState.romHistory.length > 0) {
    const sum = sessionState.romHistory.reduce((a, b) => a + b, 0);
    sessionState.avg_rom = sum / sessionState.romHistory.length;
  }
  
  // Calculate form score
  if (sessionState.total_reps > 0) {
    sessionState.form_score_pct = (sessionState.valid_reps / sessionState.total_reps) * 100.0;
  }
  
  // 6. Calories calculations
  const weight = userProfile?.weight_kg || 70.0;
  const height = userProfile?.height_cm || 175.0;
  const age = userProfile?.age || 25;
  const gender = userProfile?.gender || "male";
  
  const bmr = calculateBmr(weight, height, age, gender);
  const validRatio = sessionState.total_reps > 0 ? (sessionState.valid_reps / sessionState.total_reps) : 1.0;
  
  const pointKcal = calculateCalories(sessionState.exercise_type, bmr, sessionState.duration_sec, validRatio);
  sessionState.kcal_burned = parseFloat(pointKcal.toFixed(2));
  sessionState.kcal_lower = parseFloat((pointKcal * 0.93).toFixed(2));
  sessionState.kcal_upper = parseFloat((pointKcal * 1.07).toFixed(2));
  
  // 7. Format skeleton coordinate mappings for 2D canvas overlay
  const landmarks2D = {};
  const mpNames = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner",
    "right_eye", "right_eye_outer", "left_ear", "right_ear", "mouth_left",
    "mouth_right", "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_pinky", "right_pinky", "left_index",
    "right_index", "left_thumb", "right_thumb", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle", "left_heel",
    "right_heel", "left_foot_index", "right_foot_index"
  ];
  
  keypoints2D.forEach((kp, i) => {
    const name = mpNames[i];
    if (name && kp.score > 0.3) {
      // Normalize to [0.0, 1.0] range
      landmarks2D[name] = [kp.x / videoElement.videoWidth, kp.y / videoElement.videoHeight];
    }
  });

  return {
    ...sessionState,
    camera_online: true,
    target_lost: false,
    confidence: confidenceScore,
    auto_detected_exercise: classifiedExercise,
    landmarks_2d: landmarks2D,
    fps: 30.0 // Simulated constant camera execution
  };
}

export function setIsActive(isActive) {
  sessionState.is_active = isActive;
  if (!isActive) {
    // When paused, we stop the timer accumulation by setting startTime to null
    sessionState.startTime = null;
  } else {
    // When resuming, we adjust the start time based on already accumulated duration
    sessionState.startTime = Date.now() - (sessionState.duration_sec * 1000.0);
  }
}
