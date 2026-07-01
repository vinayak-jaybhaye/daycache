# Deployment

> This document is a placeholder. Deployment infrastructure has not yet been designed.
> Update this file when a hosting strategy is decided.

## Planned Approach

- **Frontend**: Deploy Next.js to Vercel or a self-hosted Node.js server.
- **Backend**: Containerized FastAPI behind a reverse proxy (nginx / Caddy).
- **Database**: Managed PostgreSQL (e.g., Supabase, Neon, or RDS).
- **Cache**: Managed Redis (e.g., Upstash or ElastiCache).

## Environment Variables

See [`infra/.env.example`](../infra/.env.example) for the full list of required variables.

Production secrets must never be committed to the repository. Use your hosting provider's secret management (e.g., Vercel Environment Variables, GitHub Actions Secrets, AWS Secrets Manager).

## See Also

- [Local Development](local-development.md)
- [Architecture](architecture.md)
