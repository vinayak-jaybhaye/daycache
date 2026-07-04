"""Personas API endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm.personas import DEFAULT_PERSONA_NAME, PERSONAS

router = APIRouter()


class PersonaListItem(BaseModel):
    name: str
    tagline: str


class PersonasListResponse(BaseModel):
    personas: list[PersonaListItem]
    default: str


@router.get(
    "",
    response_model=PersonasListResponse,
)
async def list_personas() -> PersonasListResponse:
    """Return the list of available AI personas for onboarding and settings."""
    items = [PersonaListItem(name=p.name, tagline=p.tagline) for p in PERSONAS.values()]
    return PersonasListResponse(personas=items, default=DEFAULT_PERSONA_NAME)
