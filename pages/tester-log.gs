/**
 * Next Stop tester log: Google Apps Script web app that writes to the Google Sheet it is attached to.
 *
 * SETUP (one time, about 3 minutes):
 *  1. Create a Google Sheet, e.g. "Next Stop testers".
 *  2. Extensions → Apps Script. Delete the sample code, paste this whole file, and Save.
 *  3. Deploy → New deployment → type "Web app".
 *       Execute as: Me
 *       Who has access: Anyone
 *     Deploy, approve the permissions, then copy the Web app URL (ends in /exec).
 *  4. Give that URL to the build: python pages/build_pages.py --log-url <URL>  (or paste it in chat).
 *
 * Tabs are created automatically:
 *   Testers  one row per tester (first seen, last seen, visits, problem reports)
 *   Events   one row per event (signin, visit, report_problem, flight_booked, flight_departed)
 */
const SECRET = 'nextstop-testers';   // must match the page; stops random junk posts

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents || '{}');
    if (d.k !== SECRET) return out({ ok: false, error: 'bad key' });
    const events = Array.isArray(d.events) ? d.events.slice(0, 200) : [d];
    const ss = SpreadsheetApp.getActiveSpreadsheet();
    const ev = sheet(ss, 'Events', ['Received', 'Event time', 'Event', 'Name', 'Email', 'Tester ID', 'Detail', 'Device', 'Build']);
    const ts = sheet(ss, 'Testers', ['Tester ID', 'Name', 'Email', 'First seen', 'Last seen', 'Visits', 'Problem reports', 'Flights booked', 'Device']);
    const lock = LockService.getScriptLock(); lock.waitLock(10000);
    try {
      const now = new Date();
      events.forEach(x => {
        const name = clip(x.name, 80), email = clip(x.email, 120), id = clip(x.tid, 40), type = clip(x.type, 40);
        ev.appendRow([now, x.at ? new Date(x.at) : now, type, name, email, id, clip(x.detail, 500), clip(x.ua, 300), clip(x.v, 30)]);
        // upsert tester summary
        const ids = ts.getRange(2, 1, Math.max(ts.getLastRow() - 1, 1), 1).getValues().map(r => r[0]);
        let row = ids.indexOf(id) + 2;
        if (row < 2) { ts.appendRow([id, name, email, now, now, 0, 0, 0, clip(x.ua, 300)]); row = ts.getLastRow(); }
        const r = ts.getRange(row, 1, 1, 9).getValues()[0];
        r[1] = name || r[1]; r[2] = email || r[2]; r[4] = now; r[8] = clip(x.ua, 300) || r[8];
        if (type === 'visit' || type === 'signin') r[5] = (+r[5] || 0) + (type === 'visit' ? 1 : 0);
        if (type === 'report_problem') r[6] = (+r[6] || 0) + 1;
        if (type === 'flight_booked') r[7] = (+r[7] || 0) + 1;
        ts.getRange(row, 1, 1, 9).setValues([r]);
      });
    } finally { lock.releaseLock(); }
    return out({ ok: true, n: events.length });
  } catch (err) {
    return out({ ok: false, error: String(err) });
  }
}
function doGet() { return out({ ok: true, service: 'next-stop tester log' }); }

function sheet(ss, name, head) {
  let s = ss.getSheetByName(name);
  if (!s) { s = ss.insertSheet(name); s.appendRow(head); s.setFrozenRows(1); s.getRange(1, 1, 1, head.length).setFontWeight('bold'); }
  return s;
}
function clip(v, n) { return String(v == null ? '' : v).slice(0, n); }
function out(o) { return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON); }
