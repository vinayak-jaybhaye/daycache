import json
from pathlib import Path

from app.main import app

if __name__ == "__main__":
    schema = app.openapi()
    with Path("openapi.json").open("w") as f:
        json.dump(schema, f, indent=2)
    print("Successfully exported OpenAPI schema to openapi.json")
