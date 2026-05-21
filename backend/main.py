import os
from datetime import datetime, timedelta, timezone

import motor.motor_asyncio
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from twilio.rest import Client

from ai import generate_blog
from devto import publish_to_platforms
from models.reminder import PublishRecord
from services.reminder_scheduler import start_scheduler

load_dotenv()

app = FastAPI(title="LeetLog AI", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Twilio Setup
# -----------------------------
twilio_client = Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"))

# -----------------------------
# MongoDB Setup
# -----------------------------
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGODB_URI"))

db = mongo_client.leetcodeai


# -----------------------------
# Models
# -----------------------------
class Problem(BaseModel):
    title: str
    description: str
    code: str
    author: str = "Anonymous Developer"
    client_time: str = None  # Optional client time string
    custom_prompt: str = None  # custom_prompt for the user
    platforms: list[str] | None = None
    publish_as_draft: bool = False
    tags: list[str] | None = None


class ReminderPreference(BaseModel):
    whatsapp_number: str
    reminder_time: str = "09:00"
    timezone: str = "Asia/Kolkata"
    is_opted_in: bool = True


# -----------------------------
# Startup Event
# -----------------------------
@app.on_event("startup")
async def startup_event():
    """
    Start background schedulers when server starts.
    """

    try:
        start_scheduler()
        print("Reminder scheduler started successfully.")
    except Exception as e:
        print(f"Reminder scheduler failed to start: {e}")


# -----------------------------
# Health Check
# -----------------------------
@app.get("/")
def health_check():
    return {"status": "ok", "message": "LeetLog AI backend is running."}


# -----------------------------
# Blog Generator Endpoint
# -----------------------------
@app.post("/generate-blog")
async def create_blog(problem: Problem):
    """
    Accepts a LeetCode problem and:
    1. Generates a blog using Gemini AI
    2. Publishes it to one or more configured platforms
    """
    if problem.custom_prompt and len(problem.custom_prompt.strip()) > 1000:
        raise HTTPException(
            status_code=400,
            detail="Custom prompt exceeds maximum length of 1000 characters.",
        )

    if not problem.code or problem.code.strip() == "":
        return {"status": "error", "message": "Code is empty, cannot generate blog."}

    try:
        blog_content = generate_blog(problem)

    except Exception as e:
        return {"status": "error", "message": f"Gemini API failure: {str(e)}"}

    try:
        platform_results = publish_to_platforms(
            problem.title,
            blog_content,
            platforms=problem.platforms,
            published=not problem.publish_as_draft,
            tags=problem.tags,
        )
        successful = [r for r in platform_results if r.get("status") == "success"]
        overall_status = (
            "success"
            if len(successful) == len(platform_results)
            else "partial_success"
            if successful
            else "error"
        )
    except Exception as e:
        return {"status": "error", "message": f"Publishing failure: {str(e)}"}
    
    try:
        record = PublishRecord(
            title=problem.title,
            date=datetime.now(timezone.utc).isoformat(),
            platforms=[r["platform"] for r in successful],
            status=overall_status,
            author=problem.author,
        )

        await db.problem_info.update_one(
            {
                "title": problem.title,
                "author": problem.author,
            },
            {
                "$set": record.model_dump(),
            },
            upsert=True,
        )

    except Exception as e:
        print(f"Database logging failed: {e}")

    return {
        "status": overall_status,
        "data": {
            "blog_content": blog_content,
            "platforms": platform_results,
        },
    }


# dashboard endpoints
@app.get("/dashboard/stats")
async def get_dashboard_stats():
    total = await db.problem_info.count_documents({})

    pipeline_platforms = [
        {"$unwind": "$platforms"},
        {"$group": {"_id": "$platforms", "count": {"$sum": 1}}},
    ]
    platform_cursor = db.problem_info.aggregate(pipeline_platforms)
    platform_counts = {doc["_id"]: doc["count"] async for doc in platform_cursor}

    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    pipeline_week = [
        {"$match": {"date": {"$gte": seven_days_ago}}},
        {
            "$group": {
                "_id": {"$substr": ["$date", 0, 10]},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]
    week_cursor = db.problem_info.aggregate(pipeline_week)
    week_activity = {doc["_id"]: doc["count"] async for doc in week_cursor}

    recent_cursor = (
        db.problem_info.find(
            {},
            {"_id": 0, "title": 1, "date": 1, "platforms": 1, "status": 1, "author": 1},
        )
        .sort("date", -1)
        .limit(10)
    )
    recent = [doc async for doc in recent_cursor]

    return {
        "total_posts": total,
        "platform_counts": platform_counts,
        "week_activity": week_activity,
        "recent": recent,
    }


@app.get("/dashboard/history")
async def get_dashboard_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    skip = (page - 1) * page_size
    cursor = (
        db.problem_info.find({}, {"_id": 0})
        .sort("date", -1)
        .skip(skip)
        .limit(page_size)
    )
    records = [doc async for doc in cursor]
    total = await db.problem_info.count_documents({})
    return {"page": page, "page_size": page_size, "total": total, "records": records}


@app.post("/dashboard/record")
async def record_publish(record: PublishRecord):
    await db.problem_info.update_one(
        {
            "title": record.title,
            "author": record.author
        },
        {
            "$set": record.model_dump()
        },
        upsert=True
    )
    return {"status": "ok"}



# -----------------------------
# Reminder Infrastructure
# -----------------------------
@app.get("/reminder-health")
def reminder_health():
    """
    Health check endpoint for reminder services.
    """

    return {"status": "active", "message": "Reminder call infrastructure is running."}


@app.post("/reminder/subscribe")
async def subscribe(pref: ReminderPreference):
    await db.preferences.update_one(
        {"whatsapp_number": pref.whatsapp_number}, {"$set": pref.dict()}, upsert=True
    )

    return {"status": "success", "message": "Subscribed!"}


@app.post("/reminder/unsubscribe")
async def unsubscribe(data: dict):
    await db.preferences.update_one(
        {"whatsapp_number": data["whatsapp_number"]}, {"$set": {"is_opted_in": False}}
    )

    return {"status": "success", "message": "Unsubscribed!"}


# -----------------------------
# Run Server
# -----------------------------
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=10000, reload=True)
