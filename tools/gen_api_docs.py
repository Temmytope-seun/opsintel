"""Generate docs/api.md from the FastAPI OpenAPI schema (so the docs always match the code).

    .venv/bin/python tools/gen_api_docs.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from opsintel.api.main import app  # noqa: E402

AUTH_NOTES = {
    ("GET", "/health"): "public (no `X-User` needed)",
    ("GET", "/kpis/cost-change"): "roles with financial access (not service_desk)",
    ("GET", "/anomalies/{kind}"): "`cost` needs financial access",
    ("GET", "/audit"): "auditor, executive",
    ("GET", "/audit/verify"): "auditor, executive",
    ("POST", "/actions"): "executive, ops_manager, analyst; at least one evidence record",
    ("POST", "/actions/{action_id}/approve"): "executive, ops_manager; not the proposer",
    ("POST", "/actions/{action_id}/reject"): "executive, ops_manager; not the proposer",
    ("POST", "/actions/{action_id}/progress"): "roles that can propose or approve",
}


def schema_ref(s: dict) -> str:
    if not s:
        return ""
    if "$ref" in s:
        return s["$ref"].split("/")[-1]
    if "anyOf" in s:
        return " | ".join(schema_ref(x) for x in s["anyOf"])
    if "enum" in s:
        return " / ".join(f"`{v}`" for v in s["enum"])
    return s.get("type", "")


def main():
    spec = app.openapi()
    L = [f"# {spec['info']['title']} - REST API", "",
         "_Generated from the OpenAPI schema by `tools/gen_api_docs.py`. Interactive docs: run `make api` and open http://localhost:8000/docs._", "",
         spec["info"].get("description", ""), "",
         "## Authentication (demo)", "",
         "Every endpoint except `/health` requires the header `X-User: <user_id>`. Demo users: `exec.demo`, `opsmgr.demo`, "
         "`opsmgr2.demo`, `analyst.demo`, `desk.demo`, `audit.demo`. Unknown users get **401**; a role without permission gets "
         "**403**. In a pilot this header is replaced by an OIDC bearer token whose group claims map to the same roles.", "",
         "## Endpoints", "",
         "| Method | Path | Summary | Access |", "|---|---|---|---|"]
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            L.append(f"| {method.upper()} | `{path}` | {op.get('summary', '')} | {AUTH_NOTES.get((method.upper(), path), 'any known user')} |")
    L += ["", "## Details", ""]
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            L += [f"### {method.upper()} `{path}`", "", op.get("description", "").strip() or op.get("summary", ""), ""]
            params = [p for p in op.get("parameters", []) if p["name"].lower() != "x-user"]
            if params:
                L += ["| Parameter | In | Type | Required | Default |", "|---|---|---|---|---|"]
                for p in params:
                    sch = p.get("schema", {})
                    L.append(f"| `{p['name']}` | {p['in']} | {schema_ref(sch)} | {'yes' if p.get('required') else 'no'} | {sch.get('default', '')} |")
                L.append("")
            body = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            if body:
                name = schema_ref(body)
                comp = spec["components"]["schemas"].get(name, {})
                L += [f"Request body: `{name}`", "", "| Field | Type | Required |", "|---|---|---|"]
                for f, fs in comp.get("properties", {}).items():
                    L.append(f"| `{f}` | {schema_ref(fs)} | {'yes' if f in comp.get('required', []) else 'no'} |")
                L.append("")
            codes = ", ".join(f"`{c}`" for c in op.get("responses", {}))
            L += [f"Responses: {codes}", ""]
    L += ["## Example", "", "```bash", "curl -s -X POST http://localhost:8000/ask \\", "  -H 'X-User: analyst.demo' -H 'Content-Type: application/json' \\",
          "  -d '{\"question\": \"What are the recurring causes of service downtime?\", \"engine\": \"rules\"}'", "```", "",
          "The response contains `answer`, `engine`, `abstained`, `grounding` (figures checked against evidence), `latency_ms` "
          "and `evidence` (one entry per tool call with its SQL and document sources).", ""]
    (ROOT / "docs" / "api.md").write_text("\n".join(L))
    print("wrote docs/api.md")


if __name__ == "__main__":
    main()
