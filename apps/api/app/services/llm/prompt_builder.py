from app.services.llm.personas import Persona


def build_persona_block(persona: Persona) -> str:
    """Build the dynamic system prompt persona instruction block."""
    return f"You are {persona.name}, a personal companion in DayCache — a private diary app.\n\n{persona.personality}"
