import os

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import admin_login_limiter, client_identifier
from app.models.api_key import ApiKey
from app.schemas.ai_configuration import AIConfigurationUpdate
from app.services.admin_auth import (
    SESSION_COOKIE,
    AdminAuthenticationError,
    AdminSession,
    admin_auth,
)
from app.services.ai_configuration import (
    AIConfigurationService,
    AIConfigurationValidationError,
    SUPPORTED_CHAT_MODELS,
)
from app.services.master_key_store import master_key_store


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "..", "templates")
)


def require_admin(request: Request) -> AdminSession:
    try:
        return admin_auth.read_session(request.cookies.get(SESSION_COOKIE))
    except AdminAuthenticationError as exc:
        raise HTTPException(
            status_code=303,
            detail=str(exc),
            headers={"Location": "/admin/login"},
        ) from exc


@router.get("", include_in_schema=False)
async def admin_root() -> RedirectResponse:
    return RedirectResponse(url="/admin/settings", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    try:
        admin_auth.read_session(request.cookies.get(SESSION_COOKIE))
        return RedirectResponse(url="/admin/settings", status_code=303)
    except AdminAuthenticationError:
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={"error": error},
        )


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    admin_login_limiter.check(client_identifier(request))
    if not admin_auth.verify_password(password):
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={"error": "Invalid password"},
            status_code=401,
        )

    response = RedirectResponse(url="/admin/settings", status_code=303)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=admin_auth.create_session_token(),
        httponly=True,
        secure=settings.is_production,
        samesite="strict",
        max_age=settings.admin_session_hours * 3600,
        path="/admin",
    )
    return response


@router.post("/logout")
async def logout(
    csrf_token: str = Form(...), session: AdminSession = Depends(require_admin)
) -> RedirectResponse:
    try:
        admin_auth.verify_csrf(session, csrf_token)
    except AdminAuthenticationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    response = RedirectResponse(url="/admin/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/admin")
    return response


async def _active_key(db: AsyncSession) -> ApiKey | None:
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.is_active.is_(True))
        .order_by(ApiKey.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _render_settings(
    request: Request,
    db: AsyncSession,
    session: AdminSession,
    *,
    error: str = "",
    message: str = "",
    status_code: int = 200,
):
    status = await AIConfigurationService(db).get_status()
    active_key = await _active_key(db)
    return templates.TemplateResponse(
        request=request,
        name="admin_settings.html",
        context={
            "status": status,
            "active_key": active_key,
            "supported_models": SUPPORTED_CHAT_MODELS,
            "csrf_token": session.csrf_token,
            "key_fingerprint": master_key_store.fingerprint,
            "error": error,
            "message": message,
        },
        status_code=status_code,
    )


@router.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    session: AdminSession = Depends(require_admin),
):
    return await _render_settings(request, db, session)


@router.post("/settings", response_class=HTMLResponse)
async def update_settings(
    request: Request,
    csrf_token: str = Form(...),
    api_key: str = Form(""),
    chat_model: str = Form(...),
    db: AsyncSession = Depends(get_db),
    session: AdminSession = Depends(require_admin),
):
    try:
        admin_auth.verify_csrf(session, csrf_token)
        update = AIConfigurationUpdate(
            api_key=api_key.strip() or None,
            chat_model=chat_model,
        )
        await AIConfigurationService(db).save(update)
    except AdminAuthenticationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (AIConfigurationValidationError, ValueError) as exc:
        await db.rollback()
        return await _render_settings(
            request, db, session, error=str(exc), status_code=422
        )

    return await _render_settings(
        request,
        db,
        session,
        message="OpenAI configuration validated and saved.",
    )


@router.get("/keys", include_in_schema=False)
async def legacy_keys_page(
    session: AdminSession = Depends(require_admin),
) -> RedirectResponse:
    return RedirectResponse(url="/admin/settings", status_code=303)
