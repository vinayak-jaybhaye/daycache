# API Conventions

Standards for designing and implementing REST endpoints in DayCache.

## Base URL

```
/api/v1/{resource}
```

All endpoints are versioned. The version is part of the URL path, not a header.

## HTTP Methods

| Method | Usage |
|---|---|
| `GET` | Retrieve a resource or collection |
| `POST` | Create a new resource |
| `PATCH` | Partial update of an existing resource |
| `DELETE` | Remove a resource |

Use `PUT` only for full resource replacement (rare).

## Resource Naming

- Use **plural nouns**: `/journals`, `/entries`, `/users`
- Use **kebab-case** for multi-word resources: `/journal-entries`
- Nest sub-resources under their parent: `/journals/{id}/entries`
- Keep nesting to one level maximum

## Request & Response

### Request bodies
All request bodies use JSON. Validated by Pydantic schemas named `{Resource}Create` or `{Resource}Update`.

### Response bodies
Successful responses return a JSON object. Collections include pagination metadata.

```json
// Single resource
{
  "id": "uuid",
  "created_at": "2024-01-01T00:00:00Z",
  ...
}

// Collection
{
  "items": [...],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

### Timestamps
All timestamps are ISO 8601 UTC strings: `"2024-01-01T12:00:00Z"`.

### IDs
All IDs are UUIDs v4, returned as strings.

## HTTP Status Codes

| Code | Meaning |
|---|---|
| `200` | Success (GET, PATCH) |
| `201` | Created (POST) |
| `204` | No Content (DELETE) |
| `400` | Bad Request — invalid input |
| `401` | Unauthorized — missing or invalid token |
| `403` | Forbidden — authenticated but lacks permission |
| `404` | Not Found |
| `409` | Conflict — e.g., duplicate resource |
| `422` | Unprocessable Entity — validation error (FastAPI default) |
| `500` | Internal Server Error |

## Error Format

FastAPI 422 validation errors follow Pydantic's default format. All other errors use:

```json
{
  "detail": "Human-readable error message"
}
```

## Authentication

All protected endpoints require a `Bearer` token in the `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

## Pagination

List endpoints support `page` and `page_size` query parameters:

```
GET /api/v1/journals?page=1&page_size=20
```

Default page size: **20**. Maximum page size: **100**.

## Filtering & Sorting

- Filter by field value: `?status=published`
- Sort: `?sort=created_at&order=desc`

## Versioning Policy

When breaking changes are required, a new version prefix (`/api/v2/`) is introduced. Old versions are supported for a minimum of 6 months with deprecation notices in response headers:

```
Deprecation: true
Sunset: Sat, 01 Jan 2026 00:00:00 GMT
```
