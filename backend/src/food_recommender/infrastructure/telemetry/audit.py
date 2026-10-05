"""Explicit developer read-back only, with current observation API and bounded pages."""

from typing import Any

import httpx


def fetch_observations(
    client: httpx.Client, trace_id: str, start: str, end: str, *, max_pages: int = 10
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    seen = set()
    for _ in range(max_pages):
        params = {
            "traceId": trace_id,
            "fromStartTime": start,
            "toStartTime": end,
            "fields": "core,basic,io,metadata,usage,model,trace_context",
            "limit": "100",
        }
        if cursor:
            params["cursor"] = cursor
        response = client.get("/api/public/v2/observations", params=params, timeout=5)
        response.raise_for_status()
        page = response.json()
        rows.extend(page["data"])
        cursor = page.get("meta", {}).get("cursor")
        if not cursor:
            return rows
        if cursor in seen:
            raise ValueError("Repeated audit cursor")
        seen.add(cursor)
    raise ValueError("Audit pagination budget exhausted")


def audit_observations(
    rows: list[dict[str, Any]], expected: dict[str, int]
) -> dict[str, Any]:
    from collections import Counter

    from food_recommender.infrastructure.telemetry.redaction import NAMES

    names = Counter(row.get("name") for row in rows)
    ids = {row["id"] for row in rows}
    roots = [row for row in rows if row.get("name") == "recommend-food"]
    failures = []
    if dict(names) != expected:
        failures.append("execution_counts")
    if len(roots) != 1:
        failures.append("root_count")
    for row in rows:
        if row.get("name") not in NAMES:
            failures.append("unknown_name")
        if row.get("input") not in (None, "", {}, []) or row.get("output") not in (
            None,
            "",
            {},
            [],
        ):
            failures.append("content")
        if row.get("parentObservationId") and row["parentObservationId"] not in ids:
            failures.append("orphan")
        if row.get("statusMessage"):
            failures.append("exception_text")
        if not row.get("sessionId"):
            failures.append("missing_session")
        name = row.get("name", "")
        expected_type = (
            "CHAIN"
            if name == "recommend-food"
            else "GENERATION"
            if name == "request-structured-response"
            else "RETRIEVER"
            if name
            in {
                "search_restaurants",
                "search_recipes",
                "search_images",
                "recommend_by_vibe",
            }
            else "TOOL"
            if name.startswith(("search_", "get_"))
            else "AGENT"
        )
        if row.get("type") != expected_type:
            failures.append("observation_type")
        metadata = row.get("metadata") or {}
        for field in ("run_id", "revision", "prompt_revision", "dataset_revision"):
            if not metadata.get(field) and not metadata.get(
                "attributes.langfuse.trace.metadata." + field
            ):
                failures.append("missing_revision_or_run")
        if "duration_ms" not in metadata:
            failures.append("missing_duration")
        if "PRIVATE_CANARY" in str(row):
            failures.append("private_canary")
        if row.get("userId"):
            failures.append("user_id")
    return {
        "observations": len(rows),
        "names": dict(names),
        "failures": sorted(set(failures)),
        "passed": not failures,
    }
