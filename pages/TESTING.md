# Stress-test guide for testers

Thanks for testing. Plan on about 20 minutes. Use the **Report a problem** button (bottom-left of the app) for every issue. It opens a GitHub issue with your browser, screen size and recent errors already filled in. You add *what happened* and, if you can, a screenshot.

You'll need a free GitHub account to file issues. If you don't have one, send a screenshot and a one-line note to whoever sent you the link.

## 1. First use (5 min) — please do this on a fresh device or private window
- [ ] Does the welcome guide appear? Is every step clear? Does **Skip** work at every step?
- [ ] In **Book a flight**, are the *Required* and *Optional* labels clear? Can you book a flight with only a name?
- [ ] Book one flight with **Work** line, a deadline and 3+ stops (try a Route chip).
- [ ] Was anything confusing in the first minute? *That's the most useful report.*

## 2. Core loop (5 min)
- [ ] Open a flight and tear tickets by **dragging the stub right**, then by **press-and-hold**.
- [ ] **Undo** a torn ticket (toast button, or the ↺ on a torn ticket).
- [ ] Tear all tickets → boarding pass prints → tear it → flight departs.
- [ ] **Fly again**, **Edit**, **Delete** (and undo the delete).
- [ ] Platform timer (1:00) runs and chimes. Leave the flight page and check the mini timer in the top bar.
- [ ] Share image (if your device supports sharing).

## 3. Try to break it (5–10 min)
- [ ] Very long names (60+ characters), emoji 🚀, non-English text (हिंदी, 中文, عربي).
- [ ] 30+ flights on the board; 40 stops on one flight (paste a list of lines into a stop box).
- [ ] Deadline in the past, deadline next year, no deadline.
- [ ] Rotate the phone; resize the browser from phone width to very wide.
- [ ] Double-tap and spam-tap buttons; tear two tickets quickly.
- [ ] Reload mid-action; use the browser Back button; open the app in two tabs at once.
- [ ] Turn sound off/on; switch Dot ↔ Flap lettering.
- [ ] **Settings → Download backup**, then **Erase everything**, then **Restore backup**. Are all flights back?
- [ ] Private / incognito window (storage may be blocked or wiped on close).

## Devices we especially need
| | |
|---|---|
| iPhone Safari | Android Chrome |
| iPad / tablet | Windows Chrome / Edge |
| Mac Safari | A very wide monitor |

## What happens to my data?
Nothing leaves your device. Flights are stored in your browser's local storage under this site only.
