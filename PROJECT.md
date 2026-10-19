# Next Stop: project overview

## Idea
To-do lists fail because tasks have no *departure time*. Next Stop borrows the airport metaphor:
- a task is a **flight** with a deadline (*departs*),
- its sub-steps are **stops**, printed as tickets,
- you **board** when you start and **depart** when you finish.

Status works like a real departures board: ON TIME → CLOSING → LAST CALL → DELAYED, then BOARDING (all stops torn) and DEPARTED.

## Vocabulary
| Next Stop | Means | Field |
|---|---|---|
| Flight | a task | `name`, `line`, `departs`, `express` |
| Flight code | short id, e.g. WK104 (line prefix + number) | `flight` |
| Line | category: Gym, Work, Learn, Home, Personal | `line` |
| Stop / ticket | sub-step, optionally with its own due date | `stops`, `stop_dates` |
| Tear | mark a stop done | `set_stop done=true` |
| Board | start working on the flight | `board_flight` |
| Depart | finish; moves to the travel log | `depart_flight` |
| Task plan (Work) | done when · next step · if yes · if no · stopped at | `done_when`, `next_step`, `if_yes`, `if_no`, `stopped_at` |

## Architecture
```
 Browser (index.html) ──REST /api/*──┐
                                     ├── server.py ── data/auth.db          (users, sessions, MCP tokens: SHA-256 only)
 Claude ──MCP POST /mcp (Bearer)─────┘              └ data/users/user_<id>.db (one SQLite per user)
```
- **One file, no dependencies.** `server.py` uses only the Python standard library.
- **Per-user databases**, with daily snapshots to `backups/` (the last 30 are kept).
- **Live sync:** the page polls `/api/rev` every 15 s, so tickets Claude creates appear on their own. Edits from both sides merge by revision.
- **MCP:** stateless Streamable-HTTP with JSON responses. Authenticate with `Authorization: Bearer ns_…`, or put the token in the path `/mcp/ns_…` for connectors that can't set headers.
- **GitHub Pages edition:** `pages/build_pages.py` turns `index.html` into a browser-only build (localStorage, no accounts, no MCP).

## Use it anywhere
| Where | How |
|---|---|
| Browser, no install | GitHub Pages edition |
| Your PC / home server / VPS | `python server.py`, exposed with Tailscale Funnel, Cloudflare Tunnel or a reverse proxy |
| Claude Desktop / claude.ai / mobile | custom connector → [docs/connectors.md](docs/connectors.md) |
| Claude Code, Cursor, any MCP client | HTTP MCP with a Bearer token |

## Claude Project
The [`claude/`](claude/) folder has everything for a Claude Project: settings to fill in, the instruction block to paste, and starter prompts.

## Roadmap / open ideas
- Notes/description on flights and stops; links between tickets (parent/child); tags; a reject/cancel state
- `spread_stops` that respects working hours and weekends
- Cross-device sync for the Pages edition
- Sprint Loop in the database, with MCP tools
- OAuth for the MCP endpoint (today it uses revocable bearer tokens)
