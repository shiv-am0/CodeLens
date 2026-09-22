from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.ai_configuration import AIConfigurationResponse
from app.services.ai_configuration import AIConfigurationService


router = APIRouter(prefix="/settings/ai", tags=["ai-settings"])


@router.get("", response_model=AIConfigurationResponse)
async def get_ai_configuration(
    db: AsyncSession = Depends(get_db),
) -> AIConfigurationResponse:
    return await AIConfigurationService(db).get_status()
