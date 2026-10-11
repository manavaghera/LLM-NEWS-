import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .reports import require_admin
from ...services.operations_service import operations_snapshot, update_pipeline_budget


router = APIRouter(dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)


class PipelineBudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    daily_call_limit: int = Field(strict=True, ge=0, le=100_000)
    monthly_call_limit: int | None = Field(default=None, strict=True, ge=0, le=2_000_000)


@router.get("")
def get_operations():
    """Update, source and model health for the authenticated site owner."""
    try:
        return operations_snapshot()
    except Exception:
        logger.exception("Failed to fetch operations")
        raise HTTPException(status_code=500, detail="Failed to fetch operations")


@router.patch("/budget")
def set_pipeline_budget(request: PipelineBudgetRequest):
    """Set the persistent daily pipeline call allowance (zero disables the cap)."""
    try:
        return update_pipeline_budget(request.daily_call_limit, request.monthly_call_limit)
    except Exception:
        logger.exception("Failed to update pipeline budget")
        raise HTTPException(status_code=500, detail="Failed to update pipeline budget")
