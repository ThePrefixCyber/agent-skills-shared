"""Offline CLI/HTTP regressions; no calls to the company's Jira instance."""

import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

import httpx

with patch.dict(os.environ, {"JIRA_BASE_URL": "https://jira.invalid", "JIRA_PAT": "test-only"}):
    from jira_tool import cli, operations as ops


class CliTests(unittest.TestCase):
    def run_cli(self, args, response):
        requests = []

        def handle(request):
            requests.append(request)
            return httpx.Response(200, json=response)

        with httpx.Client(base_url="https://jira.invalid/rest/api/2",
                          transport=httpx.MockTransport(handle)) as client, \
                httpx.Client(base_url="https://jira.invalid/rest/agile/1.0",
                             transport=httpx.MockTransport(handle)) as agile_client:
            with patch.object(ops, "api_v2", client), patch.object(ops, "agile", agile_client), \
                    contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(cli.main(args), 0)
        return requests[0], json.loads(output.getvalue())

    def test_raw_issue_preserves_empty_fields_and_omits_expand(self):
        issue = {"key": "TEST-1", "fields": {"description": None, "labels": []}}
        request, result = self.run_cli(["get-issue", "TEST-1", "--raw"], issue)
        self.assertEqual(request.url.path, "/rest/api/2/issue/TEST-1")
        self.assertEqual(dict(request.url.params), {})
        self.assertEqual(result, issue)

    def test_default_issue_stays_compact(self):
        request, result = self.run_cli(["get-issue", "TEST-1"], {
            "fields": {"summary": "Example", "description": None},
        })
        self.assertIn("summary", request.url.params["fields"])
        self.assertNotIn("expand", request.url.params)
        self.assertEqual(result["fields"], {"summary": "Example"})

    def test_search_respects_page_size_offset_and_compact_default(self):
        request, _ = self.run_cli([
            "search-issues", "project = TEST", "--max-results", "3", "--start-at", "7",
        ], {"issues": []})
        self.assertEqual(dict(request.url.params), {
            "jql": "project = TEST", "fields": ops.DEFAULT_SEARCH_FIELDS,
            "maxResults": "3", "startAt": "7",
        })

    def test_search_respects_custom_fields(self):
        request, _ = self.run_cli([
            "search-issues", "project = TEST", "--fields", "summary,customfield_123",
        ], {"issues": []})
        self.assertEqual(request.url.params["fields"], "summary,customfield_123")

    def test_user_search_starts_at_zero(self):
        request, _ = self.run_cli(["search-users", "example", "--max-results", "3"], [])
        self.assertEqual(dict(request.url.params), {
            "username": "example", "startAt": "0", "maxResults": "3",
        })

    def test_board_project_filter(self):
        request, _ = self.run_cli(["list-boards", "--project", "TEST"], {"values": []})
        self.assertEqual(request.url.params["projectKeyOrId"], "TEST")
        self.assertEqual(request.url.path, "/rest/agile/1.0/board")

    def test_sprint_state_filter(self):
        request, _ = self.run_cli(["list-sprints", "42", "--state", "active,future"], {"values": []})
        self.assertEqual(request.url.params["state"], "active,future")
        self.assertEqual(request.url.path, "/rest/agile/1.0/board/42/sprint")

    def test_board_and_sprint_filters_are_optional(self):
        for command, param in [(["list-boards"], "projectKeyOrId"),
                               (["list-sprints", "42"], "state")]:
            with self.subTest(command=command):
                request, _ = self.run_cli(command, {"values": []})
                self.assertNotIn(param, request.url.params)

    def test_writes_require_confirmation_before_any_operation(self):
        commands = [
            ["create-issue", "--project", "TEST", "--type", "Task", "--summary", "Example"],
            ["update-issue", "TEST-1", "--fields", '{"summary":"Example"}'],
            ["add-comment", "TEST-1", "--body", "Example"],
            ["transition-issue", "TEST-1", "Done"],
            ["assign-issue", "TEST-1"],
            ["add-worklog", "TEST-1", "--time-spent", "1h"],
        ]
        for args in commands:
            with self.subTest(command=args[0]), patch.object(ops, args[0].replace("-", "_")) as operation:
                with self.assertRaisesRegex(SystemExit, "Re-run with --yes"):
                    cli.main(args)
                operation.assert_not_called()


class CreateMetadataTests(unittest.TestCase):
    def test_type_and_field_pages_include_later_required_fields(self):
        pages = [
            {"startAt": 0, "maxResults": 1, "isLast": False,
             "values": [{"id": "1", "name": "Bug"}]},
            {"startAt": 1, "maxResults": 1, "isLast": True,
             "values": [{"id": "2", "name": "Task"}]},
            {"startAt": 0, "total": 2, "values": [
                {"fieldId": "summary", "name": "Summary", "required": True}]},
            {"startAt": 1, "total": 2, "values": [
                {"key": "customfield_123", "name": "Team", "required": True,
                 "allowedValues": [{"value": "Example"}]}]},
        ]
        with patch.object(ops, "_get", side_effect=pages) as get:
            result = ops.get_create_meta("TEST", "task")
        self.assertEqual(result["required_fields"], ["summary", "customfield_123"])
        self.assertEqual(result["fields"][1]["allowed_values"], ["Example"])
        self.assertEqual([call.args[2]["startAt"] for call in get.call_args_list], [0, 1, 0, 1])
        self.assertEqual(get.call_args_list[-1].args[1], "/issue/createmeta/TEST/issuetypes/2")

    def test_unpaginated_lists_remain_supported(self):
        with patch.object(ops, "_get", side_effect=[
            [{"id": "1", "name": "Task"}],
            [{"fieldId": "summary", "required": True}],
        ]):
            result = ops.get_create_meta("TEST", "Task")
        self.assertEqual(result["required_fields"], ["summary"])

    def test_empty_last_page_and_missing_type(self):
        with patch.object(ops, "_get", return_value={"isLast": True, "values": []}):
            result = ops.get_create_meta("TEST", "Task")
        self.assertEqual(result["issue_types"], [])
        self.assertIn("No issue type", result["error"])

    def test_nonprogressing_page_fails_instead_of_looping(self):
        with patch.object(ops, "_get", return_value={"isLast": False, "values": []}):
            with self.assertRaisesRegex(RuntimeError, "pagination made no progress"):
                ops.get_create_meta("TEST")


if __name__ == "__main__":
    unittest.main()
