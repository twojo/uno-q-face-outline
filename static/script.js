/**
 * Smart Mirror AI Booth — Frontend Logic
 * Follows the Arduino Bricks communication pattern from the official examples
 * (image-classification, chatbot-cloud-llm, etc.):
 *
 *   socket.on("connect", …)        ← Socket.IO built-in; connection established
 *   socket.emit("capture", data)   → send frame to backend
 *   socket.on("processing", …)     ← prompt chosen, inference starting
 *   socket.on("result", …)         ← AI image ready
 *   socket.on("transform_error", …)← inference failed
 *   socket.on("disconnect", …)     ← Socket.IO built-in; connection lost
 *
 * On the real Bricks SDK, WebUI handles the Socket.IO transport; the
 * event names and payload shapes here match app.py's ui.send_message /
 * ui.on_message calls exactly.
 */

"use strict";

/* ── Configuration ─────────────────────────────────────────────────── */

/** JPEG quality sent to the backend (0.0–1.0). */
const CAPTURE_QUALITY = 0.85;

/**
 * Camera constraints for getUserMedia.
 * facingMode: "user" = front-facing (selfie) camera.
 * Change to "environment" for the rear camera.
 */
const CAMERA_CONSTRAINTS = {
  video: {
    facingMode: "user",
    width:  { ideal: 640 },
    height: { ideal: 853 },
  },
  audio: false,
};


/* ── DOM references ────────────────────────────────────────────────── */

const video          = document.getElementById("sm-video");
const canvas         = document.getElementById("sm-canvas");
const captureBtn     = document.getElementById("sm-capture-btn");
const newBtn         = document.getElementById("sm-new-btn");
const retryBtn       = document.getElementById("sm-retry-btn");
const resultImg      = document.getElementById("sm-result-img");
const promptBadge    = document.getElementById("sm-prompt-badge");
const promptPreview  = document.getElementById("sm-prompt-preview");
const feedbackPrompt = document.getElementById("sm-feedback-prompt");
const statusDot      = document.getElementById("sm-status-dot");
const statusText     = document.getElementById("sm-status-text");
const errorMsg       = document.getElementById("sm-error-msg");
const progressBar    = document.getElementById("sm-progress-bar");
const elapsedEl      = document.getElementById("sm-elapsed");
const historyList    = document.getElementById("sm-history-list");


/* ── State helpers ─────────────────────────────────────────────────── */

/**
 * Set body[data-state] — CSS uses this to show/hide overlays and buttons.
 * Valid values: "idle" | "processing" | "result" | "error"
 */
function setState(state) {
  document.body.dataset.state = state;
}

/**
 * Set body[data-connection] — CSS pulses the status dot when connected.
 * Valid values: "disconnected" | "connected"
 */
function setConnection(state) {
  document.body.dataset.connection = state;
}

/** Update the subheader status text. */
function setStatus(msg) {
  statusText.textContent = msg;
}


/* ── Elapsed timer & progress bar ──────────────────────────────────── */
/*
 * The progress bar gives visual confirmation the model is running
 * (not frozen). It animates from 0 → 100% over PROGRESS_DURATION_S seconds
 * using a CSS transition driven by JS. If inference takes longer than that,
 * the bar stays full but keeps moving slightly via the spinner.
 * The elapsed counter ticks every second so you can see real time spent.
 */

const PROGRESS_DURATION_S = 90;  // conservative upper bound for HF free tier
let _timerInterval = null;
let _timerSeconds  = 0;

function startTimer() {
  _timerSeconds = 0;
  elapsedEl.textContent = "0s elapsed";

  /* Restart the CSS width transition each capture:
   * 1. Kill transition so the reset to 0% is instant.
   * 2. Force a reflow so the browser registers the 0% width.
   * 3. Re-apply the transition and animate to 100%. */
  progressBar.style.transition = "none";
  progressBar.style.width = "0%";
  void progressBar.offsetWidth;                         // force reflow
  progressBar.style.transition = `width ${PROGRESS_DURATION_S}s linear`;
  progressBar.style.width = "100%";

  clearInterval(_timerInterval);
  _timerInterval = setInterval(() => {
    _timerSeconds++;
    elapsedEl.textContent = `${_timerSeconds}s elapsed`;
  }, 1000);
}

function stopTimer() {
  clearInterval(_timerInterval);
  _timerInterval = null;
  /* Freeze the bar at wherever it reached */
  const computed = getComputedStyle(progressBar).width;
  progressBar.style.transition = "none";
  progressBar.style.width = computed;
}


/* ── History ledger ─────────────────────────────────────────────────── */
/*
 * Mirrors the reference app's "Recent detections" list.
 * Each entry shows: thumbnail · prompt (2-line truncated) · timestamp.
 * Clicking a row restores that result image to the viewport.
 * Keeps at most MAX_HISTORY entries; oldest are trimmed from the bottom.
 */

const MAX_HISTORY = 10;

function addHistoryEntry(data) {
  /* Remove the "No transforms yet" placeholder on first entry */
  const placeholder = historyList.querySelector(".sm-history-empty");
  if (placeholder) placeholder.remove();

  /* Format the time — prefer the server timestamp, fall back to now */
  const ts = data.timestamp ? new Date(data.timestamp) : new Date();
  const timeStr = ts.toLocaleTimeString([], {
    hour: "2-digit", minute: "2-digit", second: "2-digit"
  });
  const elapsedStr = data.elapsed_s != null ? ` · ${data.elapsed_s}s` : "";

  const li = document.createElement("li");
  li.className = "sm-history-entry";
  li.setAttribute("tabindex", "0");
  li.setAttribute("role", "button");
  li.setAttribute("aria-label", `View: ${data.prompt}`);

  const thumb = document.createElement("img");
  thumb.className = "sm-history-thumb";
  thumb.src = data.image;
  thumb.alt = "AI result thumbnail";

  const info = document.createElement("div");
  info.className = "sm-history-info";
  info.innerHTML = `
    <p class="sm-history-prompt">${data.prompt}</p>
    <p class="sm-history-time">${timeStr}${elapsedStr}</p>
  `;

  li.appendChild(thumb);
  li.appendChild(info);

  /* Clicking (or Enter key) restores that result to the viewport */
  const restore = () => {
    resultImg.onload = () => {
      promptBadge.textContent = `Prompt: ${data.prompt}`;
      feedbackPrompt.textContent = data.prompt;
      setState("result");
      captureBtn.disabled = false;
    };
    resultImg.src = data.image;
  };
  li.addEventListener("click", restore);
  li.addEventListener("keydown", (e) => { if (e.key === "Enter") restore(); });

  historyList.prepend(li);

  /* Trim to maximum */
  while (historyList.children.length > MAX_HISTORY) {
    historyList.removeChild(historyList.lastChild);
  }
}


/* ── Socket.IO wiring — mirrors official Bricks app.js pattern ─────── */

/**
 * Official Bricks pattern (from image-classification, chatbot-cloud-llm, etc.):
 *   socket = io(`http://${window.location.host}`)
 *
 * Explicitly naming the host is required so the connection works correctly
 * through Replit's reverse proxy and through the Uno Q's local network.
 * Plain io() can fail in proxied environments because Socket.IO may
 * choose a wrong base path when the origin is ambiguous.
 */
const socket = io(`http://${window.location.host}`);

/**
 * "connect" — Socket.IO built-in event; fires when the WebSocket (or
 * polling) connection to the server is established.
 * Official Bricks pattern uses this instead of a custom "welcome" event.
 * Mirrors image-classification/assets/app.js:
 *   socket.on('connect', () => { errorContainer.style.display = 'none'; })
 */
socket.on("connect", () => {
  setConnection("connected");
  setStatus("Server ready — tap Capture to transform");
  captureBtn.disabled = false;
  // Hide any previous disconnect error
  if (document.body.dataset.state === "error") {
    setState("idle");
  }
});

/**
 * "processing" — emitted by handle_capture() as soon as a prompt is
 * chosen, before the slow HuggingFace inference begins.
 * Shows the chosen prompt in the loading overlay so the user knows
 * what transformation is coming.
 */
socket.on("processing", (data) => {
  setState("processing");
  promptPreview.textContent  = `"${data.prompt}"`;
  feedbackPrompt.textContent = data.prompt;
  startTimer();
});

/**
 * "result" — emitted by handle_capture() after successful inference.
 * data.image is a data-URI; data.prompt is the prompt string.
 * Mirrors the reference's detection handler that populates the UI list.
 */
socket.on("result", (data) => {
  stopTimer();
  addHistoryEntry(data);
  resultImg.onload = () => {
    promptBadge.textContent = `Prompt: ${data.prompt}`;
    feedbackPrompt.textContent = data.prompt;
    setState("result");
    captureBtn.disabled = false;
  };
  resultImg.src = data.image;
});

/**
 * "transform_error" — emitted by handle_capture() if inference fails.
 * Shows an in-viewport error overlay with the message from Python.
 */
socket.on("transform_error", (data) => {
  stopTimer();
  errorMsg.textContent = data.message || "Inference failed — please try again.";
  setState("error");
  captureBtn.disabled = false;
});

/** Handle unexpected socket disconnection. */
socket.on("disconnect", () => {
  setConnection("disconnected");
  setStatus("Disconnected — waiting for server…");
  captureBtn.disabled = true;
});

/** Handle initial connection failure (server not yet up). */
socket.on("connect_error", () => {
  setConnection("disconnected");
  setStatus("Cannot reach server — retrying…");
});


/* ── Camera initialisation ─────────────────────────────────────────── */

/**
 * Request camera access and attach the stream to the <video> element.
 * Shows a readable error if the browser or permissions block access.
 * (Requires HTTPS on Android — Replit's proxy provides this automatically.)
 */
async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    errorMsg.textContent =
      "Your browser does not support camera access.\n" +
      "Open this page in Chrome or Firefox over HTTPS.";
    setState("error");
    setStatus("Camera API unavailable");
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia(CAMERA_CONSTRAINTS);
    video.srcObject = stream;

    video.onloadedmetadata = () => {
      video.play();
      setStatus("Camera live — waiting for server…");
    };
  } catch (err) {
    errorMsg.textContent =
      `Camera denied: ${err.message}\n` +
      "Allow camera access in your browser settings, then tap Try Again.";
    setState("error");
    setStatus("Camera unavailable");

    retryBtn.addEventListener("click", () => location.reload(), { once: true });
  }
}


/* ── Capture handler ───────────────────────────────────────────────── */

captureBtn.addEventListener("click", () => {
  const w = video.videoWidth  || 512;
  const h = video.videoHeight || 682;

  canvas.width  = w;
  canvas.height = h;

  const ctx = canvas.getContext("2d");

  /*
   * The <video> is CSS-flipped with scaleX(-1) for the mirror effect.
   * We undo that flip here so the AI receives a naturally-oriented face.
   * Technique: translate to the right edge, then scale X by -1 before drawing.
   */
  ctx.save();
  ctx.translate(w, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(video, 0, 0, w, h);
  ctx.restore();

  const dataUrl = canvas.toDataURL("image/jpeg", CAPTURE_QUALITY);

  /* Optimistically enter processing state; the "processing" socket event
   * will confirm and populate the prompt text. */
  captureBtn.disabled = true;
  setState("processing");
  promptPreview.textContent = "Choosing transformation…";
  feedbackPrompt.textContent = "…";

  /*
   * socket.emit("capture", data) — mirrors the reference's
   * socket.emit("override_th", threshold) pattern.
   * app.py's ui.on_message("capture", handle_capture) receives this.
   */
  socket.emit("capture", { image: dataUrl });
});


/* ── Secondary actions ─────────────────────────────────────────────── */

/** "New Photo" — returns to the idle live-mirror state. */
newBtn.addEventListener("click", () => {
  resultImg.src              = "";
  promptBadge.textContent    = "";
  promptPreview.textContent  = "";
  feedbackPrompt.textContent = "Tap Capture to start";
  setState("idle");
  captureBtn.disabled = false;
  setStatus("Camera ready — tap Capture to transform");
});

/** "Try Again" inside the error overlay — resets to idle. */
retryBtn.addEventListener("click", () => {
  setState("idle");
  captureBtn.disabled = false;
  setStatus("Camera ready — tap Capture to transform");
});


/* ── Boot ───────────────────────────────────────────────────────────── */
setStatus("Starting camera…");
startCamera();
