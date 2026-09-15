from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.ai_configuration import AIConfigurationResponse, AIConfigurationUpdate
from app.services.ai_configuration import (
    AIConfigurationService,
    AIConfigurationValidationError,
    AdminAuthenticationError,
)


router = APIRouter(prefix="/settings/ai", tags=["ai-settings"])


@router.get("", response_model=AIConfigurationResponse)
async def get_ai_configuration(
    db: AsyncSession = Depends(get_db),
) -> AIConfigurationResponse:
    return await AIConfigurationService(db).get_status()


@router.put("", response_model=AIConfigurationResponse)
async def update_ai_configuration(
    data: AIConfigurationUpdate,
    db: AsyncSession = Depends(get_db),
) -> AIConfigurationResponse:
    try:
        return await AIConfigurationService(db).save(data)
    except AdminAuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail={"code": "ADMIN_AUTHENTICATION_FAILED", "message": str(exc)},
        ) from exc
    except AIConfigurationValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "AI_CONFIGURATION_INVALID", "message": str(exc)},
        ) from exc
