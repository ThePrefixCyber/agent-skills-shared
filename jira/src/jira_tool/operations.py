"""Jira operations for self-hosted Jira (jiraent.staples.com).

Ported from the former MCP server; the FastMCP decorators are gone and the
behaviour of every read is unchanged. Write operations were added afterwards
and are grouped at the end of this module.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import httpx

JIRA_BASE_URL = os.environ["JIRA_BASE_URL"].rstrip("/")
JIRA_PAT = os.environ["JIRA_PAT"]


_headers = {
    "Authorization": f"Bearer {JIRA_PAT}",
    "Accept": "application/json",
}
api_v2 = httpx.Client(base_url=f"{JIRA_BASE_URL}/rest/api/2", headers=_headers, timeout=30.0)
agile = httpx.Client(base_url=f"{JIRA_BASE_URL}/rest/agile/1.0", headers=_headers, timeout=30.0)
# Bare host client for downloading attachment bytes (content URLs live under /secure/, not /rest).
files = httpx.Client(base_url=JIRA_BASE_URL, headers=_headers, timeout=60.0, follow_redirects=True)

# Human-meaningful fields returned by get_issue when no explicit `fields` are requested.
# A raw issue carries ~1500 fields (mostly null/cryptic customfields) and overflows the
# tool token limit; this curated set covers reading a ticket. Use fields=... or raw=True
# to get customfields (sprint, story points, epic link, etc.).
_DEFAULT_FIELDS = (
    "summary,status,issuetype,priority,resolution,resolutiondate,"
    "assignee,reporter,creator,created,updated,duedate,"
    "labels,components,fixVersions,versions,parent,subtasks,issuelinks,"
    "description,comment,attachment,project,timetracking,votes,watches"
)
DEFAULT_SEARCH_FIELDS = "summary,status,assignee,priority,issuetype,updated"


# Noise keys scrubbed recursively from issue responses (avatar image URLs repeated in
# every user/author object — large and never useful for reading a ticket).
_SCRUB_KEYS = {"avatarUrls"}


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if k not in _SCRUB_KEYS}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def _prune_issue(issue: dict) -> dict:
    """Drop null/empty fields and scrub avatar-URL noise so the response stays compact."""
    fields = issue.get("fields")
    if isinstance(fields, dict):
        issue["fields"] = {
            k: _scrub(v) for k, v in fields.items() if v not in (None, [], {}, "")
        }
    return issue


def _get(client: httpx.Client, path: str, params: dict | None = None) -> Any:
    r = client.get(path, params={k: v for k, v in (params or {}).items() if v is not None})
    r.raise_for_status()
    return r.json() if r.content else None


def _post(client: httpx.Client, path: str, body: dict) -> Any:
    r = client.post(path, json=body)
    _raise_with_detail(r)
    return r.json() if r.content else None


def _put(client: httpx.Client, path: str, body: dict) -> Any:
    r = client.put(path, json=body)
    _raise_with_detail(r)
    return r.json() if r.content else None


def _raise_with_detail(r: httpx.Response) -> None:
    """Jira returns the useful reason in the body, not the status line.

    A bare raise_for_status on a create gives "400 Bad Request" and nothing else;
    the errorMessages/errors payload is what actually says which field is wrong.
    """
    if r.is_success:
        return
    detail = ""
    try:
        data = r.json()
        parts = list(data.get("errorMessages") or [])
        parts += [f"{k}: {v}" for k, v in (data.get("errors") or {}).items()]
        detail = "; ".join(parts)
    except Exception:
        detail = (r.text or "")[:400]
    raise RuntimeError(f"HTTP {r.status_code} from {r.request.url.path}: {detail or r.reason_phrase}")


# ── Reference ────────────────────────────────────────────────────────

_REFERENCE_PATH = Path(__file__).parent / "REFERENCE.md"


def get_reference() -> str:
    """Return the Jira domain reference — common JQL patterns, project keys, and field tips.

    Call this before your first JQL query so you use the right project keys and field names.
    """
    try:
        return _REFERENCE_PATH.read_text()
    except FileNotFoundError:
        return "REFERENCE.md not found — it should ship with the MCP server."


# ── Issue ────────────────────────────────────────────────────────────

def get_issue(
    key: str,
    fields: str | None = None,
    expand: str | None = None,
    raw: bool = False,
) -> dict:
    """Fetch a Jira issue by key (e.g. FILL-9682).

    By default this returns a curated set of human-meaningful fields with null/empty values
    dropped, so real issues fit in a tool response (a raw issue carries ~1500 fields and
    overflows the token limit). Pass fields=... for specific fields (including customfields),
    or raw=True for the complete unfiltered issue.

    Args:
        key: Issue key.
        fields: Comma-separated field list (e.g. "summary,status,customfield_10400"). Overrides the default set.
        expand: Optional expand directives (e.g. "renderedFields,changelog").
        raw: If True, request and return every field exactly as Jira sends it.
    """
    if raw:
        return _get(api_v2, f"/issue/{key}", {"expand": expand})
    issue = _get(api_v2, f"/issue/{key}", {"fields": fields or _DEFAULT_FIELDS, "expand": expand})
    return _prune_issue(issue) if isinstance(issue, dict) else issue


def get_attachment(attachment_id: str, save_dir: str | None = None) -> dict:
    """Download an issue attachment and save it locally so its content can be opened/read.

    Use the numeric id from get_issue's `.fields.attachment[].id`. Returns the saved path
    plus metadata; for images, open the returned path to view it.

    Args:
        attachment_id: Numeric attachment id (e.g. "1198742").
        save_dir: Directory to save into. Defaults to the system temp dir.
    """
    meta = _get(api_v2, f"/attachment/{attachment_id}")
    resp = files.get(meta["content"])
    resp.raise_for_status()
    out_dir = Path(save_dir) if save_dir else Path(tempfile.gettempdir())
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / meta["filename"]
    path.write_bytes(resp.content)
    return {
        "filename": meta["filename"],
        "mimeType": meta.get("mimeType"),
        "size": meta.get("size"),
        "path": str(path),
    }


def get_issue_comments(key: str, start_at: int = 0, max_results: int = 50) -> dict:
    """Get comments on an issue."""
    return _get(api_v2, f"/issue/{key}/comment", {"startAt": start_at, "maxResults": max_results})


def get_issue_worklogs(key: str) -> dict:
    """Get worklogs on an issue."""
    return _get(api_v2, f"/issue/{key}/worklog")


def get_issue_transitions(key: str) -> dict:
    """Get available status transitions for an issue (read-only — does not perform them)."""
    return _get(api_v2, f"/issue/{key}/transitions")


def get_issue_remote_links(key: str) -> list:
    """Get remote/external links attached to an issue (Confluence pages, etc.)."""
    return _get(api_v2, f"/issue/{key}/remotelink")


def get_issue_watchers(key: str) -> dict:
    """Get watchers on an issue."""
    return _get(api_v2, f"/issue/{key}/watchers")


def _get_create_meta_values(path: str) -> list:
    """Collect every metadata page, including server-capped pages."""
    values = []
    start_at = 0
    while True:
        page = _get(api_v2, path, {"startAt": start_at, "maxResults": 50})
        if isinstance(page, list):
            return values + page
        page = page or {}
        batch = page.get("values", [])
        values.extend(batch)
        next_start = page.get("startAt", start_at) + len(batch)
        total = page.get("total")
        if page.get("isLast") is True or (total is not None and next_start >= total):
            return values
        if "isLast" not in page and total is None:
            return values
        if not batch or next_start <= start_at:
            raise RuntimeError(f"Create metadata pagination made no progress at {path}")
        start_at = next_start


def get_create_meta(project_key: str, issuetype_name: str | None = None) -> dict:
    """Field metadata for creating an issue: which fields exist, which are required,
    and the allowed values for select fields.

    Uses the paginated Data Center endpoints /issue/createmeta/{key}/issuetypes
    and .../issuetypes/{id}, including every page of types and fields.
    """
    values = _get_create_meta_values(f"/issue/createmeta/{project_key}/issuetypes")
    summary = [{"id": t.get("id"), "name": t.get("name"), "subtask": t.get("subtask")} for t in values]
    if not issuetype_name:
        return {"project": project_key, "issue_types": summary}

    match = next((t for t in values if str(t.get("name", "")).lower() == issuetype_name.lower()), None)
    if not match:
        return {
            "project": project_key,
            "error": f"No issue type named {issuetype_name!r} in {project_key}",
            "issue_types": summary,
        }
    fvals = _get_create_meta_values(f"/issue/createmeta/{project_key}/issuetypes/{match['id']}")
    return {
        "project": project_key,
        "issue_type": {"id": match.get("id"), "name": match.get("name")},
        "required_fields": [f.get("fieldId") or f.get("key") for f in fvals if f.get("required")],
        "fields": [
            {
                "id": f.get("fieldId") or f.get("key"),
                "name": f.get("name"),
                "required": f.get("required"),
                "allowed_values": [
                    v.get("value") or v.get("name") or v.get("id")
                    for v in (f.get("allowedValues") or [])
                ][:50],
            }
            for f in fvals
        ],
    }



# ── Search ───────────────────────────────────────────────────────────

def search_issues(
    jql: str,
    fields: str | None = DEFAULT_SEARCH_FIELDS,
    expand: str | None = None,
    start_at: int = 0,
    max_results: int = 50,
) -> dict:
    """Search issues by JQL.

    Args:
        jql: A JQL query, e.g. 'project = FILL AND assignee = currentUser() AND statusCategory != Done'.
        fields: Comma-separated fields to return. Defaults to a compact set.
        expand: Optional expand directives.
        start_at: Pagination offset.
        max_results: Page size (server may cap, typically 100).
    """
    return _get(
        api_v2,
        "/search",
        {
            "jql": jql,
            "fields": fields,
            "expand": expand,
            "startAt": start_at,
            "maxResults": max_results,
        },
    )


# ── Projects ─────────────────────────────────────────────────────────

def list_projects() -> list:
    """List all projects visible to the authenticated user."""
    return _get(api_v2, "/project")


def get_project(key_or_id: str) -> dict:
    """Get project details by key or numeric id."""
    return _get(api_v2, f"/project/{key_or_id}")


def get_project_versions(key_or_id: str) -> list:
    """List versions (releases / fix-versions) for a project."""
    return _get(api_v2, f"/project/{key_or_id}/versions")


def get_project_components(key_or_id: str) -> list:
    """List components for a project."""
    return _get(api_v2, f"/project/{key_or_id}/components")


# ── Users ────────────────────────────────────────────────────────────

def myself() -> dict:
    """Return the user record for the authenticated PAT — sanity check for credentials."""
    return _get(api_v2, "/myself")


def get_user(username: str) -> dict:
    """Look up a user by username (server/DC Jira)."""
    return _get(api_v2, "/user", {"username": username})


def search_users(query: str, start_at: int = 0, max_results: int = 50) -> list:
    """Search users by name or email fragment."""
    return _get(
        api_v2,
        "/user/search",
        {"username": query, "startAt": start_at, "maxResults": max_results},
    )


# ── Schema / metadata ────────────────────────────────────────────────

def list_fields() -> list:
    """List all fields, including custom field IDs and their human-readable names."""
    return _get(api_v2, "/field")


def list_issue_types() -> list:
    """List all issue types defined in this Jira instance."""
    return _get(api_v2, "/issuetype")


def list_priorities() -> list:
    """List all priorities."""
    return _get(api_v2, "/priority")


def list_resolutions() -> list:
    """List all resolutions."""
    return _get(api_v2, "/resolution")


def list_statuses() -> list:
    """List all statuses."""
    return _get(api_v2, "/status")


def server_info() -> dict:
    """Get Jira server version, deployment type, and build info."""
    return _get(api_v2, "/serverInfo")


# ── Agile (boards / sprints / backlog) ──────────────────────────────

def list_boards(
    project_key_or_id: str | None = None,
    type: str | None = None,
    name: str | None = None,
    start_at: int = 0,
    max_results: int = 50,
) -> dict:
    """List Agile boards. Filter by project, type ("scrum"/"kanban"), or name fragment."""
    return _get(
        agile,
        "/board",
        {
            "projectKeyOrId": project_key_or_id,
            "type": type,
            "name": name,
            "startAt": start_at,
            "maxResults": max_results,
        },
    )


def list_sprints(
    board_id: int,
    state: str | None = None,
    start_at: int = 0,
    max_results: int = 50,
) -> dict:
    """List sprints on a board. state can be "active", "closed", "future", or comma-combos."""
    return _get(
        agile,
        f"/board/{board_id}/sprint",
        {"state": state, "startAt": start_at, "maxResults": max_results},
    )


def get_sprint(sprint_id: int) -> dict:
    """Get details for a single sprint."""
    return _get(agile, f"/sprint/{sprint_id}")


def get_sprint_issues(
    sprint_id: int,
    jql: str | None = None,
    fields: str | None = "summary,status,assignee,priority",
    start_at: int = 0,
    max_results: int = 50,
) -> dict:
    """Get issues in a sprint, optionally filtered by an additional JQL clause."""
    return _get(
        agile,
        f"/sprint/{sprint_id}/issue",
        {"jql": jql, "fields": fields, "startAt": start_at, "maxResults": max_results},
    )


def get_board_backlog(
    board_id: int,
    jql: str | None = None,
    fields: str | None = "summary,status,assignee,priority",
    start_at: int = 0,
    max_results: int = 50,
) -> dict:
    """Get backlog issues for a board (Scrum boards only)."""
    return _get(
        agile,
        f"/board/{board_id}/backlog",
        {"jql": jql, "fields": fields, "startAt": start_at, "maxResults": max_results},
    )


def get_board_issues(
    board_id: int,
    jql: str | None = None,
    fields: str | None = "summary,status,assignee,priority",
    start_at: int = 0,
    max_results: int = 50,
) -> dict:
    """Get all issues currently on a board."""
    return _get(
        agile,
        f"/board/{board_id}/issue",
        {"jql": jql, "fields": fields, "startAt": start_at, "maxResults": max_results},
    )


# ── Writes ───────────────────────────────────────────────────────────
#
# Added when the CLI replaced the read-only MCP server. Everything above this
# line is a GET; everything below changes Jira. The CLI gates each of these
# behind an explicit --yes.


def create_issue(
    project_key: str,
    issuetype_name: str,
    summary: str,
    description: str | None = None,
    priority_name: str | None = None,
    assignee_name: str | None = None,
    labels: list[str] | None = None,
    components: list[str] | None = None,
    parent_key: str | None = None,
    extra_fields: dict | None = None,
) -> dict:
    """Create an issue. Returns the new key plus its browse URL.

    `extra_fields` is merged last and takes precedence, so custom fields can be set
    by id, e.g. {"customfield_10001": "..."}. Use get_create_meta to discover which
    fields a project/type requires and what values they allow.
    """
    fields: dict[str, Any] = {
        "project": {"key": project_key},
        "issuetype": {"name": issuetype_name},
        "summary": summary,
    }
    if description:
        fields["description"] = description
    if priority_name:
        fields["priority"] = {"name": priority_name}
    if assignee_name:
        fields["assignee"] = {"name": assignee_name}
    if labels:
        fields["labels"] = labels
    if components:
        fields["components"] = [{"name": c} for c in components]
    if parent_key:
        fields["parent"] = {"key": parent_key}
    if extra_fields:
        fields.update(extra_fields)

    created = _post(api_v2, "/issue", {"fields": fields}) or {}
    key = created.get("key")
    return {
        "key": key,
        "id": created.get("id"),
        "url": f"{JIRA_BASE_URL}/browse/{key}" if key else None,
        "self": created.get("self"),
    }


def update_issue(issue_key: str, fields: dict, notify: bool = True) -> dict:
    """Update fields on an existing issue. `fields` is the raw Jira fields object.

    This replaces the values of the fields you name; fields you omit are untouched.
    """
    if not fields:
        raise ValueError("No fields given — nothing to update")
    r = api_v2.put(f"/issue/{issue_key}", json={"fields": fields},
                   params={"notifyUsers": str(bool(notify)).lower()})
    _raise_with_detail(r)
    return {"key": issue_key, "updated_fields": sorted(fields), "url": f"{JIRA_BASE_URL}/browse/{issue_key}"}


def add_comment(issue_key: str, body: str) -> dict:
    """Add a comment to an issue."""
    if not body.strip():
        raise ValueError("Comment body is empty")
    c = _post(api_v2, f"/issue/{issue_key}/comment", {"body": body}) or {}
    return {
        "issue": issue_key,
        "comment_id": c.get("id"),
        "author": (c.get("author") or {}).get("displayName"),
        "created": c.get("created"),
        "url": f"{JIRA_BASE_URL}/browse/{issue_key}",
    }


def transition_issue(issue_key: str, transition: str, comment: str | None = None,
                     resolution_name: str | None = None) -> dict:
    """Move an issue through a workflow transition, by transition name or id.

    Jira rejects a transition id that is not currently available, so this resolves
    the name against the issue's live transition list and reports the valid options
    when there is no match.
    """
    available = (_get(api_v2, f"/issue/{issue_key}/transitions") or {}).get("transitions", [])
    match = next(
        (t for t in available
         if str(t.get("id")) == str(transition)
         or str(t.get("name", "")).lower() == str(transition).lower()),
        None,
    )
    if not match:
        return {
            "issue": issue_key,
            "error": f"No transition matching {transition!r} is available right now",
            "available": [{"id": t.get("id"), "name": t.get("name")} for t in available],
        }
    body: dict[str, Any] = {"transition": {"id": match["id"]}}
    if comment:
        body["update"] = {"comment": [{"add": {"body": comment}}]}
    if resolution_name:
        body["fields"] = {"resolution": {"name": resolution_name}}
    _post(api_v2, f"/issue/{issue_key}/transitions", body)
    after = _get(api_v2, f"/issue/{issue_key}", {"fields": "status,resolution"}) or {}
    st = (after.get("fields") or {}).get("status") or {}
    return {
        "issue": issue_key,
        "transition_applied": match.get("name"),
        "status_now": st.get("name"),
        "url": f"{JIRA_BASE_URL}/browse/{issue_key}",
    }


def assign_issue(issue_key: str, username: str | None) -> dict:
    """Assign an issue. Pass username=None to unassign."""
    r = api_v2.put(f"/issue/{issue_key}/assignee", json={"name": username})
    _raise_with_detail(r)
    return {"issue": issue_key, "assignee": username or "(unassigned)",
            "url": f"{JIRA_BASE_URL}/browse/{issue_key}"}


def add_worklog(issue_key: str, time_spent: str, comment: str | None = None,
                started: str | None = None) -> dict:
    """Log work against an issue. time_spent uses Jira syntax, e.g. '2h 30m'."""
    body: dict[str, Any] = {"timeSpent": time_spent}
    if comment:
        body["comment"] = comment
    if started:
        body["started"] = started
    w = _post(api_v2, f"/issue/{issue_key}/worklog", body) or {}
    return {"issue": issue_key, "worklog_id": w.get("id"), "time_spent": w.get("timeSpent"),
            "url": f"{JIRA_BASE_URL}/browse/{issue_key}"}
