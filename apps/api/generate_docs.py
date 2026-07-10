import json
import sys
from pathlib import Path


def get_ref_name(ref):
    if not ref:
        return ""
    return ref.split("/")[-1]


def resolve_schema(schema, components, depth=0):
    if not schema:
        return "any"
    if depth > 4:
        return "..."  # avoid infinite recursion

    if "$ref" in schema:
        ref_name = get_ref_name(schema["$ref"])
        return resolve_schema(components.get(ref_name, {}), components, depth)

    if "type" in schema:
        if schema["type"] == "array":
            return f"list[{resolve_schema(schema.get('items', {}), components, depth)}]"
        if schema["type"] == "object":
            props = schema.get("properties", {})
            if not props:
                return "object"
            lines = []
            for k, v in props.items():
                req = (
                    " (required)" if k in schema.get("required", []) else " (optional)"
                )
                # Get description if present
                desc = f" - {v.get('description')}" if "description" in v else ""
                lines.append(
                    f"{'  ' * depth}- **{k}**: `{resolve_schema(v, components, depth + 1)}`{req}{desc}"
                )
            return "\n".join(lines)
        return schema["type"]

    if "anyOf" in schema:
        types = [resolve_schema(s, components, depth) for s in schema["anyOf"]]
        return " | ".join(types)

    return "any"


def generate_markdown(openapi_path, output_path):
    with Path(openapi_path).open() as f:
        spec = json.load(f)

    paths = spec.get("paths", {})
    components = spec.get("components", {}).get("schemas", {})

    md = []
    md.append("# Detailed API Reference\n")
    md.append(
        "This document provides exhaustively detailed descriptions of all API endpoints, including full request and response JSON schemas derived from the application's OpenAPI specification.\n"
    )

    for path, methods in paths.items():
        for method, op in methods.items():
            method_upper = method.upper()
            summary = op.get("summary", "")
            desc = op.get("description", "")
            tags = op.get("tags", [])

            tag_str = f" `{tags[0]}`" if tags else ""
            md.append(f"## {method_upper} `{path}`{tag_str}")
            if summary:
                md.append(f"**Summary**: {summary}")
            if desc:
                md.append(f"\n{desc}\n")

            # Parameters
            params = op.get("parameters", [])
            if params:
                md.append("### Parameters")
                for p in params:
                    req = " (required)" if p.get("required") else " (optional)"
                    schema = p.get("schema", {})
                    ptype = schema.get("type", "string")
                    if "anyOf" in schema:
                        ptype = " | ".join(
                            s.get("type", "any") for s in schema["anyOf"]
                        )
                    desc_str = (
                        f" - {p.get('description')}" if p.get("description") else ""
                    )
                    md.append(
                        f"- **{p['name']}** ({p['in']}): `{ptype}`{req}{desc_str}"
                    )
                md.append("")

            # Request Body
            req_body = op.get("requestBody", {})
            if req_body:
                content = req_body.get("content", {})
                if "application/json" in content:
                    schema = content["application/json"].get("schema", {})
                    md.append("### Request Body (`application/json`)")
                    resolved = resolve_schema(schema, components)
                    if "\n" in resolved:
                        md.append(resolved)
                    else:
                        md.append(f"- Type: `{resolved}`")
                    md.append("")

            # Responses
            responses = op.get("responses", {})
            if responses:
                md.append("### Responses")
                for code, resp in responses.items():
                    md.append(f"#### {code}: {resp.get('description', '')}")
                    content = resp.get("content", {})
                    if "application/json" in content:
                        schema = content["application/json"].get("schema", {})
                        resolved = resolve_schema(schema, components)
                        if "\n" in resolved:
                            md.append(resolved)
                        else:
                            md.append(f"- Type: `{resolved}`")
                md.append("")
            md.append("---\n")

    with Path(output_path).open("w") as f:
        f.write("\n".join(md))


if __name__ == "__main__":
    generate_markdown("openapi.json", sys.argv[1])
