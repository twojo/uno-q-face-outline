/**
 * ═══════════════════════════════════════════════════════════════
 *  Smart Mirror AI Booth — Frontend Logic
 *  File: static/script.js
 *
 *  Responsibilities:
 *    1. Start the front-facing camera and display the live feed.
 *    2. On "Capture": grab a video frame, un-flip the mirror
 *       transform, convert to JPEG, and POST to /transform.
 *    3. Manage loading state (spinner overlay + disabled button).
 *    4. Handle all error conditions with an in-frame overlay and
 *       a contextual "Try Again" button.
 *    5. Display the AI result with the chosen prompt badge.
 *    6. Allow the user to reset back to the live mirror view.
 *
 *  Arduino Bricks integration notes:
 *  ─────────────────────────────────
 *  • Wrap all DOM references in a widget-scoped querySelector so
 *    this script works inside a shadow DOM or isolated Bricks widget.
 *    Replace `document.getElementById(...)` calls with:
 *      const root = document.querySelector('.smart-mirror-app');
 *      root.querySelector('#sm-btn-capture');
 *  • The fetch endpoint "/transform" can be made configurable via
 *    a Bricks widget setting, e.g.:
 *      const API_URL = window.SmartMirrorConfig?.apiUrl ?? "/transform";
 *  • All IDs are prefixed "sm-" to avoid collisions with other widgets.
 * ═══════════════════════════════════════════════════════════════
 */

"use strict";

/* ── Configuration ─────────────────────────────────────────────── */

/**
 * Maximum time (ms) to wait for the /transform API before giving up.
 * HuggingFace Inference API can be slow under load — 90 s is safe.
 * Decrease to 30 000 for local/offline models on the Uno Q.
 */
const FETCH_TIMEOUT_MS = 90_000;

/**
 * JPEG quality sent to the backend (0.0–1.0).
 * Lower values reduce upload size and speed up transfer over Wi-Fi.
 */
const CAPTURE_QUALITY = 0.85;

/**
 * Ideal camera resolution requested from the browser.
 * getUserMedia will fall back gracefully if unavailable.
 */
const CAMERA_CONSTRAINTS = {
  video: {
    facingMode: "user",        // front-facing ("environment" for rear)
    width:  { ideal: 640 },
    height: { ideal: 853 },
  },
  audio: false,
};


/* ── DOM references ────────────────────────────────────────────── */
/*
 * All IDs use the "sm-" prefix defined in index.html and style.css.
 */
const video        = document.getElementById("sm-video");
const resultImg    = document.getElementById("sm-result-img");
const canvas       = document.getElementById("sm-canvas");
const btnCapture   = document.getElementById("sm-btn-capture");
const captureLabel = document.getElementById("sm-capture-label");
const btnReset     = document.getElementById("sm-btn-reset");
const btnTryAgain  = document.getElementById("sm-btn-try-again");
const overlayLoad  = document.getElementById("sm-overlay-loading");
const overlayErr   = document.getElementById("sm-overlay-error");
const loadingSub   = document.getElementById("sm-loading-sub");
const promptBadge  = document.getElementById("sm-prompt-badge");
const promptText   = document.getElementById("sm-prompt-text");
const statusBar    = document.getElementById("sm-status-bar");
const errorMsg     = document.getElementById("sm-error-msg");


/* ── UI helpers ────────────────────────────────────────────────── */

/**
 * Update the status bar at the bottom of the screen.
 * @param {string}  msg   - Human-readable status text.
 * @param {boolean} live  - If true, prefix with the animated live dot.
 */
function setStatus(msg, live = true) {
  statusBar.innerHTML = live
    ? `<span class="sm-dot"></span>${msg}`
    : `<span style="color:var(--sm-muted)">${msg}</span>`;
}

/**
 * Show one overlay (loading or error) and hide the other.
 * Pass null to hide all overlays.
 * @param {HTMLElement|null} el
 */
function showOverlay(el) {
  [overlayLoad, overlayErr].forEach(o => o.classList.add("hidden"));
  if (el) el.classList.remove("hidden");
}

/**
 * Show the error overlay with a message and configure the Try Again button.
 * @param {string}  msg            - Error message shown to the user.
 * @param {boolean} reloadOnRetry  - If true, clicking Try Again reloads the
 *                                   page (used for camera permission errors).
 */
function showError(msg, reloadOnRetry = false) {
  errorMsg.textContent  = msg;
  btnTryAgain.onclick   = reloadOnRetry ? () => location.reload() : resetToMirror;
  showOverlay(overlayErr);

  // Disable capture while in the error state — user must use Try Again
  btnCapture.disabled      = true;
  captureLabel.textContent = "Capture";
}

/**
 * Reset the entire UI back to the live mirror view.
 * Called by the "New Photo" button and by the Try Again handler on
 * non-camera errors.
 */
function resetToMirror() {
  // Hide result, restore video
  resultImg.style.display  = "none";
  resultImg.src            = "";
  promptBadge.style.display = "none";
  video.style.display      = "block";

  // Clear overlays and button states
  showOverlay(null);
  btnReset.style.display   = "none";
  btnCapture.disabled      = false;
  captureLabel.textContent = "Capture";

  setStatus("Camera ready — tap Capture to transform");
}


/* ── Camera initialisation ─────────────────────────────────────── */

/**
 * Request camera access and attach the stream to the <video> element.
 * Shows an error overlay if permission is denied or the API is absent.
 */
async function startCamera() {
  // Guard: ensure the browser supports getUserMedia (HTTPS required on Android)
  if (!navigator.mediaDevices?.getUserMedia) {
    showError(
      "Your browser does not support camera access.\n" +
      "Open this page in Chrome or Firefox over HTTPS.",
      true   // reload on retry
    );
    setStatus("Camera API unavailable", false);
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia(CAMERA_CONSTRAINTS);
    video.srcObject = stream;

    // Enable the Capture button only once the video is actually playing
    video.onloadedmetadata = () => {
      video.play();
      btnCapture.disabled      = false;
      captureLabel.textContent = "Capture";
      setStatus("Camera ready — tap Capture to transform");
    };

  } catch (err) {
    // Common errors: NotAllowedError (permission denied), NotFoundError (no camera)
    showError(
      `Camera denied: ${err.message}\n` +
      "Allow camera access in your browser settings, then tap Try Again.",
      true   // reload on retry
    );
    setStatus("Camera unavailable", false);
  }
}


/* ── Capture & transform ───────────────────────────────────────── */

/**
 * Main capture handler:
 *  1. Draw the current video frame to the hidden canvas.
 *  2. Un-flip the CSS mirror transform so the AI sees natural orientation.
 *  3. Encode as JPEG and POST to /transform with a timeout.
 *  4. Display the returned AI image with the chosen prompt.
 */
btnCapture.addEventListener("click", async () => {

  /* ── Step 1: Grab frame from the live video ─────────────────── */
  const w = video.videoWidth  || 512;
  const h = video.videoHeight || 682;

  canvas.width  = w;
  canvas.height = h;

  const ctx = canvas.getContext("2d");

  /*
   * The <video> element has CSS transform: scaleX(-1) applied for the
   * mirror effect. We undo that here by translating + scaling the canvas
   * context so the captured image is in its natural (non-mirrored) state.
   * The AI model should receive a correctly-oriented face, not a reflection.
   */
  ctx.save();
  ctx.translate(w, 0);
  ctx.scale(-1, 1);
  ctx.drawImage(video, 0, 0, w, h);
  ctx.restore();

  const dataUrl = canvas.toDataURL("image/jpeg", CAPTURE_QUALITY);


  /* ── Step 2: Enter loading state ─────────────────────────────── */
  btnCapture.disabled       = true;
  captureLabel.textContent  = "Processing…";
  btnReset.style.display    = "none";
  promptBadge.style.display = "none";
  showOverlay(overlayLoad);
  loadingSub.textContent    = "Sending frame to Hugging Face…";
  setStatus("Waiting for AI model…", false);


  /* ── Step 3: POST to /transform with AbortController timeout ─── */
  const controller = new AbortController();
  const timeoutId  = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const res = await fetch("/transform", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ image: dataUrl }),
      signal:  controller.signal,
    });

    clearTimeout(timeoutId);

    /*
     * Surface non-2xx HTTP responses as errors — e.g. 500 from a crashed
     * model worker or 429 from HuggingFace rate limiting.
     */
    if (!res.ok) {
      const text = await res.text().catch(() => `HTTP ${res.status}`);
      throw new Error(`Server error ${res.status}: ${text}`);
    }

    const data = await res.json();
    if (!data.success) {
      throw new Error(data.error || "Unknown server error");
    }


    /* ── Step 4: Display the AI result ───────────────────────────── */
    /*
     * Wait for the image to fully load before swapping the view.
     * This prevents a flash of empty content.
     */
    resultImg.onload = () => {
      video.style.display       = "none";
      resultImg.style.display   = "block";
      promptText.textContent    = data.prompt;
      promptBadge.style.display = "block";
      showOverlay(null);
      btnReset.style.display    = "inline-block";
      captureLabel.textContent  = "Capture";
      setStatus("Transformation complete!", false);
    };

    resultImg.src = data.image;

  } catch (err) {
    clearTimeout(timeoutId);

    /* Build a user-friendly error message based on the failure type */
    let msg;
    if (err.name === "AbortError") {
      msg =
        `Request timed out after ${FETCH_TIMEOUT_MS / 1000} s.\n` +
        "The AI model may be busy — please try again.";
    } else if (!navigator.onLine) {
      msg = "No internet connection detected.\nCheck your network and try again.";
    } else {
      msg = err.message || "An unexpected error occurred.";
    }

    showError(msg, false);   // Try Again → resetToMirror (not reload)
    setStatus("Error — see details in the frame", false);
  }
});


/* ── Reset button ──────────────────────────────────────────────── */
/*
 * "New Photo" button appears after a successful transform.
 * Clicking it returns to the live mirror view.
 */
btnReset.addEventListener("click", resetToMirror);

/*
 * btnTryAgain.onclick is assigned dynamically inside showError()
 * because it needs different behaviour for camera vs. API errors.
 */


/* ── Boot ──────────────────────────────────────────────────────── */
setStatus("Starting camera…", false);
startCamera();
