# agent-skills-shared

Agent skills and the local CLIs behind them, usable from Claude Code, Codex, and GitHub
Copilot CLI. Each tool is a plain CLI on PATH; the skill files teach the agent how to use it.

## Tools

| Tool | What it does |
|---|---|
| [`jira`](jira/) | Staples self-hosted Jira (`jiraent.staples.com`): issues, JQL search, boards, sprints, metadata, attachments; writes gated behind `--yes` |

## Layout

```
<name>/                          tool source; entrypoint at <name>/bin/<name>
.claude/skills/<name>/SKILL.md   Claude Code skill
.codex/skills/<name>/SKILL.md    Codex skill
.github/agents/<name>.agent.md   Copilot CLI agent
```

## Setup

Requires [uv](https://docs.astral.sh/uv/) (the CLIs run through `uv run`, which creates
each tool's virtualenv on first use).

```sh
git clone https://github.com/ThePrefixCyber/agent-skills-shared.git ~/agent-skills-shared
cd ~/agent-skills-shared
```

### jira

1. Create a Personal Access Token in Jira: avatar → **Profile** → **Personal Access Tokens** →
   **Create token**.
2. Add your credentials:

   ```sh
   cp jira/.env.example jira/.env
   chmod 600 jira/.env
   # edit jira/.env and set JIRA_PAT
   ```

3. Put the CLI on PATH and check it works:

   ```sh
   mkdir -p ~/.local/bin
   ln -s "$PWD/jira/bin/jira" ~/.local/bin/jira
   jira myself
   ```

4. Link the skill into whichever agents you use:

   ```sh
   mkdir -p ~/.claude/skills ~/.codex/skills ~/.copilot/agents
   ln -s "$PWD/.claude/skills/jira" ~/.claude/skills/jira              # Claude Code
   ln -s "$PWD/.codex/skills/jira" ~/.codex/skills/jira                # Codex
   ln -s "$PWD/.github/agents/jira.agent.md" ~/.copilot/agents/        # Copilot CLI
   ```

`jira/pyproject.toml` pins uv to public PyPI, overriding a global Artifactory index (whose
package downloads return HTTP 401 without credentials). The dependencies are all public.

The skill and `jira/src/jira_tool/REFERENCE.md` assume your team's project is **FILL**. If
you're on another team, change that line in the three skill files and in `REFERENCE.md`.

Offline tests (no calls to Jira):

```sh
uv run --directory jira python -m unittest discover -s tests -v
```
