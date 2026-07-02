"""Authentication and Session management business service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)
from app.db.models import Device, Session, User, UserSettings
from app.db.repositories import DeviceRepository, SessionRepository, UserRepository
from app.exceptions import ConflictError, UnauthorizedError

if TYPE_CHECKING:
    from app.core.config import Settings
    from app.modules.auth.schemas import UserLoginRequest, UserRegisterRequest


class AuthService:
    """Orchestrates authentication, session registration, and device resolution."""

    @staticmethod
    async def register_user(db: AsyncSession, data: UserRegisterRequest) -> User:
        """Register a new user account with default settings.

        Normalises the email address to lowercase before storing.

        Args:
            db: Active database session.
            data: Registration parameters.

        Returns:
            The created User instance.

        Raises:
            ConflictError: If the email is already registered.
        """
        user_repo = UserRepository(db)
        normalized_email = data.email.lower().strip()

        # Check if email is already in use
        existing_user = await user_repo.get_by_email(normalized_email)
        if existing_user is not None:
            raise ConflictError("Email address is already in use.")

        # Create user with password hash
        hashed = hash_password(data.password)
        user = User(
            email=normalized_email,
            display_name=data.display_name,
            password_hash=hashed,
            is_verified=False,
        )

        # Initialize UserSettings with defaults
        settings = UserSettings(
            locale="en-US",
            timezone="UTC",
            theme="system",
            week_starts_on=1,
            ai_enabled=True,
            editor_font="inter",
            content_language="en",
        )
        user.settings = settings

        await user_repo.create(user)
        return user

    @staticmethod
    async def verify_email_password(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> User:
        """Verify user credentials and return the User instance if valid.

        Args:
            db: Active database session.
            email: Account email to verify.
            password: Plaintext password to compare.

        Returns:
            The authenticated User instance.

        Raises:
            UnauthorizedError: If email or password is invalid.
        """
        user_repo = UserRepository(db)
        normalized_email = email.lower().strip()

        user = await user_repo.get_by_email(normalized_email)
        if user is None or user.password_hash is None:
            # OAuth-only accounts have password_hash=None
            raise UnauthorizedError("Invalid email or password.")

        if not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password.")

        return user

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user: User,
        data: UserLoginRequest,
        ip_address: str | None,
        user_agent: str | None,
        settings: Settings,
    ) -> tuple[Session, str]:
        """Resolve/create the user's device and register a new session.

        Args:
            db: Active database session.
            user: Authenticated User instance.
            data: Device metadata.
            ip_address: Client IP address.
            user_agent: Client User-Agent string.
            settings: Settings singleton containing TTL.

        Returns:
            A tuple of (Session, raw_session_token).
        """
        device_repo = DeviceRepository(db)
        session_repo = SessionRepository(db)

        now = datetime.now(UTC)

        # 1. Resolve Device (scoped strictly to user_id + installation_id)
        device = await device_repo.get_by_installation_id(user.id, data.installation_id)

        if device is None:
            device = Device(
                user_id=user.id,
                installation_id=data.installation_id,
                name=data.device_name,
                platform=data.platform,
                last_seen_at=now,
            )
            await device_repo.create(device)
        else:
            # Update mutable metadata: name, platform, last seen
            if data.device_name:
                device.name = data.device_name
            device.platform = data.platform
            device.last_seen_at = now
            await db.flush()

        # 2. Create Session with dynamic settings TTL
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expires_at = now + timedelta(seconds=settings.SESSION_TTL)

        session = Session(
            device_id=device.id,
            token_hash=token_hash,
            created_ip=ip_address,
            created_user_agent=user_agent,
            expires_at=expires_at,
            last_used_at=now,
        )
        await session_repo.create(session)

        return session, raw_token

    @staticmethod
    async def logout_session(db: AsyncSession, token_hash: str) -> None:
        """Revoke a session matching the token hash.

        Args:
            db: Active database session.
            token_hash: SHA-256 token hash of the session to revoke.
        """
        session_repo = SessionRepository(db)
        session = await session_repo.get_by_token_hash(token_hash)
        if session is not None:
            await session_repo.delete(session)
