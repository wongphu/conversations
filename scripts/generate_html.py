#!/usr/bin/env python3
"""
Generate an interactive HTML page for a conversation from clips.json.

Usage:
    python scripts/generate_html.py <conversation_number>

Example:
    python scripts/generate_html.py 41
    python scripts/generate_html.py 36

Reads:
    docs/<N>/clips.json

Writes:
    docs/<N>.html
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"

TEMPLATE_HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Conversation {conv}</title>
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
      table {{ font-size: 0.78rem; }}
      td {{ padding: 0.4rem 0.32rem 0.45rem; }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="speed-control">
      <label for="speed">Speed / Velocidad</label>
      <input type="range" id="speed" min="50" max="150" value="100" step="5">
      <span class="speed-value" id="speedValue">100%</span>
    </div>
    <table>
      <tbody>
'''

TEMPLATE_ROW = '''        <tr>
          <td lang="en"><p data-audio="{en_file}" data-voice="{en_voice}">{en_speaker}. {en_text}</p></td>
          <td lang="es"><p data-audio="{es_file}" data-voice="{es_voice}">{es_speaker}. {es_text}</p></td>
        </tr>
'''

TEMPLATE_SCRIPT = '''      </tbody>
    </table>
  </main>
  <script type="module">
    import psola from "https://esm.sh/@audio/stretch-psola@1.2.1";

    const speakerIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3z"></path><path fill="currentColor" d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"></path><path fill="currentColor" d="M14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"></path></svg>';

    const ctx = new AudioContext();
    const bufferCache = new Map();
    let currentSource = null;
    let currentButton = null;
    let currentUrl = null;

    const speedSlider = document.getElementById("speed");
    const speedValue = document.getElementById("speedValue");

    function getSpeedFactor() {
      return 100 / Number(speedSlider.value);
    }

    async function getDecoded(url) {
      if (bufferCache.has(url)) return bufferCache.get(url);
      const resp = await fetch(url);
      const arrBuf = await resp.arrayBuffer();
      const audioBuf = await ctx.decodeAudioData(arrBuf);
      bufferCache.set(url, audioBuf);
      return audioBuf;
    }

    function stretch(audioBuf, factor) {
      const ch = audioBuf.numberOfChannels;
      const sr = audioBuf.sampleRate;
      const out = ctx.createBuffer(ch, Math.ceil(audioBuf.length * factor), sr);
      for (let i = 0; i < ch; i++) {
        const stretched = psola(audioBuf.getChannelData(i), { factor, sampleRate: sr });
        out.copyToChannel(stretched, i);
      }
      return out;
    }

    async function playClip(url, button) {
      if (ctx.state === "suspended") await ctx.resume();
      stopSpeaking();
      const buf = await getDecoded(url);
      const factor = getSpeedFactor();
      const stretched = stretch(buf, factor);

      const src = ctx.createBufferSource();
      src.buffer = stretched;
      src.connect(ctx.destination);
      src.onended = () => { if (currentSource === src) stopSpeaking(); };
      src.start();

      currentSource = src;
      currentButton = button;
      currentUrl = url;
      button.classList.add("playing");
      button.setAttribute("aria-pressed", "true");
      button.closest("td").classList.add("playing");
    }

    function stopSpeaking() {
      if (currentSource) {
        currentSource.onended = null;
        try { currentSource.stop(); } catch {}
        currentSource = null;
      }
      if (currentButton) {
        currentButton.classList.remove("playing");
        currentButton.setAttribute("aria-pressed", "false");
        currentButton.closest("td").classList.remove("playing");
      }
      currentButton = null;
      currentUrl = null;
    }

    function applySpeed() {
      const pct = Number(speedSlider.value);
      speedValue.textContent = pct + "%";
      if (currentSource && currentUrl) {
        const btn = currentButton;
        playClip(currentUrl, btn);
      }
    }
    speedSlider.addEventListener("input", applySpeed);
    speedValue.textContent = speedSlider.value + "%";

    document.querySelectorAll("p[data-audio]").forEach((paragraph) => {
      const words = document.createElement("span");
      words.className = "words";
      while (paragraph.firstChild) words.appendChild(paragraph.firstChild);

      const button = document.createElement("button");
      button.type = "button";
      button.className = "speak";
      button.innerHTML = speakerIcon;
      button.setAttribute("aria-pressed", "false");
      const voice = paragraph.dataset.voice || "paragraph";
      const line = words.textContent.replace(/\\s+/g, " ").trim();
      button.setAttribute("aria-label", "Play " + voice + ": " + line);
      button.addEventListener("click", () => {
        if (currentButton === button) {
          stopSpeaking();
          return;
        }
        playClip(paragraph.dataset.audio, button);
      });
      paragraph.append(button, words);
    });
  </script>
</body>
</html>
'''


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
    html = TEMPLATE_HEAD.format(conv=conv_num)

    for row_num in sorted(rows.keys()):
        row = rows[row_num]
        en = row.get("en")
        es = row.get("es")

        if not en or not es:
            continue

        en_speaker = "A" if en["speaker"].endswith("_a") else "B"
        es_speaker = "A" if es["speaker"].endswith("_a") else "B"
        en_voice = f"English {en_speaker}"
        es_voice = f"Spanish {es_speaker}"

        html += TEMPLATE_ROW.format(
            en_file=en["file"],
            en_voice=en_voice,
            en_speaker=en_speaker,
            en_text=en["text"],
            es_file=es["file"],
            es_voice=es_voice,
            es_speaker=es_speaker,
            es_text=es["text"],
        )

    html += TEMPLATE_SCRIPT
    return html


def main():
    parser = argparse.ArgumentParser(description="Generate HTML for a conversation.")
    parser.add_argument("conversation", type=int, help="Conversation number")
    args = parser.parse_args()

    conv_num = args.conversation
    out_path = DOCS_DIR / f"{conv_num}.html"

    html = generate_html(conv_num)
    out_path.write_text(html)
    print(f"Written to {out_path}")


if __name__ == "__main__":
    main()
