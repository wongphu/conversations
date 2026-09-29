#!/usr/bin/env python3
"""
Generate an interactive HTML page for a conversation from clips.json.

Usage:
    python scripts/generate_html.py [<conversation_number>]

Example:
    python scripts/generate_html.py 41
    python scripts/generate_html.py 36

Reads:
    docs/<N>/clips.json
    texts/<N>.md                – for the page title (its "# ..." H1), if present

Writes:
    docs/<N>.html               – loads the shared player, docs/player.js
    docs/index.html             – rebuilt every run: one link per docs/NN.html
"""

import argparse
import html
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
TEXTS_DIR = PROJECT_ROOT / "texts"

ITALIC_RE = re.compile(r"\*(.+?)\*")

TEMPLATE_HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ color-scheme: light; }}

    body {{
      margin: 0;
      background: #fff;
      color: #111;
      font-family: "Times New Roman", Times, "Liberation Serif", serif;
    }}

    main {{
      box-sizing: border-box;
      max-width: 960px;
      margin: 0 auto;
      padding: 2rem 1.35rem 2.75rem;
    }}

    .back {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 0.85rem;
      color: #2a45b0;
      text-decoration: none;
    }}

    .back:hover {{ text-decoration: underline; }}

    h1 {{
      margin: 0.6rem 0 1.1rem;
      font-size: 1.5rem;
      font-weight: 600;
      line-height: 1.25;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
      font-size: 1.0625rem;
      line-height: 1.32;
    }}

    td {{
      width: 50%;
      border: 1.5px solid #111;
      padding: 0.55rem 0.7rem 0.62rem 0.55rem;
      vertical-align: top;
    }}

    td p {{
      display: flex;
      align-items: flex-start;
      gap: 0.4rem;
      margin: 0;
      padding: 0;
      text-indent: 0;
    }}

    td p .words {{
      flex: 1 1 auto;
      min-width: 0;
      padding-left: 1.65em;
      text-indent: -1.65em;
    }}

    .speak {{
      flex: 0 0 auto;
      width: 1.55rem;
      height: 1.55rem;
      margin-top: 0.06em;
      padding: 0.14rem;
      border: 1px solid #222;
      border-radius: 4px;
      background: #fff;
      color: #111;
      cursor: pointer;
      line-height: 0;
    }}

    .speak svg {{
      display: block;
      width: 100%;
      height: 100%;
    }}

    .speak:hover {{ background: #f3f3f3; }}

    .speak:focus-visible {{
      outline: 2px solid #1d3f8f;
      outline-offset: 1px;
    }}

    .speak.playing {{
      background: #1d3f8f;
      border-color: #1d3f8f;
      color: #fff;
    }}

    td.playing {{ background: #f4f7ff; }}

    .speak.error {{
      border-color: #b00020;
      color: #b00020;
    }}

    em {{ font-style: italic; }}

    td[lang="en"] {{ color: #444; }}
    td[lang="es"] {{ color: #A0522D; }}

    .mark {{
      text-decoration: underline;
      text-decoration-color: #2a45b0;
      text-decoration-thickness: 1.5px;
      text-underline-offset: 0.12em;
    }}

    .speed-control {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin-bottom: 1rem;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 0.85rem;
      color: #333;
    }}

    .speed-control label {{
      font-weight: 500;
      white-space: nowrap;
    }}

    .speed-control input[type="range"] {{
      flex: 0 1 160px;
      accent-color: #2a45b0;
    }}

    .speed-control .speed-value {{
      min-width: 3.2em;
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}

    @media (max-width: 700px) {{
      main {{ padding: 0.7rem 0.35rem 1.4rem; }}
      h1 {{ font-size: 1.2rem; }}
      table {{ font-size: 0.78rem; }}
      td {{ padding: 0.4rem 0.32rem 0.45rem; }}
    }}
  </style>
</head>
<body>
  <main>
    <a class="back" href="index.html">&larr; All conversations / Todas las conversaciones</a>
    <h1>{title}</h1>
    <div class="speed-control">
      <label for="speed">Speed / Velocidad</label>
      <input type="range" id="speed" min="50" max="150" value="100" step="5">
      <span class="speed-value" id="speedValue">100%</span>
    </div>
    <table>
      <tbody>
'''

INDEX_HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Conversations</title>
  <style>
    :root { color-scheme: light; }

    body {
      margin: 0;
      background: #fff;
      color: #111;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    main {
      max-width: 600px;
      margin: 0 auto;
      padding: 3rem 1.5rem;
    }

    h1 {
      font-size: 1.5rem;
      font-weight: 600;
      margin-bottom: 1.5rem;
    }

    ol {
      list-style: none;
      padding: 0;
      margin: 0;
    }

    li {
      margin-bottom: 0.5rem;
    }

    a {
      display: block;
      padding: 0.75rem 1rem;
      border: 1.5px solid #ddd;
      border-radius: 6px;
      text-decoration: none;
      color: #111;
      transition: border-color 0.15s, background 0.15s;
    }

    a:hover {
      border-color: #2a45b0;
      background: #f4f7ff;
    }

    a .num {
      font-weight: 600;
      color: #2a45b0;
      margin-right: 0.5rem;
    }
  </style>
</head>
<body>
  <main>
    <h1>Conversations / Conversaciones</h1>
    <ol>
'''

INDEX_ROW = '''      <li><a href="{num}.html"><span class="num">{num}</span> {title}</a></li>
'''

INDEX_TAIL = '''    </ol>
  </main>
</body>
</html>
'''

TITLE_RE = re.compile(r"^(\d+)\.\s+(.*)$")

TEMPLATE_ROW = '''        <tr>
          <td lang="en"><p data-audio="{en_file}" data-voice="{en_voice}">{en_speaker}. {en_text}</p></td>
          <td lang="es"><p data-audio="{es_file}" data-voice="{es_voice}">{es_speaker}. {es_text}</p></td>
        </tr>
'''

TEMPLATE_SCRIPT = '''      </tbody>
    </table>
  </main>
  <script type="module" src="player.js"></script>
</body>
</html>
'''


def read_title(conv_num: int) -> str:
    """The "# NN. English — Spanish" H1 from texts/NN.md, or a generic fallback."""
    texts_path = TEXTS_DIR / f"{conv_num}.md"
    if texts_path.exists():
        for line in texts_path.read_text().splitlines():
            if line.startswith("# "):
                return line[2:].strip()
    print(f"Warning: no title found in {texts_path}", file=sys.stderr)
    return f"Conversation {conv_num}"


def generate_index() -> str:
    """The landing page: one link per docs/NN.html, in conversation order.

    Its label is the page title with the number split off and the em dash
    between the English and Spanish titles turned into a slash.
    """
    nums = sorted(int(path.stem) for path in DOCS_DIR.glob("*.html") if path.stem.isdigit())
    page = INDEX_HEAD
    for num in nums:
        match = TITLE_RE.match(read_title(num))
        title = match.group(2) if match else f"Conversation {num}"
        page += INDEX_ROW.format(num=num, title=html.escape(title.replace(" — ", " / "), quote=False))
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

    # Build HTML
    page = TEMPLATE_HEAD.format(title=html.escape(read_title(conv_num), quote=False))

    for row_num in sorted(rows.keys()):
        row = rows[row_num]
        en = row.get("en")
        es = row.get("es")

        if not en or not es:
            print(f"Warning: row {row_num} is missing a language; skipped", file=sys.stderr)
            continue

        en_speaker = en["speaker"].split("_")[-1].upper()  # "en_c" → "C"
        es_speaker = es["speaker"].split("_")[-1].upper()
        en_voice = f"English {en_speaker}"
        es_voice = f"Spanish {es_speaker}"

        page += TEMPLATE_ROW.format(
            en_file=html.escape(en["file"]),
            en_voice=en_voice,
            en_speaker=en_speaker,
            en_text=render_text(en["text"]),
            es_file=html.escape(es["file"]),
            es_voice=es_voice,
            es_speaker=es_speaker,
            es_text=render_text(es["text"]),
        )

    page += TEMPLATE_SCRIPT
    return page


def main():
    parser = argparse.ArgumentParser(description="Generate HTML for a conversation, and the index.")
    parser.add_argument("conversation", type=int, nargs="?",
                        help="Conversation number (omit to rebuild only the index)")
    args = parser.parse_args()

    if args.conversation is not None:
        out_path = DOCS_DIR / f"{args.conversation}.html"
        out_path.write_text(generate_html(args.conversation))
        print(f"Written to {out_path}")

    index_path = DOCS_DIR / "index.html"
    index_path.write_text(generate_index())
    print(f"Written to {index_path}")


if __name__ == "__main__":
    main()
