"""External system integrations.

Each sub-package wraps one external provider or API.
Services expose small, stable interfaces consumed by modules.

Rules:
- Services must never contain business rules.
- Services must never import from ``app.modules``.
- Modules may depend on services; the reverse is forbidden.
"""
