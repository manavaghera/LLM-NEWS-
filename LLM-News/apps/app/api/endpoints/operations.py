import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from .reports import require_admin
from ...core.admin_auth import require_owner
from ...core.admin_accounts import audit
from ...services.operations_service import (
    operations_snapshot, update_model_price, update_pipeline_budget, update_spending_budget,
)


router = APIRouter(dependencies=[Depends(require_admin)])
logger = logging.getLogger(__name__)


class PipelineBudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    daily_call_limit: int = Field(strict=True, ge=0, le=100_000)
    monthly_call_limit: int | None = Field(default=None, strict=True, ge=0, le=2_000_000)


class SpendingBudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    daily_usd: float = Field(strict=True, ge=0, le=1_000_000)
    monthly_usd: float = Field(strict=True, ge=0, le=1_000_000)


class ModelPriceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=200)
    input_usd_per_mtok: float = Field(strict=True, ge=0, le=1_000_000)
    output_usd_per_mtok: float = Field(strict=True, ge=0, le=1_000_000)


@router.get("")
def get_operations():
    """Update, source and model health for the authenticated site owner."""
    try:
        return operations_snapshot()
    except Exception:
        logger.exception("Failed to fetch operations")
        raise HTTPException(status_code=500, detail="Failed to fetch operations")


@router.patch("/budget")
def set_pipeline_budget(request: PipelineBudgetRequest, identity=Depends(require_owner)):
    """Set the persistent daily pipeline call allowance (zero disables the cap)."""
    try:
        result = update_pipeline_budget(request.daily_call_limit, request.monthly_call_limit)
        audit(identity, "pipeline_budget_updated")
        return result
    except Exception:
        logger.exception("Failed to update pipeline budget")
        raise HTTPException(status_code=500, detail="Failed to update pipeline budget")


@router.patch("/spending")
def set_spending_budget(request: SpendingBudgetRequest, identity=Depends(require_owner)):
    try:
        result = update_spending_budget(request.daily_usd, request.monthly_usd)
        audit(identity, "spending_budget_updated")
        return result
    except Exception:
        logger.exception("Failed to update spending budget")
        raise HTTPException(status_code=500, detail="Failed to update spending budget")


@router.put("/model-price")
def set_model_price(request: ModelPriceRequest, identity=Depends(require_owner)):
    try:
        result = update_model_price(
            request.provider, request.model, request.input_usd_per_mtok, request.output_usd_per_mtok,
        )
        audit(identity, "model_price_updated", f"{request.provider}/{request.model}")
        return result
    except Exception:
        logger.exception("Failed to update model price")
        raise HTTPException(status_code=500, detail="Failed to update model price")
