# Project settings (copy into Claude → Projects → Create project)

| Setting | Value |
|---|---|
| **Name** | Next Stop |
| **Description** | Plan and run my tasks as flights on my Next Stop departures board, through the next-stop MCP connector. |
| **Instructions** | the contents of `project-instructions.md` (below its line) |
| **Connectors / tools** | Next Stop: on. Others: off unless you need them |
| **Knowledge (optional)** | `docs/mcp-tools.md` and `PROJECT.md` from this repo, so Claude knows the fields and vocabulary |
| **Tool permissions** | *Always allow*: list_flights, get_flight, agenda. *Ask each time*: delete_flight |

Personalise these in the instructions block:
- your **time zone** (default IST, +05:30)
- your **default line** for new flights
- your **working hours**, if you want stops dated inside them
