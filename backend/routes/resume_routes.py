from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from datetime import datetime, timezone, timedelta
from bson import ObjectId
import os
import base64
from ..db import resumes, users, fs
from ..models import ResumeFeedback
from ..auth import get_current_user
from ..services.resume_parser import extract_resume_text
from ..services.ai_feedback import get_feedback
from ..services.rate_limit import rate_limit
from ..services.utils import is_gibberish, get_malaysia_time
from ..services.daily_limit import check_daily_limit, increment_daily_limit

router = APIRouter(prefix="/api/resume", tags=["resume"])

@router.get("/limits")
async def get_resume_limits(current=Depends(get_current_user)):
    can_upload, remaining = await check_daily_limit(current["id"], "daily_resume_count", 5)
    return {"remaining": remaining, "limit": 5}

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_title: str = Form(...),
    consent: bool = Form(False),
    current=Depends(get_current_user),
    _: None = Depends(rate_limit),
):
    if current.get("role") != "user":
        raise HTTPException(status_code=403, detail="Only regular users can upload resumes")
    
    can_upload, remaining = await check_daily_limit(current["id"], "daily_resume_count", 5)
    if not can_upload:
        raise HTTPException(status_code=429, detail="Daily resume analysis limit reached. Resets at 00:00 Malaysia Time.")

    if is_gibberish(job_title):
        raise HTTPException(status_code=400, detail="Invalid job title. Please provide a clear title.")

    name = file.filename
    tmp_path = os.path.join("backend", "tmp_" + name.replace(" ", "_"))
    file_bytes = await file.read()
    with open(tmp_path, "wb") as f:
        f.write(file_bytes)
    try:
        text, mime = extract_resume_text(tmp_path)
    except Exception as e:
        os.remove(tmp_path)
        raise HTTPException(status_code=400, detail=str(e))
    os.remove(tmp_path)
    feedback = get_feedback(text)
    
    # Increment daily count only after successful analysis
    await increment_daily_limit(current["id"], "daily_resume_count")
    
    # Update user status and target job title
    user_id_obj = None
    try:
        user_id_obj = ObjectId(current["id"])
    except:
        user_id_obj = current["id"]

    await users.update_one(
        {"_id": user_id_obj}, 
        {"$set": {"has_analyzed": True, "target_job_title": job_title}}
    )

    if consent:
        # Store file in GridFS
        try:
            grid_id = await fs.upload_from_stream(name, file_bytes)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to store file: {e}")
        doc = {
            "resume_id": str(ObjectId()),
            "user_id": current["id"],
            "filename": name,
            "mime_type": mime,
            "consent": consent,
            "file_id": str(grid_id),
            "text": text,
            "job_title": job_title,
            "feedback": feedback,
            "status": "pending",
            "tags": feedback.get("Keywords", []),
            "notes": "",
            "created_at": get_malaysia_time(),
        }
        res = await resumes.insert_one(doc)
        return {"id": str(res.inserted_id), "feedback": feedback}
    else:
        return {"id": None, "feedback": feedback}

@router.get("/my")
async def my_resumes(current=Depends(get_current_user)):
    if current.get("role") != "user":
        raise HTTPException(status_code=403, detail="Only regular users can view their resumes")
    cur = resumes.find({"user_id": current["id"]})
    items = []
    async for r in cur:
        items.append(
            {
                "id": str(r["_id"]),
                "filename": r["filename"],
                "status": r.get("status", "pending"),
                "created_at": r.get("created_at"),
                "tags": r.get("tags", []),
            }
        )
    return items
