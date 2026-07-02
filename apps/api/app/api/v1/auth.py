"""Authentication API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from app.api.deps import get_current_session, get_current_user, get_db, get_settings
from app.core.config import Settings
from app.db.models import Session, User
from app.db.repositories.session import SessionRepository
from app.exceptions import NotFoundError
from app.modules.auth.schemas import (
    DeviceResponse,
    DeviceSessionResponse,
    SessionResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.modules.auth.service import AuthService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Register a new email/password account."""
    return await AuthService.register_user(db, data)


@router.post(
    "/login",
    response_model=UserResponse,
)
async def login(
    request: Request,
    response: Response,
    data: UserLoginRequest,
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    """Authenticate credentials and establish a secure HTTP-Only cookie session."""
    # 1. Verify Identity
    user = await AuthService.verify_email_password(
        db=db,
        email=data.email,
        password=data.password,
    )

    # 2. Resolve Device & Register Session
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    session, raw_token = await AuthService.create_session(
        db=db,
        user=user,
        data=data,
        ip_address=ip_address,
        user_agent=user_agent,
        settings=settings,
    )

    # 3. Set Cookie with configured parameters
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE and settings.APP_ENV == "production",
        samesite=settings.SESSION_COOKIE_SAMESITE,
        domain=settings.SESSION_COOKIE_DOMAIN,
        path=settings.SESSION_COOKIE_PATH,
        expires=session.expires_at,
    )

    return user


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_session: Session = Depends(get_current_session),
    settings: Settings = Depends(get_settings),
) -> None:
    """Revoke the current active session and clear the session cookie."""
    await AuthService.logout_session(db, current_session.token_hash)
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE and settings.APP_ENV == "production",
        samesite=settings.SESSION_COOKIE_SAMESITE,
        domain=settings.SESSION_COOKIE_DOMAIN,
        path=settings.SESSION_COOKIE_PATH,
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> User:
    """Return the authenticated user's profile metadata."""
    return current_user


@router.get(
    "/sessions",
    response_model=list[SessionResponse],
)
async def list_sessions(
    current_user: User = Depends(get_current_user),
    current_session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> list[SessionResponse]:
    """List all active unexpired sessions for the authenticated user."""
    session_repo = SessionRepository(db)
    active_sessions = await session_repo.list_active_by_user(current_user.id)

    response_sessions = []
    for s in active_sessions:
        device_name = s.device.name
        device_platform = s.device.platform
        is_current = s.id == current_session.id

        response_sessions.append(
            SessionResponse(
                id=s.id,
                device_name=device_name,
                device_platform=device_platform,
                ip_address=str(s.ip_address) if s.ip_address else None,
                user_agent=s.user_agent,
                last_used_at=s.last_used_at,
                created_at=s.created_at,
                is_current=is_current,
            )
        )

    return response_sessions


@router.get(
    "/devices",
    response_model=list[DeviceResponse],
)
async def list_devices(
    current_user: User = Depends(get_current_user),
    current_session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> list[DeviceResponse]:
    """List all user devices with their active sessions grouped under them."""
    session_repo = SessionRepository(db)
    active_sessions = await session_repo.list_active_by_user(current_user.id)

    # Group sessions by device ID
    device_groups: dict[UUID, dict[str, Any]] = {}
    for s in active_sessions:
        dev = s.device
        dev_id = dev.id
        is_current_session = s.id == current_session.id

        if dev_id not in device_groups:
            device_groups[dev_id] = {
                "id": dev.id,
                "name": dev.name,
                "platform": dev.platform,
                "last_seen_at": dev.last_seen_at,
                "created_at": dev.created_at,
                "is_current": False,  # Will flag True if any session matches
                "sessions": [],
            }

        if is_current_session:
            device_groups[dev_id]["is_current"] = True

        device_groups[dev_id]["sessions"].append(
            DeviceSessionResponse(
                id=s.id,
                ip_address=str(s.ip_address) if s.ip_address else None,
                user_agent=s.user_agent,
                last_used_at=s.last_used_at,
                is_current=is_current_session,
            )
        )

    # Format list ordered by most recently seen device
    sorted_devices = sorted(
        device_groups.values(),
        key=lambda d: d["last_seen_at"],
        reverse=True,
    )

    return [DeviceResponse(**d) for d in sorted_devices]


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_session(
    session_id: UUID,
    response: Response,
    current_user: User = Depends(get_current_user),
    current_session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> None:
    """Revoke a specific session. If current session is specified, log out."""
    session_repo = SessionRepository(db)

    deleted = await session_repo.delete_by_id_for_user(
        user_id=current_user.id,
        session_id=session_id,
    )
    if not deleted:
        raise NotFoundError("Session not found or already expired.")

    # If the user deleted their own current session, clear their cookie
    if session_id == current_session.id:
        response.delete_cookie(
            key=settings.SESSION_COOKIE_NAME,
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE and settings.APP_ENV == "production",
            samesite=settings.SESSION_COOKIE_SAMESITE,
            domain=settings.SESSION_COOKIE_DOMAIN,
            path=settings.SESSION_COOKIE_PATH,
        )


@router.delete(
    "/sessions",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_other_sessions(
    current_user: User = Depends(get_current_user),
    current_session: Session = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke all active sessions for the user except the current one."""
    session_repo = SessionRepository(db)
    await session_repo.delete_other_sessions(
        user_id=current_user.id,
        current_session_id=current_session.id,
    )
