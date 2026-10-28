---
name: jira
description: Access to Staples' self-hosted Jira (jiraent.staples.com) via CLI. Use for Jira tickets, FILL/partner project keys, JQL, sprints, boards, and issue metadata.
---

Use the `jira` CLI on PATH (source: `jira/` in the agent-skills-shared repo). There is no Jira MCP server.
Reads run freely. Never print the PAT or authorization headers.
The user's team owns **FILL**; other project keys belong to partner teams.

## Workflow

Run `jira reference` once before your first JQL search for project and field guidance.
Use `jira <command> --help` for supported arguments.

```bash
jira server-info
jira myself
jira search-issues 'project = FILL AND assignee = currentUser() AND statusCategory != Done' --max-results 25
jira get-issue FILL-1234 --fields 'summary,status,assignee,priority'
jira list-boards --project FILL
jira list-sprints <board_id> --state active
```

Issue search supports `--fields`, `--max-results`, and `--start-at`; default fields are compact.
Check pagination before treating a result as complete. Most other CLI list commands return
only the first page. `create-meta` collects every issue-type and field page automatically.
`get-issue` defaults to curated fields; `--raw` returns all fields and can be very large.

| Task | Command |
|------|---------|
| Comments / worklogs / remote links / watchers | `jira get-issue-comments <KEY>`, `get-issue-worklogs`, `get-issue-remote-links`, `get-issue-watchers` |
| Available transitions (read only) | `jira get-issue-transitions <KEY>` |
| Projects | `jira list-projects`, `jira get-project <KEY>` |
| Versions / components | `jira get-project-versions <KEY>`, `jira get-project-components <KEY>` |
| Users | `jira get-user <username>`, `jira search-users '<query>' --max-results 25` |
| Schema | `jira list-fields`, `list-issue-types`, `list-priorities`, `list-resolutions`, `list-statuses` |
| Board contents | `jira get-board-issues <id>`, `jira get-board-backlog <id>` (Scrum) |
| Sprint contents | `jira get-sprint <id>`, `jira get-sprint-issues <id>` |
| Attachments | `jira get-attachment <id>` (ID from issue fields; returns a local path) |

Every abbreviated command in the table is a `jira` subcommand.

## Writes

`create-issue`, `update-issue`, `add-comment`, `transition-issue`, `assign-issue`, and
`add-worklog` require `--yes`. Before a write, show the concrete change and obtain user
authorization; existing explicit authorization for that change is sufficient.
Do not perform live writes merely to test compatibility.
Before creating, run `jira create-meta <PROJECT> --issuetype <Type>` to discover required
fields and allowed values. `update-issue --fields` replaces only the supplied fields.
For multiline comments use `--body -` and stdin.

## Compatibility

Read endpoints were verified against `jiraent.staples.com` **11.3.3** on 2026-09-23.
The CLI uses self-hosted REST `/rest/api/2`, Agile `/rest/agile/1.0`, and a Bearer PAT.
Users are addressed by username. Write endpoints were not exercised against the live server.

This CLI is **not Cloud-ready**: do not just replace `JIRA_BASE_URL` with a Cloud URL.
Cloud migration requires different authentication, account IDs, enhanced JQL search and
pagination, and a review of metadata/project response shapes and rich-text handling.
See `jira/COMPATIBILITY.md` in the agent-skills-shared repo for the audit and migration references.
