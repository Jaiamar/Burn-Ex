import os
import requests
import datetime
from typing import List, Dict, Any, Optional

# Simple environment variables loader if .env exists in backend root
from pathlib import Path
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    os.environ[parts[0].strip()] = parts[1].strip()

def get_coach_chat_reply(
    uid: str,
    message: str,
    profile: Optional[dict],
    history_sessions: List[dict],
    get_db_doc_fn,
    set_db_doc_fn,
    nutrition_ctx: Optional[dict] = None
) -> str:
    """
    Build context, retrieve conversation history, make Gemini API call,
    and update conversation history in the database.
    """
    # 1. Retrieve profile details
    name = profile.get("name") if profile else "Athlete"
    age = profile.get("age") if profile else "Unavailable"
    height = profile.get("height_cm") if profile else "Unavailable"
    weight = profile.get("weight_kg") if profile else "Unavailable"
    gender = profile.get("gender") if profile else "Unavailable"
    goal = profile.get("fitness_goal") if profile else "Unavailable"
    
    # Target weight calculation
    target_weight = "Unavailable"
    if isinstance(weight, (int, float)):
        target_weight = f"{weight - 5:.1f} kg"
    elif weight != "Unavailable":
        try:
            target_weight = f"{float(weight) - 5:.1f} kg"
        except (ValueError, TypeError):
            pass

    # Nutrition preferences can be inferred from profile or default to Vegetarian
    diet = profile.get("dietary_preference", "Vegetarian")
    activity = profile.get("activity_level", "Moderate")

    profile_text = (
        f"Name: {name}\n"
        f"Age: {age}\n"
        f"Height: {height} cm\n"
        f"Weight: {weight} kg\n"
        f"Target Weight: {target_weight}\n"
        f"Goal: {goal}\n"
        f"Diet: {diet}\n"
        f"Activity Level: {activity}"
    )

    # 2. Compile today's session stats
    today_str = datetime.date.today().isoformat()
    today_sessions = [s for s in history_sessions if str(s.get("timestamp") or "").startswith(today_str)]
    
    workout_summary = "No workout logs recorded today."
    today_kcal = 0
    if today_sessions:
        workout_summary = ""
        for s in today_sessions:
            ex_name = s.get("exercise_name") or s.get("exercise_type") or "Workout Set"
            reps = s.get("total_reps") or 0
            valid = s.get("valid_reps") or 0
            score = s.get("form_score_pct") or 100
            kcal = s.get("predicted_kcal") or 0.0
            today_kcal += kcal
            workout_summary += f"- {ex_name}: {valid}/{reps} reps (Form: {score}%, Calories: {kcal:.1f} kcal)\n"

    # Analyze message keywords to decide what context to fetch & inject
    msg_lower = message.lower()
    
    # Check queries
    asks_today_workout = any(w in msg_lower for w in ["today", "tonight", "this workout", "recent session", "reps today"])
    asks_calories = "calorie" in msg_lower or "kcal" in msg_lower or "burn" in msg_lower
    asks_nutrition = any(w in msg_lower for w in ["eat", "food", "diet", "nutrition", "meal", "protein", "carbs", "fat", "breakfast", "lunch", "dinner", "snack", "hungry"])
    asks_progress = any(w in msg_lower for w in ["progress", "improve", "improving", "better", "week", "best", "history", "past", "last", "trend", "performance", "worse"])
    asks_squat = "squat" in msg_lower
    asks_pushup = "push-up" in msg_lower or "pushup" in msg_lower or "pushups" in msg_lower
    asks_jumping = "jumping" in msg_lower or "jack" in msg_lower or "jacks" in msg_lower
    
    # Build dynamic context block list
    context_blocks = []
    
    # 1. ALWAYS inject User Profile
    context_blocks.append(f"USER PROFILE:\n{profile_text}")
    
    # 2. Inject Today's Workout if relevant or requested
    # Compile full historical analytics summary for AI Coach
    today_dt = datetime.date.today()
    fifteen_days_ago = (today_dt - datetime.timedelta(days=14)).isoformat()
    thirty_days_ago = (today_dt - datetime.timedelta(days=29)).isoformat()
    seven_days_ago = (today_dt - datetime.timedelta(days=6)).isoformat()
    prev_week_start = (today_dt - datetime.timedelta(days=13)).isoformat()
    prev_week_end = (today_dt - datetime.timedelta(days=7)).isoformat()

    # Calculate calorie totals for key time windows
    sess_this_week = [s for s in history_sessions if str(s.get("timestamp") or "")[:10] >= seven_days_ago]
    sess_prev_week = [s for s in history_sessions if prev_week_start <= str(s.get("timestamp") or "")[:10] <= prev_week_end]
    sess_15_days = [s for s in history_sessions if str(s.get("timestamp") or "")[:10] >= fifteen_days_ago]
    sess_30_days = [s for s in history_sessions if str(s.get("timestamp") or "")[:10] >= thirty_days_ago]

    kcal_this_week = sum(float(s.get("predicted_kcal") or s.get("calories_burned") or 0.0) for s in sess_this_week)
    kcal_prev_week = sum(float(s.get("predicted_kcal") or s.get("calories_burned") or 0.0) for s in sess_prev_week)
    kcal_15_days = sum(float(s.get("predicted_kcal") or s.get("calories_burned") or 0.0) for s in sess_15_days)
    kcal_30_days = sum(float(s.get("predicted_kcal") or s.get("calories_burned") or 0.0) for s in sess_30_days)

    week_diff_pct = 0.0
    if kcal_prev_week > 0:
        week_diff_pct = round(((kcal_this_week - kcal_prev_week) / kcal_prev_week) * 100.0, 1)

    # Build daily breakdown map for past 30 days
    daily_history_map = {}
    for s in history_sessions:
        dt_key = str(s.get("timestamp") or s.get("workout_date") or "")[:10]
        if not dt_key:
            continue
        c_val = float(s.get("predicted_kcal") or s.get("calories_burned") or 0.0)
        r_val = int(s.get("total_reps") or s.get("reps_completed") or 0)
        e_name = str(s.get("exercise_name") or s.get("workout_type") or "Workout")

        if dt_key not in daily_history_map:
            daily_history_map[dt_key] = {"date": dt_key, "calories": 0.0, "reps": 0, "workouts": [], "count": 0}
        daily_history_map[dt_key]["calories"] += c_val
        daily_history_map[dt_key]["reps"] += r_val
        daily_history_map[dt_key]["count"] += 1
        daily_history_map[dt_key]["workouts"].append(f"{e_name} ({c_val:.1f} kcal, {r_val} reps)")

    # Find highest calorie burn day
    best_day = max(daily_history_map.values(), key=lambda d: d["calories"]) if daily_history_map else None
    best_day_text = f"{best_day['date']} ({best_day['calories']:.1f} kcal)" if best_day else "No workouts yet"

    # Format daily history summary string for past 30 days
    daily_lines = []
    for d_key in sorted(daily_history_map.keys(), reverse=True)[:30]:
        item = daily_history_map[d_key]
        w_summary = ", ".join(item["workouts"])
        daily_lines.append(f"- {d_key}: {item['calories']:.1f} kcal across {item['count']} workouts [{w_summary}]")
    daily_summary_text = "\n".join(daily_lines) if daily_lines else "No historical workout logs recorded."

    historical_analytics_block = (
        f"HISTORICAL CALORIES & WORKOUT DATABASE:\n"
        f"Today ({today_str}): {today_kcal:.1f} kcal ({len(today_sessions)} workouts)\n"
        f"This Week (Last 7 days): {kcal_this_week:.1f} kcal across {len(sess_this_week)} workouts\n"
        f"Previous Week (7-14 days ago): {kcal_prev_week:.1f} kcal across {len(sess_prev_week)} workouts\n"
        f"Weekly Change: {week_diff_pct:+.1f}% vs previous week\n"
        f"Last 15 Days: {kcal_15_days:.1f} kcal across {len(sess_15_days)} workouts\n"
        f"Last 30 Days: {kcal_30_days:.1f} kcal across {len(sess_30_days)} workouts\n"
        f"Highest Calorie Burn Day: {best_day_text}\n\n"
        f"DAILY WORKOUT BREAKDOWN LOG (Use this to answer date-specific queries):\n"
        f"{daily_summary_text}"
    )
    context_blocks.append(historical_analytics_block)

    # 3. Inject Today's Nutrition if relevant
    if asks_nutrition or asks_calories:
        nutrition_text = "No nutrition logs recorded today."
        if nutrition_ctx:
            consumed = nutrition_ctx.get("consumed_calories", 0)
            target = nutrition_ctx.get("target_calories", 2000)
            remaining = nutrition_ctx.get("remaining_calories", 2000)
            protein = nutrition_ctx.get("consumed_protein", 0)
            tar_protein = nutrition_ctx.get("target_protein", 100)
            diet_pref_str = nutrition_ctx.get("dietary_preference", diet)
            
            nutrition_text = (
                f"Consumed Calories: {consumed} kcal / Target Calories: {target} kcal\n"
                f"Remaining Calories: {remaining} kcal\n"
                f"Protein Intake: {protein}g / Target Protein: {tar_protein}g\n"
                f"Dietary Preference: {diet_pref_str}"
            )
        context_blocks.append(f"CURRENT NUTRITION STATE (TODAY):\n{nutrition_text}")
        
    # 4. Inject Progress / History if relevant
    if asks_progress:
        # Sum up stats for the last 7 days (including today)
        seven_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
        recent_sessions = [s for s in history_sessions if str(s.get("timestamp") or "") >= seven_days_ago]
        
        if recent_sessions:
            total_recent_kcal = sum(s.get("predicted_kcal") or 0.0 for s in recent_sessions)
            total_recent_reps = sum(s.get("total_reps") or 0 for s in recent_sessions)
            avg_form_score = sum(s.get("form_score_pct") or 100 for s in recent_sessions) / len(recent_sessions)
            
            # Find best session
            best_sess = max(recent_sessions, key=lambda s: s.get("predicted_kcal") or 0.0)
            best_sess_desc = f"{best_sess.get('exercise_name') or 'Workout'} on {str(best_sess.get('timestamp') or '')[:10]} ({(best_sess.get('predicted_kcal') or 0.0):.1f} kcal, {best_sess.get('valid_reps') or 0} valid reps)"
            
            progress_summary = (
                f"Workouts in last 7 days: {len(recent_sessions)}\n"
                f"Total Calories Burned in last 7 days: {total_recent_kcal:.1f} kcal\n"
                f"Total Reps in last 7 days: {total_recent_reps}\n"
                f"Average Form Score: {avg_form_score:.1f}%\n"
                f"Best Workout this week: {best_sess_desc}\n"
            )
            
            # Listing last 5 workouts
            history_list = []
            for s in history_sessions[:5]:
                dt_str = str(s.get("timestamp") or "")[:10]
                ex_name = s.get("exercise_name") or s.get("exercise_type") or "Workout Set"
                reps = s.get("total_reps") or 0
                valid = s.get("valid_reps") or 0
                score = s.get("form_score_pct") or 100
                history_list.append(f"- {dt_str}: {ex_name} - {valid}/{reps} reps (Form: {score}%)")
            
            history_text = "\n".join(history_list)
            context_blocks.append(f"PAST WEEK PROGRESS SUMMARY:\n{progress_summary}\nRECENT WORKOUT HISTORY (Newest first):\n{history_text}")
        else:
            context_blocks.append("PAST WEEK PROGRESS SUMMARY:\nNo workout logs recorded in the last 7 days.")

    # 5. Inject Specific Exercise Metrics if relevant
    target_ex = None
    if asks_squat:
        target_ex = "squat"
    elif asks_pushup:
        target_ex = "pushup"
    elif asks_jumping:
        target_ex = "jumping_jack"
        
    if target_ex:
        # Find recent sessions for this exercise
        ex_sessions = [s for s in history_sessions if s.get("exercise_type") == target_ex or target_ex in str(s.get("exercise_name") or "").lower()]
        if ex_sessions:
            ex_summary = f"RECENT {target_ex.upper()} PERFORMANCE DATA (Newest first):\n"
            for s in ex_sessions[:3]:
                dt_str = str(s.get("timestamp") or "")[:10]
                reps = s.get("total_reps") or 0
                valid = s.get("valid_reps") or 0
                score = s.get("form_score_pct") or 100
                rom = s.get("avg_rom_deg") or s.get("avg_rom") or 0.0
                duration = s.get("duration_sec") or 0.0
                kcal = s.get("predicted_kcal") or 0.0
                ex_summary += f"- {dt_str}: {valid}/{reps} reps (Form: {score}%, Avg ROM: {rom:.1f}°, Duration: {duration:.1f}s, Burned: {kcal:.1f} kcal)\n"
            context_blocks.append(ex_summary)
        else:
            context_blocks.append(f"RECENT {target_ex.upper()} PERFORMANCE DATA:\nNo recent sets found for {target_ex} in database.")

    # Combine context
    context_injection = "\n\n".join(context_blocks)
    context_injection = f"--- USER CONTEXT ---\n{context_injection}\n--------------------"

    # 4. Load Conversation history via the passed database wrapper function
    conv_doc = get_db_doc_fn("ai_conversations", uid)
    if not conv_doc:
        conv_doc = {
            "user_id": uid,
            "messages": [],
            "created_at": datetime.datetime.now().isoformat()
        }

    # Format history for Gemini contents
    contents = []
    # Send up to the last 8 messages for context
    recent_history = conv_doc.get("messages", [])[-8:]
    for m in recent_history:
        role = 'user' if m["role"] == 'user' else 'model'
        contents.append({
            "role": role,
            "parts": [{"text": m["content"]}]
        })

    # Append current message with context injected
    current_message_with_context = f"{context_injection}\n\nUser Question: {message}"
    
    contents.append({
        "role": "user",
        "parts": [{"text": current_message_with_context}]
    })

    # System Instructions
    system_instruction = (
        "You are Burn-Ex AI Coach, a professional, clear, concise, fitness-focused, and personalized AI fitness assistant.\n"
        "Your responsibilities include:\n"
        "- Workout guidance, exercise technique guidance, and form improvement.\n"
        "- Range of Motion (ROM), rep quality, movement velocity, and tempo analysis.\n"
        "- Estimated energy expenditure and recovery explanations.\n"
        "- Workout planning and fitness goal guidance.\n"
        "- Nutrition guidance, calorie and protein tracking, and meal recommendations (focusing on Indian meals like Idli, Dosa, Sambar, Pongal, Upma, Chapati, Roti, Rice, Dal, Rajma, Chole, Paneer, Curd, Eggs, Chicken, Fish, Sundal, Poha, Ragi, Fruits, Nuts, Buttermilk).\n"
        "- Hydration and general wellness.\n\n"
        "Style and Behavior Rules:\n"
        "1. Tone: Professional, clear, practical, encouraging but not overly enthusiastic (avoid exclamation spam).\n"
        "2. Safety First: You are NOT a doctor. Do not diagnose injuries or claim medical certainty. For reports of pain or injury, explain that pain has multiple causes, advise stopping the painful movement immediately, and recommend evaluation by a qualified medical professional.\n"
        "3. Personalized Context: Refer to the user's stats (reps, ROM, calories, nutrition goals) ONLY if they are provided in the USER CONTEXT block. Do not make up or assume values. If context is missing/unavailable, explicitly state that you don't have that data.\n"
        "4. Food recommendations: Tailor recommendations to their dietary preference (e.g. Vegetarian, Vegan, Eggetarian, Non-Vegetarian) and remaining calories/protein targets.\n"
        "5. Length: Keep answers concise (2-5 sentences for simple queries, 3-8 short paragraphs or bullet lists for detailed explanations)."
    )

    # Call Gemini API
    reply = call_gemini(system_instruction, contents)

    # 5. Append message history & Save to DB
    if "messages" not in conv_doc:
        conv_doc["messages"] = []
    conv_doc["messages"].append({"role": "user", "content": message})
    conv_doc["messages"].append({"role": "assistant", "content": reply})
    conv_doc["messages"] = conv_doc["messages"][-20:]  # Limit total stored messages to 20
    conv_doc["updated_at"] = datetime.datetime.now().isoformat()
    
    set_db_doc_fn("ai_conversations", uid, conv_doc)

    return reply

def call_gemini(system_instruction: str, contents: list) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is missing")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    payload = {
        "contents": contents,
        "systemInstruction": {
            "parts": [
                {"text": system_instruction}
            ]
        },
        "generationConfig": {
            "temperature": 0.3
        }
    }
    
    res = requests.post(url, json=payload, headers=headers, timeout=12.0)
    
    if res.status_code == 200:
        data = res.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError) as e:
            print(f"[GeminiService] Failed parsing: {res.text}")
            raise ValueError("Invalid response format from Gemini API")
    else:
        print(f"[GeminiService] Error {res.status_code}: {res.text}")
        raise ValueError(f"Gemini API returned error code {res.status_code}")
