"""
Local Offline Conversational AI Fitness Assistant (Local LLM Coach).
Queries local Ollama endpoint (e.g., Gemma 4-bit) and falls back to a rule-based
biomechanical expert system if the offline model is unavailable.
"""

import json
from typing import Dict, Any, Optional
import requests


class LocalCoach:
    """
    Offline-first AI fitness assistant utilizing local LLM backends
    with a deterministic biomechanical expert system fallback.
    """

    def __init__(self, ollama_url: str = "http://localhost:11434", model_name: str = "gemma") -> None:
        self.ollama_url = ollama_url
        self.model_name = model_name

    def _check_ollama_alive(self) -> bool:
        """Check if local Ollama service is running."""
        try:
            res = requests.get(f"{self.ollama_url}/api/tags", timeout=1.0)
            return res.status_code == 200
        except Exception:
            return False

    def generate_system_prompt(self, telemetry: Dict[str, Any]) -> str:
        """
        Inject the latest biomechanical telemetry into the LLM context wrapper.
        """
        exercise = telemetry.get("exercise_type", "workout").replace("_", " ").title()
        valid = telemetry.get("valid_reps", 0)
        total = telemetry.get("total_reps", 0)
        form_score = telemetry.get("form_score_pct", 100.0)
        kcal = telemetry.get("kcal_burned", 0.0)
        error_msg = telemetry.get("form_error_msg", "None")
        
        prompt = (
            f"You are Burn-Ex Coach, an on-device AI fitness coach. The user just completed a set of {exercise}.\n"
            f"- Valid Repetitions: {valid} / {total}\n"
            f"- Form Quality Score: {form_score}%\n"
            f"- Core Form Warnings: {error_msg}\n"
            f"- Calorie Burn: {kcal:.1f} kcal\n\n"
            "Provide professional, encouraging, biomechanically sound advice based strictly on these metrics. Keep it under 4 sentences."
        )
        return prompt

    def get_response(self, user_query: str, telemetry: Dict[str, Any]) -> str:
        """
        Submit prompt to local LLM or run expert fallback if offline/uninstalled.
        """
        system_prompt = self.generate_system_prompt(telemetry)
        
        # 1. Attempt Local Ollama Endpoint
        if self._check_ollama_alive():
            try:
                payload = {
                    "model": self.model_name,
                    "prompt": f"{system_prompt}\n\nUser Question: {user_query}\nBurn-Ex Coach:",
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 150
                    }
                }
                res = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=5.0
                )
                if res.status_code == 200:
                    data = res.json()
                    return data.get("response", "").strip()
            except Exception as e:
                print(f"[LocalCoach] Ollama query failed: {e}. Falling back to Expert System.")

        # 2. Expert System Fallback
        return self._generate_expert_advice(user_query, telemetry)

    def _generate_expert_advice(self, query: str, telemetry: Dict[str, Any]) -> str:
        """
        Deterministc expert rule system mapping telemetry to pro fitness advice.
        """
        query_lower = query.lower()
        ex_type = telemetry.get("exercise_type", "squat")
        form_score = telemetry.get("form_score_pct", 100.0)
        valid = telemetry.get("valid_reps", 0)
        total = telemetry.get("total_reps", 0)
        kcal = telemetry.get("kcal_burned", 0.0)
        error = telemetry.get("form_error_msg", "None")

        # Response blocks based on intent
        if "form" in query_lower or "score" in query_lower or "accuracy" in query_lower or "reps" in query_lower:
            if form_score >= 80:
                advice = (
                    f"Excellent work! Your form score was a solid **{form_score}%** with **{valid}/{total}** clean reps. "
                    "You maintained clean movement path, proper ROM, and steady cadence. Keep up this exact posture on your next set!"
                )
            else:
                advice = (
                    f"Your form score dropped to **{form_score}%** (**{valid}/{total}** valid reps). "
                    f"The main deviation detected was: *'{error}'*. "
                )
                if ex_type == "squat":
                    advice += "Ensure you squat deep enough to let your thighs break parallel (hips below 90°), and keep your heels firmly planted."
                elif ex_type == "pushup":
                    advice += "Maintain a straight plank position from shoulders to ankles. Squeezing your glutes will prevent your chest/hips from sagging."
                elif ex_type == "jumping_jack":
                    advice += "Focus on raising both wrists synchronized above 145 degrees and fully return arms to your side on the landing phase."
            return advice

        elif "calorie" in query_lower or "kcal" in query_lower or "burn" in query_lower or "energy" in query_lower:
            return (
                f"You burned approximately **{kcal:.1f} kcal** during this set. "
                "Burn-Ex calculates this using your Mifflin-St Jeor BMR base scaled by active joint velocity telemetry. "
                "Because your form quality acts as a multiplier, completing cleaner reps will yield higher calorie scores than fast, lazy half-reps!"
            )

        elif "next" in query_lower or "what should i do" in query_lower or "routine" in query_lower:
            return (
                "For your next set, focus on a slow, controlled negative phase (eccentric lowering) to recruit maximum muscle fibers. "
                "Check the 'Today's Circuit' queue on your left dashboard to see which exercise is next in your program."
            )

        # General helper response
        return (
            f"Hey! As your coach, I see you did **{valid} valid {ex_type}s** and burned **{kcal:.1f} kcal**. "
            f"Your current warning state is '{error}'. "
            "To maximize performance, ensure you maintain a tight core brace and focus on deep range of motion rather than speed."
        )
