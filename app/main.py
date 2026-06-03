from __future__ import annotations

import asyncio
import uuid
import io
import csv
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.config import settings
from app.db import Base, engine, get_db
from app.models import LookupJob, LookupJobItem, LookupRequest, LookupResult
from app.schemas import (
    BulkLookupRequest,
    BulkLookupJobResponse,
    BulkLookupSyncResponse,
    JobStatusOut,
    JobItemOut,
    LookupRequestInput,
    LookupResponse,
    LookupResultOut,
)
from app.services.normalizer import normalize_phone
from app.services.orchestrator import create_lookup_request, run_lookup_with_store


app = FastAPI(title=settings.APP_NAME)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _to_result_out(row: LookupResult) -> LookupResultOut:
    details = row.details or {}
    return LookupResultOut(
        source=row.source,
        platform=details.get("platform"),
        match_type=row.match_type,
        name=row.name,
        account_handle=row.account_handle,
        account_url=row.account_url,
        organization=row.organization,
        location=row.location,
        confidence=float(row.confidence),
        evidence=row.evidence or [],
        details=details,
        raw=row.raw or {},
        discovered_at=row.discovered_at,
    )


def _to_job_item_out(row: LookupJobItem) -> JobItemOut:
    return JobItemOut(
        request_id=row.request_id,
        phone_raw=row.phone_raw,
        phone_e164=row.phone_e164,
        status=row.status,
        error=row.error,
        row_index=int(row.row_index),
    )


@app.get("/")
def root() -> FileResponse:
    return FileResponse(Path("app/static/index.html"))


@app.get("/api/v1/sources")
def sources() -> list[dict[str, str]]:
    return [
        {"key": "phonenumbers_metadata", "name": "Telefoon metadata", "status": "gratis"},
        {"key": "numverify", "name": "Numverify API", "status": "key vereist"},
        {"key": "serpapi", "name": "SerpAPI", "status": "key vereist"},
        {"key": "duckduckgo_search", "name": "DuckDuckGo Search", "status": "open internet"},
    ]


@app.post("/api/v1/lookup", response_model=LookupResponse)
async def lookup(phone_input: LookupRequestInput, db: Session = Depends(get_db)):
    try:
        normalize_phone(phone_input.phone_number)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ongeldig telefoonnummer",
        ) from exc

    request, created_new, phone_e164 = create_lookup_request(db, phone_input.phone_number)
    if request.status == "done" and not created_new:
        results = (
            db.query(LookupResult)
            .filter(LookupResult.request_id == request.id)
            .order_by(LookupResult.source)
            .all()
        )
        return LookupResponse(
            request_id=request.id,
            phone_raw=request.phone_raw,
            phone_e164=phone_e164,
            status="done",
            cached=True,
            results=[_to_result_out(r) for r in results],
        )

    try:
        results = await run_lookup_with_store(db, request)
    except Exception as exc:
        request.status = "error"
        request.error = str(exc)
        request.updated_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=500, detail="Lookup fout")

    return LookupResponse(
        request_id=request.id,
        phone_raw=request.phone_raw,
        phone_e164=phone_e164,
        status=request.status,
        cached=False,
        results=[_to_result_out(r) for r in results],
    )


@app.post("/api/v1/lookup/bulk", response_model=BulkLookupSyncResponse | BulkLookupJobResponse)
async def lookup_bulk(
    payload: BulkLookupRequest,
    background_tasks,
    db: Session = Depends(get_db),
):
    numbers = [n.strip() for n in payload.numbers if n and n.strip()]
    if not numbers:
        raise HTTPException(status_code=400, detail="Geen telefoonnummers ontvangen")
    if len(numbers) > settings.MAX_BULK_ITEMS or payload.max_items > settings.MAX_BULK_ITEMS:
        raise HTTPException(
            status_code=400,
            detail=f"Max {settings.MAX_BULK_ITEMS} per batch",
        )
    invalid: list[str] = []
    for raw in numbers:
        try:
            normalize_phone(raw)
        except Exception:
            invalid.append(raw)
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Ongeldige nummers: {', '.join(invalid)}",
        )

    if len(numbers) > payload.max_items:
        numbers = numbers[:payload.max_items]

    if not payload.async_mode:
        results: list[LookupResponse] = []
        for raw in numbers:
            req, created_new, phone_e164 = create_lookup_request(db, raw)
            if created_new:
                response = await run_lookup_with_store(db, req)
            else:
                response = (
                    db.query(LookupResult)
                    .filter(LookupResult.request_id == req.id)
                    .order_by(LookupResult.source)
                    .all()
                )
            results.append(
                LookupResponse(
                    request_id=req.id,
                    phone_raw=req.phone_raw,
                    phone_e164=phone_e164,
                    status=req.status,
                    cached=not created_new,
                    results=[_to_result_out(row) for row in response],
                )
            )
        return BulkLookupSyncResponse(results=results, request_count=len(results))

    job = LookupJob(
        id=str(uuid.uuid4()),
        status="queued",
        total_items=len(numbers),
        processed_items=0,
    )
    db.add(job)
    db.flush()
    for idx, raw in enumerate(numbers):
        db.add(
            LookupJobItem(
                id=str(uuid.uuid4()),
                job_id=job.id,
                phone_raw=raw,
                row_index=idx,
                status="queued",
            )
        )
    db.commit()

    background_tasks.add_task(_process_job, job.id, numbers)
    return BulkLookupJobResponse(job_id=job.id, total_items=len(numbers), async_mode=True)


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusOut)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(LookupJob).filter(LookupJob.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job bestaat niet")
    items = (
        db.query(LookupJobItem)
        .filter(LookupJobItem.job_id == job_id)
        .order_by(LookupJobItem.row_index)
        .all()
    )
    percent = 0.0
    if job.total_items > 0:
        percent = round((job.processed_items / job.total_items) * 100, 2)
    return JobStatusOut(
        job_id=job.id,
        status=job.status,
        total_items=job.total_items,
        processed_items=job.processed_items,
        percent=percent,
        items=[_to_job_item_out(item) for item in items],
        error=job.error,
    )


@app.get("/api/v1/requests/{request_id}", response_model=LookupResponse)
def get_request(request_id: str, db: Session = Depends(get_db)):
    req = db.query(LookupRequest).filter(LookupRequest.id == request_id).one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Request bestaat niet")
    results = db.query(LookupResult).filter(LookupResult.request_id == req.id).order_by(LookupResult.source).all()
    return LookupResponse(
        request_id=req.id,
        phone_raw=req.phone_raw,
        phone_e164=req.phone_e164,
        status=req.status,
        cached=False,
        results=[_to_result_out(r) for r in results],
    )


@app.get("/api/v1/jobs/{job_id}/results")
def get_job_results(job_id: str, db: Session = Depends(get_db)):
    job = db.query(LookupJob).filter(LookupJob.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job bestaat niet")
    rows = (
        db.query(LookupJobItem)
        .filter(LookupJobItem.job_id == job_id)
        .order_by(LookupJobItem.row_index)
        .all()
    )
    out = []
    for row in rows:
        if row.request_id:
            req = db.query(LookupRequest).filter(LookupRequest.id == row.request_id).one_or_none()
            out.append(
                {
                    "row_index": int(row.row_index),
                    "phone_raw": row.phone_raw,
                    "phone_e164": row.phone_e164,
                    "request_id": row.request_id,
                    "status": row.status,
                    "result_count": req and db.query(LookupResult).filter(LookupResult.request_id == req.id).count() or 0,
                }
            )
        else:
            out.append(
                {
                    "row_index": int(row.row_index),
                    "phone_raw": row.phone_raw,
                    "phone_e164": row.phone_e164,
                    "status": row.status,
                    "request_id": None,
                    "result_count": 0,
                }
            )
    return {"job_id": job_id, "status": job.status, "items": out}


@app.get("/api/v1/requests/{request_id}/export.csv")
def export_request_csv(request_id: str, db: Session = Depends(get_db)):
    req = db.query(LookupRequest).filter(LookupRequest.id == request_id).one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail="Request bestaat niet")
    rows = (
        db.query(LookupResult)
        .filter(LookupResult.request_id == req.id)
        .order_by(LookupResult.source, LookupResult.confidence.desc())
        .all()
    )

    def _iter_csv() -> io.StringIO:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "request_id",
                "phone_raw",
                "phone_e164",
                "source",
                "platform",
                "match_type",
                "name",
                "organization",
                "location",
                "account_handle",
                "account_url",
                "confidence",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    req.id,
                    req.phone_raw,
                    req.phone_e164,
                    row.source,
                    (row.details or {}).get("platform", ""),
                    row.match_type,
                    row.name or "",
                    row.organization or "",
                    row.location or "",
                    row.account_handle or "",
                    row.account_url or "",
                    row.confidence,
                ]
            )
        output.seek(0)
        return output

    return StreamingResponse(
        _iter_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="lookup_{request_id}.csv"'},
    )


async def _process_job(job_id: str, numbers: list[str]) -> None:
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        job = db.query(LookupJob).filter(LookupJob.id == job_id).one()
        job.status = "running"
        db.commit()

        for idx, raw in enumerate(numbers):
            item = (
                db.query(LookupJobItem)
                .filter(LookupJobItem.job_id == job_id, LookupJobItem.row_index == idx)
                .one_or_none()
            )
            if item is None:
                continue
            item.status = "running"
            db.commit()
            try:
                req, _, phone_e164 = create_lookup_request(db, raw)
                if req.status != "done":
                    await run_lookup_with_store(db, req)
                item.request_id = req.id
                item.phone_e164 = phone_e164
                item.status = "done"
            except Exception as exc:
                item.status = "error"
                item.error = str(exc)
                db.flush()
            job.processed_items = job.processed_items + 1
            db.commit()
            await asyncio.sleep(0)

        job.status = "done"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as exc:
        job = db.query(LookupJob).filter(LookupJob.id == job_id).one_or_none()
        if job:
            job.status = "error"
            job.error = str(exc)
            db.commit()
    finally:
        db.close()
