# Jira Reference (jiraent.staples.com)

Self-hosted Jira Server/Data Center. REST API v2 at `/rest/api/2`, Agile API at `/rest/agile/1.0`.

## Project keys

The user's primary project is **FILL** (Astra team). Other keys you may see (FLCN, DSETEAM, MB, P2DTEAM, etc.) are partner teams — do not assume the user owns them.

## Common JQL patterns

- My open work: `assignee = currentUser() AND statusCategory != Done ORDER BY updated DESC`
- Recently updated in a project: `project = FILL AND updated >= -7d ORDER BY updated DESC`
- By status: `project = FILL AND status = "In Progress"`
- By type: `project = FILL AND issuetype = Bug`
- Linked to an epic: `"Epic Link" = FILL-1234`
- Mentioned in: `text ~ "lead time"` (full-text)
- In active sprint: `project = FILL AND sprint in openSprints()`

## Field tips

- This instance is **Server/DC**, so users are referenced by `username` (not `accountId`).
- Custom fields use ids like `customfield_10001`. Use `jira list-fields` to map ids ↔ names.
- "Epic Link" and "Sprint" are typically custom fields — quote them in JQL.

## Reading issues (`jira get-issue`)

- By default `get_issue` returns a **curated set** of human-meaningful fields (summary, status, assignee, description, comments, attachments, etc.) with null/empty values and avatar-URL noise stripped. A raw issue here carries ~1500 fields and overflows the tool token limit.
- Need a customfield (Sprint, Story Points, Epic Link) or the full dev-status blob? Pass `--fields "summary,customfield_10400,..."` to request specific fields, or `--raw` for the complete unfiltered issue.

## Attachments (`jira get-attachment`)

- Issue attachments (screenshots, logs) carry their id in `get_issue` → `.fields.attachment[].id`.
- `jira get-attachment <attachment_id>` downloads the file (using the server's PAT auth — the `/secure/attachment/...` URLs are not publicly fetchable) and saves it to disk, returning the local `path`. For images, open that path to view the content.

## Status categories

`statusCategory` values: `To Do`, `In Progress`, `Done`. Useful for cross-status filtering.

## Pagination

Most list endpoints support `startAt` / `maxResults`. The server typically caps `maxResults` at 100. Check `total` in the response.

## Writes and compatibility

The CLI includes six write commands, each gated by `--yes`. Obtain authorization for the
specific change before using them. Read-only compatibility tests must not mutate tickets.
Run `jira create-meta FILL --issuetype Story` before creation; metadata is paginated automatically.

Verified read endpoints against self-hosted 11.3.3 on 2026-09-23. Cloud requires a separate
adapter; see `jira/COMPATIBILITY.md` in the agent-skills-shared repo. Changing the URL alone is insufficient.
