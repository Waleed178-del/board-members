# Staged governance change

Agents cannot write into `.claude/`, `tests/` or `CLAUDE.md`. This folder holds the change, mirrored to its final paths:

- `.claude/skills/` 9 skills (3 with calculators)
- `.claude/agents/` the 5 agents with `skills:` preloaded and connector rules
- `.claude/hooks/guard_state.py` guard with MCP allowlist, connector protection, human only scripts
- `.claude/settings.json` hook covers MCP tools, enables the 3 project MCP servers
- `CLAUDE.md` adds sections 8 (Skills) and 9 (Connectors)
- `tests/test_connectors.py` 12 tests

Install: `python3 staging/install.py` in your own terminal. See `CONNECTORS.md`.
