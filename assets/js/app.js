// SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
// SPDX-License-Identifier: MIT
//
// Wojo's Uno Q Face Outline Demo — Application Logic
// Separated from index.html for maintainability.
//
// This module handles:
//   - MediaPipe Face Landmarker initialization
//   - Camera capture and face detection
//   - Landmark sanity validation (delegate auto-switching)
//   - Multi-face tracking with persistent IDs
//   - Canvas overlay rendering (mesh, outline, iris, emojis)
//   - System stats polling
//   - Adaptive performance throttling

function showFatalError(title, detail, suggestions) {
    const viewport = document.querySelector(".viewport");
    const errorDiv = document.createElement("div");
    errorDiv.className = "camera-error";
    let html = '<h2>' + title + '</h2>' +
        '<p>' + detail + '</p>';
    if (suggestions && suggestions.length > 0) {
        html += '<ol class="cam-steps">';
        for (const s of suggestions) html += '<li>' + s + '</li>';
        html += '</ol>';
    }
    html += '<p style="margin-top:16px"><button onclick="location.reload()" style="' +
        'padding:8px 24px;border:1px solid #60a5fa;border-radius:6px;background:transparent;' +
        'color:#60a5fa;cursor:pointer;font-family:inherit;font-size:13px">Retry</button></p>';
    errorDiv.innerHTML = html;
    viewport.appendChild(errorDiv);
    document.getElementById("diagPanel").style.display = "block";
}

function setDiag(id, status, info) {
    const row = document.getElementById(id);
    const dot = row.querySelector(".diag-dot");
    const detail = document.getElementById(id + "Info");
    dot.className = "diag-dot dot-" + status;
    detail.textContent = info;
}

const testCanvas = document.createElement("canvas");
const gl = testCanvas.getContext("webgl2") || testCanvas.getContext("webgl") || testCanvas.getContext("experimental-webgl");
if (gl) {
    const renderer = gl.getParameter(gl.RENDERER);
    setDiag("dWebGL", "ok", (gl.getParameter(gl.VERSION)) + " — " + renderer);
} else {
    setDiag("dWebGL", "fail", "No WebGL — face detection requires a browser with WebGL");
}

let FaceLandmarker, FilesetResolver, DrawingUtils;
try {
    const mp = await import("https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/+esm");
    FaceLandmarker = mp.FaceLandmarker;
    FilesetResolver = mp.FilesetResolver;
    DrawingUtils = mp.DrawingUtils;
    setDiag("dImport", "ok", "tasks-vision 0.10.3 loaded");
} catch (e) {
    setDiag("dImport", "fail", e.message || String(e));
    showFatalError(
        "Cannot Load Face Detection Engine",
        "MediaPipe could not be downloaded from cdn.jsdelivr.net. This usually means the board has no internet connection yet.",
        [
            "Make sure your Uno Q is connected to <strong>Wi-Fi</strong> (check App Lab > Settings > Network)",
            "If you just updated the firmware, the board may need a moment to reconnect — wait 15-30 seconds and hit <strong>Retry</strong>",
            "If behind a corporate firewall, ensure <strong>cdn.jsdelivr.net</strong> and <strong>storage.googleapis.com</strong> are allowed",
            "Try opening <a href=\"https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/+esm\" target=\"_blank\">this link</a> in a browser tab — if it fails, the network is the issue"
        ]
    );
    throw e;
}

let wasm;
try {
    wasm = await FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.3/wasm"
    );
    setDiag("dWasm", "ok", "WASM fileset resolved");
} catch (e) {
    setDiag("dWasm", "fail", e.message || String(e));
    showFatalError(
        "WASM Runtime Failed to Load",
        "The MediaPipe WASM engine could not be initialized. This is usually a network or memory issue.",
        [
            "Check your <strong>internet connection</strong> — the WASM files are ~4 MB from cdn.jsdelivr.net",
            "If on a 2 GB Uno Q, close other browser tabs to free memory",
            "Wait a moment and hit <strong>Retry</strong> — the CDN may have been temporarily slow"
        ]
    );
    throw e;
}

let fl = null;
let usedDelegate = "none";

async function tryDelegate(delegate) {
    const cfg = {
        baseOptions: {
            modelAssetPath: "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
            delegate: delegate
        },
        outputFaceBlendshapes: true,
        runningMode: "VIDEO",
        numFaces: 4,
        minFaceDetectionConfidence: 0.3,
        minFacePresenceConfidence: 0.3,
        minTrackingConfidence: 0.3
    };
    return await FaceLandmarker.createFromOptions(wasm, cfg);
}

try {
    fl = await tryDelegate("CPU");
    usedDelegate = "CPU";
    setDiag("dModel", "ok", "Loaded with CPU delegate (reliable)");
} catch (cpuErr) {
    setDiag("dModel", "warn", "CPU failed: " + cpuErr.message.slice(0, 60) + "... trying GPU");
    try {
        fl = await tryDelegate("GPU");
        usedDelegate = "GPU";
        setDiag("dModel", "ok", "Loaded with GPU delegate (CPU unavailable)");
    } catch (gpuErr) {
        setDiag("dModel", "fail", "Both CPU and GPU failed: " + gpuErr.message.slice(0, 80));
        showFatalError(
            "Face Detection Model Failed to Load",
            "The face landmarker model (~4 MB) could not be downloaded or initialized with either CPU or GPU delegates.",
            [
                "Check that <strong>storage.googleapis.com</strong> is reachable from this device",
                "If you just updated the board firmware, the network stack may still be initializing — wait 30 seconds and <strong>Retry</strong>",
                "On a 2 GB board, memory pressure can cause model allocation failures — close other tabs",
                "CPU error: " + cpuErr.message.slice(0, 60),
                "GPU error: " + gpuErr.message.slice(0, 60)
            ]
        );
        throw gpuErr;
    }
}

document.getElementById("specDel").textContent = usedDelegate;

const SANITY = {
    state: "UNTESTED",
    framesChecked: 0,
    framesPassed: 0,
    framesFailed: 0,
    framesToCheck: 5,
    passThreshold: 3,
    lastContinuousCheck: 0,
    continuousIntervalMs: 60000,
    switchAttempted: false,
    failReasons: []
};

function validateLandmarks(landmarks) {
    const checks = { passed: true, reasons: [] };
    const n = landmarks.length;

    if (n !== 478) {
        checks.passed = false;
        checks.reasons.push("count=" + n + " (expected 478)");
        return checks;
    }

    let minX = 1, maxX = 0, minY = 1, maxY = 0;
    for (let i = 0; i < n; i++) {
        const lm = landmarks[i];
        if (lm.x < minX) minX = lm.x;
        if (lm.x > maxX) maxX = lm.x;
        if (lm.y < minY) minY = lm.y;
        if (lm.y > maxY) maxY = lm.y;
    }
    const spanX = maxX - minX;
    const spanY = maxY - minY;

    if (spanX < 0.03 || spanY < 0.03) {
        checks.passed = false;
        checks.reasons.push("collapsed: span=" + spanX.toFixed(3) + "x" + spanY.toFixed(3));
    }

    let outOfBounds = 0;
    for (let i = 0; i < n; i++) {
        const lm = landmarks[i];
        if (lm.x < -0.2 || lm.x > 1.2 || lm.y < -0.2 || lm.y > 1.2) outOfBounds++;
    }
    if (outOfBounds > 20) {
        checks.passed = false;
        checks.reasons.push("OOB=" + outOfBounds + "/478");
    }

    const nose = landmarks[1];
    const faceCenterX = (minX + maxX) / 2;
    const faceCenterY = (minY + maxY) / 2;
    const noseDriftX = Math.abs(nose.x - faceCenterX) / (spanX || 0.001);
    const noseDriftY = Math.abs(nose.y - faceCenterY) / (spanY || 0.001);
    if (noseDriftX > 0.6 || noseDriftY > 0.6) {
        checks.passed = false;
        checks.reasons.push("nose-drift: dx=" + noseDriftX.toFixed(2) + " dy=" + noseDriftY.toFixed(2));
    }

    const eyeL = landmarks[468];
    const eyeR = landmarks[473];
    const eyeDist = Math.sqrt(Math.pow(eyeL.x - eyeR.x, 2) + Math.pow(eyeL.y - eyeR.y, 2));
    if (eyeDist < 0.02 || eyeDist > 0.5) {
        checks.passed = false;
        checks.reasons.push("eye-dist=" + eyeDist.toFixed(3) + " (expect 0.02-0.5)");
    }

    const forehead = landmarks[10];
    const chin = landmarks[152];
    if (forehead.y > chin.y + 0.02) {
        checks.passed = false;
        checks.reasons.push("inverted: forehead.y=" + forehead.y.toFixed(3) + " > chin.y=" + chin.y.toFixed(3));
    }

    return checks;
}

async function switchToDelegate(newDelegate) {
    console.log("[SANITY] Switching delegate to " + newDelegate + "...");
    setDiag("dSanity", "warn", "Switching to " + newDelegate + " delegate...");
    setDiag("dModel", "warn", "Reloading model with " + newDelegate + " delegate...");
    try {
        fl = await tryDelegate(newDelegate);
        usedDelegate = newDelegate;
        document.getElementById("specDel").textContent = newDelegate;
        setDiag("dModel", "ok", "Reloaded with " + newDelegate + " delegate");
        SANITY.state = "VALIDATING";
        SANITY.framesChecked = 0;
        SANITY.framesPassed = 0;
        SANITY.framesFailed = 0;
        SANITY.failReasons = [];
        console.log("[SANITY] Delegate switched to " + newDelegate + ", re-validating...");
    } catch (e) {
        SANITY.state = "FAILED_PERMANENT";
        console.error("[SANITY] Failed to switch to " + newDelegate + ":", e);
        setDiag("dSanity", "fail", "Unrecoverable: " + newDelegate + " load failed — " + e.message.slice(0, 50));
    }
}

function runSanityCheck(landmarks) {
    const result = validateLandmarks(landmarks);

    if (SANITY.state === "UNTESTED") {
        SANITY.state = "VALIDATING";
        console.log("[SANITY] First face detected — starting validation (" + SANITY.framesToCheck + " frames)");
    }

    if (SANITY.state === "VALIDATING") {
        SANITY.framesChecked++;

        if (result.passed) {
            SANITY.framesPassed++;
        } else {
            SANITY.framesFailed++;
            SANITY.failReasons.push(result.reasons.join(", "));
            console.warn("[SANITY] Frame " + SANITY.framesChecked + "/" + SANITY.framesToCheck +
                " FAILED: " + result.reasons.join(", "));
        }

        setDiag("dSanity", "warn",
            "Validating: " + SANITY.framesPassed + "/" + SANITY.framesChecked +
            " passed (" + SANITY.framesToCheck + " needed)");

        if (SANITY.framesChecked >= SANITY.framesToCheck) {
            if (SANITY.framesPassed >= SANITY.passThreshold) {
                SANITY.state = "PASSED";
                SANITY.lastContinuousCheck = performance.now();
                const msg = usedDelegate + " delegate validated (" +
                    SANITY.framesPassed + "/" + SANITY.framesToCheck + " frames OK)";
                console.log("[SANITY] " + msg);
                setDiag("dSanity", "ok", msg);
            } else {
                SANITY.state = "FAILED";
                const msg = usedDelegate + " delegate FAILED validation (" +
                    SANITY.framesPassed + "/" + SANITY.framesToCheck + " passed). " +
                    "Issues: " + SANITY.failReasons.slice(0, 3).join("; ");
                console.error("[SANITY] " + msg);
                setDiag("dSanity", "fail", msg);

                if (!SANITY.switchAttempted && usedDelegate === "GPU") {
                    SANITY.switchAttempted = true;
                    SANITY.state = "RECOVERING";
                    console.log("[SANITY] Auto-switching from GPU to CPU...");
                    switchToDelegate("CPU");
                } else if (!SANITY.switchAttempted && usedDelegate === "CPU") {
                    SANITY.switchAttempted = true;
                    SANITY.state = "RECOVERING";
                    console.log("[SANITY] CPU failed — trying GPU as last resort...");
                    switchToDelegate("GPU");
                }
            }
        }
        return;
    }

    if (SANITY.state === "PASSED") {
        const now = performance.now();
        if (now - SANITY.lastContinuousCheck >= SANITY.continuousIntervalMs) {
            SANITY.lastContinuousCheck = now;
            if (!result.passed) {
                SANITY.state = "DEGRADED";
                console.warn("[SANITY] Continuous check failed: " + result.reasons.join(", "));
                setDiag("dSanity", "warn", "Degraded: " + result.reasons.join(", "));
            }
        }
    }

    if (SANITY.state === "DEGRADED") {
        const now = performance.now();
        if (now - SANITY.lastContinuousCheck >= SANITY.continuousIntervalMs) {
            SANITY.lastContinuousCheck = now;
            if (result.passed) {
                SANITY.state = "PASSED";
                setDiag("dSanity", "ok", usedDelegate + " delegate recovered — landmarks OK");
                console.log("[SANITY] Recovered from DEGRADED state");
            }
        }
    }
}

const tess = FaceLandmarker.FACE_LANDMARKS_TESSELATION;
const oval = FaceLandmarker.FACE_LANDMARKS_FACE_OVAL;
const tessType = tess ? (Array.isArray(tess[0]) ? "array-tuples" : (tess[0] && tess[0].start !== undefined ? "start-end-objects" : "unknown:" + JSON.stringify(tess[0]))) : "null";
console.log("[DIAG] TESSELATION type:", tessType, "length:", tess ? tess.length : 0, "OVAL length:", oval ? oval.length : 0);
console.log("[DIAG] Sample connection:", tess ? JSON.stringify(tess[0]) : "none");

const cam = document.getElementById("cam");
const cvs = document.getElementById("overlay");
const ctx = cvs.getContext("2d");
const presetEl = document.getElementById("preset");
const hudBL = document.getElementById("hudBL");
const faceListEl = document.getElementById("faceList");

let du = new DrawingUtils(ctx);

let cameraStream = null;
try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false
    });
    cam.srcObject = cameraStream;
    await new Promise(r => { cam.onloadeddata = r; });
    await cam.play();
    await new Promise(r => setTimeout(r, 200));

    const vw = cam.videoWidth, vh = cam.videoHeight;
    const mp = ((vw * vh) / 1000000).toFixed(1);
    document.getElementById("hRes").textContent = vw + "\u00D7" + vh;

    const track = cameraStream.getVideoTracks()[0];
    const settings = track.getSettings();
    const caps = track.getCapabilities ? track.getCapabilities() : {};
    const camLabel = track.label || "Unknown Camera";

    const fpsActual = settings.frameRate ? Math.round(settings.frameRate) : "?";
    const fpsMax = caps.frameRate && caps.frameRate.max ? Math.round(caps.frameRate.max) : null;
    const maxW = caps.width && caps.width.max ? caps.width.max : null;
    const maxH = caps.height && caps.height.max ? caps.height.max : null;
    const maxRes = (maxW && maxH) ? (maxW + "x" + maxH + " (" + ((maxW*maxH)/1000000).toFixed(1) + "MP)") : null;
    const facingMode = settings.facingMode || "user";

    let camSpecParts = [vw + "x" + vh + " (" + mp + "MP)", fpsActual + "fps"];
    if (maxRes) camSpecParts.push("max " + maxRes);
    camSpecParts.push(facingMode);

    const camSpecStr = camSpecParts.join(" | ");
    const diagDetail = camLabel + " — " + camSpecStr;
    setDiag("dCamera", "ok", diagDetail);

    document.getElementById("specCam").textContent = vw + "x" + vh + " " + mp + "MP " + fpsActual + "fps";
    document.getElementById("specCamChip").style.display = "";

    console.log("[CAMERA] Device: " + camLabel);
    console.log("[CAMERA] Active: " + vw + "x" + vh + " @ " + fpsActual + "fps (" + mp + "MP)");
    console.log("[CAMERA] Facing: " + facingMode);
    if (maxRes) console.log("[CAMERA] Max resolution: " + maxRes);
    if (fpsMax) console.log("[CAMERA] Max framerate: " + fpsMax + "fps");
    console.log("[CAMERA] Settings:", JSON.stringify(settings));
    if (Object.keys(caps).length > 0) console.log("[CAMERA] Capabilities:", JSON.stringify(caps));

} catch (e) {
    const errMsg = e.message || String(e);
    const isNotFound = e.name === "NotFoundError" || e.name === "DevicesNotFoundError" ||
                       errMsg.includes("Requested device not found") || errMsg.includes("no device");
    const isDenied = e.name === "NotAllowedError" || e.name === "PermissionDeniedError";

    let diagMsg = errMsg;
    if (isNotFound) diagMsg = "No camera detected — plug in a USB webcam";
    else if (isDenied) diagMsg = "Camera permission denied — allow access in browser settings";

    setDiag("dCamera", "fail", diagMsg);

    const viewport = document.querySelector(".viewport");
    const errorDiv = document.createElement("div");
    errorDiv.className = "camera-error";

    if (isNotFound) {
        errorDiv.innerHTML = '<h2>No Camera Detected</h2>' +
            '<p>This demo requires a webcam to track faces in real time.</p>' +
            '<ol class="cam-steps">' +
            '<li>Plug a <strong>USB webcam</strong> into any USB port on the Uno Q (or your computer)</li>' +
            '<li>Wait 2-3 seconds for the device to be recognized</li>' +
            '<li>Refresh this page to retry camera detection</li>' +
            '</ol>' +
            '<p style="font-size:11px;color:var(--muted)">Compatible with any UVC-class USB camera. ' +
            'Recommended: 720p or higher, 30fps capable.</p>' +
            '<p style="margin-top:12px"><a href="https://docs.arduino.cc/tutorials/uno-q/getting-started/" target="_blank">Uno Q Setup Guide</a> · ' +
            '<a href="https://store.arduino.cc/collections/arduino-days-promo/products/uno-q-4gb" target="_blank">Get Uno Q</a></p>';
    } else if (isDenied) {
        errorDiv.innerHTML = '<h2>Camera Access Denied</h2>' +
            '<p>The browser blocked camera access. To fix this:</p>' +
            '<ol class="cam-steps">' +
            '<li>Click the <strong>camera icon</strong> in your browser\'s address bar</li>' +
            '<li>Select <strong>"Allow"</strong> for camera access</li>' +
            '<li>Refresh this page</li>' +
            '</ol>' +
            '<p style="font-size:11px;color:var(--muted)">On the Uno Q, make sure the browser is running with camera permissions enabled.</p>';
    } else {
        errorDiv.innerHTML = '<h2>Camera Error</h2>' +
            '<p>' + errMsg + '</p>' +
            '<p style="font-size:11px;color:var(--muted)">Try unplugging and reconnecting the camera, then refresh.</p>';
    }

    viewport.appendChild(errorDiv);
    throw e;
}

cvs.width = cam.videoWidth;
cvs.height = cam.videoHeight;
du = new DrawingUtils(ctx);

ctx.fillStyle = "rgba(0,255,0,0.3)";
ctx.fillRect(0, 0, cvs.width, cvs.height);
ctx.font = "bold 24px Inter";
ctx.fillStyle = "#00ff00";
ctx.textAlign = "center";
ctx.fillText("CANVAS OK — WAITING FOR FACE...", cvs.width / 2, cvs.height / 2);
setDiag("dCanvas", "ok", cvs.width + "x" + cvs.height + " — drawing test passed");

const sysStats = {
    cpu_pct: 0, ram_pct: 0, ram_used_mb: 0, ram_total_mb: 0,
    ip: "...", disk_pct: 0, cpu_temp_c: null, py_rss_mb: 0,
    cpu_count: 0, net_ifaces: {}, lastFetch: 0
};
const SYS_POLL_MS = 2000;

async function pollSysStats() {
    try {
        const r = await fetch("/api/stats");
        if (!r.ok) {
            document.getElementById("hSysLine").textContent = "SYS: server error (" + r.status + ")";
            return;
        }
        const d = await r.json();
        Object.assign(sysStats, d);
        sysStats.lastFetch = performance.now();

        const parts = [];
        parts.push("CPU " + d.cpu_pct.toFixed(0) + "%" + (d.cpu_count ? " \u00D7" + d.cpu_count : ""));
        parts.push("RAM " + d.ram_used_mb + "/" + d.ram_total_mb + "MB (" + d.ram_pct.toFixed(0) + "%)");
        parts.push("IP " + d.ip);
        if (d.cpu_temp_c !== null) parts.push("Temp " + d.cpu_temp_c.toFixed(0) + "\u00B0C");
        parts.push("Disk " + d.disk_pct.toFixed(0) + "%");
        parts.push("Flask " + d.py_rss_mb + "MB");

        document.getElementById("hSysLine").textContent = parts.join("  \u2502  ");
    } catch (e) {
        document.getElementById("hSysLine").textContent = "SYS: offline";
    }
}
pollSysStats();
setInterval(pollSysStats, SYS_POLL_MS);

function drawSysOverlay(ctx, w, h) {
    if (!sysStats.lastFetch) return;

    ctx.save();
    ctx.translate(w - 8, 60);
    ctx.scale(-1, 1);

    ctx.font = "10px 'JetBrains Mono', monospace";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";

    const lines = [];
    lines.push("CPU " + sysStats.cpu_pct.toFixed(0) + "% \u00D7" + sysStats.cpu_count);
    lines.push("RAM " + sysStats.ram_used_mb + "/" + sysStats.ram_total_mb + "MB");

    const barW = 50, barH = 4;
    const cpuFrac = Math.min(sysStats.cpu_pct / 100, 1);
    const ramFrac = Math.min(sysStats.ram_pct / 100, 1);

    const lineH = 14;
    const totalH = lines.length * lineH + 2 * lineH + 12;
    const bgW = 160;

    ctx.fillStyle = "rgba(0,0,0,0.35)";
    ctx.beginPath();
    ctx.roundRect(-4, -4, bgW, totalH, 4);
    ctx.fill();

    let y = 0;

    ctx.fillStyle = "rgba(200,220,255,0.55)";
    ctx.fillText(lines[0], 0, y);
    y += lineH;
    ctx.fillStyle = "rgba(0,0,0,0.4)";
    ctx.fillRect(0, y, barW, barH);
    ctx.fillStyle = cpuFrac > 0.8 ? "rgba(255,80,80,0.7)" : "rgba(80,200,120,0.6)";
    ctx.fillRect(0, y, barW * cpuFrac, barH);
    y += lineH;

    ctx.fillStyle = "rgba(200,220,255,0.55)";
    ctx.fillText(lines[1], 0, y);
    y += lineH;
    ctx.fillStyle = "rgba(0,0,0,0.4)";
    ctx.fillRect(0, y, barW, barH);
    ctx.fillStyle = ramFrac > 0.8 ? "rgba(255,80,80,0.7)" : "rgba(100,160,255,0.6)";
    ctx.fillRect(0, y, barW * ramFrac, barH);
    y += lineH;

    ctx.fillStyle = "rgba(200,220,255,0.45)";
    ctx.fillText("IP " + sysStats.ip, 0, y);
    y += lineH;
    if (sysStats.cpu_temp_c !== null) {
        ctx.fillText("Temp " + sysStats.cpu_temp_c.toFixed(0) + "\u00B0C", 0, y);
        y += lineH;
    }
    ctx.fillText("Disk " + sysStats.disk_pct.toFixed(0) + "%  Flask " + sysStats.py_rss_mb + "MB", 0, y);

    ctx.restore();
}

const FACE_COLORS = [
    { mesh: "rgba(120,160,255,0.55)", edge: "rgba(90,160,255,0.95)",  feat: "rgba(100,180,255,1)", iris: "rgba(0,220,255,1)",  dot: "rgba(90,160,255,0.7)",  tag: "#7799ff" },
    { mesh: "rgba(255,190,80,0.55)", edge: "rgba(255,190,70,0.95)", feat: "rgba(255,200,80,1)", iris: "rgba(255,220,90,1)",  dot: "rgba(255,190,70,0.7)", tag: "#ffbb44" },
    { mesh: "rgba(100,240,170,0.55)", edge: "rgba(90,240,160,0.95)", feat: "rgba(100,250,180,1)", iris: "rgba(120,255,200,1)", dot: "rgba(90,240,160,0.7)", tag: "#66ee99" },
    { mesh: "rgba(240,150,240,0.55)", edge: "rgba(240,140,240,0.95)", feat: "rgba(250,160,250,1)", iris: "rgba(255,170,255,1)", dot: "rgba(240,140,240,0.7)", tag: "#ee88ee" },
];

const PRESETS = {
    full:    { mesh:1, outline:1, eyes:1, brows:1, lips:1, iris:1, dots:1, emojis:1 },
    outline: { mesh:0, outline:1, eyes:1, brows:1, lips:1, iris:1, dots:0, emojis:1 },
    mesh:    { mesh:1, outline:0, eyes:0, brows:0, lips:0, iris:0, dots:0, emojis:0 },
    dots:    { mesh:0, outline:0, eyes:0, brows:0, lips:0, iris:0, dots:1, emojis:0 },
    minimal: { mesh:0, outline:1, eyes:0, brows:0, lips:0, iris:1, dots:0, emojis:0 },
    emojis:  { mesh:0, outline:1, eyes:0, brows:0, lips:1, iris:0, dots:0, emojis:1 },
};

let L = { ...PRESETS.full };
presetEl.onchange = () => { L = { ...PRESETS[presetEl.value] }; };

const PERF = {
    skipFrames: 0,
    fpsHistory: [],
    fpsWindowSize: 5,
    lowFpsThreshold: 8,
    highFpsThreshold: 14,
    isThrottled: false,
    checkInterval: 2000,
    lastCheck: 0,
};
let frameSkipCounter = 0;
const MAX_FACES = 4;

let cW = cvs.width, cH = cvs.height;
let fpsCnt = 0, fpsT = 0, fps = 0, total = 0;
const startTime = performance.now();
let lastHud = 0;
let lastVideoTime = -1;
let latMs = 0, nFaces = 0, yaw = 0, pitch = 0;
let hudBlinkL = 0, hudBlinkR = 0;
let hudPupilL = 0, hudPupilR = 0;

function measureIris(lm, centerIdx, edgeIndices, vw, vh) {
    var c = lm[centerIdx];
    if (!c) return null;
    var totalR = 0, cnt = 0;
    for (var ei = 0; ei < edgeIndices.length; ei++) {
        var e = lm[edgeIndices[ei]];
        if (!e) continue;
        var dx = (e.x - c.x) * vw, dy = (e.y - c.y) * vh;
        totalR += Math.sqrt(dx * dx + dy * dy);
        cnt++;
    }
    if (cnt === 0) return null;
    var avgR = totalR / cnt;
    var diamPx = avgR * 2;
    var diamMm = (diamPx / vw) * 280;
    return { cx: c.x * vw, cy: c.y * vh, r: avgR, diamPx: diamPx, diamMm: diamMm };
}

function drawPupilOverlay(ctx, iris, label) {
    if (!iris) return;
    ctx.strokeStyle = "rgba(255,40,40,0.9)";
    ctx.lineWidth = 2.5;
    ctx.setLineDash([4, 3]);
    ctx.beginPath();
    ctx.arc(iris.cx, iris.cy, iris.r, 0, 6.283);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(iris.cx - iris.r - 4, iris.cy);
    ctx.lineTo(iris.cx + iris.r + 4, iris.cy);
    ctx.strokeStyle = "rgba(255,40,40,0.5)";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.save();
    ctx.translate(iris.cx, iris.cy + iris.r + 12);
    ctx.scale(-1, 1);
    ctx.font = "600 10px 'JetBrains Mono', monospace";
    ctx.fillStyle = "rgba(255,40,40,0.95)";
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillText(label + " ~" + iris.diamMm.toFixed(1) + "mm", 0, 0);
    ctx.restore();
}

let trackedFaces = [];
let nextFaceId = 1;
const TRACK_TTL = 800;
let detectErrors = 0;
let renderErrors = 0;
let totalDetectCalls = 0;
let maxFacesEverSeen = 0;
let firstFaceLogged = false;

function fmtTime(ms) {
    const s = Math.floor(ms / 1000);
    if (s < 60) return s + "s";
    return Math.floor(s / 60) + "m " + (s % 60) + "s";
}

function fmtUptime(ms) {
    const s = Math.floor(ms / 1000);
    return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}

function faceCenter(lm) {
    const nose = lm[1], lc = lm[234], rc = lm[454];
    return { x: (lc.x + rc.x) / 2, y: nose.y, w: Math.abs(rc.x - lc.x) };
}

function matchFaces(newFaces, now) {
    const centers = newFaces.map(lm => faceCenter(lm));
    const usedTrack = new Set();
    const usedNew = new Set();
    const matched = new Array(centers.length).fill(null);

    const pairs = [];
    for (let i = 0; i < centers.length; i++) {
        for (let j = 0; j < trackedFaces.length; j++) {
            const c = centers[i], t = trackedFaces[j];
            const threshold = Math.max(t.w * 1.5, 0.08);
            const dist = Math.sqrt(Math.pow(c.x - t.x, 2) + Math.pow(c.y - t.y, 2));
            if (dist < threshold) pairs.push({ i, j, dist });
        }
    }
    pairs.sort((a, b) => a.dist - b.dist);

    for (const p of pairs) {
        if (usedNew.has(p.i) || usedTrack.has(p.j)) continue;
        usedNew.add(p.i);
        usedTrack.add(p.j);
        const t = trackedFaces[p.j], c = centers[p.i];
        matched[p.i] = { id: t.id, x: c.x, y: c.y, w: c.w, since: t.since, colorIdx: t.colorIdx, lastSeen: now };
    }

    for (let i = 0; i < centers.length; i++) {
        if (matched[i]) continue;
        const c = centers[i];
        const ci = (nextFaceId - 1) % FACE_COLORS.length;
        matched[i] = { id: nextFaceId++, x: c.x, y: c.y, w: c.w, since: now, colorIdx: ci, lastSeen: now };
    }

    const survivors = trackedFaces.filter((t, j) => !usedTrack.has(j) && (now - t.lastSeen) < TRACK_TTL);
    trackedFaces = matched.concat(survivors);
    return matched;
}

function updateAdaptivePerf(now) {
    if (now - PERF.lastCheck < PERF.checkInterval) return;
    PERF.lastCheck = now;
    if (fps > 0) {
        PERF.fpsHistory.push(fps);
        if (PERF.fpsHistory.length > PERF.fpsWindowSize)
            PERF.fpsHistory.shift();
    }
    if (PERF.fpsHistory.length < 3) return;
    const avgFps = PERF.fpsHistory.reduce((a, b) => a + b, 0) / PERF.fpsHistory.length;
    const badge = document.getElementById("perfBadge");

    if (!PERF.isThrottled && avgFps < PERF.lowFpsThreshold && avgFps > 0) {
        PERF.skipFrames = 1;
        PERF.isThrottled = true;
        console.log("[PERF] Auto-throttle ON — avg FPS " + avgFps.toFixed(1) + " < " + PERF.lowFpsThreshold);
        badge.textContent = "AUTO-THROTTLED";
        badge.className = "perf-indicator perf-throttled";
    } else if (PERF.isThrottled && avgFps > PERF.highFpsThreshold) {
        PERF.skipFrames = 0;
        PERF.isThrottled = false;
        PERF.fpsHistory = [];
        console.log("[PERF] Auto-throttle OFF — avg FPS " + avgFps.toFixed(1) + " > " + PERF.highFpsThreshold);
        badge.textContent = "OPTIMAL";
        badge.className = "perf-indicator perf-optimal";
    }
}

function draw() {
    requestAnimationFrame(draw);

    if (cam.paused || cam.ended || !cam.videoWidth || !fl) return;

    if (cam.currentTime === lastVideoTime) return;
    lastVideoTime = cam.currentTime;

    frameSkipCounter++;
    if (PERF.skipFrames > 0 && (frameSkipCounter % (PERF.skipFrames + 1)) !== 0) {
        total++;
        fpsCnt++;
        return;
    }

    const vw = cam.videoWidth, vh = cam.videoHeight;
    if (cW !== vw || cH !== vh) {
        cvs.width = vw;
        cvs.height = vh;
        cW = vw; cH = vh;
        du = new DrawingUtils(ctx);
    }

    const nowMs = performance.now();

    const before = performance.now();
    let res;
    try {
        res = fl.detectForVideo(cam, nowMs);
        totalDetectCalls++;
    } catch (e) {
        detectErrors++;
        if (detectErrors <= 3) console.error("detectForVideo error #" + detectErrors + ":", e);
        setDiag("dDetect", "fail", "detectForVideo threw: " + (e.message || e).slice(0, 80));
        return;
    }
    latMs = performance.now() - before;

    ctx.clearRect(0, 0, vw, vh);
    total++;
    fpsCnt++;
    const now = performance.now();
    if (now - fpsT >= 1000) { fps = Math.round(fpsCnt * 1000 / (now - fpsT)); fpsCnt = 0; fpsT = now; }

    let faces = res && res.faceLandmarks ? res.faceLandmarks : [];
    if (faces.length > MAX_FACES) faces = faces.slice(0, MAX_FACES);
    nFaces = faces.length;
    if (nFaces === 0) { hudPupilL = 0; hudPupilR = 0; hudBlinkL = 0; hudBlinkR = 0; }

    if (nFaces > maxFacesEverSeen) maxFacesEverSeen = nFaces;

    if (nFaces > 0) {
        runSanityCheck(faces[0]);
    }

    if (nFaces > 0 && !firstFaceLogged) {
        firstFaceLogged = true;
        console.log("[FACE-DETECTED] First detection! Result keys:", Object.keys(res));
        console.log("[FACE-DETECTED] faceLandmarks type:", typeof res.faceLandmarks, "length:", res.faceLandmarks.length);
        console.log("[FACE-DETECTED] Face 0 length:", faces[0].length, "Sample lm[0]:", JSON.stringify(faces[0][0]));
        console.log("[FACE-DETECTED] Sample lm[1]:", JSON.stringify(faces[0][1]), "lm[10]:", JSON.stringify(faces[0][10]));
    }

    if (nFaces > 0 || totalDetectCalls % 30 === 0 || totalDetectCalls <= 5) {
        if (nFaces > 0) {
            const lmSample = faces[0][0];
            const lmInfo = lmSample ? ("lm0={x:" + lmSample.x.toFixed(3) + ",y:" + lmSample.y.toFixed(3) + "}") : "lm0=null";
            setDiag("dDetect", "ok", nFaces + " face(s) — " + faces[0].length + " pts — " + lmInfo + " — call #" + totalDetectCalls);
        } else {
            const status = maxFacesEverSeen > 0 ? "warn" : (totalDetectCalls > 60 ? "warn" : "wait");
            setDiag("dDetect", status, "0 faces (calls: " + totalDetectCalls + ", errors: " + detectErrors + ", max seen: " + maxFacesEverSeen + ")");
        }
    }

    let renderErr = null;
    try {
        const tracked = matchFaces(faces, now);

        for (let i = 0; i < faces.length; i++) {
            const lm = faces[i];
            if (!lm || lm.length < 468) continue;
            const clr = FACE_COLORS[(tracked[i] ? tracked[i].colorIdx : 0) % FACE_COLORS.length];

            function drawConns(conns, color, lw) {
                if (!conns || !conns.length) return;
                ctx.strokeStyle = color;
                ctx.lineWidth = lw;
                ctx.beginPath();
                for (const c of conns) {
                    let si, ei;
                    if (Array.isArray(c)) { si = c[0]; ei = c[1]; }
                    else if (c.start !== undefined) { si = c.start; ei = c.end; }
                    else continue;
                    const a = lm[si], b = lm[ei];
                    if (!a || !b) continue;
                    ctx.moveTo(a.x * vw, a.y * vh);
                    ctx.lineTo(b.x * vw, b.y * vh);
                }
                ctx.stroke();
            }

            if (L.mesh && FaceLandmarker.FACE_LANDMARKS_TESSELATION) {
                var ovalSet = new Set();
                if (L.outline && FaceLandmarker.FACE_LANDMARKS_FACE_OVAL) {
                    for (var oi0 = 0; oi0 < FaceLandmarker.FACE_LANDMARKS_FACE_OVAL.length; oi0++) {
                        var c0 = FaceLandmarker.FACE_LANDMARKS_FACE_OVAL[oi0];
                        var s0 = Array.isArray(c0) ? c0[0] : c0.start;
                        var e0 = Array.isArray(c0) ? c0[1] : c0.end;
                        ovalSet.add(s0 + "," + e0);
                        ovalSet.add(e0 + "," + s0);
                    }
                }
                ctx.strokeStyle = clr.mesh;
                ctx.lineWidth = 3.5;
                ctx.beginPath();
                for (var ti = 0; ti < FaceLandmarker.FACE_LANDMARKS_TESSELATION.length; ti++) {
                    var tc = FaceLandmarker.FACE_LANDMARKS_TESSELATION[ti];
                    var tsi = Array.isArray(tc) ? tc[0] : tc.start;
                    var tei = Array.isArray(tc) ? tc[1] : tc.end;
                    if (ovalSet.has(tsi + "," + tei)) continue;
                    var ta = lm[tsi], tb = lm[tei];
                    if (!ta || !tb) continue;
                    ctx.moveTo(ta.x * vw, ta.y * vh);
                    ctx.lineTo(tb.x * vw, tb.y * vh);
                }
                ctx.stroke();
            }
            if (L.outline && FaceLandmarker.FACE_LANDMARKS_FACE_OVAL)
                drawConns(FaceLandmarker.FACE_LANDMARKS_FACE_OVAL, clr.edge, 5);
            let eyeBlinkL_v = 0, eyeBlinkR_v = 0;
            if (i === 0) { hudBlinkL = 0; hudBlinkR = 0; }
            if (res.faceBlendshapes && res.faceBlendshapes[i]) {
                for (const b of res.faceBlendshapes[i].categories) {
                    if (b.categoryName === "eyeBlinkLeft") eyeBlinkL_v = b.score;
                    if (b.categoryName === "eyeBlinkRight") eyeBlinkR_v = b.score;
                }
                if (i === 0) { hudBlinkL = eyeBlinkL_v; hudBlinkR = eyeBlinkR_v; }
            }
            const BLINK_TH = 0.45;
            const blinkColorL = eyeBlinkL_v > BLINK_TH ? "rgba(255,60,100,1)" : clr.feat;
            const blinkColorR = eyeBlinkR_v > BLINK_TH ? "rgba(255,60,100,1)" : clr.feat;
            if (L.eyes) {
                if (FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE) drawConns(FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE, blinkColorR, 4);
                if (FaceLandmarker.FACE_LANDMARKS_LEFT_EYE) drawConns(FaceLandmarker.FACE_LANDMARKS_LEFT_EYE, blinkColorL, 4);
            }
            if (L.brows) {
                if (FaceLandmarker.FACE_LANDMARKS_RIGHT_EYEBROW) drawConns(FaceLandmarker.FACE_LANDMARKS_RIGHT_EYEBROW, clr.feat, 4);
                if (FaceLandmarker.FACE_LANDMARKS_LEFT_EYEBROW) drawConns(FaceLandmarker.FACE_LANDMARKS_LEFT_EYEBROW, clr.feat, 4);
            }
            if (L.lips && FaceLandmarker.FACE_LANDMARKS_LIPS)
                drawConns(FaceLandmarker.FACE_LANDMARKS_LIPS, clr.feat, 4);
            if (L.iris) {
                if (FaceLandmarker.FACE_LANDMARKS_RIGHT_IRIS) drawConns(FaceLandmarker.FACE_LANDMARKS_RIGHT_IRIS, clr.iris, 4.5);
                if (FaceLandmarker.FACE_LANDMARKS_LEFT_IRIS) drawConns(FaceLandmarker.FACE_LANDMARKS_LEFT_IRIS, clr.iris, 4.5);

                var irisR = measureIris(lm, 468, [469, 470, 471, 472], vw, vh);
                var irisL = measureIris(lm, 473, [474, 475, 476, 477], vw, vh);
                drawPupilOverlay(ctx, irisR, "R");
                drawPupilOverlay(ctx, irisL, "L");
                if (i === 0) {
                    hudPupilL = irisL ? irisL.diamMm : 0;
                    hudPupilR = irisR ? irisR.diamMm : 0;
                }
            }

            if (L.dots) {
                ctx.fillStyle = clr.dot;
                for (let j = 0; j < lm.length; j++) {
                    if (!lm[j]) continue;
                    ctx.beginPath();
                    ctx.arc(lm[j].x * vw, lm[j].y * vh, 3, 0, 6.283);
                    ctx.fill();
                }
            }

            const t = tracked[i];
            if (t && lm[10]) {
                const tagX = t.x * vw;
                const tagY = (lm[10].y * vh) - 20;
                const dur = fmtTime(now - t.since);
                const label = "Face " + t.id + "  \u00B7  " + dur;
                ctx.save();
                ctx.translate(tagX, tagY);
                ctx.scale(-1, 1);
                ctx.font = "600 15px 'Inter', sans-serif";
                const tw = ctx.measureText(label).width;
                ctx.fillStyle = "rgba(0,0,0,0.65)";
                ctx.beginPath();
                ctx.roundRect(-tw / 2 - 9, -13, tw + 18, 26, 6);
                ctx.fill();
                ctx.fillStyle = clr.tag;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(label, 0, 0);
                ctx.restore();
            }

            if (L.emojis) {
            let smileScore = 0, angerScore = 0, surpriseScore = 0, browUpScore = 0;
            let winkScore = 0, puckerScore = 0, squintScore = 0, mouthFrown = 0;
            if (res.faceBlendshapes && res.faceBlendshapes[i]) {
                const bs = res.faceBlendshapes[i].categories;
                let eyeBlinkL = 0, eyeBlinkR = 0;
                for (const b of bs) {
                    switch (b.categoryName) {
                        case "mouthSmileLeft": case "mouthSmileRight":
                            smileScore = Math.max(smileScore, b.score); break;
                        case "browDownLeft": case "browDownRight":
                            angerScore = Math.max(angerScore, b.score); break;
                        case "jawOpen":
                            surpriseScore = Math.max(surpriseScore, b.score); break;
                        case "browOuterUpLeft": case "browOuterUpRight":
                            browUpScore = Math.max(browUpScore, b.score); break;
                        case "eyeBlinkLeft": eyeBlinkL = b.score; break;
                        case "eyeBlinkRight": eyeBlinkR = b.score; break;
                        case "mouthPucker":
                            puckerScore = Math.max(puckerScore, b.score); break;
                        case "eyeSquintLeft": case "eyeSquintRight":
                            squintScore = Math.max(squintScore, b.score); break;
                        case "mouthFrownLeft": case "mouthFrownRight":
                            mouthFrown = Math.max(mouthFrown, b.score); break;
                    }
                }
                surpriseScore = Math.min(1, surpriseScore * 0.7 + browUpScore * 0.5);
                winkScore = Math.abs(eyeBlinkL - eyeBlinkR) > 0.4 ? Math.max(eyeBlinkL, eyeBlinkR) : 0;
            }

            const emojis = [
                { ch: "\uD83D\uDE00", on: smileScore > 0.4, glow: "rgba(255,220,50,0.9)" },
                { ch: "\uD83D\uDE20", on: angerScore > 0.45, glow: "rgba(255,60,60,0.9)" },
                { ch: "\uD83E\uDEE8", on: surpriseScore > 0.5, glow: "rgba(140,120,255,0.9)" },
                { ch: "\uD83E\uDEE1", on: browUpScore > 0.35, glow: "rgba(80,200,120,0.9)" },
                { ch: "\uD83D\uDE09", on: winkScore > 0.5, glow: "rgba(255,180,220,0.9)" },
                { ch: "\uD83D\uDE19", on: puckerScore > 0.4, glow: "rgba(255,130,170,0.9)" },
                { ch: "\uD83D\uDE12", on: squintScore > 0.55 && smileScore < 0.2, glow: "rgba(180,180,180,0.9)" },
                { ch: "\u2639\uFE0F", on: mouthFrown > 0.4, glow: "rgba(100,150,255,0.9)" },
            ];
            const chin = lm[152];
            if (chin) {
                const baseX = (t ? t.x * vw : chin.x * vw);
                const baseY = chin.y * vh + 35;
                const spacing = 32;
                const totalW = emojis.length * spacing;
                const startX = baseX - totalW / 2 + spacing / 2;
                for (let ei = 0; ei < emojis.length; ei++) {
                    const em = emojis[ei];
                    ctx.save();
                    ctx.translate(startX + ei * spacing, baseY);
                    ctx.scale(-1, 1);
                    ctx.font = "22px sans-serif";
                    ctx.textAlign = "center";
                    ctx.textBaseline = "middle";
                    if (em.on) {
                        ctx.shadowColor = em.glow;
                        ctx.shadowBlur = 16;
                        ctx.globalAlpha = 1;
                        ctx.fillText(em.ch, 0, 0);
                        ctx.shadowBlur = 0;
                    } else {
                        ctx.globalAlpha = 0.12;
                        ctx.fillText(em.ch, 0, 0);
                    }
                    ctx.restore();
                }
            }
            }
        }

        if (faces.length > 0 && faces[0].length >= 455) {
            const p = faces[0];
            const n = p[1], lc = p[234], rc = p[454], fh = p[10], ch = p[152];
            if (n && lc && rc && fh && ch) {
                const fw = Math.abs(rc.x - lc.x) || 0.01;
                const fht = Math.abs(ch.y - fh.y) || 0.01;
                yaw = Math.round(((n.x - (lc.x + rc.x) / 2) / fw) * 90);
                pitch = Math.round(((n.y - (fh.y + ch.y) / 2) / fht) * 90);
            }
            hudBL.classList.add("on");
        } else {
            hudBL.classList.remove("on");
        }
    } catch (e) {
        renderErr = e;
        renderErrors++;
        if (renderErrors <= 5) console.error("Render error #" + renderErrors + ":", e);
        setDiag("dCanvas", "fail", "RENDER ERROR #" + renderErrors + ": " + (e.message || e).slice(0, 100));
    }

    drawSysOverlay(ctx, vw, vh);

    updateAdaptivePerf(now);

    if (now - lastHud >= 500) {
        lastHud = now;
        document.getElementById("hFaces").textContent = nFaces + (nFaces === 1 ? " face" : " faces");
        document.getElementById("hPts").textContent = nFaces > 0 ? (478 * nFaces).toLocaleString() : "--";
        document.getElementById("hFps").textContent = fps;
        document.getElementById("hLat").textContent = Math.round(latMs) + "ms";
        document.getElementById("hDev").textContent = "Uno Q";
        document.getElementById("hUp").textContent = fmtUptime(now - startTime);
        document.getElementById("hFrames").textContent = total.toLocaleString();
        document.getElementById("hDetects").textContent = totalDetectCalls.toLocaleString();
        document.getElementById("hBlinkL").textContent = hudBlinkL.toFixed(2);
        document.getElementById("hBlinkR").textContent = hudBlinkR.toFixed(2);
        document.getElementById("hPupilL").textContent = hudPupilL > 0 ? "~" + hudPupilL.toFixed(1) + "mm" : "--";
        document.getElementById("hPupilR").textContent = hudPupilR > 0 ? "~" + hudPupilR.toFixed(1) + "mm" : "--";

        let listHtml = "";
        for (const t of trackedFaces) {
            const dur = fmtTime(now - t.since);
            const clr = FACE_COLORS[t.colorIdx];
            listHtml += '<div class="face-entry"><span class="face-id" style="color:' + clr.tag + '">Face ' + t.id + '</span><span class="face-time">' + dur + '</span></div>';
        }
        faceListEl.innerHTML = listHtml;

        if (nFaces > 0) {
            document.getElementById("hYaw").textContent = (yaw > 0 ? "+" : "") + yaw + "\u00B0";
            document.getElementById("hPitch").textContent = (pitch > 0 ? "+" : "") + pitch + "\u00B0";
        } else {
            document.getElementById("hYaw").textContent = "--";
            document.getElementById("hPitch").textContent = "--";
        }

        if (!renderErr) {
            setDiag("dCanvas", "ok", cW + "x" + cH + " — rendering" + (nFaces > 0 ? " " + nFaces + " face(s)" : ""));
        }
    }
}

requestAnimationFrame(draw);
