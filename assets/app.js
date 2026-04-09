// SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
//
// SPDX-License-Identifier: MIT
//
// Wojo's Face Outline Demo — Frontend Logic
// Arduino Uno Q | Qualcomm QRB2210 | Arduino App Lab
//
// Runs MediaPipe Face Landmarker in-browser (WASM) for real-time
// face mesh / outline / iris tracking. Sends telemetry to the
// WebUI brick via Socket.IO for Bridge RPC forwarding to the MCU.

import {
  FaceLandmarker,
  FilesetResolver,
  DrawingUtils
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/vision_bundle.mjs";

const THROTTLE_MS = 500;
const MAX_FACES = 4;
const MAX_RECENT_SCANS = 8;
const CAM_WIDTH = 640;
const CAM_HEIGHT = 480;

const FACE_OVAL = FaceLandmarker.FACE_LANDMARKS_FACE_OVAL;
const LEFT_EYE = FaceLandmarker.FACE_LANDMARKS_LEFT_EYE;
const RIGHT_EYE = FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE;
const LEFT_IRIS = FaceLandmarker.FACE_LANDMARKS_LEFT_IRIS;
const RIGHT_IRIS = FaceLandmarker.FACE_LANDMARKS_RIGHT_IRIS;
const LIPS = FaceLandmarker.FACE_LANDMARKS_LIPS;
const TESSELATION = FaceLandmarker.FACE_LANDMARKS_TESSELATION;

const video = document.getElementById("webcamVideo");
const canvas = document.getElementById("overlayCanvas");
const ctx = canvas.getContext("2d");
const placeholder = document.getElementById("videoPlaceholder");
const statusBadge = document.getElementById("statusBadge");
const feedbackContent = document.getElementById("feedback-content");
const recentDetections = document.getElementById("recentDetections");
const faceCountNumber = document.getElementById("faceCountNumber");
const drawModeSelect = document.getElementById("drawModeSelect");
const errorContainer = document.getElementById("error-container");

const hudFps = document.getElementById("hudFps");
const hudFaces = document.getElementById("hudFaces");
const hudExpression = document.getElementById("hudExpression");
const hudYaw = document.getElementById("hudYaw");
const hudPitch = document.getElementById("hudPitch");

let faceLandmarker = null;
let drawingUtils = null;
let running = false;
let scans = [];
let lastSendTime = 0;
let faceVisible = false;
let frameCount = 0;
let fpsTime = performance.now();
let currentFps = 0;
let drawMode = "outline";
let minConfidence = 0.5;

var socket = null;

drawModeSelect.addEventListener("change", function () {
  drawMode = this.value;
});

async function initLandmarker() {
  updatePlaceholder("Loading face model...");
  var vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm"
  );
  faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
      delegate: "GPU"
    },
    runningMode: "VIDEO",
    numFaces: MAX_FACES,
    outputFaceBlendshapes: true,
    outputFacialTransformationMatrixes: true,
    minFaceDetectionConfidence: minConfidence,
    minFacePresenceConfidence: minConfidence,
    minTrackingConfidence: minConfidence
  });
  drawingUtils = new DrawingUtils(ctx);
}

async function startCamera() {
  updatePlaceholder("Requesting camera...");
  try {
    var stream = await navigator.mediaDevices.getUserMedia({
      video: { width: CAM_WIDTH, height: CAM_HEIGHT, facingMode: "user" },
      audio: false
    });
    video.srcObject = stream;
    await video.play();
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    placeholder.style.display = "none";
    video.style.display = "block";
    canvas.style.display = "block";
    running = true;
    requestAnimationFrame(detectLoop);
  } catch (err) {
    updatePlaceholder("Camera error: " + err.message);
  }
}

function detectLoop(timestamp) {
  if (!running) return;

  frameCount++;
  var now = performance.now();
  if (now - fpsTime >= 1000) {
    currentFps = frameCount;
    frameCount = 0;
    fpsTime = now;
    hudFps.textContent = currentFps;
  }

  if (currentFps > 0 && currentFps < 8) {
    requestAnimationFrame(detectLoop);
    return;
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!faceLandmarker) {
    requestAnimationFrame(detectLoop);
    return;
  }

  var results = faceLandmarker.detectForVideo(video, timestamp);
  var numFaces = results.faceLandmarks ? results.faceLandmarks.length : 0;

  faceCountNumber.textContent = numFaces;
  faceCountNumber.className = "face-count-number" + (numFaces > 0 ? " active" : "");
  hudFaces.textContent = numFaces;

  if (numFaces > 0) {
    for (var i = 0; i < numFaces; i++) {
      var lm = results.faceLandmarks[i];
      drawFace(lm, i);
    }

    var blendshapes = results.faceBlendshapes && results.faceBlendshapes[0]
      ? results.faceBlendshapes[0].categories
      : [];
    var expression = detectExpression(blendshapes);
    hudExpression.textContent = expression;

    var matrix = results.facialTransformationMatrixes && results.facialTransformationMatrixes[0]
      ? results.facialTransformationMatrixes[0]
      : null;
    var headPose = extractHeadPose(matrix);
    hudYaw.textContent = headPose.yaw.toFixed(1) + "\u00B0";
    hudPitch.textContent = headPose.pitch.toFixed(1) + "\u00B0";

    if (!faceVisible) {
      faceVisible = true;
      showGreeting();
      setStatus("Face Detected", "active");
    }

    if (now - lastSendTime > THROTTLE_MS) {
      lastSendTime = now;
      var payload = {
        faces: numFaces,
        expression: expression,
        yaw: headPose.yaw,
        pitch: headPose.pitch,
        timestamp: new Date().toISOString()
      };
      if (socket) socket.emit("face_data", payload);

      addDetection({
        content: expression,
        confidence: results.faceBlendshapes && results.faceBlendshapes[0]
          ? getTopBlendshapeScore(results.faceBlendshapes[0].categories)
          : 0.9,
        timestamp: payload.timestamp
      });
    }
  } else {
    hudExpression.textContent = "--";
    hudYaw.textContent = "--";
    hudPitch.textContent = "--";

    if (faceVisible) {
      faceVisible = false;
      setStatus("Scanning...", "scanning");
      showFeedback("System response will appear here");
      if (socket) socket.emit("face_data", { faces: 0 });
    }
  }

  requestAnimationFrame(detectLoop);
}

function drawFace(landmarks, faceIndex) {
  if (drawMode === "none") return;

  var colors = [
    { line: "#30FF30", dot: "#FF3030" },
    { line: "#30AAFF", dot: "#FFAA30" },
    { line: "#FF30FF", dot: "#30FFAA" },
    { line: "#FFFF30", dot: "#3030FF" }
  ];
  var c = colors[faceIndex % colors.length];

  if (drawMode === "mesh") {
    drawingUtils.drawConnectors(landmarks, TESSELATION, {
      color: "#C0C0C030",
      lineWidth: 1
    });
    drawingUtils.drawConnectors(landmarks, FACE_OVAL, {
      color: c.line,
      lineWidth: 2
    });
    drawingUtils.drawConnectors(landmarks, LEFT_EYE, {
      color: c.line,
      lineWidth: 1
    });
    drawingUtils.drawConnectors(landmarks, RIGHT_EYE, {
      color: c.line,
      lineWidth: 1
    });
    drawingUtils.drawConnectors(landmarks, LIPS, {
      color: c.line,
      lineWidth: 1
    });
  }

  if (drawMode === "outline" || drawMode === "mesh") {
    drawingUtils.drawConnectors(landmarks, FACE_OVAL, {
      color: c.line,
      lineWidth: 2
    });
    drawingUtils.drawConnectors(landmarks, LEFT_EYE, {
      color: c.line,
      lineWidth: 1.5
    });
    drawingUtils.drawConnectors(landmarks, RIGHT_EYE, {
      color: c.line,
      lineWidth: 1.5
    });
    drawingUtils.drawConnectors(landmarks, LIPS, {
      color: c.line,
      lineWidth: 1.5
    });
  }

  if (drawMode === "dots") {
    for (var j = 0; j < landmarks.length; j++) {
      var pt = landmarks[j];
      ctx.beginPath();
      ctx.arc(pt.x * canvas.width, pt.y * canvas.height, 1.2, 0, 2 * Math.PI);
      ctx.fillStyle = c.dot;
      ctx.fill();
    }
  }

  if (drawMode !== "none") {
    drawIris(landmarks, LEFT_IRIS, c.dot);
    drawIris(landmarks, RIGHT_IRIS, c.dot);
  }
}

function drawIris(landmarks, irisConnections, color) {
  if (!irisConnections || irisConnections.length === 0) return;
  var indices = new Set();
  for (var i = 0; i < irisConnections.length; i++) {
    indices.add(irisConnections[i].start);
    indices.add(irisConnections[i].end);
  }
  var pts = [];
  indices.forEach(function (idx) {
    if (landmarks[idx]) pts.push(landmarks[idx]);
  });
  if (pts.length === 0) return;

  var cx = 0, cy = 0;
  for (var i = 0; i < pts.length; i++) {
    cx += pts[i].x;
    cy += pts[i].y;
  }
  cx = (cx / pts.length) * canvas.width;
  cy = (cy / pts.length) * canvas.height;

  var maxR = 0;
  for (var i = 0; i < pts.length; i++) {
    var dx = pts[i].x * canvas.width - cx;
    var dy = pts[i].y * canvas.height - cy;
    var r = Math.sqrt(dx * dx + dy * dy);
    if (r > maxR) maxR = r;
  }

  ctx.beginPath();
  ctx.arc(cx, cy, maxR, 0, 2 * Math.PI);
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(cx, cy, 2, 0, 2 * Math.PI);
  ctx.fillStyle = color;
  ctx.fill();
}

function detectExpression(blendshapes) {
  if (!blendshapes || blendshapes.length === 0) return "neutral";
  var map = {};
  for (var i = 0; i < blendshapes.length; i++) {
    map[blendshapes[i].categoryName] = blendshapes[i].score;
  }

  var smile = (map["mouthSmileLeft"] || 0) + (map["mouthSmileRight"] || 0);
  var browUp = (map["browInnerUp"] || 0);
  var browDown = (map["browDownLeft"] || 0) + (map["browDownRight"] || 0);
  var jawOpen = map["jawOpen"] || 0;
  var eyeSquint = (map["eyeSquintLeft"] || 0) + (map["eyeSquintRight"] || 0);
  var eyeWide = (map["eyeWideLeft"] || 0) + (map["eyeWideRight"] || 0);

  if (smile > 0.6) return "happy";
  if (jawOpen > 0.5 && eyeWide > 0.4) return "surprised";
  if (browDown > 0.5 && eyeSquint > 0.3) return "angry";
  if (browUp > 0.4 && eyeWide > 0.3) return "surprised";
  if (browDown > 0.3) return "sad";
  return "neutral";
}

function getTopBlendshapeScore(categories) {
  if (!categories || categories.length === 0) return 0;
  var top = 0;
  for (var i = 0; i < categories.length; i++) {
    if (categories[i].score > top) top = categories[i].score;
  }
  return top;
}

function extractHeadPose(matrix) {
  if (!matrix || !matrix.data) return { yaw: 0, pitch: 0 };
  var m = matrix.data;
  var yaw = Math.atan2(m[8], m[0]) * (180 / Math.PI);
  var pitch = Math.asin(-m[4]) * (180 / Math.PI);
  return { yaw: yaw, pitch: pitch };
}

function updatePlaceholder(msg) {
  var p = placeholder.querySelector(".feedback-text");
  if (p) p.textContent = msg;
}

function showGreeting() {
  var greetings = [
    "Hello!", "Hi there!", "Hey!", "Nice to see you!",
    "Looking good!", "There you are!", "Howdy!",
    "Face detected!", "Hello, human!", "I see you!"
  ];
  var text = greetings[Math.floor(Math.random() * greetings.length)];
  var el = document.createElement("p");
  el.className = "greeting-text";
  el.textContent = text;
  feedbackContent.replaceChildren(el);
}

function showFeedback(msg) {
  var el = document.createElement("p");
  el.className = "feedback-text";
  el.textContent = msg;
  feedbackContent.replaceChildren(el);
}

function addDetection(det) {
  scans.unshift(det);
  if (scans.length > MAX_RECENT_SCANS) scans.pop();
  renderDetections();
}

function renderDetections() {
  recentDetections.replaceChildren();

  if (scans.length === 0) {
    var emptyEl = document.createElement("div");
    emptyEl.className = "no-recent-scans";
    emptyEl.textContent = "No face detected yet";
    recentDetections.replaceChildren(emptyEl);
    return;
  }

  for (var i = 0; i < scans.length; i++) {
    var scan = scans[i];
    var row = document.createElement("div");
    row.className = "scan-container";

    var cellContainer = document.createElement("span");
    cellContainer.className = "scan-cell-container cell-border";

    var contentText = document.createElement("span");
    contentText.className = "scan-content";
    var result = Math.floor(scan.confidence * 1000) / 10;
    contentText.textContent = result + "% \u2014 " + (scan.content || "Face");

    var timeText = document.createElement("span");
    timeText.className = "scan-content-time";
    timeText.textContent = new Date(scan.timestamp).toLocaleTimeString();

    cellContainer.appendChild(contentText);
    cellContainer.appendChild(timeText);
    row.appendChild(cellContainer);
    recentDetections.appendChild(row);
  }
}

function initConfidenceSlider() {
  var slider = document.getElementById("confidenceSlider");
  var input = document.getElementById("confidenceInput");
  var resetBtn = document.getElementById("confidenceResetButton");

  slider.addEventListener("input", updateConfidence);
  input.addEventListener("input", function () {
    var v = parseFloat(input.value);
    if (isNaN(v)) v = 0.5;
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    slider.value = v;
    updateConfidence();
  });
  input.addEventListener("blur", function () {
    var v = parseFloat(input.value);
    if (isNaN(v)) v = 0.5;
    if (v < 0) v = 0;
    if (v > 1) v = 1;
    input.value = v.toFixed(2);
  });
  resetBtn.addEventListener("click", function (e) {
    if (e.target.classList.contains("reset-icon") || e.target.closest(".reset-icon")) {
      slider.value = "0.5";
      input.value = "0.50";
      updateConfidence();
    }
  });

  updateConfidence();
}

function updateConfidence() {
  var slider = document.getElementById("confidenceSlider");
  var input = document.getElementById("confidenceInput");
  var display = document.getElementById("confidenceValueDisplay");
  var progress = document.getElementById("sliderProgress");

  var value = parseFloat(slider.value);
  minConfidence = value;

  if (socket) socket.emit("override_th", value);
  var pct = (value - slider.min) / (slider.max - slider.min) * 100;
  var formatted = value.toFixed(2);
  display.textContent = formatted;
  if (document.activeElement !== input) input.value = formatted;
  progress.style.width = pct + "%";
  display.style.left = pct + "%";
}

function initSocketIO() {
  if (typeof io === "undefined") return;

  try {
    socket = io({ reconnectionAttempts: 3, timeout: 5000 });

    socket.on("connect", function () {
      if (errorContainer) {
        errorContainer.style.display = "none";
        errorContainer.textContent = "";
      }
    });

    socket.on("connect_error", function () {
      socket.close();
      socket = null;
    });

    socket.on("disconnect", function () {
      if (errorContainer) {
        errorContainer.textContent = "Connection to the board lost.";
        errorContainer.style.display = "block";
      }
    });
  } catch (e) {
    socket = null;
  }
}

function setStatus(text, className) {
  statusBadge.textContent = text;
  statusBadge.className = "status-badge " + (className || "");
}

async function main() {
  setStatus("Loading...", "");
  initSocketIO();
  initConfidenceSlider();
  renderDetections();
  await initLandmarker();
  setStatus("Starting camera...", "");
  await startCamera();
  setStatus("Scanning...", "scanning");
}

main();
