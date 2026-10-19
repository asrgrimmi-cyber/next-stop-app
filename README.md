# Next Stop ✈️

**Your to-do list as a departures board.** Every task is a *flight*, every sub-step is a *ticket* you tear, and when you finish, a boarding pass prints and the task takes off.

You can also **talk to it from Claude**. Next Stop has its own MCP server, so Claude (Desktop, web, mobile or Claude Code) can book, update and finish your tickets for you.

- 🟢 **Try it in the browser (no install):** https://asrgrimmi-cyber.github.io/next-stop/
- 🖥️ **Self-host with accounts + Claude/MCP:** one Python file, no dependencies → [docs/self-hosting.md](docs/self-hosting.md)
- 🤖 **Connect Claude:** [docs/connectors.md](docs/connectors.md)
- 📁 **Ready-made Claude Project:** [claude/](claude/)

| | |
|---|---|
| Board | Split-flap departures board, live countdowns, last-call reminders, 5 colour-coded lines (Gym, Work, Learn, Home, Personal) |
| Tickets | Stops (sub-steps) with their own due dates, tear-to-complete, boarding pass, travel log |
| Work tasks | *Done when*, *next step / hypothesis*, *if yes / if no*, *stopped at* |
| Share | Image card with a QR code → WhatsApp / Instagram |
| Claude | 10 MCP tools: list, get, book, update, add stops, tick stops, board, depart, delete, agenda |
| Extras | Sprint Loop game (`/sprint`), debug-plan page (`/debug`), brand playbook (`/playbook`) |

## Quick start (self-hosted)
```bash
git clone https://github.com/asrgrimmi-cyber/next-stop-app.git
cd next-stop-app
python server.py --port 8080          # Python 3.9+, standard library only
```
Open http://localhost:8080, create an account, then go to **Settings → Connect Claude → Create link**.

## How Claude uses it
```
You:    "Work flight: renew the customer licence, due Monday 5 pm, done when it's emailed.
         Steps: check expiry, generate licence, send it."
Claude: book_flight(...)  →  WK104 · Renew customer licence · Mon 17:00 · 3 stops
Board:  the ticket appears on your board within 15 seconds
```
See [PROJECT.md](PROJECT.md) for the full picture and [docs/mcp-tools.md](docs/mcp-tools.md) for every tool and field.

## Repository layout
```
server.py              accounts, per-user SQLite, REST API, MCP endpoint (stdlib only)
index.html             the app (single file: HTML + CSS + JS)
sprint.html            Sprint Loop game          debug.html   debug-plan page
sw.js                  service worker (last-call notifications)
playbook/              design system: DESIGN.md, playbook page, slide template
pages/                 build script for the browser-only GitHub Pages edition
claude/                Claude Project: settings + instructions to paste
docs/                  connectors, self-hosting, MCP tools, privacy
scripts/               run/auto-restart helpers (Windows + Linux/macOS)
```

## Contributing
Issues and PRs are welcome; see [CONTRIBUTING.md](CONTRIBUTING.md). MIT licensed.
