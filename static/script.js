/**
 * Smart Mirror AI Booth — Frontend Logic
 * Follows the Arduino Bricks communication pattern from the reference app:
 *
 *   socket.on("welcome", …)        ← server ready
 *   socket.emit("capture", data)   → send frame to backend
 *   socket.on("processing", …)     ← prompt chosen, inference starting
 *   socket.on("result", …)         ← AI image ready
 *   socket.on("transform_error", …)← inference failed
 *
 * On the real Bricks SDK, WebUI handles the Socket.IO transport; the
 * event names and payload shapes here match app.py's ui.send_message /
 * ui.on_message calls exactly.
 *
 * Bricks widget porting notes:
 *   • Swap document.getElementById("sm-…") for
 *       root.querySelector("#sm-…")
 *     where root = the widget's shadow root or container element.
 *   • Socket.IO is provided by the Bricks runtime; replace
 *       const socket = io()
 *     with whatever handle the SDK exposes.
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


/* ── Socket.IO wiring — mirrors reference app.js ───────────────────── */

/**
 * io() with no arguments connects back to the page's own origin.
 * On the Uno Q the real WebUI serves the Socket.IO endpoint on the same
 * host/port, so this call is identical in both environments.
 */
const socket = io();

/**
 * "welcome" — emitted by on_client_connect() in app.py immediately
 * after the browser connects.  Mirrors the reference's welcome handler
 * that sends camera status and pairing secret.
 */
socket.on("welcome", (data) => {
  setConnection("connected");
  setStatus("Server ready — tap Capture to transform");
  captureBtn.disabled = false;
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
});

/**
 * "result" — emitted by handle_capture() after successful inference.
 * data.image is a data-URI; data.prompt is the prompt string.
 * Mirrors the reference's detection handler that populates the UI list.
 */
socket.on("result", (data) => {
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
