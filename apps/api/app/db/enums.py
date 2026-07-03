"""Shared database enums matching Postgres enum types."""

from __future__ import annotations

from enum import StrEnum


class OAuthProvider(StrEnum):
    """Supported third-party identity providers."""

    GOOGLE = "google"
    APPLE = "apple"
    GITHUB = "github"


class DevicePlatform(StrEnum):
    """Platforms supporting DayCache clients."""

    WEB = "web"
    IOS = "ios"
    ANDROID = "android"


class MediaType(StrEnum):
    """Media attachment categories."""

    IMAGE = "image"
    VIDEO = "video"


class MediaProcessingStatus(StrEnum):
    """Lifecycle status of uploaded media files processed by background workers."""

    PENDING = "pending"  # uploaded to object storage, awaiting processing
    PROCESSING = "processing"  # picked up by background worker
    COMPLETED = "completed"  # thumbnail, metadata, processing done
    FAILED = "failed"  # processing failed


class MediaUploadStatus(StrEnum):
    """Upload lifecycle status — tracks whether the client completed the upload."""

    PENDING = "pending"  # presigned URL issued, client hasn't uploaded yet
    UPLOADED = "uploaded"  # client confirmed upload; object exists in storage
    EXPIRED = "expired"  # upload TTL elapsed; cleanup cron will remove the row


class SummaryScope(StrEnum):
    """Time-series scope of an AI summary."""

    ENTRY = "entry"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class SummaryKind(StrEnum):
    """AI output variations for content synthesis."""

    SUMMARY = "summary"


class EmbeddingStatus(StrEnum):
    """Lifecycle status of AI embeddings generation."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
