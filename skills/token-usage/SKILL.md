---
name: token-usage
description: DaisyDisk-style view of Claude Code token usage since the last quota reset. Shows the plan quotas and what is left, then which projects, conversations and requests used the most, as an interactive sunburst HTML page plus a text summary. Use when the user asks how much they have used, what is left, where their tokens go, which project or conversation costs the most, or types /token-usage. Everything is read locally, nothing is sent anywhere.
---

# token-usage

## What it does
- Reads the account quotas from the Claude desktop app when available (tool `mcp__ccd_session_mgmt__get_usage`, see step 1) and the local Claude Code transcripts in `~/.claude/projects` (subagents included), counting each model request once.
- Writes one self-contained HTML page, DaisyDisk style: the quota in the centre, projects on the first ring, conversations on the second, requests on the third. Hover for details, click to zoom, click the centre to go back. The three quotas and their reset times sit in the header.
- Prints the same summary as text for the chat.
- Changes nothing else. Reads only local files, sends nothing anywhere.

## Measured vs estimated (say it in one line every time)
- Measured: the app's percentages and the transcript tokens (new context, cache reads, written).
- Estimated: the "weight" (cost ratios: cache read 0.1, new context 1.25, written 5) and the window budget derived from the app's percentage. The app never gives the limit in tokens.
- Transcripts cover this machine only. Sessions on claude.ai, in the cloud or on another computer count toward the quota but are not in the rings. Say so when the gap is visible.

## Steps
1. Quotas. In the Claude desktop app, load the tool with ToolSearch ("select:mcp__ccd_session_mgmt__get_usage"), call it, and save its output verbatim to `<scratchpad>/usage.json`. In a plain terminal or in Cowork, this tool does not exist: skip it and use `--since` in step 2 (default 7 days, or `24h`, `5h`, an ISO date).
2. Run the script (about 10 s for a week of transcripts):
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/token-usage/scripts/token_usage.py --usage <scratchpad>/usage.json --window weekly --top 10 --actions 30 --html <output>/token-usage.html
```
   - `--window`: `weekly` (default, all models), `model` (the per-model weekly quota, keeps only that model's requests), `5h`.
   - Without `--usage`: `--since 7d` (or `24h`, or a date).
   - `--top N`: rows per table. `--actions N`: requests named per conversation in the third ring, the rest grouped as "N more requests" (muted segment).
   - `--project "Name"` or `--conversation 14b1dbc2`: drill down.
   - `--lang fr`: French labels. `--json <file>`: raw detail if the user wants to dig.
   - Output folder: the user's documents or project folder, one file rewritten each run (for example `~/Documents/token-usage.html`).
3. Open the page for the user (`open <file>` on macOS, `xdg-open` on Linux) and, where screenshots are possible, show one in the chat.
   In the chat: one sentence (the fullest quota, what is left, what used the most), the page path, the screenshot. Paste the text summary only if asked or if the page cannot be opened.
4. If the user asks what is left, read the most constraining quota (often the per-model weekly one), not only "all models".

## Pitfalls
- A "request" is one call to the model. The heaviest ones are almost always session or subagent startups (the initial context: system prompt, tools, memory, CLAUDE.md), marked `[startup: initial context]`. Say so rather than letting the user believe one command cost 300k.
- Windows start at "reset minus 5 h" or "minus 7 days"; a transcript file untouched since the window start is skipped (that is what keeps the script fast).
- The real savings lever is the number of subagents launched and the length of conversations, not one isolated action.
