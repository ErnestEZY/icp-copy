import asyncio
import sys, os
import io
from datetime import datetime, timezone
from docx import Document
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import ObjectId

# Add the project root to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.config import MONGO_URI, DB_NAME
from backend.auth import hash_password
from backend.services.utils import get_malaysia_time

async def main():
    # Initialize client inside async function to avoid loop conflicts
    client = AsyncIOMotorClient(MONGO_URI or "mongodb://localhost:27017")
    db = client[DB_NAME]
    
    users = db["users"]
    resumes = db["resumes"]
    interviews = db["interviews"]
    audit_logs = db["audit_logs"]
    fs = AsyncIOMotorGridFSBucket(db, bucket_name="resume_files")
    
    print("Clearing existing data...")
    await users.delete_many({})
    await resumes.delete_many({})
    await interviews.delete_many({})
    await audit_logs.delete_many({})
    
    now = get_malaysia_time()
    
    print("Seeding users...")
    u1_doc = {
        "email": "alice@example.com",
        "password_hash": hash_password("Pass123!"),
        "role": "user",
        "created_at": now,
        "weekly_question_count": 0,
        "weekly_reset_at": now,
        "daily_resume_count": 0,
        "daily_interview_count": 0,
        "daily_reset_at": now,
        "last_login_ip": "127.0.0.1"
    }
    u2_doc = {
        "email": "bob@example.com",
        "password_hash": hash_password("Pass123!"),
        "role": "user",
        "created_at": now,
        "weekly_question_count": 0,
        "weekly_reset_at": now,
        "daily_resume_count": 0,
        "daily_interview_count": 0,
        "daily_reset_at": now,
        "last_login_ip": "127.0.0.1"
    }
    
    u1 = await users.insert_one(u1_doc)
    u2 = await users.insert_one(u2_doc)
    
    print("Creating sample resume file in GridFS...")
    # Create a sample DOCX and store in GridFS
    buf = io.BytesIO()
    doc = Document()
    doc.add_paragraph("Alice Sample Resume\n\nExperience: Software Developer at ExampleCorp\nSkills: Python, FastAPI, MongoDB")
    doc.save(buf)
    buf.seek(0)
    grid_id = await fs.upload_from_stream("alice_sample_resume.docx", buf.getvalue())
    
    print("Seeding resumes...")
    await resumes.insert_one({
        "user_id": str(u1.inserted_id),
        "filename": "alice_sample_resume.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "consent": True,
        "file_id": str(grid_id),
        "text": "Alice Sample Resume\n\nExperience: Software Developer at ExampleCorp\nSkills: Python, FastAPI, MongoDB",
        "feedback": {
            "Score": 85,
            "Advantages": ["Clear technical stack", "Relevant experience"],
            "Disadvantages": ["Missing certifications", "Short project descriptions"],
            "Suggestions": ["Add GitHub link", "Quantify achievements"],
            "Keywords": ["Python", "FastAPI", "MongoDB"]
        },
        "status": "approved",
        "tags": ["Python", "FastAPI"],
        "notes": "Excellent candidate for backend role.",
        "created_at": now
    })
    
    await resumes.insert_one({
        "user_id": str(u2.inserted_id),
        "filename": "bob_cv.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "consent": True,
        "text": "Bob resume text content for testing purposes.",
        "feedback": {
            "Score": 70,
            "Advantages": ["Good layout"],
            "Disadvantages": ["Lacks specific skills"],
            "Suggestions": ["Be more specific about tools used"],
            "Keywords": ["Management"]
        },
        "status": "pending",
        "tags": ["Management"],
        "notes": "Needs more technical depth.",
        "created_at": now
    })
    
    print("Seeding successful!")
    client.close()

if __name__ == "__main__":
    asyncio.run(main())
