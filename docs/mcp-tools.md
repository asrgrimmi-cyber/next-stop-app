# MCP tools

Endpoint: `POST /mcp` (JSON-RPC 2.0, Streamable HTTP, JSON responses). The server name is `next-stop`.
Times are ISO 8601. A time without an offset is read as the server's local time zone.

| Tool | What it does | Key arguments |
|---|---|---|
| `list_flights` | list flights with their status | `include` upcoming/departed/all, `line` |
| `get_flight` | full detail, including stops and task plan | `flight` (id, code like WK104, or part of the name) |
| `book_flight` | create a flight | see below |
| `update_flight` | change fields; `departs:"none"` clears the deadline | `flight` + any field, `stopped_at` |
| `add_stops` | add stops to the end | `flight`, `stops`, `stop_dates` |
| `set_stop` | tear or undo a stop, rename it, change its date | `flight`, `stop` (id, number or name), `done`, `name`, `due` |
| `board_flight` | mark as started (stops last-call reminders) | `flight` |
| `depart_flight` | finish (`force` also tears any open stops) | `flight`, `force` |
| `delete_flight` | delete permanently | `flight` |
| `agenda` | what's due in the next N days, stop by stop | `days` 1–60 |

## book_flight fields
| Field | Required | Notes |
|---|---|---|
| `name` | ✓ | short, starts with the action |
| `line` | | Gym, Work, Learn, Home, Personal (default Work) |
| `departs` | | deadline, e.g. `2026-10-22T19:00` |
| `stops` | | sub-steps in order |
| `stop_dates` | | ISO date per stop, in the same order |
| `spread_stops` | | date the stops evenly up to the deadline |
| `express` | | priority; boards first |
| `done_when` | recommended for Work | what finished looks like |
| `next_step` | | hypothesis / first move |
| `if_yes`, `if_no` | | what to do if the hypothesis holds / fails |

## Example
```json
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"book_flight","arguments":{
  "name":"Film and post the demo Reel","line":"Work","departs":"2026-10-22T19:00",
  "stops":["Record screen flow","Generate avatar video","Edit + captions","Set up auto-DM","Post + pin comment"],
  "spread_stops":true,"done_when":"Reel is live and comments get the link by DM"}}}
```
This returns the flight (e.g. `WK118`, status `ON TIME`) with every stop and its due date.

Quick test with curl:
```bash
curl -s https://YOUR-HOST/mcp -H "Authorization: Bearer ns_xxx" -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```
