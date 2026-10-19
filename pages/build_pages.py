"""Build the github.io (static, browser-only) edition of Next Stop from the live index.html.

Never edits the live app. Writes everything into ../../next-stop-pages/ (the GitHub repo folder).
Each replacement is asserted, so if index.html changes shape the build fails loudly instead of shipping a broken page.
Usage:  python build_pages.py [version]
"""
import os, pathlib, re, shutil, sys, datetime

HERE = pathlib.Path(__file__).resolve().parent
SRC = HERE.parent / "index.html"
OUT = HERE.parent.parent / "next-stop-pages"
REPO = "asrgrimmi-cyber/next-stop"
args = sys.argv[1:]
LOG_FILE = HERE / "log_url.txt"
if "--log-url" in args:
    i = args.index("--log-url"); LOG_FILE.write_text(args[i + 1].strip(), encoding="utf-8"); del args[i:i + 2]
LOG_URL = LOG_FILE.read_text(encoding="utf-8").strip() if LOG_FILE.exists() else ""
VERSION = args[0] if args else datetime.datetime.now().strftime("v%Y.%m.%d-%H%M")

html = SRC.read_text(encoding="utf-8")

def sub(old, new, count=1):
    global html
    n = html.count(old)
    assert n >= 1, f"pattern not found: {old[:80]!r}"
    html = html.replace(old, new) if count == 0 else html.replace(old, new, count)

def resub(pat, new, flags=re.S):
    global html
    html, n = re.subn(pat, new, html, count=1, flags=flags)
    assert n == 1, f"regex not found: {pat[:80]!r}"

# 1. Storage: no server on github.io -> always this browser, never show the login screen.
resub(r"async function initStore\(\) \{.*?\n\}\n",
      "async function initStore() {\n  Store.offline = true;\n  return startLocal();\n}\n")
# never hit /api from the static build
resub(r"async function api\(method, path, body\) \{",
      "async function api(method, path, body) {\n  { const err = new Error('Not available in the browser-only edition'); err.status = 0; throw err; }")
sub("? 'Guest mode: your flights are saved in this browser only.'",
    "? 'Your flights are saved in this browser only. Nothing is uploaded. Use Settings → Download backup to keep a copy.'")
sub(": 'In this browser only. Sign in to an account to keep flights across devices.';",
    ": 'In this browser only (nothing is uploaded). Clearing browser data erases them, so download a backup from time to time.';")

# 1b. First use: default new flights to Personal. Work requires a DONE WHEN line, which blocked
#     first-timers who typed only a name (found in the pre-release stress test).
sub("const lr = $('#f-line-' + (pre.line || S.filter || 'W'));", "const lr = $('#f-line-' + (pre.line || S.filter || 'P'));")

# 2. Remove server-only pieces of the top bar (Sprint / Playbook / Debug links).
for page in ("sprint", "playbook", "debug"):
    resub(r'\s*<a class="icon-btn" href="/' + page + r'"[^\n]*?</a>', "")

# 3. Relative paths so it works under /next-stop/ on github.io.
sub("navigator.serviceWorker.register('/sw.js')", "navigator.serviceWorker.register('sw.js')")

# 4. Branding / SEO / no indexing of a test build.
sub("<title>Next Stop</title>",
    '<title>Next Stop · test build</title>\n<meta name="description" content="Next Stop: your to-do list as a departures board. Test build.">\n'
    '<meta name="robots" content="noindex">\n<meta name="theme-color" content="#111113">\n'
    '<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E%3Ccircle cx=%2716%27 cy=%2716%27 r=%2716%27 fill=%27%23E03A2D%27/%3E%3Cpath d=%27M8 16h16M18 10l6 6-6 6%27 stroke=%27white%27 stroke-width=%273.2%27 fill=%27none%27 stroke-linecap=%27round%27 stroke-linejoin=%27round%27/%3E%3C/svg%3E">')

# 5. Guided tour, field tips, feedback button, backup tools.
addon = (HERE / "addon.html").read_text(encoding="utf-8").replace("__VERSION__", VERSION).replace("__REPO__", REPO).replace("__LOG_URL__", LOG_URL)
sub("</body></html>", addon + "\n</body></html>")

# 6. Public repo: no customer / company names.
PRIVATE = os.environ.get("NS_PRIVATE_NAMES", "")  # e.g. "acme|internal-host" to block your own names
assert not (PRIVATE and re.search(PRIVATE, html, re.I)), "private name left in public build"

# sanity: nothing left that calls the server
assert "href=\"/sprint\"" not in html and "register('/sw.js')" not in html
leftover = re.findall(r"""['"]/(?:sprint|playbook|debug|mcp)\b""", html)
assert not leftover, leftover

# write the repo folder (keep .git if it exists)
OUT.mkdir(exist_ok=True)
for p in OUT.iterdir():
    if p.name in (".git",):
        continue
    shutil.rmtree(p) if p.is_dir() else p.unlink()
(OUT / "index.html").write_text(html, encoding="utf-8")
shutil.copy(SRC.parent / "sw.js", OUT / "sw.js")
(OUT / ".nojekyll").write_text("")
(OUT / "404.html").write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=./"><a href="./">Next Stop</a>', encoding="utf-8")
for f in ("README.md", "TESTING.md", "LICENSE"):
    if (HERE / f).exists():
        shutil.copy(HERE / f, OUT / f)
gh = OUT / ".github" / "ISSUE_TEMPLATE"; gh.mkdir(parents=True, exist_ok=True)
shutil.copy(HERE / "bug_report.md", gh / "bug_report.md")
print(f"built {VERSION} -> {OUT}  ({len(html):,} bytes)  tester log: {LOG_URL or 'NOT SET (check-ins queue in each browser)'}")
