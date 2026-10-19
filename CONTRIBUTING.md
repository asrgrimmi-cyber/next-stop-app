# Contributing

Thanks for helping! Small, focused PRs are easiest to review.

- **Run locally:** `python server.py --port 8081` (use a spare port and a throwaway account).
- **No dependencies:** the server stays standard-library Python, and the app stays a single `index.html`.
- **Design:** follow [playbook/DESIGN.md](playbook/DESIGN.md) (Doto, split-flap tiles, Archivo, Alfa Slab One, and the floor/sign/amber palette). Test on phone (390 px), tablet and wide screens.
- **MCP:** if you add a tool, add it to `TOOLS` and `run_tool` in `server.py` and document it in [docs/mcp-tools.md](docs/mcp-tools.md). Keep `status_of()` (Python) and `statusOf()` (JS) in sync.
- **Pages edition:** after changing `index.html`, run `python pages/build_pages.py`. It checks that its replacements still match.
- **Never commit** `data/`, `backups/`, logs or tokens.

Report bugs and ideas as GitHub issues. Please include the steps, what you expected vs what happened, and your screen size.
