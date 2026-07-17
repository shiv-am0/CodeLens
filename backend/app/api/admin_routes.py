from fastapi import APIRouter, Depends, HTTPException, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import settings
from app.models.api_key import ApiKey
from app.services.key_manager import key_manager
import os

router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))


async def verify_admin(request: Request):
    token = request.cookies.get("admin_token")
    if token != "authenticated":
        raise HTTPException(status_code=303, detail="Not authenticated")
    return True


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse(
        "admin_login.html", {"request": request, "error": error}
    )


@router.post("/login")
async def login(request: Request, password: str = Form(...)):
    if password == settings.admin_password:
        response = RedirectResponse(url="/admin/keys", status_code=303)
        response.set_cookie(key="admin_token", value="authenticated", httponly=True, max_age=86400)
        return response
    return templates.TemplateResponse(
        "admin_login.html", {"request": request, "error": "Invalid password"}, status_code=401
    )


@router.get("/keys", response_class=HTMLResponse)
async def keys_page(request: Request, db: AsyncSession = Depends(get_db), _=Depends(verify_admin)):
    keys = await key_manager.load_keys_sync(db)
    return templates.TemplateResponse(
        "admin_keys.html", {"request": request, "keys": keys}
    )


@router.post("/keys/add")
async def add_key(
    request: Request,
    name: str = Form(...),
    key: str = Form(...),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    encrypted = key_manager.encrypt(key)
    prefix = key[:8] if len(key) >= 8 else key
    new_key = ApiKey(name=name, key_encrypted=encrypted, key_prefix=prefix)
    db.add(new_key)
    await db.commit()
    return RedirectResponse(url="/admin/keys", status_code=303)


@router.post("/keys/{key_id}/toggle")
async def toggle_key(
    request: Request,
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    key.is_active = not key.is_active
    await db.commit()
    return RedirectResponse(url="/admin/keys", status_code=303)


@router.post("/keys/{key_id}/delete")
async def delete_key(
    request: Request,
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_admin),
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
    await db.delete(key)
    await db.commit()
    return RedirectResponse(url="/admin/keys", status_code=303)
