"""jira — CLI for self-hosted Jira (jiraent.staples.com).

Read subcommand names match the previous bypass CLI so existing skills and agent
definitions keep working. Writes are new: the old MCP server was read-only, which
is why ticket creation used to be done with ad-hoc curl.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

# operations.py reads JIRA_BASE_URL / JIRA_PAT at import time, so the environment
# has to be in place before it is imported.
load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from . import operations as ops  # noqa: E402


def _out(data) -> None:
    print(data if isinstance(data, str) else json.dumps(data, indent=2, default=str))


def _confirm(args, action: str) -> None:
    if not args.yes:
        raise SystemExit(
            f"error: {action} changes Jira. Re-run with --yes to confirm.\n"
            f"       Check the target first — writes here are not reversible from the CLI."
        )


def _json_arg(value: str | None, label: str) -> dict | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as e:
        raise SystemExit(f"error: --{label} must be a JSON object: {e}")
    if not isinstance(parsed, dict):
        raise SystemExit(f"error: --{label} must be a JSON object")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jira", description="Query and update self-hosted Jira.")
    sub = p.add_subparsers(dest="command", required=True)

    # ── reads ────────────────────────────────────────────────────────
    sub.add_parser("reference", help="domain guide — JQL patterns, project keys, field tips")
    sub.add_parser("myself", help="the authenticated user")
    sub.add_parser("server-info", help="Jira version and deployment info")
    sub.add_parser("list-fields", help="all fields with ids (incl. customfield_*)")
    sub.add_parser("list-issue-types", help="all issue types")
    sub.add_parser("list-priorities", help="all priorities")
    sub.add_parser("list-resolutions", help="all resolutions")
    sub.add_parser("list-statuses", help="all statuses")
    sub.add_parser("list-projects", help="all visible projects")
    sp = sub.add_parser("list-boards", help="all agile boards")
    sp.add_argument("--project", help="project key or id, e.g. FILL")

    sp = sub.add_parser("get-issue", help="read one issue")
    sp.add_argument("issue_key")
    sp.add_argument("--fields", help="comma-separated field list (default: curated set)")
    sp.add_argument("--raw", action="store_true", help="return the unpruned issue")

    for name, helptext, arg in (
        ("get-issue-comments", "comments on an issue", "issue_key"),
        ("get-issue-worklogs", "worklogs on an issue", "issue_key"),
        ("get-issue-transitions", "transitions available right now", "issue_key"),
        ("get-issue-remote-links", "remote links on an issue", "issue_key"),
        ("get-issue-watchers", "watchers on an issue", "issue_key"),
        ("get-project", "one project", "project_key"),
        ("get-project-versions", "versions in a project", "project_key"),
        ("get-project-components", "components in a project", "project_key"),
        ("get-user", "one user by username", "username"),
        ("get-sprint", "one sprint", "sprint_id"),
        ("get-sprint-issues", "issues in a sprint", "sprint_id"),
        ("get-board-backlog", "backlog for a board", "board_id"),
        ("get-board-issues", "issues on a board", "board_id"),
    ):
        sp = sub.add_parser(name, help=helptext)
        sp.add_argument(arg)

    sp = sub.add_parser("list-sprints", help="sprints on a board")
    sp.add_argument("board_id")
    sp.add_argument("--state", help="active, closed, future, or a comma-separated combination")

    sp = sub.add_parser("search-issues", help="run a JQL search")
    sp.add_argument("jql")
    sp.add_argument("--fields", default=ops.DEFAULT_SEARCH_FIELDS)
    sp.add_argument("--max-results", type=int, default=50)
    sp.add_argument("--start-at", type=int, default=0)

    sp = sub.add_parser("search-users", help="find users")
    sp.add_argument("query")
    sp.add_argument("--max-results", type=int, default=50)

    sp = sub.add_parser("get-attachment", help="download an attachment by id")
    sp.add_argument("attachment_id")

    sp = sub.add_parser("create-meta", help="fields/required/allowed-values for creating an issue")
    sp.add_argument("project_key")
    sp.add_argument("--issuetype", help="restrict to one issue type, e.g. Story")

    # ── writes (each requires --yes) ─────────────────────────────────
    sp = sub.add_parser("create-issue", help="create an issue [WRITE]")
    sp.add_argument("--project", required=True, help="project key, e.g. FILL")
    sp.add_argument("--type", dest="issuetype", required=True, help="issue type, e.g. Story")
    sp.add_argument("--summary", required=True)
    sp.add_argument("--description")
    sp.add_argument("--priority")
    sp.add_argument("--assignee", help="username")
    sp.add_argument("--labels", help="comma-separated")
    sp.add_argument("--components", help="comma-separated")
    sp.add_argument("--parent", help="parent issue key, for sub-tasks")
    sp.add_argument("--fields", help='JSON object of extra/custom fields, merged last')
    sp.add_argument("--yes", action="store_true")

    sp = sub.add_parser("update-issue", help="update fields on an issue [WRITE]")
    sp.add_argument("issue_key")
    sp.add_argument("--fields", required=True, help="JSON object of fields to set")
    sp.add_argument("--no-notify", action="store_true", help="do not email watchers")
    sp.add_argument("--yes", action="store_true")

    sp = sub.add_parser("add-comment", help="comment on an issue [WRITE]")
    sp.add_argument("issue_key")
    sp.add_argument("--body", required=True, help="comment text, or '-' to read stdin")
    sp.add_argument("--yes", action="store_true")

    sp = sub.add_parser("transition-issue", help="move an issue through its workflow [WRITE]")
    sp.add_argument("issue_key")
    sp.add_argument("transition", help="transition name or id (see get-issue-transitions)")
    sp.add_argument("--comment")
    sp.add_argument("--resolution")
    sp.add_argument("--yes", action="store_true")

    sp = sub.add_parser("assign-issue", help="assign or unassign an issue [WRITE]")
    sp.add_argument("issue_key")
    sp.add_argument("--to", dest="username", help="username; omit to unassign")
    sp.add_argument("--yes", action="store_true")

    sp = sub.add_parser("add-worklog", help="log work on an issue [WRITE]")
    sp.add_argument("issue_key")
    sp.add_argument("--time-spent", required=True, help="Jira syntax, e.g. '2h 30m'")
    sp.add_argument("--comment")
    sp.add_argument("--started", help="ISO8601, e.g. 2026-09-04T10:00:00.000+0000")
    sp.add_argument("--yes", action="store_true")
    return p


def _csv(v): return [x.strip() for x in v.split(",") if x.strip()] if v else None


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    c = a.command

    simple = {
        "reference": ops.get_reference, "myself": ops.myself, "server-info": ops.server_info,
        "list-fields": ops.list_fields, "list-issue-types": ops.list_issue_types,
        "list-priorities": ops.list_priorities, "list-resolutions": ops.list_resolutions,
        "list-statuses": ops.list_statuses, "list-projects": ops.list_projects,
    }
    one_arg = {
        "get-issue-comments": (ops.get_issue_comments, "issue_key"),
        "get-issue-worklogs": (ops.get_issue_worklogs, "issue_key"),
        "get-issue-transitions": (ops.get_issue_transitions, "issue_key"),
        "get-issue-remote-links": (ops.get_issue_remote_links, "issue_key"),
        "get-issue-watchers": (ops.get_issue_watchers, "issue_key"),
        "get-project": (ops.get_project, "project_key"),
        "get-project-versions": (ops.get_project_versions, "project_key"),
        "get-project-components": (ops.get_project_components, "project_key"),
        "get-user": (ops.get_user, "username"),
        "get-sprint": (ops.get_sprint, "sprint_id"),
        "get-sprint-issues": (ops.get_sprint_issues, "sprint_id"),
        "get-board-backlog": (ops.get_board_backlog, "board_id"),
        "get-board-issues": (ops.get_board_issues, "board_id"),
        "get-attachment": (ops.get_attachment, "attachment_id"),
    }

    if c in simple:
        _out(simple[c]())
    elif c in one_arg:
        fn, arg = one_arg[c]
        _out(fn(getattr(a, arg)))
    elif c == "get-issue":
        _out(ops.get_issue(a.issue_key, fields=a.fields, raw=a.raw))
    elif c == "list-boards":
        _out(ops.list_boards(project_key_or_id=a.project))
    elif c == "list-sprints":
        _out(ops.list_sprints(a.board_id, state=a.state))
    elif c == "search-issues":
        _out(ops.search_issues(a.jql, fields=a.fields, max_results=a.max_results, start_at=a.start_at))
    elif c == "search-users":
        _out(ops.search_users(a.query, max_results=a.max_results))
    elif c == "create-meta":
        _out(ops.get_create_meta(a.project_key, a.issuetype))

    elif c == "create-issue":
        _confirm(a, "create-issue")
        _out(ops.create_issue(a.project, a.issuetype, a.summary, a.description, a.priority,
                              a.assignee, _csv(a.labels), _csv(a.components), a.parent,
                              _json_arg(a.fields, "fields")))
    elif c == "update-issue":
        _confirm(a, "update-issue")
        _out(ops.update_issue(a.issue_key, _json_arg(a.fields, "fields"), not a.no_notify))
    elif c == "add-comment":
        _confirm(a, "add-comment")
        body = sys.stdin.read() if a.body == "-" else a.body
        _out(ops.add_comment(a.issue_key, body))
    elif c == "transition-issue":
        _confirm(a, "transition-issue")
        _out(ops.transition_issue(a.issue_key, a.transition, a.comment, a.resolution))
    elif c == "assign-issue":
        _confirm(a, "assign-issue")
        _out(ops.assign_issue(a.issue_key, a.username))
    elif c == "add-worklog":
        _confirm(a, "add-worklog")
        _out(ops.add_worklog(a.issue_key, a.time_spent, a.comment, a.started))
    return 0


if __name__ == "__main__":
    sys.exit(main())
