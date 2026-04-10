// Wojo's Uno Q Face Outline Tracker Demo — Frontend Logic
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

var THROTTLE_MS = 500;
var MAX_FACES = 2;
var MAX_RECENT_SCANS = 8;
var CAM_WIDTH = 640;
var CAM_HEIGHT = 480;

var FACE_OVAL = FaceLandmarker.FACE_LANDMARKS_FACE_OVAL;
var LEFT_EYE = FaceLandmarker.FACE_LANDMARKS_LEFT_EYE;
var RIGHT_EYE = FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE;
var LEFT_IRIS = FaceLandmarker.FACE_LANDMARKS_LEFT_IRIS;
var RIGHT_IRIS = FaceLandmarker.FACE_LANDMARKS_RIGHT_IRIS;
var LIPS = FaceLandmarker.FACE_LANDMARKS_LIPS;
var TESSELATION = FaceLandmarker.FACE_LANDMARKS_TESSELATION;

var video = document.getElementById("webcamVideo");
var canvas = document.getElementById("overlayCanvas");
var ctx = canvas.getContext("2d");
var placeholder = document.getElementById("videoPlaceholder");
var statusBadge = document.getElementById("statusBadge");
var feedbackContent = document.getElementById("feedback-content");
var recentDetections = document.getElementById("recentDetections");
var faceCountNumber = document.getElementById("faceCountNumber");
var drawModeSelect = document.getElementById("drawModeSelect");
var errorContainer = document.getElementById("error-container");

var hudFps = document.getElementById("hudFps");
var hudFaces = document.getElementById("hudFaces");
var hudExpression = document.getElementById("hudExpression");
var hudYaw = document.getElementById("hudYaw");
var hudPitch = document.getElementById("hudPitch");

var faceLandmarker = null;
var drawingUtils = null;
var running = false;
var scans = [];
var lastSendTime = 0;
var faceVisible = false;
var frameCount = 0;
var fpsTime = performance.now();
var currentFps = 0;
var drawMode = "outline";
var minConfidence = 0.5;
var lastExpression = "";

var socket = null;

drawModeSelect.addEventListener("change", function () {
  drawMode = this.value;
});

async function initLandmarker() {
  updatePlaceholder("Loading face model...");
  var vision = await FilesetResolver.forVisionTasks(
    "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm"
  );

  var delegate = "GPU";
  try {
    var testCanvas = document.createElement("canvas");
    var gl = testCanvas.getContext("webgl2");
    if (!gl) delegate = "CPU";
  } catch (e) {
    delegate = "CPU";
  }

  faceLandmarker = await FaceLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath:
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
      delegate: delegate
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

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!faceLandmarker) {
    requestAnimationFrame(detectLoop);
    return;
  }

  var results;
  try {
    results = faceLandmarker.detectForVideo(video, timestamp);
  } catch (e) {
    requestAnimationFrame(detectLoop);
    return;
  }

  var numFaces = results.faceLandmarks ? results.faceLandmarks.length : 0;

  faceCountNumber.textContent = numFaces;
  faceCountNumber.className = "face-count-number" + (numFaces > 0 ? " active" : "");
  hudFaces.textContent = numFaces;

  if (numFaces > 0) {
    for (var i = 0; i < numFaces; i++) {
      drawFace(results.faceLandmarks[i], i);
    }

    var blendshapes = results.faceBlendshapes && results.faceBlendshapes[0]
      ? results.faceBlendshapes[0].categories
      : [];
    var expression = detectExpression(blendshapes);
    hudExpression.textContent = expression;

    var blinks = detectBlinks(blendshapes);

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
        blinks: blinks,
        yaw: Math.round(headPose.yaw * 10) / 10,
        pitch: Math.round(headPose.pitch * 10) / 10,
        timestamp: new Date().toISOString()
      };
      if (socket) socket.emit("face_data", payload);

      if (expression !== lastExpression) {
        lastExpression = expression;
        if (socket) socket.emit("expression_change", { expression: expression });
      }

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
      lastExpression = "";
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

function detectBlinks(blendshapes) {
  if (!blendshapes || blendshapes.length === 0) return { left: false, right: false };
  var map = {};
  for (var i = 0; i < blendshapes.length; i++) {
    map[blendshapes[i].categoryName] = blendshapes[i].score;
  }
  return {
    left: (map["eyeBlinkLeft"] || 0) > 0.4,
    right: (map["eyeBlinkRight"] || 0) > 0.4
  };
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
  var pitch = Math.asin(Math.max(-1, Math.min(1, -m[4]))) * (180 / Math.PI);
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
    socket = io({ reconnectionAttempts: 5, timeout: 5000 });
    var failCount = 0;

    socket.on("connect", function () {
      failCount = 0;
      if (errorContainer) {
        errorContainer.style.display = "none";
        errorContainer.textContent = "";
      }
      socket.emit("get_modulinos", {});
    });

    socket.on("connect_error", function () {
      failCount++;
      if (failCount >= 5) {
        socket.close();
        socket = null;
      }
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

function initModulino() {
  if (!socket) return;

  socket.on("modulino_detected", function (data) {
    var modules = data.modules || [];
    if (modules.length === 0) return;
    var section = document.getElementById("modulinoSection");
    section.style.display = "";
    var modsDiv = document.getElementById("modulinoModules");
    modsDiv.replaceChildren();
    for (var i = 0; i < modules.length; i++) {
      var badge = document.createElement("span");
      badge.className = "mod-badge";
      badge.textContent = modules[i];
      modsDiv.appendChild(badge);
    }
    var ctrlDiv = document.getElementById("modulinoControls");
    ctrlDiv.replaceChildren();
    buildModulinoControls(modules, ctrlDiv);
  });

  socket.on("modulino_knob", function (data) {
    var el = document.getElementById("modKnobPos");
    if (el) el.textContent = data.position;
    var btn = document.getElementById("modKnobBtn");
    if (btn) {
      btn.textContent = data.pressed ? "Pressed" : "Released";
      btn.className = data.pressed ? "mod-knob-pressed" : "";
    }
  });

  socket.on("modulino_buttons", function (data) {
    var states = data.states || [];
    var ids = ["modBtnA", "modBtnB", "modBtnC"];
    for (var i = 0; i < ids.length && i < states.length; i++) {
      var el = document.getElementById(ids[i]);
      if (el) el.className = "mod-btn-indicator" + (states[i] ? " pressed" : "");
    }
  });

  socket.on("modulino_distance", function (data) {
    var el = document.getElementById("modDistVal");
    if (el) el.textContent = data.mm;
  });

  socket.on("modulino_thermo", function (data) {
    var el = document.getElementById("modThermoTemp");
    if (el) el.textContent = data.temp.toFixed(1);
    var hel = document.getElementById("modThermoHum");
    if (hel) hel.textContent = data.humidity.toFixed(1);
  });
}

function buildModulinoControls(modules, container) {
  for (var i = 0; i < modules.length; i++) {
    var mod = modules[i];
    var ctrl = document.createElement("div");
    ctrl.className = "mod-ctrl";

    var header = document.createElement("div");
    header.className = "mod-ctrl-header";
    var label = document.createElement("span");
    label.className = "mod-label";
    label.textContent = mod.charAt(0).toUpperCase() + mod.slice(1);
    header.appendChild(label);
    ctrl.appendChild(header);

    var body = document.createElement("div");
    body.className = "mod-ctrl-body";

    if (mod === "pixels") {
      buildPixelsControl(body);
    } else if (mod === "buzzer") {
      buildBuzzerControl(body);
    } else if (mod === "knob") {
      body.className = "mod-ctrl-body mod-readout";
      var posSpan = document.createElement("span");
      posSpan.textContent = "Position: ";
      var posVal = document.createElement("strong");
      posVal.id = "modKnobPos";
      posVal.textContent = "0";
      posSpan.appendChild(posVal);
      body.appendChild(posSpan);
      var btnSpan = document.createElement("span");
      btnSpan.id = "modKnobBtn";
      btnSpan.textContent = "Released";
      body.appendChild(btnSpan);
    } else if (mod === "buttons") {
      body.className = "mod-ctrl-body mod-readout";
      var labels = ["A", "B", "C"];
      for (var j = 0; j < 3; j++) {
        var ind = document.createElement("span");
        ind.className = "mod-btn-indicator";
        ind.id = "modBtn" + labels[j];
        ind.textContent = labels[j];
        body.appendChild(ind);
      }
    } else if (mod === "distance") {
      body.className = "mod-ctrl-body mod-readout";
      var dSpan = document.createElement("span");
      var dVal = document.createElement("strong");
      dVal.id = "modDistVal";
      dVal.textContent = "--";
      dSpan.appendChild(dVal);
      dSpan.appendChild(document.createTextNode(" mm"));
      body.appendChild(dSpan);
    } else if (mod === "thermo") {
      body.className = "mod-ctrl-body mod-readout";
      var tSpan = document.createElement("span");
      var tVal = document.createElement("strong");
      tVal.id = "modThermoTemp";
      tVal.textContent = "--";
      tSpan.appendChild(tVal);
      tSpan.appendChild(document.createTextNode(" \u00B0C"));
      body.appendChild(tSpan);
      var hSpan = document.createElement("span");
      var hVal = document.createElement("strong");
      hVal.id = "modThermoHum";
      hVal.textContent = "--";
      hSpan.appendChild(hVal);
      hSpan.appendChild(document.createTextNode(" %"));
      body.appendChild(hSpan);
    }

    ctrl.appendChild(body);
    container.appendChild(ctrl);
  }
}

function buildPixelsControl(body) {
  var colorInput = document.createElement("input");
  colorInput.type = "color";
  colorInput.id = "modPixelColor";
  colorInput.className = "mod-color-input";
  colorInput.value = "#ff0000";
  body.appendChild(colorInput);

  var setBtn = document.createElement("button");
  setBtn.className = "mod-btn";
  setBtn.textContent = "Set All";
  setBtn.addEventListener("click", function () {
    var hex = document.getElementById("modPixelColor").value;
    var r = parseInt(hex.substring(1, 3), 16);
    var g = parseInt(hex.substring(3, 5), 16);
    var b = parseInt(hex.substring(5, 7), 16);
    if (socket) socket.emit("set_mod_pixels", { payload: "all:" + r + ":" + g + ":" + b });
  });
  body.appendChild(setBtn);

  var clearBtn = document.createElement("button");
  clearBtn.className = "mod-btn mod-btn-outline";
  clearBtn.textContent = "Clear";
  clearBtn.addEventListener("click", function () {
    if (socket) socket.emit("set_mod_pixels", { payload: "clear" });
  });
  body.appendChild(clearBtn);
}

function buildBuzzerControl(body) {
  var freqInput = document.createElement("input");
  freqInput.type = "number";
  freqInput.className = "mod-input";
  freqInput.id = "modBuzzerFreq";
  freqInput.value = "440";
  freqInput.min = "100";
  freqInput.max = "5000";
  freqInput.step = "100";
  body.appendChild(freqInput);

  var hzLabel = document.createElement("span");
  hzLabel.className = "mod-readout";
  hzLabel.textContent = "Hz";
  body.appendChild(hzLabel);

  var durInput = document.createElement("input");
  durInput.type = "number";
  durInput.className = "mod-input";
  durInput.id = "modBuzzerDur";
  durInput.value = "200";
  durInput.min = "50";
  durInput.max = "2000";
  durInput.step = "50";
  body.appendChild(durInput);

  var msLabel = document.createElement("span");
  msLabel.className = "mod-readout";
  msLabel.textContent = "ms";
  body.appendChild(msLabel);

  var playBtn = document.createElement("button");
  playBtn.className = "mod-btn";
  playBtn.textContent = "Play";
  playBtn.addEventListener("click", function () {
    var freq = document.getElementById("modBuzzerFreq").value;
    var dur = document.getElementById("modBuzzerDur").value;
    if (socket) socket.emit("play_mod_buzzer", { payload: freq + ":" + dur });
  });
  body.appendChild(playBtn);
}

function setStatus(text, className) {
  statusBadge.textContent = text;
  statusBadge.className = "status-badge " + (className || "");
}

async function main() {
  setStatus("Loading...", "");
  initSocketIO();
  initModulino();
  initConfidenceSlider();
  renderDetections();
  try {
    await initLandmarker();
  } catch (e) {
    updatePlaceholder("Model load failed: " + e.message);
    setStatus("Error", "");
    return;
  }
  setStatus("Starting camera...", "");
  await startCamera();
  setStatus("Scanning...", "scanning");
}

main();
