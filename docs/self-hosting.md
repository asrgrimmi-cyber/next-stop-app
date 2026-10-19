# Self-hosting

## Run
```bash
python server.py --port 8080             # http://localhost:8080
python server.py --host 127.0.0.1        # local only
```
Requirements: Python 3.9+, no packages. Data is stored in `data/` (created on first run) and snapshots in `backups/`.

## Keep it running
- **Windows:** `scripts/run-next-stop.cmd` restarts the server automatically. To start it at login, edit the folder path inside `scripts/start-next-stop.vbs`, then put it in `shell:startup`.
- **Linux/macOS:** `scripts/run-next-stop.sh`, or a systemd unit:
```ini
[Service]
WorkingDirectory=/opt/next-stop
ExecStart=/usr/bin/python3 server.py --port 8080
Restart=always
```

## Make it reachable from Claude (HTTPS)
| Option | Command |
|---|---|
| Tailscale Funnel | `tailscale funnel --bg 8080` → `https://<machine>.<tailnet>.ts.net` |
| Cloudflare Tunnel | `cloudflared tunnel --url http://localhost:8080` |
| VPS + reverse proxy | Caddy: `your.domain { reverse_proxy localhost:8080 }` |

The server reads `X-Forwarded-Host/Proto`, so the links it prints use your public URL.

## Admin
```bash
python server.py --list-users
python server.py --make-token <user> --label "Claude Desktop"
python server.py --reset-password <user>
python server.py --delete-user <user>
python server.py --backup
```

## Security notes
- Passwords are hashed with PBKDF2-SHA256. Sessions and MCP tokens are stored only as SHA-256 hashes.
- Anyone who can reach the URL can sign up. For a private instance, keep it on your tailnet or put it behind your proxy's auth.
- Never commit `data/` or `backups/`. They're already in `.gitignore`.
