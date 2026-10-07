# Roadmap

Ideas for improving the site, written up on 2026-10-06 after a review of the live pages.
Nothing here is built yet. They're in suggested order: the most help to learners for the
least work first. Tick an item off (or delete it) when it ships.

State of the site at the time: 14 conversations, 13 MB in `docs/`, 0.5–1.5 MB of
audio per conversation; pages have only `charset`/`viewport` meta tags; no favicon (every
page load 404s on `/favicon.ico`), no manifest, no service worker; the index has no
JavaScript.

## Before you start (applies to every item)

- **Old iOS Safari must keep working.** Read the "old iOS Safari" gotcha in `AGENTS.md`
  before touching `docs/player.js`, and feature-detect anything newer.
- **After editing `docs/player.js`, run `scripts/generate_html.py --all`.** Pages load it as
  `player.js?v=<hash>`; `check.py` and the tests flag every page until you rebuild.
- **Test player changes in a real browser.** There is no Node or Chrome on the dev Mac,
  but Brave is installed. Install Playwright in a scratch venv
  (`python3 -m venv pw && pw/bin/pip install playwright`) and launch
  `/Applications/Brave Browser.app/Contents/MacOS/Brave Browser` headless with
  `--autoplay-policy=no-user-gesture-required`, against `python3 -m http.server -d docs`.
  To time playback, wrap `AudioBufferSourceNode.prototype.start`/`stop` in an init script
  and log `performance.now()`; to simulate a slow network, delay `window.fetch` there too.
  That's how the stale-player bug and the "Igualmente" pause were reproduced and fixed.

## 1. Practice mode for Play all — *small*

- [ ] **Why:** the Hide toggles tell learners "Say it aloud, then check", but Play all
  simply skips the hidden language, so there is no way to drill speaking hands-free.
- **What:** in a Hide mode, Play all plays the visible line, waits for the learner to say
  the translation, then plays the hidden line and reveals it (adds `.shown` to its `.line`).
- **How:** all in `docs/player.js` (`playAll`, `rowLangs`). Make the wait the hidden clip's
  duration × ~1.5 plus a second, scaled by `getSpeedFactor()`; the clip is already
  decoded by the prefetch, so `getDecoded(url)` gives its `duration`. Decide whether this
  replaces the current Hide behaviour or is a separate "Practice" button; a separate
  button keeps "listen only to English" available.
- **Done when:** in Hide Spanish, Play all goes EN → pause → ES (revealed) → row pause.

## 2. Offline use and "Add to Home Screen" — *medium*

- [ ] **Why:** learners are often on weak connections (the long pause before "Igualmente"
  was a slow download). A conversation is only 0.5–1.5 MB, so saving it on the phone is
  cheap.
- **How:** `docs/manifest.webmanifest` (name, icons, `display: standalone`) linked from
  every page and the index, plus `docs/sw.js` registered from `player.js` behind
  `if ("serviceWorker" in navigator)` (iOS 11.3+; older iOS just skips it).
- **Watch out:**
  - HTML, `player.js` and `index.html` must be **network-first** (fall back to the cache),
    or we recreate the stale-page bugs that the `?v=` hash fixed.
  - **MP3 URLs are not versioned:** `pipeline.py` re-voices a changed line in place under
    the same filename. So don't cache MP3s forever; use stale-while-revalidate, or key
    them by a hash of `clips.json`.
  - `generate_html.py` must emit the `<link rel="manifest">`; the tests compare pages with
    its output.
- **Done when:** with the network off, a previously opened conversation loads and plays.

## 3. Link previews and a favicon — *small*

- [ ] **Why:** a link shared on WhatsApp currently shows a bare URL (no title or
  description), and every page load 404s on the favicon.
- **How:** in `generate_html.py`, add `<meta name="description">` and Open Graph tags
  (`og:title` like "Shopping · Compras", `og:description` with the level, e.g.
  "A1 · English–Spanish conversation with audio") to pages and the index. Add a PNG
  favicon and an `apple-touch-icon` (180×180) under `docs/`; older Safari ignores SVG
  favicons, so include the PNG.
- **Done when:** pasting a page link in WhatsApp shows its title and description.

## 4. Role-play: be one speaker — *small–medium*

- [ ] **What:** choose "I'm speaker A"; Play all plays only the other speakers' lines and
  leaves a gap (as in #1) for the learner's own lines.
- **How:** each row is `.turn.a` / `.turn.b` / `.turn.c` (speaker letter from
  `generate_html.py`), so `playAll` can skip or pause on the chosen speaker. Needs a small
  speaker picker in the toolbar (template in `generate_html.py`).

## 5. Remember settings and progress — *small*

- [ ] Keep speed and Hide mode between pages, and let learners mark a conversation as
  practised (a tick on the index).
- **How:** `localStorage`, wrapped in try/catch: old iOS private browsing throws on
  `setItem`, and the page must work without it.

## 6. Filter the index by level — *small*

- [ ] A1 / A2 / B1 / B2 buttons above the list. Each row already has
  `<span class="level level-a">A1</span>`; add a `data-level` on the `<li>` and a few
  lines of inline script (the index has none yet). More useful as conversations are added.

## 7. Repeat a line — *small*

- [ ] A loop button, or play-twice, for shadowing one line. Avoid long-press on iOS, which
  triggers text selection and the callout menu.

## 8. Automatic audio checks — *medium*

- [ ] **Why:** `check.py` can't tell whether an MP3 actually says its text (see
  `AGENTS.md`), and TTS can hallucinate, skip words, or cut off an ending. For example,
  the speech in `docs/5/audio/es/13-b.mp3` ("Igualmente.") runs right up to the end of
  the file, so its ending may be clipped. Listen to it first.
- **How:** a `scripts/audit_audio.py [NN]` that:
  - transcribes each clip with the Whisper model `generate_audio.py` already uses
    (`STT_MODEL`, via `mlx_audio.stt`; Apple Silicon only);
  - compares the transcript with the clip text (normalised: lower-case, no punctuation, no
    `*`, numbers spelled out) and flags a high word error rate;
  - flags clips whose duration is an outlier for their text length;
  - flags clips whose last ~30 ms are still loud (likely truncated).
  - Keep it a report: re-voicing stays a manual "delete the MP3, re-run the pipeline"
    step.

## 9. Run the tests on every push — *small*

- [ ] A GitHub Actions workflow (`.github/workflows/tests.yml`) that sets up Python 3.14
  and runs `python -m unittest discover tests`; no `pip install` needed. Checked on
  2026-10-06: the suite passes with site-packages disabled (`.venv/bin/python -S -m
  unittest discover tests`). This catches a broken page or a missing `Level:` line
  before GitHub Pages publishes it.
