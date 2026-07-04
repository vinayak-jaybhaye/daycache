# DayCache Backend Features & API Endpoints

Welcome to the **DayCache API documentation**. This guide details all the core features, their associated HTTP endpoints, and short examples of how to interact with them.

---

## Table of Contents
1. [Authentication (`/auth`)](#1-authentication-auth)
2. [User Management (`/users`)](#2-user-management-users)
3. [Settings (`/settings`)](#3-settings-settings)
4. [Calendar Days (`/days`)](#4-calendar-days-days)
5. [Journal Entries (`/entries`)](#5-journal-entries-entries)
6. [Tags (`/tags`)](#6-tags-tags)
7. [Moods (`/moods`)](#7-moods-moods)
8. [Collections (`/collections`)](#8-collections-collections)
9. [Search (`/search`)](#9-search-search)
10. [AI Summaries (`/ai/summaries`)](#10-ai-summaries-aisummaries)
11. [Recall AI (`/recall`)](#11-recall-ai-recall)
12. [Reflect Conversational Chat (`/reflect`)](#12-reflect-conversational-chat-reflect)
13. [Health Check (`/health`)](#13-health-check-health)

---

## 1. Authentication (`/auth`)
Manages registration, secure cookie-based session login, logging out, and token refreshes.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Register a new user account |
| `POST` | `/api/v1/auth/login` | Login user, sets session cookie |
| `POST` | `/api/v1/auth/logout` | Invalidate current session and clear cookie |
| `POST` | `/api/v1/auth/refresh` | Extend active session credentials |
| `POST` | `/api/v1/auth/oauth` | Register or login using OAuth credentials |

### Quick Example
**Login:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepassword"}'
```

---

## 2. User Management (`/users`)
Handles profile retrieval, profile updates, and avatar uploads.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/users/me` | Retrieve authenticated user profile info |
| `PATCH` | `/api/v1/users/me` | Update email, display name, password, etc. |
| `POST` | `/api/v1/users/me/avatar` | Initiate avatar profile image upload |
| `POST` | `/api/v1/users/me/avatar/confirm` | Confirm upload completion |

### Quick Example
**Update profile details:**
```bash
curl -X PATCH http://localhost:8000/api/v1/users/me \
  -H "Content-Type: application/json" \
  -d '{"display_name": "New Name"}'
```

---

## 3. Settings (`/settings`)
Retrieves and updates user preferences, specifically configuring AI feature toggles.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/settings` | Get user configurations (AI summaries, theme, language) |
| `PATCH` | `/api/v1/settings` | Update user settings and AI preferences |

### Quick Example
**Enable AI summarization:**
```bash
curl -X PATCH http://localhost:8000/api/v1/settings \
  -H "Content-Type: application/json" \
  -d '{"ai_enabled": true}'
```

---

## 4. Calendar Days (`/days`)
Represents a specific day in the diary. Holds metadata like weather, location, or associated moods.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/days` | Initialize a diary entry day |
| `GET` | `/api/v1/days` | List all day records |
| `GET` | `/api/v1/days/{day_id}` | Retrieve specific day details |

---

## 5. Journal Entries (`/entries`)
Manages standard diary entries. Content is structured using Tiptap JSON schema.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/entries` | Create a new journal entry |
| `GET` | `/api/v1/entries` | List journal entries |
| `GET` | `/api/v1/entries/{entry_id}` | Retrieve a specific journal entry |
| `PATCH` | `/api/v1/entries/{entry_id}` | Edit title or content of an entry |
| `DELETE` | `/api/v1/entries/{entry_id}` | Delete a journal entry |
| `POST` | `/api/v1/entries/{entry_id}/favorite` | Toggle the favorite flag |
| `GET` | `/api/v1/entries/date/{date_val}` | Retrieve entry for a specific calendar date (`YYYY-MM-DD`) |

---

## 6. Tags (`/tags`)
Manages organizational tags to group entries.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/tags` | Create a new tag (name, color) |
| `GET` | `/api/v1/tags` | List all tags |
| `DELETE` | `/api/v1/tags/{tag_id}` | Delete a tag |
| `POST` | `/api/v1/tags/associate` | Associate tags with a journal entry |
| `GET` | `/api/v1/tags/entry/{entry_id}` | Get tags associated with an entry |

### Quick Example
**Associate tags:**
```bash
curl -X POST http://localhost:8000/api/v1/tags/associate \
  -H "Content-Type: application/json" \
  -d '{"journal_entry_id": "<entry_uuid>", "tags": ["<tag_uuid_1>", "<tag_uuid_2>"]}'
```

---

## 7. Moods (`/moods`)
Manages mood tracking, allowing users to define custom moods and assign them to journal entries with intensity levels (1-5).

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/moods` | Create a custom mood |
| `GET` | `/api/v1/moods` | List all custom mood definitions |
| `DELETE` | `/api/v1/moods/{mood_id}` | Delete a custom mood |
| `POST` | `/api/v1/moods/associate` | Associate mood intensity to an entry |
| `GET` | `/api/v1/moods/entry/{entry_id}` | Get moods associated with an entry |

---

## 8. Collections (`/collections`)
Allows ordering and grouping of journal entries into structured collections (e.g. "Travel Logs").

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/collections` | Create a collection |
| `GET` | `/api/v1/collections` | List all collections |
| `GET` | `/api/v1/collections/{collection_id}` | Get collection details |
| `PATCH` | `/api/v1/collections/{collection_id}` | Update metadata |
| `DELETE` | `/api/v1/collections/{collection_id}` | Delete collection |
| `POST` | `/api/v1/collections/{collection_id}/entries` | Add a journal entry to a collection |
| `DELETE` | `/api/v1/collections/{collection_id}/entries/{entry_id}` | Remove a journal entry |
| `GET` | `/api/v1/collections/{collection_id}/entries` | Get entries in a collection |
| `PATCH` | `/api/v1/collections/{collection_id}/order` | Re-order entries inside collection |

---

## 9. Search (`/search`)
Executes full-text, vector, or hybrid searches across your journal entries.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/search` | Execute text, semantic, or hybrid search |

### Quick Example
**Hybrid Search:**
```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "my trip to the beach", "mode": "hybrid", "limit": 5}'
```

---

## 10. AI Summaries (`/ai/summaries`)
Generates structured summaries across various scopes.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/ai/summaries/entry` | Generate/regenerate entry summary |
| `POST` | `/api/v1/ai/summaries/day` | Generate/regenerate daily summary |
| `GET` | `/api/v1/ai/summaries/week/{year}/{week}` | Retrieve/generate weekly summary |
| `GET` | `/api/v1/ai/summaries/month/{year}/{month}` | Retrieve/generate monthly summary |
| `GET` | `/api/v1/ai/summaries/year/{year}` | Retrieve/generate yearly summary |

---

## 11. Recall AI (`/recall`)
Allows you to ask questions about your past entries. The system performs vector searches across your entries and uses an LLM to synthesize a natural answer.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/recall` | Post a query and stream the AI answer turn |
| `GET` | `/api/v1/recall/messages` | Get history of recall chat messages |
| `DELETE` | `/api/v1/recall/messages` | Clear recall message logs |

### Quick Example
**Ask Recall a question (streams answer):**
```bash
curl -X POST http://localhost:8000/api/v1/recall \
  -H "Content-Type: application/json" \
  -d '{"content": "Where did I go on vacation last year?"}'
```

---

## 12. Reflect Conversational Chat (`/reflect`)
Provides a friendly chat interface. Reflect acts as a conversational partner to help you journal, automatically compiling entries behind the scenes once you chat enough (3+ user messages, 50+ total words).

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/reflect/messages` | Send message and stream Reflect response |
| `GET` | `/api/v1/reflect/messages` | Retrieve Reflect message history |
| `GET` | `/api/v1/reflect/today` | Retrieve today's chat messages specifically |

### Quick Example
**Send message (streams response):**
```bash
curl -X POST http://localhost:8000/api/v1/reflect/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Today was quite a busy day at work."}'
```

---

## 13. Health Check (`/health`)
Checks if database connections and system metrics are running healthy.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Get server status |
