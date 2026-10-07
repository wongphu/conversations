#!/usr/bin/env python3
"""
Generate an interactive HTML page for a conversation from clips.json.

Usage:
    python scripts/generate_html.py [<conversation_number> | --all]

Example:
    python scripts/generate_html.py 41
    python scripts/generate_html.py 36
    python scripts/generate_html.py --all     # every page, e.g. after editing player.js

Reads:
    docs/<N>/clips.json
    texts/<N>.md                – for the page title (its "# ..." H1), if present,
                                  and the CEFR level (its "Level: A2" line) for the badges

Writes:
    docs/<N>.html               – loads the shared player, docs/player.js, as
                                  player.js?v=<hash of its contents>
    docs/index.html             – rebuilt every run: one link per docs/NN.html
"""

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
TEXTS_DIR = PROJECT_ROOT / "texts"
PLAYER_PATH = DOCS_DIR / "player.js"

ITALIC_RE = re.compile(r"\*(.+?)\*")

TEMPLATE_HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #fbf8f2;
      --fg: #1d1b18;
      --muted: #857e72;
      --es: #9b4d24;
      --rule: #e6dfd2;
      --hl: #f3ead8;
      --accent: #7a3e1d;
      --error: #b00020;
      --level-a: #3d6b45;
      --level-a-bg: #e2ede0;
      --level-b: #85561a;
      --level-b-bg: #f3e4c6;
      --level-c: #9b3324;
      --level-c-bg: #f5dcd5;
    }}

    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #171513;
        --fg: #ece6dc;
        --muted: #8f877b;
        --es: #e0a47e;
        --rule: #2e2a25;
        --hl: #2a241d;
        --accent: #e0a47e;
        --error: #ff6b6b;
        --level-a: #a6cfa9;
        --level-a-bg: #1f2b21;
        --level-b: #e3bd78;
        --level-b-bg: #30271a;
        --level-c: #eda193;
        --level-c-bg: #3a201c;
      }}
    }}

    body {{
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font: 19px/1.5 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    }}

    main {{
      box-sizing: border-box;
      max-width: 1000px;
      margin: 0 auto;
      padding: 1.4rem 1.5rem 4rem;
    }}

    .back {{
      font: 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--muted);
      text-decoration: none;
    }}

    .back:hover {{ color: var(--fg); text-decoration: underline; }}

    header {{
      text-align: center;
      margin: 0.8rem 0 0.6rem;
    }}

    .num {{
      font-size: 0.85rem;
      letter-spacing: 0.25em;
      color: var(--muted);
    }}

    .level {{
      display: inline-block;
      margin-left: 0.5rem;
      padding: 0.15rem 0.55rem;
      border-radius: 999px;
      vertical-align: 0.1em;
      font: 600 12px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0.06em;
    }}

    .level-a {{ color: var(--level-a); background: var(--level-a-bg); }}
    .level-b {{ color: var(--level-b); background: var(--level-b-bg); }}
    .level-c {{ color: var(--level-c); background: var(--level-c-bg); }}

    h1 {{
      font-weight: 400;
      font-size: 2rem;
      line-height: 1.2;
      margin: 0.3rem 0 0;
    }}

    .subtitle {{
      margin: 0.2rem 0 0;
      color: var(--es);
      font-style: italic;
      font-size: 1.2rem;
    }}

    .toolbar {{
      position: -webkit-sticky;
      position: sticky;
      top: 0;
      z-index: 2;
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: center;
      padding: 0.3rem 0;
      background: var(--bg);
      font: 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--muted);
    }}

    .toolbar > * {{ margin: 0.3rem 0.7rem; }}

    .seg {{
      display: inline-flex;
      border: 1px solid var(--rule);
      border-radius: 999px;
      padding: 2px;
    }}

    .seg button {{
      border: 0;
      background: transparent;
      color: var(--muted);
      font: inherit;
      padding: 0.3rem 0.8rem;
      border-radius: 999px;
      cursor: pointer;
    }}

    .seg button[aria-pressed="true"] {{
      background: var(--accent);
      color: var(--bg);
    }}

    .play-all {{
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--accent);
      border-radius: 999px;
      background: transparent;
      color: var(--accent);
      font: inherit;
      padding: 0.3rem 0.9rem 0.3rem 0.6rem;
      cursor: pointer;
    }}

    .play-all svg {{
      width: 1rem;
      height: 1rem;
      margin-right: 0.35rem;
    }}

    .play-all .stop-icon,
    .play-all[aria-pressed="true"] .play-icon {{ display: none; }}

    .play-all[aria-pressed="true"] .stop-icon {{ display: block; }}

    .play-all[aria-pressed="true"] {{
      background: var(--accent);
      color: var(--bg);
    }}

    .play-all:focus-visible {{
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }}

    .speed-control {{
      display: flex;
      align-items: center;
    }}

    .speed-control input[type="range"] {{
      width: 130px;
      margin: 0 0.6rem;
      accent-color: var(--accent);
    }}

    .speed-control .speed-value {{
      min-width: 3.2em;
      font-variant-numeric: tabular-nums;
    }}

    .hint {{
      min-height: 1.4em;
      margin: 0 0 0.6rem;
      text-align: center;
      font-size: 0.85rem;
      font-style: italic;
      color: var(--muted);
    }}

    .turn {{
      display: grid;
      grid-template-columns: 2.5rem 1fr 1fr;
      grid-column-gap: 1.5rem;
    }}

    .turn > * {{
      min-width: 0;
      padding: 0.75rem 0;
      border-bottom: 1px solid var(--rule);
    }}

    .turn.head > * {{
      padding: 0 0 0.4rem;
      border-bottom-color: var(--fg);
      font: 600 11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0.15em;
      color: var(--muted);
    }}

    .who {{
      padding-top: 1.05rem;
      font: 600 13px/1 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0.06em;
      color: var(--muted);
    }}

    .turn.b .who {{ color: var(--accent); }}

    .line p {{
      display: flex;
      align-items: flex-start;
      margin: 0;
    }}

    .line p .words {{
      flex: 1 1 auto;
      min-width: 0;
    }}

    .line.es {{ color: var(--es); }}

    .line.playing .words {{ background: var(--hl); }}

    em {{ font-style: italic; }}

    .speak {{
      flex: 0 0 auto;
      width: 1.5rem;
      height: 1.5rem;
      margin: 0.15rem 0.5rem 0 0;
      padding: 0.25rem;
      border: 1px solid var(--rule);
      border-radius: 50%;
      background: transparent;
      color: var(--muted);
      cursor: pointer;
      line-height: 0;
    }}

    .speak svg {{
      display: block;
      width: 100%;
      height: 100%;
    }}

    .speak:hover {{ color: var(--fg); }}

    .speak:focus-visible {{
      outline: 2px solid var(--accent);
      outline-offset: 1px;
    }}

    .speak.playing {{
      background: var(--accent);
      border-color: var(--accent);
      color: var(--bg);
    }}

    .speak.error {{
      border-color: var(--error);
      color: var(--error);
    }}

    body.hide-en .line.en:not(.shown) .words,
    body.hide-es .line.es:not(.shown) .words {{
      -webkit-filter: blur(6px);
      filter: blur(6px);
      cursor: pointer;
      -webkit-user-select: none;
      user-select: none;
    }}

    @media (max-width: 640px) {{
      body {{ font-size: 17px; }}
      main {{ padding: 0.9rem 1rem 3rem; }}
      h1 {{ font-size: 1.6rem; }}
      .turn {{ display: block; }}
      .turn.head {{ display: none; }}
      .turn > * {{ padding: 0.2rem 0; border: 0; }}
      .who {{ margin-top: 0.4rem; padding-top: 0.9rem; border-top: 1px solid var(--rule); }}
    }}
  </style>
</head>
<body>
  <main>
    <a class="back" href="index.html">&larr; All conversations / Todas las conversaciones</a>
    <header>
{header}
    </header>
    <div class="toolbar">
      <button type="button" class="play-all" id="playAll" aria-pressed="false">
        <svg class="play-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 4.5v15l12.5-7.5z"></path></svg>
        <svg class="stop-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 6h12v12H6z"></path></svg>
        <span id="playAllLabel">Play all</span>
      </button>
      <div class="seg" role="group" aria-label="Show">
        <button type="button" data-mode="" aria-pressed="true">Both</button>
        <button type="button" data-mode="hide-es" aria-pressed="false">Hide Spanish</button>
        <button type="button" data-mode="hide-en" aria-pressed="false">Hide English</button>
      </div>
      <div class="speed-control">
        <label for="speed">Speed / Velocidad</label>
        <input type="range" id="speed" min="50" max="150" value="100" step="5">
        <span class="speed-value" id="speedValue">100%</span>
      </div>
    </div>
    <p class="hint" id="hint"></p>
    <div class="turns">
      <div class="turn head" aria-hidden="true"><div></div><div>ENGLISH</div><div>ESPAÑOL</div></div>
'''

INDEX_HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Conversations</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #fbf8f2;
      --fg: #1d1b18;
      --muted: #857e72;
      --es: #9b4d24;
      --rule: #e6dfd2;
      --hl: #f3ead8;
      --level-a: #3d6b45;
      --level-a-bg: #e2ede0;
      --level-b: #85561a;
      --level-b-bg: #f3e4c6;
      --level-c: #9b3324;
      --level-c-bg: #f5dcd5;
    }

    @media (prefers-color-scheme: dark) {
      :root {
        --bg: #171513;
        --fg: #ece6dc;
        --muted: #8f877b;
        --es: #e0a47e;
        --rule: #2e2a25;
        --hl: #2a241d;
        --level-a: #a6cfa9;
        --level-a-bg: #1f2b21;
        --level-b: #e3bd78;
        --level-b-bg: #30271a;
        --level-c: #eda193;
        --level-c-bg: #3a201c;
      }
    }

    body {
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font: 19px/1.4 "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif;
    }

    main {
      box-sizing: border-box;
      max-width: 680px;
      margin: 0 auto;
      padding: 2.4rem 1.5rem 4rem;
    }

    header {
      text-align: center;
      margin-bottom: 1.8rem;
    }

    h1 {
      font-weight: 400;
      font-size: 2rem;
      line-height: 1.2;
      margin: 0;
    }

    .subtitle {
      margin: 0.2rem 0 0;
      color: var(--es);
      font-style: italic;
      font-size: 1.2rem;
    }

    ol {
      list-style: none;
      margin: 0;
      padding: 0;
      border-top: 1px solid var(--fg);
    }

    li { border-bottom: 1px solid var(--rule); }

    a {
      display: flex;
      align-items: baseline;
      padding: 0.75rem 0.4rem;
      color: inherit;
      text-decoration: none;
    }

    a:hover { background: var(--hl); }

    .num {
      flex: 0 0 2.6rem;
      font: 600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0.06em;
      color: var(--muted);
    }

    .es {
      display: block;
      color: var(--es);
      font-style: italic;
      font-size: 0.9em;
    }

    .title {
      flex: 1 1 auto;
      min-width: 0;
      padding-right: 0.8rem;
    }

    .level {
      flex: none;
      padding: 0.15rem 0.55rem;
      border-radius: 999px;
      font: 600 12px/1.2 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0.06em;
    }

    .level-a { color: var(--level-a); background: var(--level-a-bg); }
    .level-b { color: var(--level-b); background: var(--level-b-bg); }
    .level-c { color: var(--level-c); background: var(--level-c-bg); }

    .legend {
      margin: 0.9rem 0 0;
      font: 12px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--muted);
    }

    .legend .level {
      padding: 0.05rem 0.4rem;
      font-size: 11px;
    }

    @media (max-width: 640px) {
      body { font-size: 17px; }
      main { padding: 1.6rem 1rem 3rem; }
      h1 { font-size: 1.6rem; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Conversations</h1>
      <p class="subtitle" lang="es">Conversaciones</p>
      <p class="legend">CEFR level: <span class="level level-a">A</span> beginner &middot; <span class="level level-b">B</span> intermediate &middot; <span class="level level-c">C</span> advanced<br>
        <span lang="es">Nivel MCER: A principiante &middot; B intermedio &middot; C avanzado</span></p>
    </header>
    <ol>
'''

INDEX_ROW = '''      <li><a href="{num}.html"><span class="num">{num}</span><span class="title">{en_title}{es_title}</span>{level}</a></li>
'''

INDEX_ROW_ES = '''<span class="es" lang="es">{title}</span>'''

LEVEL_BADGE = '''<span class="level level-{band}" title="CEFR {level}: {name}">{level}</span>'''

INDEX_TAIL = '''    </ol>
  </main>
</body>
</html>
'''

TITLE_RE = re.compile(r"^(\d+)\.\s+(.*)$")

# The refine step writes a "Level: A2" line under the title of texts/NN.md.
LEVEL_RE = re.compile(r"^Level:\s*([ABC][12])\s*$", re.MULTILINE)
LEVEL_NAMES = {
    "A1": "beginner", "A2": "elementary",
    "B1": "intermediate", "B2": "upper intermediate",
    "C1": "advanced", "C2": "proficient",
}

TEMPLATE_HEADER = '''      <div class="num">CONVERSATION {num}{level}</div>
      <h1>{en_title}</h1>'''

TEMPLATE_SUBTITLE = '''
      <p class="subtitle" lang="es">{es_title}</p>'''

TEMPLATE_ROW = '''      <div class="turn {speaker_class}">
        <div class="who">{speaker}</div>
        <div class="line en" lang="en"><p data-audio="{en_file}" data-voice="{en_voice}">{en_text}</p></div>
        <div class="line es" lang="es"><p data-audio="{es_file}" data-voice="{es_voice}">{es_text}</p></div>
      </div>
'''

TEMPLATE_SCRIPT = '''    </div>
  </main>
  <script type="module" src="player.js?v={player_version}"></script>
</body>
</html>
'''


def player_version() -> str:
    """A short hash of docs/player.js for the page's script URL.

    A browser that cached an older player.js would otherwise run it against
    a newer page (after the restyle, the old player looked for <td>s and
    every play button threw). A new hash makes it fetch the matching one.
    """
    return hashlib.sha256(PLAYER_PATH.read_bytes()).hexdigest()[:10]


def read_title(conv_num: int) -> str:
    """The "# NN. English — Spanish" H1 from texts/NN.md, or a generic fallback."""
    texts_path = TEXTS_DIR / f"{conv_num}.md"
    if texts_path.exists():
        for line in texts_path.read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    print(f"Warning: no title found in {texts_path}", file=sys.stderr)
    return f"Conversation {conv_num}"


def parse_level(md_text: str) -> str | None:
    """The CEFR level (A1…C2) from a texts/NN.md "Level: A2" line, or None."""
    match = LEVEL_RE.search(md_text)
    return match.group(1) if match else None


def read_level(conv_num: int) -> str | None:
    """The CEFR level of texts/NN.md; None (with a warning) if it has none."""
    texts_path = TEXTS_DIR / f"{conv_num}.md"
    level = parse_level(texts_path.read_text()) if texts_path.exists() else None
    if level is None:
        print(f"Warning: no 'Level: A1…C2' line in {texts_path}", file=sys.stderr)
    return level


def level_badge(level: str | None) -> str:
    """The CEFR badge for the index and the page header, tinted by band; "" if no level."""
    if level is None:
        return ""
    return LEVEL_BADGE.format(band=level[0].lower(), level=level, name=LEVEL_NAMES[level])


def generate_index() -> str:
    """The landing page: one link per docs/NN.html, in conversation order.

    Its label is the page title with the number split off: the English title,
    with the Spanish one (after the em dash) on a line below it, then a badge
    with the CEFR level, tinted by band (A, B or C).
    """
    nums = sorted(int(path.stem) for path in DOCS_DIR.glob("*.html") if path.stem.isdigit())
    page = INDEX_HEAD
    for num in nums:
        match = TITLE_RE.match(read_title(num))
        title = match.group(2) if match else f"Conversation {num}"
        en_title, _, es_title = title.partition(" — ")
        page += INDEX_ROW.format(
            num=num,
            en_title=render_text(en_title),
            es_title=INDEX_ROW_ES.format(title=render_text(es_title)) if es_title else "",
            level=level_badge(read_level(num)),
        )
    return page + INDEX_TAIL


def render_text(text: str) -> str:
    """Escape a line for HTML, turning markdown *italics* into <em>."""
    return ITALIC_RE.sub(r"<em>\1</em>", html.escape(text, quote=False))


def generate_html(conv_num: int) -> str:
    """Generate HTML content for a conversation."""
    clips_path = DOCS_DIR / str(conv_num) / "clips.json"
    if not clips_path.exists():
        sys.exit(f"Error: {clips_path} not found")

    clips = json.loads(clips_path.read_text())

    # Group clips by row number
    rows: dict[str, dict[str, dict]] = defaultdict(dict)
    for clip in clips:
        # Extract row number from filename: "41/audio/en/00-a.mp3" → "00"
        parts = clip["file"].split("/")
        filename = parts[-1]  # "00-a.mp3"
        row_num = filename.split("-")[0]  # "00"
        lang = clip["lang"]  # "en" or "es"
        rows[row_num][lang] = clip

    # Build HTML: the "NN. English — Spanish" title is split for the header
    title = read_title(conv_num)
    match = TITLE_RE.match(title)
    num, name = (match.group(1), match.group(2)) if match else (str(conv_num), title)
    en_title, _, es_title = name.partition(" — ")
    header = TEMPLATE_HEADER.format(num=num, level=level_badge(read_level(conv_num)),
                                    en_title=render_text(en_title))
    if es_title:
        header += TEMPLATE_SUBTITLE.format(es_title=render_text(es_title))
    page = TEMPLATE_HEAD.format(title=html.escape(title, quote=False), header=header)

    for row_num in sorted(rows.keys()):
        row = rows[row_num]
        en = row.get("en")
        es = row.get("es")

        if not en or not es:
            print(f"Warning: row {row_num} is missing a language; skipped", file=sys.stderr)
            continue

        # The speaker column shows the English speaker, which picks the voices
        speaker = en["speaker"].split("_")[-1]  # "en_c" → "c"
        es_speaker = es["speaker"].split("_")[-1]

        page += TEMPLATE_ROW.format(
            speaker_class=speaker,
            speaker=speaker.upper(),
            en_file=html.escape(en["file"]),
            en_voice=f"English {speaker.upper()}",
            en_text=render_text(en["text"]),
            es_file=html.escape(es["file"]),
            es_voice=f"Spanish {es_speaker.upper()}",
            es_text=render_text(es["text"]),
        )

    page += TEMPLATE_SCRIPT.format(player_version=player_version())
    return page


def main():
    parser = argparse.ArgumentParser(description="Generate HTML for a conversation, and the index.")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("conversation", type=int, nargs="?",
                        help="Conversation number (omit to rebuild only the index)")
    target.add_argument("--all", action="store_true",
                        help="Rebuild every existing docs/NN.html (e.g. after editing player.js)")
    args = parser.parse_args()

    if args.all:
        convs = sorted(int(path.stem) for path in DOCS_DIR.glob("*.html") if path.stem.isdigit())
    else:
        convs = [args.conversation] if args.conversation is not None else []
    for conv in convs:
        out_path = DOCS_DIR / f"{conv}.html"
        out_path.write_text(generate_html(conv))
        print(f"Written to {out_path}")

    index_path = DOCS_DIR / "index.html"
    index_path.write_text(generate_index())
    print(f"Written to {index_path}")


if __name__ == "__main__":
    main()
