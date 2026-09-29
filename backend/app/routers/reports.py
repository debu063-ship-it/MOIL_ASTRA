# -*- coding: utf-8 -*-
import os
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from .. import config
from ..db import ReportJob, session
from ..services.report_builder import generate_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate")
def generate(background: BackgroundTasks, scope: str = "full"):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with session() as s:
        job = ReportJob(created_at=now, scope=scope, status="queued")
        s.add(job)
        s.commit()
        s.refresh(job)
        job_id = job.id
    background.add_task(generate_report, scope, job_id)
    return {"job_id": job_id, "status": "queued", "poll": f"/api/v1/reports/status/{job_id}"}


@router.get("/status/{job_id}")
def status(job_id: int):
    with session() as s:
        job = s.get(ReportJob, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        return {"job_id": job.id, "status": job.status, "file": job.file_path,
                "error": job.error, "created_at": job.created_at}


@router.get("/download/{job_id}")
def download(job_id: int):
    with session() as s:
        job = s.get(ReportJob, job_id)
        if not job:
            raise HTTPException(404, "job not found")
        if job.status != "done" or not job.file_path or not os.path.exists(job.file_path):
            raise HTTPException(409, f"report not ready (status={job.status})")
        media = "application/pdf" if job.file_path.endswith(".pdf") else "text/html"
        return FileResponse(job.file_path, media_type=media,
                            filename=os.path.basename(job.file_path))
