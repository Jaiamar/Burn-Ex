"""
Dynamic Workout Generation Engine for Burn-Ex.
Generates personalized fitness circuits based on physical profiles and fitness goals.
"""

from typing import Dict, Any, List


def generate_daily_circuit(
    weight_kg: float,
    height_cm: float,
    age: int,
    gender: str,
    goal: str
) -> Dict[str, Any]:
    """
    Generate a deterministic circuit based on athlete physical profile and goals.
    """
    clean_goal = str(goal).strip().lower()
    
    # Base structure
    circuit = {
        "goal": goal,
        "circuit_name": "",
        "rounds": 3,
        "exercises": []
    }
    
    # 1. Hypertrophy Goal
    if "hypertrophy" in clean_goal:
        circuit["circuit_name"] = "Burn-Ex Mass & Strength Protocol"
        circuit["rounds"] = 4
        circuit["exercises"] = [
            {
                "exercise_type": "pushup",
                "exercise_name": "Push-Up",
                "sets": 4,
                "target_reps": 12,
                "target_duration_sec": 0,
                "intensity": "High",
                "description": "Slow cadence: 3s down, 1s up. Focus on full chest extension."
            },
            {
                "exercise_type": "squat",
                "exercise_name": "Squat",
                "sets": 4,
                "target_reps": 12,
                "target_duration_sec": 0,
                "intensity": "High",
                "description": "Slow tempo: 3s descent, 1s ascent. Squat until thighs are parallel to ground."
            }
        ]
        
    # 2. Fat Loss Goal
    elif "fat" in clean_goal or "loss" in clean_goal or "shred" in clean_goal:
        circuit["circuit_name"] = "Burn-Ex Shred Circuit"
        circuit["rounds"] = 3
        circuit["exercises"] = [
            {
                "exercise_type": "jumping_jack",
                "exercise_name": "Jumping Jack",
                "sets": 3,
                "target_reps": 0,
                "target_duration_sec": 60,
                "intensity": "High",
                "description": "High velocity. Jump continuously to keep heart rate in zone."
            },
            {
                "exercise_type": "squat",
                "exercise_name": "Squat",
                "sets": 3,
                "target_reps": 15,
                "target_duration_sec": 0,
                "intensity": "Medium",
                "description": "Steady repetitions. Focus on keeping joints active."
            }
        ]
        
    # 3. Endurance Goal
    elif "endurance" in clean_goal or "volume" in clean_goal:
        circuit["circuit_name"] = "Burn-Ex High-Volume Stamina Circuit"
        circuit["rounds"] = 3
        circuit["exercises"] = [
            {
                "exercise_type": "jumping_jack",
                "exercise_name": "Jumping Jack",
                "sets": 3,
                "target_reps": 40,
                "target_duration_sec": 0,
                "intensity": "Medium",
                "description": "Constant, steady pace. Focus on rhythmic breathing."
            },
            {
                "exercise_type": "pushup",
                "exercise_name": "Push-Up",
                "sets": 3,
                "target_reps": 15,
                "target_duration_sec": 0,
                "intensity": "Medium",
                "description": "High volume. Maintain core tightness throughout the set."
            },
            {
                "exercise_type": "squat",
                "exercise_name": "Squat",
                "sets": 3,
                "target_reps": 20,
                "target_duration_sec": 0,
                "intensity": "Medium",
                "description": "High volume. Keep foot pressure evenly distributed."
            }
        ]
        
    # 4. Posture / Rehab Goal (Default fallback)
    else:
        circuit["circuit_name"] = "Burn-Ex Active Stability & Rehab Program"
        circuit["rounds"] = 3
        circuit["exercises"] = [
            {
                "exercise_type": "squat",
                "exercise_name": "Squat",
                "sets": 3,
                "target_reps": 8,
                "target_duration_sec": 0,
                "intensity": "Low",
                "description": "Shallow depth to start. Focus on balancing weight and knee tracking."
            },
            {
                "exercise_type": "pushup",
                "exercise_name": "Push-Up",
                "sets": 3,
                "target_reps": 6,
                "target_duration_sec": 0,
                "intensity": "Low",
                "description": "Perform push-ups on knees if necessary. Focus on shoulder blade posture."
            }
        ]
        
    # Fine-tune repetitions based on age/weight if hypertrophy or endurance
    # Older athletes or higher weight -> slightly lower reps to protect joints
    for ex in circuit["exercises"]:
        if ex["target_reps"] > 0:
            adj = 0
            if age > 50:
                adj -= 2
            if weight_kg > 95:
                adj -= 1
            ex["target_reps"] = max(4, ex["target_reps"] + adj)
            
    return circuit


def generate_weekly_plan(goal: str) -> Dict[str, Any]:
    """
    Generate a 7-day daily circuit schedule for an athlete based on goals.
    """
    clean_goal = str(goal).strip().lower()
    
    # 7-day structure
    plan = {}
    
    # Map goals to weekly focus plans
    if "fat" in clean_goal or "hiit" in clean_goal or "shred" in clean_goal:
        focuses = [
            ("HIIT Cardio Blast", [{"exercise": "Jumping Jacks", "duration_sec": 60, "sets": 3}, {"exercise": "Squats", "reps": 15, "sets": 3}], "Focus on rapid jumping jacks cadence today."),
            ("Lower Body Power", [{"exercise": "Squats", "reps": 20, "sets": 4}], "Squat until thighs break parallel. Feel the leg burn!"),
            ("Active Recovery", [{"exercise": "Jumping Jacks", "duration_sec": 30, "sets": 2}], "Keep moving at a light pace. Focus on breathing."),
            ("Upper Body & Core Strength", [{"exercise": "Push-ups", "reps": 12, "sets": 3}, {"exercise": "Squats", "reps": 12, "sets": 3}], "Keep your abdominal brace tight on push-ups."),
            ("Aerobic Conditioning", [{"exercise": "Jumping Jacks", "duration_sec": 45, "sets": 4}, {"exercise": "Squats", "reps": 15, "sets": 4}], "Maintain a steady heart rate. No rest between reps."),
            ("Metabolic Finish", [{"exercise": "Push-ups", "reps": 10, "sets": 3}, {"exercise": "Jumping Jacks", "duration_sec": 60, "sets": 3}], "Combine speed and stability today."),
            ("Full Rest & Restructuring", [], "Take a well-deserved rest today. Hydrate and stretch.")
        ]
    elif "strength" in clean_goal or "hypertrophy" in clean_goal:
        focuses = [
            ("Push-up Progressive Overload", [{"exercise": "Push-ups", "reps": 15, "sets": 4}], "Take 3 seconds on the lowering phase of each push-up."),
            ("Leg Hypertrophy Focus", [{"exercise": "Squats", "reps": 20, "sets": 4}], "Slow descent. Push through the heels to explode up."),
            ("Rest Day", [], "Rest and recover. Muscle growth happens during rest."),
            ("Chest & Shoulder Volume", [{"exercise": "Push-ups", "reps": 12, "sets": 4}], "Focus on complete elbow extension at the peak."),
            ("Full Body Kinematics", [{"exercise": "Squats", "reps": 15, "sets": 3}, {"exercise": "Push-ups", "reps": 10, "sets": 3}], "Squeeze glutes at the top of each squat and push-up."),
            ("Explosive Power Set", [{"exercise": "Jumping Jacks", "duration_sec": 30, "sets": 3}, {"exercise": "Squats", "reps": 12, "sets": 3}], "Use jumping jacks for shoulder warm-up followed by deep squats."),
            ("Full Rest & Restructuring", [], "Rest and fuel your muscles for the upcoming week.")
        ]
    elif "endurance" in clean_goal or "stamina" in clean_goal:
        focuses = [
            ("Continuous Cardio Zone", [{"exercise": "Jumping Jacks", "duration_sec": 90, "sets": 3}], "Steady breathing. Keep hands fully raised on the jump."),
            ("High Volume Squats", [{"exercise": "Squats", "reps": 25, "sets": 3}], "Develop endurance in your quadriceps. Focus on continuous pace."),
            ("Upper Body Endurance", [{"exercise": "Push-ups", "reps": 18, "sets": 3}], "Brace core. Perform in a steady rhythm."),
            ("Active Recovery", [{"exercise": "Jumping Jacks", "duration_sec": 30, "sets": 2}], "Keep the pace light and relaxed."),
            ("Stamina Circuit A", [{"exercise": "Jumping Jacks", "duration_sec": 60, "sets": 3}, {"exercise": "Squats", "reps": 15, "sets": 3}], "Zero rest between exercises, 30s rest between sets."),
            ("Stamina Circuit B", [{"exercise": "Push-ups", "reps": 12, "sets": 3}, {"exercise": "Squats", "reps": 20, "sets": 3}], "Focus on stamina. Keep reps moving smoothly."),
            ("Rest & Stretch", [], "Allow your cardiovascular system to fully recover today.")
        ]
    else: # Mobility, General, Beginner, Home workout, Rehab, etc.
        focuses = [
            ("Mobility & Joint Alignment", [{"exercise": "Squats", "reps": 10, "sets": 3}], "Squat comfortably. Prioritize posture uprightness."),
            ("Upper Body Foundation", [{"exercise": "Push-ups", "reps": 8, "sets": 3}], "Keep push-ups slow. Perform from knees if needed."),
            ("Heart Rate Warm-up", [{"exercise": "Jumping Jacks", "duration_sec": 30, "sets": 3}], "Focus on symmetric arm extensions."),
            ("Rest & Flexibility", [], "Stretch hip flexors and chest muscles today."),
            ("Kinematic Control", [{"exercise": "Squats", "reps": 12, "sets": 3}, {"exercise": "Push-ups", "reps": 8, "sets": 3}], "Concentrate on form score accuracy over velocity."),
            ("Light Fitness Mix", [{"exercise": "Jumping Jacks", "duration_sec": 45, "sets": 2}, {"exercise": "Squats", "reps": 10, "sets": 2}], "Keep movements soft and controlled."),
            ("Active Recovery & Walk", [], "Rest today. Take a light walk outside.")
        ]
        
    for i in range(7):
        day_key = f"day_{i+1}"
        focus, circuit, msg = focuses[i]
        plan[day_key] = {
            "focus": focus,
            "circuit": circuit,
            "coach_message": msg
        }
        
    return plan
