"""Versioned AI prompt builder templates for various summary scopes."""

from __future__ import annotations

# Prompt version identifiers
ENTRY_SUMMARY_PROMPT_VERSION = "v1"
DAY_SUMMARY_PROMPT_VERSION = "v1"
WEEK_SUMMARY_PROMPT_VERSION = "v1"
MONTH_SUMMARY_PROMPT_VERSION = "v1"
YEAR_SUMMARY_PROMPT_VERSION = "v1"

JSON_FORMAT_INSTRUCTIONS = """
Your output must be a single, valid JSON object matching the following structure:
{
  "content": "A detailed paragraph (prose) summarizing the entries.",
  "highlights": ["Concise string of a positive key moment or win. Max 10 words."],
  "challenges": ["Concise string of a struggle, obstacle, or worry. Max 10 words."],
  "themes": ["Single word or short phrase representing a topic. Max 3 words."],
  "mood_analysis": {
    "trend": "improving / stable / declining / unknown",
    "average": 5.0,
    "breakdown": [
       {"mood": "mood_name_here", "count": 2}
    ]
  }
}

Constraints:
1. Do NOT wrap your response in markdown code blocks or code fences (e.g., do NOT start with ```json and do NOT end with ```). Return ONLY raw, valid JSON.
2. Provide a rich, detailed emotional mood analysis in the "mood_analysis" field (the "average" field must be a numeric value between 1.0 and 10.0 representing emotional intensity). Set it to null only if the text is completely neutral or lacks any emotional keywords, feelings, or sentiments whatsoever.
3. Every item in the "highlights", "challenges", and "themes" list must be extremely concise (maximum 10 words).
4. Write the "content" summary in a supportive, personal, and conversational second-person tone (using "you", "your"). Never refer to "the journal entries", "the user", "the writer", "the text", or "the input" (e.g., do NOT start with "Two entries describe" or "This summary shows"). Focus directly on what happened and how you felt (e.g., "You pushed through a grueling run and felt proud...").
"""


def build_entry_summary_prompt(content: str) -> str:
    """Build prompt for summarizing a single journal entry."""
    return f"""You are a personal diary assistant. Summarize the following single journal entry.

Journal Entry:
\"\"\"
{content}
\"\"\"
{JSON_FORMAT_INSTRUCTIONS}"""


def build_day_summary_prompt(entries: list[str], date_str: str) -> str:
    """Build prompt for summarizing all journal entries written on a specific day."""
    entries_text = "\n---\n".join(entries)
    return f"""You are a personal diary assistant. Summarize all journal entries written on {date_str}.

Journal Entries:
\"\"\"
{entries_text}
\"\"\"
{JSON_FORMAT_INSTRUCTIONS}"""


def build_week_summary_prompt(entries: list[str], period_str: str) -> str:
    """Build prompt for summarizing entries written over a specific week."""
    entries_text = "\n---\n".join(entries)
    return f"""You are a personal diary assistant. Summarize all journal entries written during the week: {period_str}.

Journal Entries:
\"\"\"
{entries_text}
\"\"\"
{JSON_FORMAT_INSTRUCTIONS}"""


def build_month_summary_prompt(entries: list[str], period_str: str) -> str:
    """Build prompt for summarizing entries written over a specific month."""
    entries_text = "\n---\n".join(entries)
    return f"""You are a personal diary assistant. Summarize all journal entries written during the month: {period_str}.

Journal Entries:
\"\"\"
{entries_text}
\"\"\"
{JSON_FORMAT_INSTRUCTIONS}"""


def build_year_summary_prompt(entries: list[str], period_str: str) -> str:
    """Build prompt for summarizing entries written over a specific year."""
    entries_text = "\n---\n".join(entries)
    return f"""You are a personal diary assistant. Summarize all journal entries written during the year: {period_str}.

Journal Entries:
\"\"\"
{entries_text}
\"\"\"
{JSON_FORMAT_INSTRUCTIONS}"""
