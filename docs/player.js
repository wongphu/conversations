// Conversation page player, loaded by every docs/NN.html.
// Must keep working on old iOS Safari: see the "old iOS Safari" gotcha in AGENTS.md.

const speakerIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 9v6h4l5 5V4L7 9H3z"></path><path fill="currentColor" d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"></path><path fill="currentColor" d="M14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"></path></svg>';

// Older iOS Safari (< 14.5) only has the prefixed constructor. The context
// is created on the first tap, since iOS won't start one outside a gesture.
const AudioCtx = window.AudioContext || window.webkitAudioContext;
let ctx = null;
let psolaPromise = null;

// iOS plays Web Audio in the "ambient" session, which the ring/silent
// switch mutes. Ask for "playback", as an <audio> element gets (iOS 16.4+).
if (navigator.audioSession) navigator.audioSession.type = "playback";

// Older iOS has no audioSession API. There, a playing <audio> element
// switches the page into the "playback" session too, so a silent one
// loops for as long as a clip is playing.
const needsSilentTag = !navigator.audioSession &&
  (/iP(hone|ad|od)/.test(navigator.userAgent) ||
   (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1));
let silentTag = null;

function silentWavUrl() {
  const n = 800;  // 0.1 s of 8 kHz, 8-bit mono silence
  const view = new DataView(new ArrayBuffer(44 + n));
  const text = (off, s) => {
    for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + n, true);
  text(8, "WAVEfmt ");
  view.setUint32(16, 16, true);    // fmt chunk size
  view.setUint16(20, 1, true);     // PCM
  view.setUint16(22, 1, true);     // mono
  view.setUint32(24, 8000, true);  // sample rate
  view.setUint32(28, 8000, true);  // byte rate
  view.setUint16(32, 1, true);     // block align
  view.setUint16(34, 8, true);     // bits per sample
  text(36, "data");
  view.setUint32(40, n, true);
  for (let i = 0; i < n; i++) view.setUint8(44 + i, 128);  // 8-bit silence
  return URL.createObjectURL(new Blob([view], { type: "audio/wav" }));
}

function startSilentTag() {
  if (!needsSilentTag) return;
  if (!silentTag) {
    silentTag = document.createElement("audio");
    silentTag.src = silentWavUrl();
    silentTag.loop = true;
  }
  const p = silentTag.play();
  if (p) p.catch((err) => console.warn("Silent-switch workaround failed", err));
}

const bufferCache = new Map();
let currentSource = null;
let currentButton = null;
let currentUrl = null;
// Resolves the promise playClip returned: true when the clip played to
// the end, false when it was stopped, replaced or failed.
let finishCurrent = null;
// Bumped by every stop/play, so a clip that finishes loading after the
// user has moved on (clicked another line, or stopped) is discarded.
let playToken = 0;

const speedSlider = document.getElementById("speed");
const speedValue = document.getElementById("speedValue");

function getSpeedFactor() {
  return 100 / Number(speedSlider.value);
}

// Must run synchronously inside the tap: iOS only unlocks audio (and
// resumes a context it "interrupted", e.g. after a call) from a gesture.
function unlockAudio() {
  startSilentTag();
  if (!ctx) ctx = new AudioCtx();
  if (ctx.state !== "running" && ctx.resume) ctx.resume();
  const silence = ctx.createBufferSource();
  silence.buffer = ctx.createBuffer(1, 1, 22050);
  silence.connect(ctx.destination);
  silence.start(0);
}

// Loaded only when the speed is changed, so a failed load can't take down
// playback at normal speed. The vendored copy is an ES2015 build, since the
// package's own source uses syntax older iOS can't parse.
function loadPsola() {
  if (!psolaPromise) {
    psolaPromise = import("./vendor/stretch-psola.js")
      .then((m) => m.default)
      .catch((err) => { psolaPromise = null; throw err; });
  }
  return psolaPromise;
}

async function fetchDecoded(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  const arrBuf = await resp.arrayBuffer();
  // Older Safari only supports the callback form of decodeAudioData.
  return new Promise((resolve, reject) => {
    ctx.decodeAudioData(arrBuf, resolve, reject);
  });
}

// Caches the promise, not the buffer, so a prefetch and the play that
// follows it share one download.
function getDecoded(url) {
  if (!bufferCache.has(url)) {
    bufferCache.set(url, fetchDecoded(url).catch((err) => {
      bufferCache.delete(url);  // let a later play retry it
      throw err;
    }));
  }
  return bufferCache.get(url);
}

function stretch(psola, audioBuf, factor) {
  const ch = audioBuf.numberOfChannels;
  const sr = audioBuf.sampleRate;
  const out = ctx.createBuffer(ch, Math.ceil(audioBuf.length * factor), sr);
  for (let i = 0; i < ch; i++) {
    const stretched = psola(audioBuf.getChannelData(i), { factor, sampleRate: sr });
    out.getChannelData(i).set(stretched);  // copyToChannel is Safari 14.1+
  }
  return out;
}

// Returns a promise that resolves to true once the clip has played to the
// end, or to false if it is stopped first or can't be played.
async function playClip(url, button) {
  stopSpeaking();
  try {
    unlockAudio();
  } catch (err) {
    console.error("Web Audio unavailable", err);
    button.classList.add("error");
    button.title = "This browser can't play audio";
    return false;
  }
  const token = playToken;
  const ended = new Promise((resolve) => { finishCurrent = resolve; });

  // Mark the line as active right away (while loading), so a second click
  // on it stops it instead of starting a second copy.
  currentButton = button;
  currentUrl = url;
  button.classList.remove("error");
  button.classList.add("playing");
  button.setAttribute("aria-pressed", "true");
  button.closest(".line").classList.add("playing");

  try {
    const buf = await getDecoded(url);
    if (token !== playToken) return ended;
    const factor = getSpeedFactor();
    const psola = factor === 1 ? null : await loadPsola();
    if (token !== playToken) return ended;

    const src = ctx.createBufferSource();
    src.buffer = psola ? stretch(psola, buf, factor) : buf;
    src.connect(ctx.destination);
    src.onended = () => {
      if (currentSource !== src) return;
      const finish = finishCurrent;
      finishCurrent = null;
      stopSpeaking();
      if (finish) finish(true);
    };
    src.start(0);
    currentSource = src;
  } catch (err) {
    if (token !== playToken) return ended;
    console.error("Could not play " + url, err);
    stopSpeaking();
    button.classList.add("error");
    button.title = "Could not load audio (serve the page over http://, not file://)";
  }
  return ended;
}

function stopSpeaking() {
  playToken++;
  if (currentSource) {
    currentSource.onended = null;
    try { currentSource.stop(0); } catch (e) {}
    currentSource = null;
  }
  // During "Play all" the silent tag keeps looping across the pauses:
  // older iOS won't restart it outside a tap.
  if (silentTag && !playAllRunning) silentTag.pause();
  if (currentButton) {
    currentButton.classList.remove("playing");
    currentButton.setAttribute("aria-pressed", "false");
    currentButton.closest(".line").classList.remove("playing");
  }
  currentButton = null;
  currentUrl = null;
  if (finishCurrent) {
    const finish = finishCurrent;
    finishCurrent = null;
    finish(false);
  }
}

function applySpeed() {
  const pct = Number(speedSlider.value);
  speedValue.textContent = pct + "%";
  if (currentSource && currentUrl) {
    // Restart the clip at the new speed. Hand its promise on, so a running
    // "Play all" carries on instead of seeing the restart as a stop.
    const btn = currentButton;
    const finish = finishCurrent;
    finishCurrent = null;
    const restarted = playClip(currentUrl, btn);
    if (finish) restarted.then(finish);
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
  const line = words.textContent.replace(/\s+/g, " ").trim();
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

// Study toggle: blur one language's lines; tapping a blurred line or
// playing it reveals it. Picking a mode hides every line again.
const hint = document.getElementById("hint");
const modeButtons = document.querySelectorAll(".seg button");
Array.prototype.forEach.call(modeButtons, (button) => {
  button.addEventListener("click", () => {
    Array.prototype.forEach.call(modeButtons, (other) => {
      other.setAttribute("aria-pressed", other === button ? "true" : "false");
    });
    document.body.className = button.dataset.mode;
    Array.prototype.forEach.call(document.querySelectorAll(".line.shown"), (line) => {
      line.classList.remove("shown");
    });
    if (hint) {
      hint.textContent = button.dataset.mode
        ? "Say it aloud, then tap the blurred line (or play it) to check."
        : "";
    }
  });
});
document.addEventListener("click", (event) => {
  const line = event.target.closest(".line");
  if (line && (event.target.closest(".words") || event.target.closest(".speak"))) {
    line.classList.add("shown");
  }
});

// "Play all": every row in order, in the languages the study toggle shows
// (both, or only the one that isn't hidden), with a pause between lines.
const PAUSE_BETWEEN_LANGUAGES = 600;  // ms, English to Spanish in one row
const PAUSE_BETWEEN_ROWS = 1200;      // ms, one speaker's turn to the next
const playAllButton = document.getElementById("playAll");
const playAllLabel = document.getElementById("playAllLabel");
let playAllRunning = false;
let playAllRun = 0;
let pauseTimer = null;
let wakePause = null;

// Slower playback gets longer pauses, to keep the same rhythm.
function pause(ms) {
  return new Promise((resolve) => {
    wakePause = resolve;
    pauseTimer = setTimeout(resolve, ms * getSpeedFactor());
  });
}

function scrollToTurn(turn) {
  const rect = turn.getBoundingClientRect();
  const toolbar = document.querySelector(".toolbar").getBoundingClientRect();
  if (rect.top < toolbar.bottom || rect.bottom > window.innerHeight) {
    window.scrollBy(0, rect.top - window.innerHeight / 3);
  }
}

function setPlayAll(running) {
  playAllRunning = running;
  playAllButton.setAttribute("aria-pressed", running ? "true" : "false");
  playAllLabel.textContent = running ? "Stop" : "Play all";
}

function stopPlayAll() {
  playAllRun++;
  clearTimeout(pauseTimer);
  if (wakePause) wakePause();
  wakePause = null;
  setPlayAll(false);
  // A line tapped mid-run is playing now and still needs the silent tag.
  if (silentTag && !currentButton) silentTag.pause();
}

// The languages "Play all" reads in a row: both, or the one not hidden.
function rowLangs() {
  const mode = document.body.className;
  return mode === "hide-es" ? ["en"] : mode === "hide-en" ? ["es"] : ["en", "es"];
}

function clipIn(turn, lang) {
  return turn.querySelector(".line." + lang + " p[data-audio]");
}

async function playAll() {
  const run = ++playAllRun;
  setPlayAll(true);
  const turns = document.querySelectorAll(".turn:not(.head)");
  let first = true;
  for (let t = 0; t < turns.length; t++) {
    // Read the toggle per row, so switching it mid-run takes effect.
    const langs = rowLangs();
    for (let i = 0; i < langs.length; i++) {
      if (!first) await pause(i === 0 ? PAUSE_BETWEEN_ROWS : PAUSE_BETWEEN_LANGUAGES);
      if (run !== playAllRun) return;
      first = false;
      const paragraph = clipIn(turns[t], langs[i]);
      if (i === 0) scrollToTurn(turns[t]);
      const played = playClip(paragraph.dataset.audio, paragraph.querySelector(".speak"));
      // Fetch the next line while this one plays, so a slow download
      // doesn't stretch the pause before it.
      const next = i + 1 < langs.length ? clipIn(turns[t], langs[i + 1])
        : t + 1 < turns.length ? clipIn(turns[t + 1], rowLangs()[0]) : null;
      if (next) getDecoded(next.dataset.audio).catch(() => {});
      const ok = await played;
      // Stopped, failed, or the user tapped a line: end the run.
      if (!ok || run !== playAllRun) {
        if (run === playAllRun) stopPlayAll();
        return;
      }
    }
  }
  stopPlayAll();
}

// A page cached from before "Play all" has no button; the rest still works.
if (playAllButton) {
  playAllButton.addEventListener("click", () => {
    if (playAllRunning) {
      stopPlayAll();
      stopSpeaking();
    } else {
      playAll();
    }
  });
}
