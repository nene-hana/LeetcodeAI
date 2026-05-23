import asyncio
import os
from datetime import datetime, timezone
import motor.motor_asyncio
from alerts.elevenlabs_service import generate_message
from alerts.twilio_service import send_whatsapp_message

# Setup sync-to-async MongoDB connection
mongo_client = motor.motor_asyncio.AsyncIOMotorClient(os.getenv("MONGODB_URI"))
db = mongo_client.leetcodeai

async def _check_unsolved_users_async():
    # Fetch all opted-in users from preferences
    cursor = db.preferences.find({"is_opted_in": True})
    users = await cursor.to_list(length=100)
    
    # Check if they have solved a problem today
    today = datetime.now(timezone.utc).date()
    
    for user in users:
        phone = user.get("whatsapp_number")
        if not phone:
            continue
            
        # Check if there is a blog post created today
        # Date is stored as ISO format string, we can do a regex or range query
        # Since it's stored as '2026-05-23T...', we can do a prefix match
        today_str = today.isoformat()
        
        solved_today_count = await db.problem_info.count_documents({
            "date": {"$regex": f"^{today_str}"}
        })
        
        if solved_today_count == 0:
            # Not solved today, send reminder!
            name = "Vansh" # Fallback or could add name to DB
            message = generate_message(name)
            
            print("Triggering alert for:", name)
            print(message)
            try:
                send_whatsapp_message(phone, message)
                print(f"WhatsApp message sent successfully to {phone}!")
            except Exception as e:
                print(f"Failed to send WhatsApp message to {phone}:", e)
                
            try:
                # 1. Generate Audio via ElevenLabs
                from alerts.elevenlabs_service import generate_audio
                from alerts.twilio_service import make_call
                
                print("Generating audio via ElevenLabs...")
                audio_file = generate_audio(message)
                
                # 2. Construct public URL to the static file
                # If running on Render, construct the correct host
                backend_url = os.getenv("BACKEND_URL", "https://leetcodeai-backend.onrender.com")
                # Ensure no trailing slash
                if backend_url.endswith("/"):
                    backend_url = backend_url[:-1]
                
                audio_url = f"{backend_url}/{audio_file}"
                print(f"Audio available at: {audio_url}")
                
                # 3. Make the Voice Call via Twilio
                print(f"Making phone call to {phone}...")
                call_sid = make_call(phone, audio_url)
                print(f"Call placed successfully to {phone}, SID: {call_sid}")
            except Exception as e:
                print(f"Failed to generate audio or make call to {phone}:", e)
                
        else:
            print(f"User {phone} has already solved {solved_today_count} problems today!")

def check_unsolved_users():
    asyncio.run(_check_unsolved_users_async())
