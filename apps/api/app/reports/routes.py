"""Reports API routes."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user_id, get_db_with_rls
from app.core.config import settings
from app.core.business_metrics import BusinessMetric
from app.core.metrics_service import MetricsService
from app.reports import schemas
from app.reports.service import (
    ReportService,
    ExportService,
    TemplateService,
    ScheduleService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


# Dashboard Endpoints

@router.get("/dashboards/{dashboard_type}", response_model=schemas.DashboardResponse)
async def get_dashboard(
    dashboard_type: str,
    org_unit_id: Optional[UUID] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    group_by: Optional[str] = Query(None, pattern="^(day|week|month|quarter|year)$"),
    include_children: bool = Query(False),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get predefined dashboard data."""
    # Validate dashboard type
    valid_types = ["membership", "attendance", "finance", "cells", "overview"]
    if dashboard_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid dashboard type. Must be one of: {', '.join(valid_types)}",
        )

    tenant_id = UUID(settings.tenant_id)

    try:
        data = ReportService.get_dashboard(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            dashboard_type=dashboard_type,
            org_unit_id=org_unit_id,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            include_children=include_children,
        )

        # Emit business metric
        MetricsService.emit_report_metric(
            metric_name=BusinessMetric.REPORT_DASHBOARD_VIEWED,
            tenant_id=tenant_id,
            user_id=user_id,
            report_type=dashboard_type,
        )

        return schemas.DashboardResponse(
            data={
                "results": data.get("results", []),
                "total": data.get("total", 0),
            },
            metadata={
                "dashboard_type": dashboard_type,
                **data.get("metadata", {}),
            },
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


# Query Endpoint

@router.post("/query", response_model=schemas.ReportQueryResponse)
async def execute_query(
    query: schemas.ReportQueryRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Execute flexible query for custom visualizations."""
    tenant_id = UUID(settings.tenant_id)

    try:
        # Convert Pydantic models to dicts for service layer
        query_dict = query.model_dump()
        query_dict["aggregations"] = [
            agg.model_dump() if isinstance(agg, schemas.AggregationConfig) else agg
            for agg in query.aggregations
        ]
        query_dict["order_by"] = [
            order.model_dump() if isinstance(order, schemas.OrderByConfig) else order
            for order in query.order_by
        ]
        if query.data_quality:
            query_dict["data_quality"] = query.data_quality.model_dump()
        if query.visualization:
            query_dict["visualization"] = query.visualization.model_dump()

        result = ReportService.execute_query(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            query_request=query_dict,
        )

        # Emit business metric
        MetricsService.emit_report_metric(
            metric_name=BusinessMetric.REPORT_QUERY_EXECUTED,
            tenant_id=tenant_id,
            user_id=user_id,
            report_type=query.entity_type if hasattr(query, 'entity_type') else None,
        )

        return schemas.ReportQueryResponse(
            results=result["results"],
            total=result.get("total"),
            limit=result["limit"],
            offset=result["offset"],
            metadata=result.get("metadata", {}),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query execution failed: {str(e)}",
        ) from e


# Export Endpoints

@router.post("/exports", response_model=schemas.ExportJobResponse, status_code=status.HTTP_201_CREATED)
async def create_export(
    request: schemas.ExportJobRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create export job."""
    tenant_id = UUID(settings.tenant_id)

    # Validate request
    if not request.query and not request.template_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either query or template_id must be provided",
        )

    try:
        # Get query definition
        if request.template_id:
            template = TemplateService.get_template(db, request.template_id, tenant_id, user_id)
            if not template:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Template {request.template_id} not found or access denied",
                )
            query_definition = template.query_definition
            # Apply overrides if provided
            if request.query_overrides:
                query_definition.update(request.query_overrides)
        else:
            query_definition = request.query.model_dump()

        # Create export job
        job = ExportService.create_export_job(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            format=request.format,
            query_definition=query_definition,
            template_id=request.template_id,
        )

        # TODO: Enqueue background job if large, or process synchronously if small
        # For now, return job status
        from app.jobs.queue import exports_queue
        exports_queue.enqueue("app.jobs.tasks.process_export_job", str(job.id))

        # Emit business metric
        MetricsService.emit_report_metric(
            metric_name=BusinessMetric.REPORT_EXPORT_CREATED,
            tenant_id=tenant_id,
            user_id=user_id,
            report_type=request.format,
        )

        return schemas.ExportJobResponse(
            id=job.id,
            status=job.status,
            format=job.format,
            file_url=None,
            file_size=None,
            error_message=None,
            total_rows=None,
            processed_rows=None,
            progress_percent=0.0,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


@router.get("/exports/{export_id}", response_model=schemas.ExportJobResponse)
async def get_export_status(
    export_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get export job status."""
    tenant_id = UUID(settings.tenant_id)

    job = ExportService.get_export_status(db, export_id, tenant_id, user_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job {export_id} not found",
        )

    # Generate presigned URL if file exists
    file_url = None
    if job.file_path and job.status == "completed":
        from app.imports.s3_utils import S3Client
        s3_client = S3Client()
        try:
            file_url = s3_client.get_presigned_url(job.file_path, expiration=3600)
            
            # Emit business metric for export download
            MetricsService.emit_report_metric(
                metric_name=BusinessMetric.REPORT_EXPORT_DOWNLOADED,
                tenant_id=tenant_id,
                user_id=user_id,
                report_type=job.format,
            )
        except Exception as e:
            logger.warning(f"Failed to generate presigned URL: {e}")

    # Calculate progress percentage
    progress_percent = None
    if job.total_rows and job.total_rows > 0:
        progress_percent = (job.processed_rows or 0) / job.total_rows * 100
    elif job.status == "completed":
        progress_percent = 100.0
    elif job.status == "pending":
        progress_percent = 0.0

    return schemas.ExportJobResponse(
        id=job.id,
        status=job.status,
        format=job.format,
        file_url=file_url,
        file_size=job.file_size,
        error_message=job.error_message,
        total_rows=job.total_rows,
        processed_rows=job.processed_rows,
        progress_percent=progress_percent,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.get("/exports/{export_id}/stream")
async def stream_export_progress(
    export_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """
    Stream export job progress via Server-Sent Events (SSE).
    
    Client can connect using EventSource API:
    const eventSource = new EventSource('/api/v1/reports/exports/{export_id}/stream');
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log('Progress:', data);
    };
    """
    tenant_id = UUID(settings.tenant_id)
    
    # Verify job exists and user has access
    job = ExportService.get_export_status(db, export_id, tenant_id, user_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Export job {export_id} not found or not accessible",
        )

    async def event_generator():
        """Generate SSE events for export progress."""
        last_processed = -1
        last_status = None
        timeout_seconds = 600  # 10 minutes timeout (exports can take longer)
        start_time = asyncio.get_event_loop().time()
        
        try:
            while True:
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout_seconds:
                    yield f"event: timeout\ndata: {json.dumps({'message': 'Connection timeout'})}\n\n"
                    break
                
                # Re-query job from database to get latest status
                current_job = ExportService.get_export_status(db, export_id, tenant_id, user_id)
                if not current_job:
                    yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
                    break
                
                # Calculate progress percentage
                progress_percent = None
                if current_job.total_rows and current_job.total_rows > 0:
                    progress_percent = (current_job.processed_rows or 0) / current_job.total_rows * 100
                elif current_job.status == "completed":
                    progress_percent = 100.0
                elif current_job.status == "pending":
                    progress_percent = 0.0
                
                # Send update if progress changed or status changed
                if ((current_job.processed_rows or 0) != last_processed or 
                    current_job.status != last_status):
                    
                    data = {
                        "job_id": str(current_job.id),
                        "status": current_job.status,
                        "format": current_job.format,
                        "processed_rows": current_job.processed_rows,
                        "total_rows": current_job.total_rows,
                        "progress_percent": round(progress_percent, 2) if progress_percent is not None else None,
                    }
                    
                    yield f"event: progress\ndata: {json.dumps(data)}\n\n"
                    
                    last_processed = current_job.processed_rows or 0
                    last_status = current_job.status
                
                # Stop if job is completed or failed
                if current_job.status in ["completed", "failed"]:
                    # Generate file URL if completed
                    file_url = None
                    if current_job.status == "completed" and current_job.file_path:
                        from app.imports.s3_utils import S3Client
                        s3_client = S3Client()
                        try:
                            file_url = s3_client.get_presigned_url(
                                current_job.file_path, expiration=3600
                            )
                        except Exception as e:
                            logger.warning(f"Failed to generate presigned URL: {e}")
                    
                    final_data = {
                        "job_id": str(current_job.id),
                        "status": current_job.status,
                        "format": current_job.format,
                        "processed_rows": current_job.processed_rows,
                        "total_rows": current_job.total_rows,
                        "progress_percent": 100.0 if current_job.status == "completed" else None,
                        "file_url": file_url,
                        "file_size": current_job.file_size,
                        "error_message": current_job.error_message,
                    }
                    yield f"event: complete\ndata: {json.dumps(final_data)}\n\n"
                    break
                
                # Wait before next check
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            logger.info(f"SSE connection cancelled for export job {export_id}")
        except Exception as e:
            logger.error(f"Error in SSE stream for export job {export_id}: {e}", exc_info=True)
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


# Template Endpoints

@router.get("/templates", response_model=schemas.ReportTemplateListResponse)
async def list_templates(
    include_shared: bool = Query(True),
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List templates accessible to user."""
    tenant_id = UUID(settings.tenant_id)

    templates = TemplateService.list_templates(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        include_shared=include_shared,
    )

    return schemas.ReportTemplateListResponse(
        items=[
            schemas.ReportTemplateResponse(
                id=t.id,
                name=t.name,
                description=t.description,
                query_definition=t.query_definition,
                visualization_config=t.visualization_config,
                pdf_config=t.pdf_config,
                is_shared=t.is_shared,
                shared_with_org_units=t.shared_with_org_units,
                user_id=t.user_id,
                created_at=t.created_at.isoformat(),
                updated_at=t.updated_at.isoformat(),
            )
            for t in templates
        ],
        total=len(templates),
    )


@router.post("/templates", response_model=schemas.ReportTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: schemas.ReportTemplateRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a report template."""
    tenant_id = UUID(settings.tenant_id)

    try:
        template = TemplateService.create_template(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            name=request.name,
            query_definition=request.query_definition.model_dump(),
            description=request.description,
            visualization_config=request.visualization_config.model_dump() if request.visualization_config else None,
            pdf_config=request.pdf_config.model_dump() if request.pdf_config else None,
            is_shared=request.is_shared,
            shared_with_org_units=request.shared_with_org_units,
        )

        return schemas.ReportTemplateResponse(
            id=template.id,
            name=template.name,
            description=template.description,
            query_definition=template.query_definition,
            visualization_config=template.visualization_config,
            pdf_config=template.pdf_config,
            is_shared=template.is_shared,
            shared_with_org_units=template.shared_with_org_units,
            user_id=template.user_id,
            created_at=template.created_at.isoformat(),
            updated_at=template.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


@router.get("/templates/{template_id}", response_model=schemas.ReportTemplateResponse)
async def get_template(
    template_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Get template details."""
    tenant_id = UUID(settings.tenant_id)

    template = TemplateService.get_template(db, template_id, tenant_id, user_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found or access denied",
        )

    return schemas.ReportTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        query_definition=template.query_definition,
        visualization_config=template.visualization_config,
        pdf_config=template.pdf_config,
        is_shared=template.is_shared,
        shared_with_org_units=template.shared_with_org_units,
        user_id=template.user_id,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.put("/templates/{template_id}", response_model=schemas.ReportTemplateResponse)
async def update_template(
    template_id: UUID,
    request: schemas.ReportTemplateRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a report template."""
    tenant_id = UUID(settings.tenant_id)

    template = TemplateService.get_template(db, template_id, tenant_id, user_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found or access denied",
        )

    # Check ownership
    if template.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only template owner can update",
        )

    # Update fields
    template.name = request.name
    template.description = request.description
    template.query_definition = request.query_definition.model_dump()
    template.visualization_config = request.visualization_config.model_dump() if request.visualization_config else None
    template.pdf_config = request.pdf_config.model_dump() if request.pdf_config else None
    template.is_shared = request.is_shared
    template.shared_with_org_units = request.shared_with_org_units

    db.commit()
    db.refresh(template)

    return schemas.ReportTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        query_definition=template.query_definition,
        visualization_config=template.visualization_config,
        pdf_config=template.pdf_config,
        is_shared=template.is_shared,
        shared_with_org_units=template.shared_with_org_units,
        user_id=template.user_id,
        created_at=template.created_at.isoformat(),
        updated_at=template.updated_at.isoformat(),
    )


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a report template."""
    tenant_id = UUID(settings.tenant_id)

    template = TemplateService.get_template(db, template_id, tenant_id, user_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found or access denied",
        )

    # Check ownership
    if template.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only template owner can delete",
        )

    db.delete(template)
    db.commit()


@router.post("/templates/{template_id}/execute", response_model=schemas.ReportQueryResponse)
async def execute_template(
    template_id: UUID,
    overrides: Optional[dict] = None,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Execute a saved template with optional overrides."""
    tenant_id = UUID(settings.tenant_id)

    template = TemplateService.get_template(db, template_id, tenant_id, user_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found or access denied",
        )

    # Apply overrides
    query_definition = template.query_definition.copy()
    if overrides:
        query_definition.update(overrides)

    try:
        result = ReportService.execute_query(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            query_request=query_definition,
        )

        return schemas.ReportQueryResponse(
            results=result["results"],
            total=result.get("total"),
            limit=result["limit"],
            offset=result["offset"],
            metadata=result.get("metadata", {}),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


# Schedule Endpoints

@router.get("/schedules", response_model=schemas.ReportScheduleListResponse)
async def list_schedules(
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """List user's schedules."""
    tenant_id = UUID(settings.tenant_id)

    schedules = ScheduleService.list_schedules(db=db, tenant_id=tenant_id, user_id=user_id)

    return schemas.ReportScheduleListResponse(
        items=[
            schemas.ReportScheduleResponse(
                id=s.id,
                template_id=s.template_id,
                frequency=s.frequency,
                day_of_week=s.day_of_week,
                day_of_month=s.day_of_month,
                time=s.time.isoformat(),
                recipients=s.recipients,
                is_active=s.is_active,
                last_run_at=s.last_run_at.isoformat() if s.last_run_at else None,
                next_run_at=s.next_run_at.isoformat(),
                created_at=s.created_at.isoformat(),
                updated_at=s.updated_at.isoformat(),
            )
            for s in schedules
        ],
        total=len(schedules),
    )


@router.post("/templates/{template_id}/schedule", response_model=schemas.ReportScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    template_id: UUID,
    request: schemas.ReportScheduleRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Create a scheduled report."""
    tenant_id = UUID(settings.tenant_id)

    # Verify template exists and user has access
    template = TemplateService.get_template(db, template_id, tenant_id, user_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template {template_id} not found or access denied",
        )

    try:
        schedule = ScheduleService.create_schedule(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            template_id=template_id,
            frequency=request.frequency,
            time=request.time,
            recipients=request.recipients,
            day_of_week=request.day_of_week,
            day_of_month=request.day_of_month,
            query_overrides=request.query_overrides,
        )

        return schemas.ReportScheduleResponse(
            id=schedule.id,
            template_id=schedule.template_id,
            frequency=schedule.frequency,
            day_of_week=schedule.day_of_week,
            day_of_month=schedule.day_of_month,
            time=schedule.time.isoformat(),
            recipients=schedule.recipients,
            is_active=schedule.is_active,
            last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
            next_run_at=schedule.next_run_at.isoformat(),
            created_at=schedule.created_at.isoformat(),
            updated_at=schedule.updated_at.isoformat(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        ) from e


@router.put("/schedules/{schedule_id}", response_model=schemas.ReportScheduleResponse)
async def update_schedule(
    schedule_id: UUID,
    request: schemas.ReportScheduleRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Update a scheduled report."""
    tenant_id = UUID(settings.tenant_id)

    from app.reports.models import ReportSchedule
    from sqlalchemy import select

    schedule = db.execute(
        select(ReportSchedule).where(
            ReportSchedule.id == schedule_id,
            ReportSchedule.tenant_id == tenant_id,
            ReportSchedule.user_id == user_id,
        )
    ).scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )

    # Update fields
    schedule.frequency = request.frequency
    schedule.day_of_week = request.day_of_week
    schedule.day_of_month = request.day_of_month
    schedule.time = request.time
    schedule.recipients = request.recipients
    schedule.query_overrides = request.query_overrides

    # Recalculate next_run_at
    from app.reports.service import _calculate_next_run
    schedule.next_run_at = _calculate_next_run(
        request.frequency, request.time, request.day_of_week, request.day_of_month
    )

    db.commit()
    db.refresh(schedule)

    return schemas.ReportScheduleResponse(
        id=schedule.id,
        template_id=schedule.template_id,
        frequency=schedule.frequency,
        day_of_week=schedule.day_of_week,
        day_of_month=schedule.day_of_month,
        time=schedule.time.isoformat(),
        recipients=schedule.recipients,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        next_run_at=schedule.next_run_at.isoformat(),
        created_at=schedule.created_at.isoformat(),
        updated_at=schedule.updated_at.isoformat(),
    )


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: Session = Depends(get_db_with_rls),
):
    """Delete a scheduled report."""
    tenant_id = UUID(settings.tenant_id)

    from app.reports.models import ReportSchedule
    from sqlalchemy import select

    schedule = db.execute(
        select(ReportSchedule).where(
            ReportSchedule.id == schedule_id,
            ReportSchedule.tenant_id == tenant_id,
            ReportSchedule.user_id == user_id,
        )
    ).scalar_one_or_none()

    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found",
        )

    db.delete(schedule)
    db.commit()

