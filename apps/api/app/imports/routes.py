"""Import API routes."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.auth.dependencies import get_current_user_id, get_db_with_rls
from app.core.business_metrics import BusinessMetric
from app.core.config import settings
from app.core.metrics_service import MetricsService
from app.imports import schemas
from app.imports.service import ImportService
from app.imports.models import ImportJob
from app.jobs.queue import imports_queue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/upload", response_model=schemas.ImportJobResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    entity_type: str = Query(..., description="Entity type: people, memberships, first_timers, services, attendance, cells, cell_reports, finance_entries"),
    import_mode: str = Query(
        default="create_only",
        pattern="^(create_only|update_existing)$",
        description="Import mode",
    ),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Upload file and create import job."""
    tenant_id = UUID(settings.tenant_id)

    # Validate file size (100MB limit)
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File size exceeds maximum of {MAX_FILE_SIZE / (1024*1024)}MB",
        )

    try:
        job = ImportService.upload_file(
            db=db,
            user_id=user_id,
            tenant_id=tenant_id,
            file_content=file_content,
            filename=file.filename or "uploaded_file",
            entity_type=entity_type,
            import_mode=import_mode,
        )

        # Emit business metric
        MetricsService.emit_import_metric(
            metric_name=BusinessMetric.IMPORT_STARTED,
            tenant_id=tenant_id,
            user_id=user_id,
            entity_type=entity_type,
        )

        return schemas.ImportJobResponse(
            id=job.id,
            tenant_id=job.tenant_id,
            user_id=job.user_id,
            entity_type=job.entity_type,
            file_name=job.file_name,
            file_format=job.file_format,
            file_size=job.file_size,
            status=job.status,
            import_mode=job.import_mode,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            imported_count=job.imported_count,
            error_count=job.error_count,
            skipped_count=job.skipped_count,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get("/jobs/{job_id}", response_model=schemas.ImportJobResponse)
async def get_job_status(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get import job status."""
    tenant_id = UUID(settings.tenant_id)

    job = ImportService.get_job_status(db, job_id, tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import job {job_id} not found",
        )

    return schemas.ImportJobResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        user_id=job.user_id,
        entity_type=job.entity_type,
        file_name=job.file_name,
        file_format=job.file_format,
        file_size=job.file_size,
        status=job.status,
        import_mode=job.import_mode,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        imported_count=job.imported_count,
        error_count=job.error_count,
        skipped_count=job.skipped_count,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/jobs/{job_id}/preview", response_model=schemas.ImportPreviewResponse)
async def create_preview(
    job_id: UUID,
    mapping_config: Optional[schemas.ImportMappingRequest] = None,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create preview with auto-mapped columns."""
    tenant_id = UUID(settings.tenant_id)

    try:
        mapping_dict = None
        if mapping_config:
            mapping_dict = {
                source: {
                    "target_field": config.target_field,
                    "coercion_type": config.coercion_type,
                    "required": config.required,
                    "default_value": config.default_value,
                }
                for source, config in mapping_config.mapping_config.items()
            }

        preview = ImportService.create_preview(
            db=db,
            job_id=job_id,
            tenant_id=tenant_id,
            mapping_config=mapping_dict,
        )

        return schemas.ImportPreviewResponse(**preview)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch("/jobs/{job_id}/mapping", response_model=schemas.ImportJobResponse)
async def update_mapping(
    job_id: UUID,
    request: schemas.ImportMappingRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update column mapping."""
    tenant_id = UUID(settings.tenant_id)

    try:
        mapping_dict = {
            source: {
                "target_field": config.target_field,
                "coercion_type": config.coercion_type,
                "required": config.required,
                "default_value": config.default_value,
            }
            for source, config in request.mapping_config.items()
        }

        job = ImportService.update_mapping(
            db=db,
            job_id=job_id,
            tenant_id=tenant_id,
            mapping_config=mapping_dict,
        )

        return schemas.ImportJobResponse(
            id=job.id,
            tenant_id=job.tenant_id,
            user_id=job.user_id,
            entity_type=job.entity_type,
            file_name=job.file_name,
            file_format=job.file_format,
            file_size=job.file_size,
            status=job.status,
            import_mode=job.import_mode,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            imported_count=job.imported_count,
            error_count=job.error_count,
            skipped_count=job.skipped_count,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/jobs/{job_id}/validate", response_model=schemas.ImportValidationResponse)
async def validate_preview(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Validate all rows in the import file."""
    tenant_id = UUID(settings.tenant_id)

    try:
        validation = ImportService.validate_preview(db, job_id, tenant_id)
        
        # Emit business metric if there are validation errors
        if validation.get("total_errors", 0) > 0:
            # Get job to get entity_type
            from app.common.models import ImportJob
            job = db.get(ImportJob, job_id)
            if job:
                MetricsService.emit_import_metric(
                    metric_name=BusinessMetric.IMPORT_VALIDATION_ERROR,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    entity_type=job.entity_type,
                    total_errors=validation.get("total_errors", 0),
                    errors_by_type=validation.get("errors_by_type", {}),
                )
        
        return schemas.ImportValidationResponse(**validation)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post("/jobs/{job_id}/execute", response_model=schemas.ImportJobResponse)
async def execute_import(
    job_id: UUID,
    request: Optional[schemas.ImportExecuteRequest] = None,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Execute import (async)."""
    tenant_id = UUID(settings.tenant_id)

    job = ImportService.get_job_status(db, job_id, tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import job {job_id} not found",
        )

    if job.status not in ["previewing", "mapping", "validating"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot execute import in status: {job.status}",
        )

    if not job.mapping_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mapping configuration not set",
        )

    # Handle dry_run mode
    dry_run = False
    if request and request.dry_run:
        dry_run = True
        job.dry_run = True
        job.status = "validating"
    else:
        job.status = "queued"
    
    db.commit()

    # Enqueue background job
    imports_queue.enqueue("app.jobs.tasks.process_import_job", str(job.id))

    # Emit business metric
    MetricsService.emit_import_metric(
        metric_name=BusinessMetric.IMPORT_STARTED,
        tenant_id=tenant_id,
        user_id=user_id,
        entity_type=job.entity_type,
        dry_run=dry_run,
    )

    return schemas.ImportJobResponse(
        id=job.id,
        tenant_id=job.tenant_id,
        user_id=job.user_id,
        entity_type=job.entity_type,
        file_name=job.file_name,
        file_format=job.file_format,
        file_size=job.file_size,
        status=job.status,
        import_mode=job.import_mode,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        imported_count=job.imported_count,
        error_count=job.error_count,
        skipped_count=job.skipped_count,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/jobs/{job_id}/errors")
async def download_error_report(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Download error report CSV."""
    tenant_id = UUID(settings.tenant_id)

    error_content = ImportService.download_error_report(db, job_id, tenant_id)
    if not error_content:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Error report not found",
        )

    return StreamingResponse(
        iter([error_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="import_errors_{job_id}.csv"'},
    )


@router.get("/jobs/{job_id}/stream")
async def stream_import_progress(
    job_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """
    Stream import job progress via Server-Sent Events (SSE).
    
    Client can connect using EventSource API:
    const eventSource = new EventSource('/api/v1/imports/jobs/{job_id}/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Progress:', data);
    };
    """
    tenant_id = UUID(settings.tenant_id)
    
    # Verify job exists and user has access
    job = ImportService.get_job_status(db, job_id, tenant_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import job {job_id} not found",
        )

    async def event_generator():
        """Generate SSE events for import progress."""
        last_processed = -1
        last_status = None
        timeout_seconds = 300  # 5 minutes timeout
        start_time = asyncio.get_event_loop().time()
        
        try:
            while True:
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout_seconds:
                    yield f"event: timeout\ndata: {json.dumps({'message': 'Connection timeout'})}\n\n"
                    break
                
                # Re-query job from database to get latest status
                current_job = ImportService.get_job_status(db, job_id, tenant_id)
                if not current_job:
                    yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
                    break
                
                # Calculate progress percentage
                progress_percent = None
                if current_job.total_rows and current_job.total_rows > 0:
                    progress_percent = (current_job.processed_rows / current_job.total_rows) * 100
                
                # Send update if progress changed or status changed
                if (current_job.processed_rows != last_processed or 
                    current_job.status != last_status):
                    
                    data = {
                        "job_id": str(current_job.id),
                        "status": current_job.status,
                        "processed_rows": current_job.processed_rows,
                        "total_rows": current_job.total_rows,
                        "imported_count": current_job.imported_count,
                        "error_count": current_job.error_count,
                        "skipped_count": current_job.skipped_count,
                        "progress_percent": round(progress_percent, 2) if progress_percent else None,
                    }
                    
                    yield f"event: progress\ndata: {json.dumps(data)}\n\n"
                    
                    last_processed = current_job.processed_rows
                    last_status = current_job.status
                
                # Stop if job is completed or failed
                if current_job.status in ["completed", "failed"]:
                    final_data = {
                        "job_id": str(current_job.id),
                        "status": current_job.status,
                        "processed_rows": current_job.processed_rows,
                        "total_rows": current_job.total_rows,
                        "imported_count": current_job.imported_count,
                        "error_count": current_job.error_count,
                        "skipped_count": current_job.skipped_count,
                        "progress_percent": 100.0 if current_job.status == "completed" else None,
                    }
                    yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"
                    break
                
                # Wait before next check
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for import job {job_id}")
        except Exception as e:
            logger.error(f"Error in SSE stream for import job {job_id}: {e}", exc_info=True)
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/jobs", response_model=list[schemas.ImportJobResponse])
async def list_import_jobs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List user's import jobs."""
    tenant_id = UUID(settings.tenant_id)

    jobs = db.execute(
        select(ImportJob)
        .where(ImportJob.tenant_id == tenant_id, ImportJob.user_id == user_id)
        .order_by(ImportJob.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    return [
        schemas.ImportJobResponse(
            id=job.id,
            tenant_id=job.tenant_id,
            user_id=job.user_id,
            entity_type=job.entity_type,
            file_name=job.file_name,
            file_format=job.file_format,
            file_size=job.file_size,
            status=job.status,
            import_mode=job.import_mode,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            imported_count=job.imported_count,
            error_count=job.error_count,
            skipped_count=job.skipped_count,
            started_at=job.started_at,
            completed_at=job.completed_at,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )
        for job in jobs
    ]

