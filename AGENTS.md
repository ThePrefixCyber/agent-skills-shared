# Agent Skills (shared)

Skills and the local CLIs behind them, for Codex, Claude Code, and GitHub Copilot CLI.

## Layout

Each tool's code lives in `<name>/`, with its entrypoint at `<name>/bin/<name>`. Tools are
plain CLIs on PATH, not MCP servers.

Maintain parallel skill definitions in all three places:

| Surface | Path |
|---|---|
| Codex | `.codex/skills/<name>/SKILL.md` |
| Claude Code | `.claude/skills/<name>/SKILL.md` |
| Copilot CLI | `.github/agents/<name>.agent.md` |

When creating or updating skills, update all three surfaces unless the change is explicitly
scoped to one tool. Add each new tool to the table in `README.md`.

## Secrets

Credentials live in each tool's gitignored `.env`; commit only `.env.example`. Never print
tokens or authorization headers. This repo is public: no credentials, tokens, or personal data.
