#!/usr/bin/env python3
"""gmconfig.py — set up a Great Migration digitization appointment.

Replaces the legacy `gmconfig` (Pashua-based, no longer functional) and
`makegm` (bash, tightly coupled to gmconfig) pair. Captures session details
via an HTML form in the browser (or CLI fallback), writes session.json
inside the new session directory, and creates the per-format
ACCESS/PRESERVATION/notes structure.

Modes:
    gmconfig.py                          open form, save config, create dirs
    gmconfig.py --config-only            open form, save config, skip dirs
    gmconfig.py --from-config PATH       skip form, read session.json, create dirs
    gmconfig.py --cli                    terminal prompts fallback (no browser)
"""
from __future__ import annotations

import argparse
import base64
import html
import http.server
import json
import re
import subprocess
import tempfile
import sys
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from common import get_logger, install_sigterm_trap  # noqa: E402

log = get_logger()


# --- Constants -----------------------------------------------------------------

SCHEMA_VERSION = 2
ET = ZoneInfo("America/New_York")


class SessionExistsError(Exception):
    """Raised when the target session dir already has content and --force wasn't given."""


@dataclass(frozen=True)
class Format:
    """One archival format the team digitizes. The legacy makegm script defined
    these inline; we keep the same folder names and notes-file slugs for output
    compatibility with anything that already references the old structure."""
    id: str            # canonical identifier (stable across versions)
    label: str         # human-readable name shown in the form
    folder: str        # subdirectory created under the session dir
    slug: str          # used in the notes filename (folder != slug for V8 only)
    media_type: str    # "film" or "tape" — drives template verb choice
    description: str   # used in the notes-file template (e.g. "35mm films")


FORMATS: list[Format] = [
    Format("35mm",                       "35mm",                                  "35mm",                "35mm",                "film", "35mm films"),
    Format("16mm",                       "16mm",                                  "16mm",                "16mm",                "film", "16mm films"),
    Format("R8",                         "Regular 8mm (R8)",                      "Regular8mm",          "Regular8mm",          "film", "Regular 8mm films"),
    Format("S8",                         "Super 8 (S8)",                          "Super8",              "Super8",              "film", "Super 8 films"),
    Format("VHS",                        "VHS",                                   "VHS",                 "VHS",                 "tape", "VHS tapes"),
    Format("MiniDV",                     "MiniDV",                                "MiniDV",              "MiniDV",              "tape", "MiniDV tapes"),
    Format("V8",                         "Video8 (V8)",                           "Video8",              "V8",                  "tape", "Video8 tapes"),
    Format("Hi8",                        "Hi8",                                   "Hi8",                 "Hi8",                 "tape", "Hi8 tapes"),
    Format("D8",                         "Digital8 (D8)",                         "Digital8",            "Digital8",            "tape", "Digital8 tapes"),
    Format("U-matic",                    "U-matic",                               "Umatic",              "Umatic",              "tape", "U-matic tapes"),
    Format("Betacam",                    "Betacam (Beta)",                        "Betacam",             "Betacam",             "tape", "Betacam tapes"),
    Format("BetacamSP",                  "BetacamSP (BetaSP)",                    "BetacamSP",           "BetacamSP",           "tape", "BetacamSP tapes"),
    Format("DigiBeta",                   "Digital Betacam (DigiBeta)",            "DigiBeta",            "DigiBeta",            "tape", "Digital Betacam tapes"),
    Format("OneInchVideo",               '1" Video (TypeC)',                      "OneInchVideo",        "OneInchVideo",        "tape", "1-inch Video tapes"),
    Format("HalfInchVideo",              '1/2" Open-Reel Video (EIAJ)',           "HalfInchVideo",       "HalfInchVideo",       "tape", "1/2-inch Video tapes"),
    Format("CompactAudioCassette",       "Compact Audio Cassette (CAC)",          "AudioCassette",       "AudioCassette",       "tape", "Compact Audio Cassette tapes"),
    Format("QuarterInchOpenReelAudio",   '1/4" Reel-To-Reel Audio (QinA)',        "QuarterInchOpenReel", "QuarterInchOpenReel", "tape", "1/4-inch open reel tapes"),
]

FORMATS_BY_ID: dict[str, Format] = {f.id: f for f in FORMATS}

# Notes templates — match the wording of the legacy makegm script so the
# resulting text is the same as what the team was producing before.
GENERAL_NOTES_TEMPLATE = (
    "These are general notes concerning the appointment of {first} {last} on {date}. "
    "They were written by the TBM preservationist, {operator}, and contain observations about the "
    "appointment and information relayed by {first} {last}.\n"
)

FORMAT_NOTES_TEMPLATE = (
    "These are notes concerning the {description} of {first} {last} which were "
    "{verb_past} on {date} by the TBM preservationist {operator}. They cover technical and "
    "preservation concerns of the {medium}, noted by the TBM preservationist at the time of "
    "initial inspection and {verb_noun}, not content of the {medium}.\n"
)

VERB_PAST = {"film": "scanned", "tape": "digitized"}
VERB_NOUN = {"film": "scanning", "tape": "digitization"}
MEDIUM    = {"film": "films",   "tape": "tapes"}


# --- Session data + filesystem actions -----------------------------------------

def now_local_iso() -> str:
    """ISO-8601 timestamp in the local (ET) zone with offset."""
    return datetime.now(ET).isoformat(timespec="seconds")


def date_iso() -> str:
    """YYYYMMDD — matches the legacy DATE_ISO from makegm."""
    return datetime.now(ET).strftime("%Y%m%d")


def date_hyphen() -> str:
    """YYYY-MM-DD — matches the legacy DATE_HYPHEN from makegm."""
    return datetime.now(ET).strftime("%Y-%m-%d")


def build_session(form: dict) -> dict:
    """Assemble the session.json structure from form data."""
    gm_dir = Path(form["gm_dir"]).expanduser().resolve()
    # appointment_date is supplied by the form (HTML5 date input) or CLI prompt.
    # Defaulting happened upstream (render_form / run_cli_form); validate() has
    # already confirmed the YYYY-MM-DD shape before we get here.
    appointment_date = form.get("appointment_date") or date_hyphen()
    sub = f"{appointment_date.replace('-', '')}_{form['last']}_{form['first']}"
    session_dir = gm_dir / sub
    selected = [FORMATS_BY_ID[fid] for fid in form["formats"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "created": now_local_iso(),
        "appointment_date": appointment_date,
        "operator": form["operator"],
        "profile": {
            "first": form["first"],
            "last": form["last"],
        },
        "study_collection_number": form["study_collection_number"],
        "formats": [{"id": f.id, "folder": f.folder} for f in selected],
        "gm_dir": str(gm_dir),
        "session_dir": str(session_dir),
    }


def create_session_dirs(
    session: dict,
    *,
    created_files: list[Path] | None = None,
    created_dirs: list[Path] | None = None,
) -> list[Path]:
    """Create per-format ACCESS/PRESERVATION subdirs + notes files.

    If `created_files` and `created_dirs` are provided, they are appended to
    after every successful mkdir / write_text — so if any step raises mid-way,
    the caller has an accurate record of partial state for rollback. (Without
    this, the returned list would be inaccessible to the caller when the
    function raised before returning.) Each format's container dir
    (e.g. 35mm/) is mkdir'd explicitly so it's tracked too — previously
    mkdir(parents=True) on the ACCESS subdir would create it implicitly,
    leaving an orphan empty dir on rollback in the --force merge case.

    Returns the combined list of newly-created paths (for the legacy
    single-list caller signature; unused by the rollback-aware caller)."""
    if created_files is None:
        created_files = []
    if created_dirs is None:
        created_dirs = []
    session_dir = Path(session["session_dir"])
    profile = session["profile"]
    first, last = profile["first"], profile["last"]
    operator = session["operator"]
    # Pin filename dates to what the session was built with so --from-config on a
    # later day, or a form left open across midnight, doesn't produce note files
    # named with a different date than the session dir.
    d_hyphen = session["appointment_date"]
    d_iso = d_hyphen.replace("-", "")

    # General notes file for the whole appointment.
    general_notes = session_dir / f"{d_iso}_{last}_{first}_generalNotes.txt"
    if not general_notes.exists():
        general_notes.write_text(GENERAL_NOTES_TEMPLATE.format(
            first=first, last=last, date=d_hyphen, operator=operator,
        ))
        created_files.append(general_notes)

    # Per-format subdirectories + notes.
    for f_entry in session["formats"]:
        fmt = FORMATS_BY_ID[f_entry["id"]]
        fdir = session_dir / fmt.folder
        if not fdir.exists():
            fdir.mkdir()
            created_dirs.append(fdir)
        for sub in ("ACCESS", "PRESERVATION"):
            d = fdir / sub
            if not d.exists():
                d.mkdir()
                created_dirs.append(d)
        notes = fdir / f"{d_iso}_{last}_{first}_{fmt.slug}_Notes.txt"
        if not notes.exists():
            notes.write_text(FORMAT_NOTES_TEMPLATE.format(
                description=fmt.description,
                first=first, last=last,
                verb_past=VERB_PAST[fmt.media_type],
                verb_noun=VERB_NOUN[fmt.media_type],
                date=d_hyphen,
                operator=operator,
                medium=MEDIUM[fmt.media_type],
            ))
            created_files.append(notes)
    return created_files + created_dirs


# --- Validation ----------------------------------------------------------------

_UNSAFE_NAME_CHARS = ("/", "\\", "\x00")

# Strict ISO-date pattern. `datetime.strptime("2026-5-18", "%Y-%m-%d")` accepts
# 1-digit month/day, which after `.replace("-", "")` produces a 7-digit dir
# prefix (e.g. "2026518") that breaks the YYYYMMDD convention. We also need the
# exact shape for --from-config safety: a hand-edited appointment_date like
# "../outside" is dash-stripped to "../outside" (no dashes to remove), then
# baked into a filename via session_dir / f"{d_iso}_..." — Python's Path
# operator interprets the slash as a separator and writes outside session_dir.
_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _is_valid_iso_date(s: str) -> bool:
    """True if `s` matches YYYY-MM-DD exactly AND is a real calendar date."""
    if not _ISO_DATE_RE.match(s):
        return False
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _is_own_artifact(p: Path) -> bool:
    """True if `p` is one of gmconfig's own files in session_dir: the canonical
    session.json or a uniquely-named staging temp file (session.json.<rand>.tmp).
    Used to keep the documented --config-only -> --from-config workflow from
    tripping the "session_dir has content" guard on its own session.json, and
    to ignore stale tmps from a previous crashed run."""
    name = p.name
    return name == "session.json" or (
        name.startswith("session.json.") and name.endswith(".tmp")
    )


def validate(form: dict) -> list[str]:
    """Return a list of error messages; empty list means form is valid."""
    errors: list[str] = []
    for required in ("first", "last", "operator", "appointment_date",
                     "study_collection_number", "gm_dir"):
        if not form.get(required, "").strip():
            errors.append(f"{required} is required.")
    # `first` and `last` get baked into a path segment ({date}_{last}_{first}); reject
    # characters that would let a typo escape the chosen output directory.
    for name_field in ("first", "last"):
        v = form.get(name_field, "")
        if v and (v == ".." or any(c in v for c in _UNSAFE_NAME_CHARS)):
            errors.append(f"{name_field} contains invalid characters (no slashes or '..').")
    # Appointment date must match YYYY-MM-DD exactly. HTML5 <input type="date">
    # always supplies this shape, but CLI prompts and direct API misuse can not.
    # Lenient parsing (e.g. "2026-5-18") would produce a 7-digit dir prefix and,
    # if the field were ever populated with a slash, escape the session dir via
    # the notes filename.
    d = form.get("appointment_date", "").strip()
    if d and not _is_valid_iso_date(d):
        errors.append(f"appointment_date must be YYYY-MM-DD (got: {d!r})")
    fmts = form.get("formats", [])
    if not fmts:
        errors.append("At least one format must be selected.")
    else:
        unknown = [fid for fid in fmts if fid not in FORMATS_BY_ID]
        if unknown:
            errors.append(f"Unknown format ids: {', '.join(unknown)}")
    gd = form.get("gm_dir", "").strip()
    if gd:
        p = Path(gd).expanduser()
        if not p.exists():
            errors.append(f"GM_DIR does not exist: {p}")
        elif not p.is_dir():
            errors.append(f"GM_DIR is not a directory: {p}")
    return errors


# --- HTML form -----------------------------------------------------------------

def _load_logo_data_uri() -> str:
    """Read tools/assets/nmaahc_logo.png and return it as a data: URI, or empty
    string if the file is missing. Embedded inline so the form is self-contained."""
    p = Path(__file__).resolve().parent / "assets" / "nmaahc_logo.png"
    if not p.exists():
        return ""
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode("ascii")


LOGO_DATA_URI = _load_logo_data_uri()
LOGO_HTML = (
    f'<div class="logo-bar"><img src="{LOGO_DATA_URI}" '
    f'alt="National Museum of African American History &amp; Culture / Smithsonian"></div>'
    if LOGO_DATA_URI else ""
)


# CSS + form HTML. Doubled braces escape Python's str.format substitution.
FORM_HTML = """\
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Great Migration appointment setup</title>
<style>
:root {{
  --fg: #222; --muted: #666; --bg: #582C83; --card: #fff;
  --border: #ccc; --accent: #582C83; --err: #c0392b; --errbg: #fdecea;
}}
body {{
  font-family: -apple-system, system-ui, "Helvetica Neue", sans-serif;
  color: #fff; background: var(--bg);
  max-width: 760px; margin: 2em auto; padding: 0 1em; line-height: 1.4;
}}
h1 {{ margin-top: 0; color: #fff; }}
.logo-bar {{ background: #fff; padding: 0.8em 1em; border-radius: 6px;
            text-align: center; margin: 0 0 1.5em; }}
.logo-bar img {{ max-width: 420px; width: 100%; height: auto; }}
fieldset {{
  margin: 1em 0; padding: 1em 1.2em; border: 1px solid var(--border);
  border-radius: 6px; background: var(--card); color: var(--fg);
}}
legend {{ font-weight: bold; padding: 0.1em 0.5em; color: var(--fg);
         background: var(--card); border: 1px solid var(--border); border-radius: 4px; }}
label {{ display: block; margin: 0.6em 0; }}
label > span {{ display: block; margin-bottom: 0.2em; }}
input[type=text] {{
  width: 100%; padding: 0.45em 0.6em; border: 1px solid var(--border);
  border-radius: 4px; box-sizing: border-box; font: inherit;
}}
.row {{ display: flex; gap: 0.6em; align-items: stretch; }}
.row > input {{ flex: 1; }}
.row > button {{ flex: 0 0 auto; }}
.formats {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.4em 1.2em; }}
.formats label {{ display: flex; align-items: center; gap: 0.5em; margin: 0; cursor: pointer; }}
.helptext {{ color: var(--muted); font-size: 0.88em; margin-top: 0.3em; }}
.errors {{
  background: var(--errbg); border: 1px solid var(--err);
  color: var(--err); padding: 0.6em 0.9em; border-radius: 4px;
  margin-bottom: 1em;
}}
.errors ul {{ margin: 0.3em 0 0 1.2em; }}
button {{
  padding: 0.6em 1.4em; font-size: 1em; border-radius: 4px; border: 0;
  cursor: pointer; background: var(--accent); color: white;
}}
button.browse {{ padding: 0.45em 0.9em; background: #eee; color: var(--fg); border: 1px solid var(--border); }}
button.abort {{ background: var(--err); }}
button[type="submit"] {{ background: #2e8b57; }}
.actions {{ display: flex; gap: 0.6em; align-items: center; margin-top: 0.5em; }}
button:hover {{ opacity: 0.9; }}
.namecheck {{ font-family: ui-monospace, monospace; color: var(--muted); font-size: 0.88em; margin-top: 0.3em; }}
</style>
</head>
<body>
{logo_html}
<h1>Great Migration appointment</h1>
<p>Fill out the fields below to set up a new digitization session. A new directory
will be created under your selected output location, named after today's date and the
profile's last and first names.</p>

{errors_html}

<form method="POST" action="/submit">

  <fieldset>
    <legend>Appointment</legend>
    <label><span>Last name of Great Migration appointment *</span><input type="text" name="last" value="{last}" required></label>
    <label><span>First name of Great Migration appointment *</span><input type="text" name="first" value="{first}" required></label>
    <label><span>Name of the TBM preservationist running the appointment *</span><input type="text" name="operator" value="{operator}" required></label>
    <label>
      <span>Date of the drop-off appointment *</span>
      <input type="date" name="appointment_date" value="{appointment_date}" required>
      <div class="helptext">Defaults to today. Change this if you're setting up an appointment based on a different date. The date drives both the session directory name and the dates written into the notes files.</div>
    </label>
    <label>
      <span>Study collection number *</span>
      <input type="text" name="study_collection_number" value="{scn}" placeholder="SC.0001" required>
      <div class="helptext">Default is <code>SC.0001</code> — only change this if the study collection number is something else.</div>
    </label>
  </fieldset>

  <fieldset>
    <legend>Output directory</legend>
    <label>
      <span>Great Migration root directory *</span>
      <div class="row">
        <input type="text" name="gm_dir" id="gm_dir" value="{gm_dir}" required placeholder="/Volumes/...">
        <button type="button" class="browse" onclick="browseDir()">Browse…</button>
      </div>
      <div class="helptext">A subdirectory named <code><span id="dir_preview">YYYYMMDD_LastName_FirstName</span>/</code> will be created here (date is taken from the appointment-date field above).</div>
    </label>
  </fieldset>

  <fieldset>
    <legend>Formats to digitize this session *</legend>
    <div class="formats">
      {format_checkboxes}
    </div>
    <div class="helptext">Each selected format gets an <code>ACCESS/</code> + <code>PRESERVATION/</code>
    pair and a pre-filled <code>&lt;format&gt;_Notes.txt</code> for the TBM preservationist to expound upon.</div>
  </fieldset>

  <div class="actions">
    <button type="submit">Create session</button>
    <button type="button" class="abort" onclick="abortSession()">Abort</button>
  </div>
</form>

<script>
async function browseDir() {{
  try {{
    const r = await fetch('/pick_dir');
    if (!r.ok) throw new Error('server returned ' + r.status);
    const j = await r.json();
    if (j.path) document.getElementById('gm_dir').value = j.path;
  }} catch (e) {{
    alert('Browse failed: ' + e + '\\nType or paste the directory path instead.');
  }}
}}

async function abortSession() {{
  if (!confirm('Abort? Nothing will be created and you will return to the terminal.')) return;
  try {{
    const r = await fetch('/abort', {{method: 'POST'}});
    const txt = await r.text();
    document.open();
    document.write(txt);
    document.close();
  }} catch (e) {{
    document.body.innerHTML = '<h1 style="color:#e0e0e0;background:#15151a;padding:1em;">Aborted — you can close this tab.</h1>';
    document.body.style.background = '#15151a';
  }}
}}

// Live-update the directory-preview helptext as the user types/picks values.
function updateDirPreview() {{
  const d = document.querySelector('input[name="appointment_date"]').value;
  const last = document.querySelector('input[name="last"]').value;
  const first = document.querySelector('input[name="first"]').value;
  const datePart = d ? d.replaceAll('-', '') : 'YYYYMMDD';
  const lastPart = last || 'LastName';
  const firstPart = first || 'FirstName';
  document.getElementById('dir_preview').textContent =
    `${{datePart}}_${{lastPart}}_${{firstPart}}`;
}}
['appointment_date', 'last', 'first'].forEach(name => {{
  const el = document.querySelector(`input[name="${{name}}"]`);
  if (el) el.addEventListener('input', updateDirPreview);
}});
updateDirPreview();
</script>

</body>
</html>
"""


SUCCESS_HTML = """\
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Session created — {sessions_count} so far</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 760px;
       margin: 2em auto; padding: 0 1em;
       background: #15151a; color: #e0e0e0; }}
.ok {{ background: #1c2e1f; border: 1px solid #3a7a4a;
      color: #c5e2cc; padding: 1em; border-radius: 6px; }}
.ok h1 {{ color: #d5e8d8; margin-top: 0; }}
.ok strong {{ color: #e8f5e8; }}
.runcount {{ color: #98c0a3; font-size: 0.9em; margin-top: 0.6em; }}
h3 {{ color: #d0d0d0; }}
code {{ font-family: ui-monospace, monospace; background: #2a2a30;
       color: #e8e8e8; padding: 1px 4px; border-radius: 3px; }}
pre {{ background: #1f1f24; color: #e0e0e0; padding: 1em;
      border-radius: 4px; overflow-x: auto; }}
.actions {{ display: flex; gap: 0.6em; margin-top: 1em; flex-wrap: wrap; }}
button, .btnlink {{
  padding: 0.6em 1.4em; font-size: 1em; border-radius: 4px; border: 0;
  cursor: pointer; color: white; text-decoration: none; display: inline-block;
}}
.btnlink {{ background: #2e8b57; }}
button.done {{ background: #582C83; }}
button:hover, .btnlink:hover {{ opacity: 0.9; }}
.fallback {{ color: #888; font-size: 0.9em; margin-top: 0.6em; }}
kbd {{ background: #2a2a30; border: 1px solid #444; padding: 1px 5px;
      border-radius: 3px; font-family: ui-monospace, monospace;
      font-size: 0.85em; color: #e0e0e0; }}
</style>
</head>
<body>
<div class="ok">
<h1>Session created</h1>
<p>Created session for <strong>{first} {last}</strong> at:</p>
<p><code>{session_dir}</code></p>
<p class="runcount">{sessions_count} session{sessions_plural} created in this run.</p>
<div class="actions">
  <a class="btnlink" href="/?next=1">Create another appointment</a>
  <button class="done" onclick="finish()">Done</button>
</div>
</div>
<h3>session.json:</h3>
<pre>{session_json}</pre>
<script>
async function finish() {{
  try {{
    const r = await fetch('/done', {{method: 'POST'}});
    const txt = await r.text();
    document.open();
    document.write(txt);
    document.close();
  }} catch (e) {{
    document.body.innerHTML = '<h1 style="color:#e0e0e0;background:#15151a;padding:1em;">Done — you can close this tab.</h1>';
    document.body.style.background = '#15151a';
  }}
}}
</script>
</body>
</html>
"""


# Final page shown when the user clicks "Done" after one or more sessions. Uses
# .format() — doubled braces escape CSS.
DONE_HTML = """\
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Finished — {count} session{plural} created</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 760px;
       margin: 2em auto; padding: 0 1em;
       background: #15151a; color: #e0e0e0; }}
.done {{ background: #1c2e1f; border: 1px solid #3a7a4a;
        color: #c5e2cc; padding: 1em; border-radius: 6px; }}
.done h1 {{ color: #d5e8d8; margin-top: 0; }}
ol {{ margin: 0.5em 0 0 1.4em; padding: 0; }}
li {{ margin-bottom: 0.4em; }}
code {{ font-family: ui-monospace, monospace; background: #2a2a30;
       color: #e8e8e8; padding: 1px 4px; border-radius: 3px; }}
.fallback {{ color: #888; font-size: 0.9em; margin-top: 0.6em; }}
kbd {{ background: #2a2a30; border: 1px solid #444; padding: 1px 5px;
      border-radius: 3px; font-family: ui-monospace, monospace;
      font-size: 0.85em; color: #e0e0e0; }}
button {{ padding: 0.6em 1.4em; font-size: 1em; border-radius: 4px; border: 0;
         cursor: pointer; background: #582C83; color: white; margin-top: 0.8em; }}
button:hover {{ opacity: 0.9; }}
</style>
</head>
<body>
<div class="done">
<h1>Finished</h1>
<p>Created {count} session{plural} in this run. The script has exited; you can
close this tab and return to your terminal.</p>
<ol>
{session_items}
</ol>
<button onclick="exitNow()">Close tab</button>
<p id="fallback" class="fallback" style="display:none;">
  Your browser blocked auto-close. Press <kbd>⌘W</kbd> to close this tab.
</p>
</div>
<script>
function exitNow() {{
  window.close();
  setTimeout(function() {{
    document.getElementById('fallback').style.display = 'block';
  }}, 300);
}}
</script>
</body>
</html>
"""


# No format placeholders, so single braces in the CSS are fine.
ABORT_HTML = """\
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Session aborted</title>
<style>
body { font-family: -apple-system, system-ui, sans-serif; max-width: 760px;
       margin: 2em auto; padding: 0 1em;
       background: #15151a; color: #e0e0e0; }
.aborted { background: #2a2026; border: 1px solid #6a4a55;
          color: #d8c0c8; padding: 1em; border-radius: 6px; }
.aborted h1 { color: #ebcad2; margin-top: 0; }
button { padding: 0.6em 1.4em; font-size: 1em; border-radius: 4px; border: 0;
         cursor: pointer; background: #582C83; color: white; margin-top: 0.8em; }
button:hover { opacity: 0.9; }
.fallback { color: #888; font-size: 0.9em; margin-top: 0.6em; }
kbd { background: #2a2a30; border: 1px solid #444; padding: 1px 5px;
      border-radius: 3px; font-family: ui-monospace, monospace;
      font-size: 0.85em; color: #e0e0e0; }
</style>
</head>
<body>
<div class="aborted">
<h1>Aborted</h1>
<p>The script has exited. Any sessions you already created in this run remain
on disk; only the form you were filling out has been discarded. You can close
this tab and return to your terminal.</p>
<button onclick="exitNow()">Exit</button>
<p id="fallback" class="fallback" style="display:none;">
  Your browser blocked auto-close. Press <kbd>⌘W</kbd> to close this tab.
</p>
</div>
<script>
function exitNow() {
  window.close();
  setTimeout(function() {
    document.getElementById('fallback').style.display = 'block';
  }, 300);
}
</script>
</body>
</html>
"""


# Rendered when filesystem work in do_POST fails. Uses single braces (no .format
# placeholders here) — the message is substituted by render_error() with f-string.
ERROR_HTML_TEMPLATE = """\
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Session creation failed</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 760px;
       margin: 2em auto; padding: 0 1em;
       background: #15151a; color: #e0e0e0; }}
.err {{ background: #2e1a1a; border: 1px solid #8a4a4a;
       color: #e8c5c5; padding: 1em; border-radius: 6px; }}
.err h1 {{ color: #f0d5d5; margin-top: 0; }}
pre {{ background: #1f1f24; color: #e0e0e0; padding: 1em;
      border-radius: 4px; overflow-x: auto; }}
</style>
</head>
<body>
<div class="err">
<h1>Session creation failed</h1>
<p>The form was valid, but writing the session to disk failed. The wrapper
attempted to roll back any partial writes so a fresh retry should work; if it
doesn't, inspect the target directory and either delete it or pass
<code>--force</code> on the next attempt. Error detail:</p>
<pre>{message}</pre>
</div>
</body>
</html>
"""


def render_error(message: str) -> str:
    return ERROR_HTML_TEMPLATE.format(message=html.escape(message))


def render_form(defaults: dict, errors: list[str] | None = None) -> str:
    """Render the HTML form, optionally with errors shown above it."""
    errors_html = ""
    if errors:
        items = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
        errors_html = f'<div class="errors"><strong>Please fix:</strong><ul>{items}</ul></div>'

    selected = set(defaults.get("formats", []))
    checkboxes = []
    for f in FORMATS:
        checked = " checked" if f.id in selected else ""
        checkboxes.append(
            f'<label><input type="checkbox" name="fmt_{f.id}" value="1"{checked}>'
            f'<span>{f.label}</span></label>'
        )
    format_checkboxes = "\n".join(checkboxes)

    return FORM_HTML.format(
        logo_html=LOGO_HTML,
        errors_html=errors_html,
        last=html.escape(defaults.get("last", "")),
        first=html.escape(defaults.get("first", "")),
        operator=html.escape(defaults.get("operator", "")),
        appointment_date=html.escape(defaults.get("appointment_date", date_hyphen())),
        scn=html.escape(defaults.get("study_collection_number", "SC.0001")),
        gm_dir=html.escape(defaults.get("gm_dir", "")),
        format_checkboxes=format_checkboxes,
    )


def render_success(session: dict, sessions_count: int) -> str:
    return SUCCESS_HTML.format(
        first=html.escape(session["profile"]["first"]),
        last=html.escape(session["profile"]["last"]),
        session_dir=html.escape(session["session_dir"]),
        session_json=html.escape(json.dumps(session, indent=2)),
        sessions_count=sessions_count,
        sessions_plural="" if sessions_count == 1 else "s",
    )


def render_done(sessions: list[dict]) -> str:
    """Final summary page shown when the user clicks Done after one or more
    successful submissions. Lists every session created in this run."""
    count = len(sessions)
    items_html = "\n".join(
        f'<li><strong>{html.escape(s["profile"]["first"])} '
        f'{html.escape(s["profile"]["last"])}</strong> — '
        f'<code>{html.escape(s["session_dir"])}</code></li>'
        for s in sessions
    )
    return DONE_HTML.format(
        count=count,
        plural="" if count == 1 else "s",
        session_items=items_html,
    )


# --- HTTP server ---------------------------------------------------------------

class _FormHandler(http.server.BaseHTTPRequestHandler):
    """Serves the form, handles directory-picker bridge, captures submissions.

    Multi-session lifecycle: a successful /submit creates the session on disk and
    appends it to `sessions_created`, but does NOT signal the exit event — the
    server stays up so the user can click "Create another appointment" (which
    hits GET /?next=1 and pre-fills the form from `last_session`) or "Done"
    (which POSTs /done, shows the final summary, and signals exit)."""

    # Class-level shared state — set by run_form_server() before serving.
    submission_event: threading.Event | None = None
    aborted: bool = False
    done: bool = False
    creation_error: str | None = None
    create_dirs: bool = True
    force: bool = False
    last_session: dict | None = None       # for ?next=1 form pre-fill
    sessions_created: list[dict] = []      # for the Done summary

    def log_message(self, format, *args):  # noqa: A002 — match BaseHTTPRequestHandler signature
        # Quiet — don't spam stderr with one line per request.
        pass

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _carryover_defaults(self) -> dict:
        """Fields to pre-fill from last_session when the user clicks
        'Create another appointment'. Carries over the per-day context
        (operator, scn, gm_dir, date) and clears the per-person fields
        (first, last, formats)."""
        ls = _FormHandler.last_session
        if not ls:
            return {}
        return {
            "operator": ls.get("operator", ""),
            "study_collection_number": ls.get("study_collection_number", ""),
            "gm_dir": ls.get("gm_dir", ""),
            "appointment_date": ls.get("appointment_date", ""),
        }

    def do_GET(self):  # noqa: N802 — http.server naming
        if self.path == "/pick_dir":
            self._handle_pick_dir()
            return
        if self.path == "/" or self.path.startswith("/?"):
            # ?next=1 means the user clicked "Create another" on the success
            # page; pre-fill from the previous session.
            defaults = {}
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if qs.get("next", ["0"])[0] == "1":
                defaults = self._carryover_defaults()
            body = render_form(defaults=defaults)
            self._send(200, "text/html; charset=utf-8", body.encode("utf-8"))
            return
        self._send(404, "text/plain", b"not found\n")

    def do_POST(self):  # noqa: N802
        if self.path == "/abort":
            self._send(200, "text/html; charset=utf-8", ABORT_HTML.encode("utf-8"))
            _FormHandler.aborted = True
            if _FormHandler.submission_event is not None:
                _FormHandler.submission_event.set()
            return
        if self.path == "/done":
            # User clicked Done on the success page — render the final summary
            # and signal the main thread to wrap up.
            body = render_done(_FormHandler.sessions_created)
            self._send(200, "text/html; charset=utf-8", body.encode("utf-8"))
            _FormHandler.done = True
            if _FormHandler.submission_event is not None:
                _FormHandler.submission_event.set()
            return
        if self.path != "/submit":
            self._send(404, "text/plain", b"not found\n")
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        raw = urllib.parse.parse_qs(body, keep_blank_values=True)
        form = {
            "first": raw.get("first", [""])[0].strip(),
            "last": raw.get("last", [""])[0].strip(),
            "operator": raw.get("operator", [""])[0].strip(),
            "appointment_date": raw.get("appointment_date", [""])[0].strip(),
            "study_collection_number": raw.get("study_collection_number", [""])[0].strip(),
            "gm_dir": raw.get("gm_dir", [""])[0].strip(),
            "formats": [f.id for f in FORMATS if f"fmt_{f.id}" in raw],
        }
        errors = validate(form)
        if errors:
            body = render_form(defaults=form, errors=errors)
            self._send(200, "text/html; charset=utf-8", body.encode("utf-8"))
            return

        session = build_session(form)
        # Do filesystem work *before* telling the browser it succeeded. If the
        # disk is full / target is a file / dir already has content (without
        # --force) / etc., the browser should see an error page, not "Session
        # created" while nothing was actually written. On failure we keep the
        # server running — user can hit Back, fix the issue, and resubmit.
        try:
            do_session_creation(
                session,
                create_dirs=_FormHandler.create_dirs,
                force=_FormHandler.force,
            )
        except Exception as e:
            log.error(f"Session creation failed: {e}")
            self._send(500, "text/html; charset=utf-8",
                       render_error(str(e)).encode("utf-8"))
            return

        # Success — record the session and offer Next/Done. Do NOT signal
        # the exit event; the user might create more sessions.
        _FormHandler.last_session = session
        _FormHandler.sessions_created.append(session)
        html_out = render_success(session, sessions_count=len(_FormHandler.sessions_created))
        self._send(200, "text/html; charset=utf-8", html_out.encode("utf-8"))

    def _handle_pick_dir(self):
        """Bridge to a native macOS folder-picker via osascript."""
        cmd = ["osascript", "-e",
               'POSIX path of (choose folder with prompt "Select Great Migration directory:")']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            self._send(500, "application/json",
                       json.dumps({"error": str(e)}).encode("utf-8"))
            return
        if result.returncode != 0:
            # User cancelled the dialog — return empty path, no error.
            self._send(200, "application/json",
                       json.dumps({"path": ""}).encode("utf-8"))
            return
        path = result.stdout.strip().rstrip("/")
        self._send(200, "application/json",
                   json.dumps({"path": path}).encode("utf-8"))


def run_form_server(*, create_dirs: bool, force: bool) -> int:
    """Start the form server, open a browser, block until the user clicks
    Done or Abort (or hits Ctrl-C). Filesystem work happens in the handler
    after each submit; the server stays up between submissions so the team
    can create multiple sessions in one drop-off appointment.

    Returns the process exit code: 0 if at least one session was created and
    the user clicked Done, non-zero on abort or zero-session Done."""
    _FormHandler.submission_event = threading.Event()
    _FormHandler.aborted = False
    _FormHandler.done = False
    _FormHandler.creation_error = None
    _FormHandler.create_dirs = create_dirs
    _FormHandler.force = force
    _FormHandler.last_session = None
    _FormHandler.sessions_created = []
    server = http.server.HTTPServer(("127.0.0.1", 0), _FormHandler)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info(f"Form open at {url}")
    webbrowser.open(url)
    try:
        _FormHandler.submission_event.wait()
    except KeyboardInterrupt:
        log.warning("Cancelled — server interrupted.")
        n = len(_FormHandler.sessions_created)
        if n:
            log.info(f"{n} session(s) had already been created before Ctrl-C; they remain on disk.")
        sys.exit(130)
    # Brief pause so the response bytes finish flushing to the browser before
    # we exit. We deliberately don't call server.shutdown() — the browser holds
    # the TCP connection open and shutdown() blocks on it. The serve_forever
    # thread is a daemon and dies cleanly when the process exits.
    time.sleep(0.3)
    if _FormHandler.aborted:
        log.warning("Aborted from browser — no further sessions created.")
        n = len(_FormHandler.sessions_created)
        if n:
            log.info(f"{n} session(s) had been created before abort; they remain on disk.")
            return 0
        sys.exit(130)
    # Normal Done path.
    n = len(_FormHandler.sessions_created)
    log.info(f"Done. {n} session{'s' if n != 1 else ''} created this run.")
    for s in _FormHandler.sessions_created:
        log.info(f"  {s['session_dir']}")
    return 0


# --- CLI fallback --------------------------------------------------------------

def _ask(prompt: str, *, default: str = "", required: bool = False) -> str:
    """Prompt with optional default + required-enforcement."""
    while True:
        suffix = f" [{default}]" if default else ""
        val = input(f"{prompt}{suffix}: ").strip()
        if not val and default:
            return default
        if not val and required:
            log.error("This field is required.")
            continue
        return val


def _ask_yn(prompt: str, *, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    while True:
        v = input(f"{prompt} [{d}]: ").strip().lower()
        if not v:
            return default
        if v in ("y", "yes"):
            return True
        if v in ("n", "no"):
            return False
        print("Please answer y or n.")


def run_cli_form() -> dict:
    """Terminal walkthrough of the same form."""
    print("\nGreat Migration appointment setup\n" + "=" * 35 + "\n")
    last = _ask("Last name of Great Migration appointment", required=True)
    first = _ask("First name of Great Migration appointment", required=True)
    operator = _ask("Name of the TBM preservationist running the appointment", required=True)
    appointment_date = _ask(
        "Date of the drop-off appointment (YYYY-MM-DD)",
        default=date_hyphen(), required=True,
    )
    scn = _ask("Study collection number (press enter to accept default)", default="SC.0001", required=True)
    gm_dir = _ask("Great Migration root directory path", required=True)

    print("\nFormats to digitize this session (mark each y/N):")
    selected: list[str] = []
    for f in FORMATS:
        if _ask_yn(f"  {f.label}", default=False):
            selected.append(f.id)
    if not selected:
        log.error("At least one format must be selected. Restart and try again.")
        sys.exit(2)

    form = {
        "first": first, "last": last, "operator": operator,
        "appointment_date": appointment_date,
        "study_collection_number": scn,
        "gm_dir": gm_dir, "formats": selected,
    }
    errors = validate(form)
    if errors:
        log.error("Form has errors:")
        for e in errors:
            log.error(f"  - {e}")
        sys.exit(2)
    return build_session(form)


# --- Top-level actions ---------------------------------------------------------

def _print_tree(root: Path) -> None:
    """Print an ASCII directory tree rooted at `root` to stdout."""
    print(f"{root}/")
    _print_tree_children(root, prefix="")


def _print_tree_children(parent: Path, prefix: str) -> None:
    children = sorted(parent.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    for i, child in enumerate(children):
        is_last = i == len(children) - 1
        branch = "└── " if is_last else "├── "
        suffix = "/" if child.is_dir() else ""
        print(f"{prefix}{branch}{child.name}{suffix}")
        if child.is_dir():
            extension = "    " if is_last else "│   "
            _print_tree_children(child, prefix + extension)


def do_session_creation(session: dict, *, create_dirs: bool, force: bool = False) -> int:
    """Stage and commit a session.

    Writes session.json to a uniquely-named temp file, runs all per-format
    mkdirs/note writes, then atomically promotes the temp to session.json.
    On any failure, _rollback() removes ONLY paths we explicitly tracked.
    We never rmtree the session dir — that branch existed in an earlier
    revision and could destroy a real session.json carried over from a
    prior --config-only run that the artifact filter correctly hides
    from the collision guard.

    Raises SessionExistsError if the target path exists but isn't a directory,
    or if it contains non-gmconfig files and `force` is False.
    """
    session_dir = Path(session["session_dir"])
    if session_dir.exists() and not session_dir.is_dir():
        raise SessionExistsError(
            f"Target path exists but is not a directory: {session_dir}"
        )
    dir_existed_before = session_dir.is_dir()
    # Ignore our own artifacts when deciding whether the dir is "occupied":
    # a session.json from a prior --config-only is the canonical handoff for
    # --from-config and shouldn't trip the collision guard. Same for any
    # stale unique-named session.json.<rand>.tmp from an interrupted run.
    if dir_existed_before:
        external_content = [p for p in session_dir.iterdir() if not _is_own_artifact(p)]
    else:
        external_content = []
    dir_had_external_content_before = bool(external_content)

    if dir_had_external_content_before:
        if not force:
            raise SessionExistsError(
                f"Session dir contains files that aren't gmconfig artifacts: {session_dir}. "
                f"Pass --force to merge into the existing dir."
            )
        log.warning(f"Session dir has external content; --force given, will merge into {session_dir}")

    real_json_path = session_dir / "session.json"

    # Tracking lists are declared OUTSIDE the try so _rollback() — defined
    # below, also outside the try — closes over them. They start empty and
    # are populated as each staging step succeeds. If any step raises (even
    # the very first one), _rollback only ever unlinks what's actually been
    # recorded.
    created_files: list[Path] = []
    created_dirs: list[Path] = []
    tmp_json_path: Path | None = None  # set the instant the tmp file exists

    def _rollback():
        # Selective cleanup only. Never rmtree the session dir — there may
        # be a pre-existing session.json from --config-only or a prior
        # --from-config attempt that we must not destroy.
        nonlocal tmp_json_path
        if tmp_json_path is not None:
            try:
                tmp_json_path.unlink(missing_ok=True)
            except OSError as e:
                log.warning(f"rollback: could not remove {tmp_json_path}: {e}")
        for f in reversed(created_files):
            try:
                f.unlink(missing_ok=True)
            except OSError as e:
                log.warning(f"rollback: could not remove {f}: {e}")
        # Walk created leaf dirs upward, rmdir'ing any that are empty. Safe by
        # construction: rmdir only succeeds on empty dirs, so anything we didn't
        # create (or that the user later added content to) stops the walk.
        seen: set[Path] = set()
        for d in reversed(created_dirs):
            cur = d
            while cur not in seen and cur != session_dir and session_dir in cur.parents:
                seen.add(cur)
                try:
                    cur.rmdir()
                except OSError:
                    break
                cur = cur.parent
        # If we created session_dir itself (it didn't exist before), and it's
        # now empty after the cleanup above, remove it too. If it contains
        # anything we don't track (carried-over session.json, user files
        # under --force, etc.), rmdir fails and we leave it untouched.
        if not dir_existed_before:
            try:
                session_dir.rmdir()
            except OSError:
                pass

    try:
        # All filesystem-mutating staging is inside the try block so any
        # partial state is reachable by _rollback. (Previously mkdir + tmp
        # write happened above the try; an early staging failure left a new
        # session_dir plus a partial tmp file with no cleanup hook.)
        session_dir.mkdir(parents=True, exist_ok=True)

        # Unique tmp name via tempfile so we never collide with — and silently
        # overwrite — a pre-existing session.json.<rand>.tmp left by a prior
        # interrupted run or a concurrent invocation.
        tmp_handle = tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8",
            dir=str(session_dir), prefix="session.json.", suffix=".tmp",
            delete=False,
        )
        # Record the tmp path immediately — NamedTemporaryFile creates the
        # file as part of __init__, so even if json.dump below raises, the
        # file is on disk and _rollback needs to know about it.
        tmp_json_path = Path(tmp_handle.name)
        try:
            json.dump(session, tmp_handle, indent=2)
            tmp_handle.write("\n")
        finally:
            tmp_handle.close()

        if create_dirs:
            create_session_dirs(
                session,
                created_files=created_files,
                created_dirs=created_dirs,
            )
        # Atomic commit — point of no return. After this rename succeeds,
        # session.json on disk is the new content. We zero tmp_json_path so
        # any logging-stage failure (extremely unlikely) doesn't try to
        # roll back a commit we already made.
        tmp_json_path.replace(real_json_path)
        tmp_json_path = None
    except Exception:
        log.error("Session creation failed; rolling back any partial writes.")
        _rollback()
        raise

    if create_dirs:
        log.info(f"Done. Session ready at {session_dir}")
        _print_tree(session_dir)
    else:
        log.info(f"Skipped dir creation (--config-only). Session.json at {real_json_path}")
    return 0


def validate_session(session: dict) -> list[str]:
    """Validate a loaded session.json. Returns list of errors; empty = valid.
    Mirrors form validation so --from-config can't trust a malformed/edited file
    to write outside the intended GM root or trip on missing keys later."""
    errs: list[str] = []

    for k in ("operator", "profile", "formats", "session_dir", "gm_dir", "appointment_date"):
        if k not in session:
            errs.append(f"Missing required key: {k}")
    if errs:
        return errs  # downstream checks would IndexError without these

    # Scalar string fields. Emitting an explicit type error (rather than silently
    # passing when the type is wrong) keeps a hand-edited config from making it
    # past --from-config validation and then exploding later in Path() or string
    # concatenation.
    operator = session.get("operator")
    if not isinstance(operator, str) or not operator.strip():
        errs.append(f"operator must be a non-empty string (got: {operator!r})")

    profile = session.get("profile")
    if not isinstance(profile, dict):
        errs.append(f"profile must be an object, got {type(profile).__name__}")
    else:
        for k in ("first", "last"):
            v = profile.get(k, "")
            if not isinstance(v, str) or not v.strip():
                errs.append(f"profile.{k} is missing or empty")
            elif v == ".." or any(c in v for c in _UNSAFE_NAME_CHARS):
                errs.append(f"profile.{k} contains invalid characters (no slashes or '..')")

    fmts = session.get("formats")
    if not isinstance(fmts, list) or not fmts:
        errs.append("formats must be a non-empty list")
    else:
        for i, f in enumerate(fmts):
            if not isinstance(f, dict) or "id" not in f:
                errs.append(f"formats[{i}] is malformed: {f!r}")
                continue
            # `f["id"] in FORMATS_BY_ID` calls hash(f["id"]); unhashable values
            # (list, dict) would raise TypeError here. Reject non-string ids
            # explicitly before any membership test.
            fid = f["id"]
            if not isinstance(fid, str):
                errs.append(f"formats[{i}].id must be a string, got {type(fid).__name__}")
            elif fid not in FORMATS_BY_ID:
                errs.append(f"formats[{i}] has unknown id: {fid!r}")

    gm_dir = session.get("gm_dir")
    session_dir = session.get("session_dir")
    # Explicit type errors first so a numeric/list value doesn't silently slip
    # past the inner isinstance gate of the path check.
    if not isinstance(gm_dir, str) or not gm_dir:
        errs.append(f"gm_dir must be a non-empty string (got: {gm_dir!r})")
    if not isinstance(session_dir, str) or not session_dir:
        errs.append(f"session_dir must be a non-empty string (got: {session_dir!r})")
    if isinstance(gm_dir, str) and isinstance(session_dir, str) and gm_dir and session_dir:
        gp = Path(gm_dir).expanduser()
        sp = Path(session_dir).expanduser()
        if not gp.is_dir():
            errs.append(f"gm_dir does not exist or is not a directory: {gp}")
        else:
            try:
                sp.resolve().relative_to(gp.resolve())
            except ValueError:
                errs.append(f"session_dir is not inside gm_dir: {sp} (gm_dir={gp})")

    # appointment_date is concatenated into per-format and general-notes filenames
    # via session_dir / f"{d_iso}_..._Notes.txt". A hand-edited config with a slash
    # or "../" in this field would let those writes escape session_dir even after
    # session_dir itself has been validated. Enforce strict YYYY-MM-DD.
    ad = session.get("appointment_date", "")
    if not isinstance(ad, str) or not _is_valid_iso_date(ad):
        errs.append(f"appointment_date must be a YYYY-MM-DD string (got: {ad!r})")

    return errs


def load_session(path: Path) -> dict:
    """Load and fully validate an existing session.json."""
    if not path.exists():
        log.error(f"Config not found: {path}")
        sys.exit(2)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        log.error(f"Could not parse {path}: {e}")
        sys.exit(2)
    if not isinstance(data, dict):
        log.error(f"Top-level session.json must be an object, got {type(data).__name__}")
        sys.exit(2)
    if data.get("schema_version") != SCHEMA_VERSION:
        log.warning(f"Schema version mismatch in {path} "
                    f"(file={data.get('schema_version')}, code={SCHEMA_VERSION})")
    errors = validate_session(data)
    if errors:
        log.error(f"Invalid session in {path}:")
        for e in errors:
            log.error(f"  - {e}")
        sys.exit(2)
    return data


# --- main ----------------------------------------------------------------------

def main() -> int:
    install_sigterm_trap()
    p = argparse.ArgumentParser(
        prog="gmconfig.py",
        description="Set up a Great Migration digitization appointment.",
    )
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--config-only", action="store_true",
                      help="Open form, save session.json, but don't create the directory structure.")
    mode.add_argument("--from-config", type=Path, metavar="PATH",
                      help="Skip the form. Read an existing session.json and create its dirs.")
    mode.add_argument("--cli", action="store_true",
                      help="Use terminal prompts instead of the browser form.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite/merge into an existing non-empty session dir.")
    args = p.parse_args()
    create_dirs = not args.config_only

    try:
        if args.from_config:
            session = load_session(args.from_config)
            return do_session_creation(session, create_dirs=True, force=args.force)
        if args.cli:
            session = run_cli_form()
            return do_session_creation(session, create_dirs=create_dirs, force=args.force)
        # Browser form path: filesystem work happens inside the handler so we
        # can render an error page if it fails. run_form_server returns the
        # final exit code.
        return run_form_server(create_dirs=create_dirs, force=args.force)
    except SessionExistsError as e:
        log.error(str(e))
        return 2


if __name__ == "__main__":
    sys.exit(main())
