# Jira compatibility audit — 2026-09-23

The running Staples server reports **11.3.3**, build **11030004**. Existing Bearer PAT
access and the REST v2/Agile APIs work. No upgrade-induced failure was observed in the
read operations tested. This is a sampled compatibility check, not a guarantee for every
permission, custom field, or workflow.

## Live checks

All 28 checks passed: server info, authenticated user, JQL search, FILL boards;
fields, issue types, priorities, resolutions, statuses, projects; FILL project details,
versions, components, create issue types and Story creation fields; user lookup and
search; issue detail, comments, worklogs, transitions, remote links and watchers;
board issues, backlog, sprint list, sprint detail and sprint issues.

Issue-related probes used FILL-9461; board/sprint probes used a visible FILL Scrum board.
Probes used GET only and emitted status summaries without credentials or issue bodies.
Attachment downloads and live writes were not tested. Creation metadata and available
transitions were read successfully, but this does not prove write permissions or payload
acceptance for every workflow. Write CLI confirmation gates are tested offline.

## Corrections

These were existing local defects, not demonstrated Jira 11 regressions:

- `get-issue --raw` had been passed into the expansion argument.
- Issue search page size had been passed into the expansion argument, leaving a 50-row default.
- User search page size had been passed as its start offset.
- CLI issue searches overrode compact default fields with None.
- Creation metadata stopped at the first page and had a broken list-response fallback.
- Documented board project and sprint state filters were absent from the parser.
- Skills and the domain reference retained contradictory retired MCP/read-only instructions.

Run regression tests with:

```sh
uv run --directory jira python -m unittest discover -s tests -v   # from the repo root
```

## Future Cloud migration

The current client is self-hosted only. Do not switch only the hostname.

| Area | Required review/change |
|---|---|
| Authentication | Replace DC Bearer PAT with an approved Cloud flow, such as OAuth 2.0 or email/API-token basic auth for a personal script. Scoped tokens may use the API gateway and cloud ID. |
| Users | Replace username/name identities with accountId, including lookup and assignment; remap JQL user literals. |
| Search | Adopt enhanced `/rest/api/3/search/jql` (or Cloud v2 equivalent); legacy Cloud `/search` is being removed. Handle `nextPageToken` instead of offset pagination. |
| Text | If targeting v3, handle Atlassian Document Format for descriptions, comments, worklog comments and multiline custom fields. Cloud v2 is also available; v3 is a choice requiring payload changes. |
| Metadata | Revalidate creation metadata, project pagination, migrated custom-field IDs, required fields, workflows, board/sprint IDs and permissions. |
| Validation | Test against the actual Cloud tenant; authenticate and run read probes first, then explicitly authorized writes to a test project. |

Sources checked on the audit date:

- [Cloud authentication](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/)
- [Cloud identity migration](https://developer.atlassian.com/cloud/jira/platform/deprecation-notice-user-privacy-api-migration-guide/)
- [Cloud enhanced JQL search](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/)
- [Cloud API versions and ADF](https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/)
