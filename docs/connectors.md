# Connect Claude (and other MCP clients)

Every connector needs the same two things: **your server's public URL and a token**.

## 1. Get a link
1. For Claude Desktop, claude.ai and mobile, your server must be reachable over **HTTPS from the internet**, because Anthropic connects from its own servers. See [self-hosting.md](self-hosting.md). `localhost` only works for Claude Code and other local clients.
2. Log in, then go to **Settings → Connect Claude → Create link**. You get:
   - **Connector URL:** `https://YOUR-HOST/mcp/ns_xxxxxxxx` (the token is inside, for apps that can't send headers)
   - **Claude Code command:** uses an `Authorization: Bearer` header
3. Treat the link like a password. Create **one link per app**, so you can revoke one without breaking the others. You can revoke links anytime on the same screen.

From the command line instead: `python server.py --make-token <username> --label "Claude Desktop"`

## 2. Claude Desktop, claude.ai web, Claude mobile
Connectors belong to your Claude account, so once you add it, it appears in all three.
1. Go to **Settings → Connectors → Add custom connector**.
2. Name it `Next Stop`, paste your connector URL as the URL, and click **Add**.
3. In a chat, open the **+ / tools** menu and make sure **Next Stop** is on.
4. The first time a tool runs, Claude asks for permission. Choose *Always allow* for the read tools (list_flights, get_flight, agenda).
5. Test it: *"what's on my board today?"*

## 3. Claude Code
```bash
claude mcp add --transport http -s user next-stop https://YOUR-HOST/mcp \
  --header "Authorization: Bearer ns_xxxxxxxx"
claude mcp list        # next-stop ✔ Connected
```
Then copy [`claude/project-instructions.md`](../claude/project-instructions.md) into your `CLAUDE.md`.

## 4. Claude Desktop without exposing your server (local bridge)
This needs Node.js. Edit `claude_desktop_config.json` (Settings → Developer → Edit config):
```json
{
  "mcpServers": {
    "next-stop": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://localhost:8080/mcp", "--header", "Authorization:Bearer ns_xxxxxxxx"]
    }
  }
}
```
Then fully quit Claude (tray → Quit) and reopen it.

## 5. Cursor / other MCP clients
```json
{ "mcpServers": { "next-stop": { "url": "https://YOUR-HOST/mcp", "headers": { "Authorization": "Bearer ns_xxxxxxxx" } } } }
```

## Troubleshooting
| Symptom | Fix |
|---|---|
| Connector fails to add, or tools fail | The server is down or the PC is asleep. Check that `https://YOUR-HOST/` opens. |
| `401` | The token was revoked or mistyped. Create a new link. |
| Works in Claude Code but not Desktop | Desktop needs a public HTTPS URL (or use the local bridge). |
| Tickets don't appear on the board | Wait 15 s or refresh, and check you're logged in as the same user. |
