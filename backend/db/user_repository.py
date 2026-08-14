"""
backend/db/user_repository.py
Repository layer for the MongoDB 'users' collection.
All DB queries for user profiles go through here.
"""

import datetime
from typing import Optional, Dict, Any
from bson import ObjectId
from db.mongodb import get_database


def _serialize(doc: dict) -> dict:
    """Convert BSON types to JSON-serializable Python types."""
    if doc is None:
        return None
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime.datetime):
            out[k] = v.isoformat() + "Z"
        else:
            out[k] = v
    return out


async def find_user_by_uid(firebase_uid: str) -> Optional[Dict[str, Any]]:
    """Fetch a user document by Firebase UID. Returns None if not found."""
    db = get_database()
    if db is None:
        return None
    doc = await db.users.find_one({"firebase_uid": firebase_uid})
    return _serialize(doc) if doc else None


async def find_user_by_mobile(mobile: str, exclude_uid: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Check if a mobile number is already taken. Optionally exclude a given firebase_uid."""
    db = get_database()
    if db is None:
        return None
    query: Dict[str, Any] = {"mobile_number": mobile}
    if exclude_uid:
        query["firebase_uid"] = {"$ne": exclude_uid}
    doc = await db.users.find_one(query)
    return _serialize(doc) if doc else None


async def find_user_by_alt_mobile(mobile: str, exclude_uid: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Check if an alternate mobile number is already taken."""
    db = get_database()
    if db is None:
        return None
    query: Dict[str, Any] = {"alternate_mobile_number": mobile}
    if exclude_uid:
        query["firebase_uid"] = {"$ne": exclude_uid}
    doc = await db.users.find_one(query)
    return _serialize(doc) if doc else None


async def create_user(data: Dict[str, Any]) -> str:
    """
    Insert a new user document. Returns the inserted document ID as a string.
    """
    db = get_database()
    if db is None:
        raise RuntimeError("MongoDB not connected")
    now = datetime.datetime.utcnow()
    data.setdefault("created_at", now.isoformat() + "Z")
    data.setdefault("updated_at", now.isoformat() + "Z")
    result = await db.users.insert_one(data)
    return str(result.inserted_id)


async def update_user(firebase_uid: str, updates: Dict[str, Any]) -> bool:
    """
    Partial update on a user document. Returns True if a document was modified.
    """
    db = get_database()
    if db is None:
        return False
    updates["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    result = await db.users.update_one(
        {"firebase_uid": firebase_uid},
        {"$set": updates}
    )
    return result.modified_count > 0


async def upsert_user(firebase_uid: str, data: Dict[str, Any]) -> bool:
    """
    Insert-or-update user document. Returns True on success.
    """
    db = get_database()
    if db is None:
        return False
    now = datetime.datetime.utcnow().isoformat() + "Z"
    data["updated_at"] = now
    data.setdefault("created_at", now)
    result = await db.users.update_one(
        {"firebase_uid": firebase_uid},
        {"$set": data},
        upsert=True
    )
    return result.matched_count > 0 or result.upserted_id is not None


# ==============================================================================
# WORKOUT HISTORY & CALORIES ANALYTICS REPOSITORY
# ==============================================================================

async def save_workout_history(doc: Dict[str, Any]) -> str:
    """
    Save a workout session into the 'workout_history' collection.
    Creates index on (firebase_uid, workout_date) if not already created.
    """
    db = get_database()
    if db is None:
        return ""
    
    # Ensure index
    try:
        await db.workout_history.create_index([("firebase_uid", 1), ("workout_date", -1)])
        await db.workout_history.create_index([("user_id", 1), ("workout_date", -1)])
    except Exception as e:
        print("[MongoDB] Index creation warning:", e)

    now = datetime.datetime.utcnow().isoformat() + "Z"
    doc.setdefault("created_at", now)
    doc.setdefault("workout_date", datetime.date.today().isoformat())
    doc.setdefault("user_id", doc.get("firebase_uid", ""))

    result = await db.workout_history.insert_one(doc)
    return str(result.inserted_id)


async def get_workout_history(
    firebase_uid: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> Dict[str, Any]:
    """
    Query workout history for a specific user with date range and text filtering.
    """
    db = get_database()
    if db is None:
        return {"items": [], "total": 0}

    query: Dict[str, Any] = {"$or": [{"firebase_uid": firebase_uid}, {"user_id": firebase_uid}, {"uid": firebase_uid}]}

    if start_date or end_date:
        date_query: Dict[str, Any] = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        query["workout_date"] = date_query

    if search:
        query["$and"] = [
            {"$or": [
                {"exercise_type": {"$regex": search, "$options": "i"}},
                {"exercise_name": {"$regex": search, "$options": "i"}},
                {"workout_type": {"$regex": search, "$options": "i"}}
            ]}
        ]

    total = await db.workout_history.count_documents(query)
    cursor = db.workout_history.find(query).sort("workout_date", -1).skip(skip).limit(limit)
    docs = await cursor.to_list(length=limit)
    items = [_serialize(d) for d in docs]

    return {"items": items, "total": total}


async def get_calories_analytics(
    firebase_uid: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Calculate total calories, total workouts, average daily calories, and daily breakdown.
    """
    db = get_database()
    if db is None:
        return {"totalCalories": 0, "workouts": 0, "avgDaily": 0, "dailyBreakdown": []}

    query: Dict[str, Any] = {"$or": [{"firebase_uid": firebase_uid}, {"user_id": firebase_uid}, {"uid": firebase_uid}]}
    if start_date or end_date:
        date_query: Dict[str, Any] = {}
        if start_date:
            date_query["$gte"] = start_date
        if end_date:
            date_query["$lte"] = end_date
        query["workout_date"] = date_query

    cursor = db.workout_history.find(query).sort("workout_date", 1)
    docs = await cursor.to_list(length=2000)

    daily_map = {}
    total_kcal = 0.0
    total_reps = 0

    for d in docs:
        w_date = d.get("workout_date") or str(d.get("timestamp", ""))[:10]
        if not w_date:
            continue
        kcal = float(d.get("calories_burned") or d.get("predicted_kcal") or 0.0)
        reps = int(d.get("total_reps") or d.get("reps_completed") or 0)
        
        total_kcal += kcal
        total_reps += reps

        if w_date not in daily_map:
            daily_map[w_date] = {
                "date": w_date,
                "calories": 0.0,
                "workouts": 0,
                "reps": 0
            }
        daily_map[w_date]["calories"] += kcal
        daily_map[w_date]["workouts"] += 1
        daily_map[w_date]["reps"] += reps

    daily_breakdown = list(daily_map.values())
    for d in daily_breakdown:
        d["calories"] = round(d["calories"], 1)

    days_count = len(daily_breakdown) if daily_breakdown else 1
    avg_daily = round(total_kcal / days_count, 1)

    return {
        "totalCalories": round(total_kcal, 1),
        "workouts": len(docs),
        "totalReps": total_reps,
        "avgDaily": avg_daily,
        "dailyBreakdown": daily_breakdown
    }
