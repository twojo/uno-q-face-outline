var recentDetectionsElement = document.getElementById('recentDetections');
var feedbackContentElement = document.getElementById('feedback-content');
var hudFaces = document.getElementById('hudFaces');
var hudExpression = document.getElementById('hudExpression');
var errorContainer = document.getElementById('error-container');
var overlayCanvas = document.getElementById('overlayCanvas');
var overlayCtx = overlayCanvas ? overlayCanvas.getContext('2d') : null;
var MAX_RECENT_SCANS = 5;
var scans = [];
var socket = io('http://' + window.location.host);
var handVisible = false;
var faceLandmarker = null;
var webcamVideo = null;
var trackingRunning = false;

initSocketIO();
initializeConfidenceSlider();
renderDetections();
initFaceTracking();

function initSocketIO() {
    var detectionTimeout;

    socket.on('connect', function () {
        if (errorContainer) {
            errorContainer.style.display = 'none';
            errorContainer.textContent = '';
        }
    });

    socket.on('disconnect', function () {
        if (errorContainer) {
            errorContainer.textContent = 'Connection to the board lost. Please check the connection.';
            errorContainer.style.display = 'block';
        }
    });

    socket.on('detection', function (message) {
        clearTimeout(detectionTimeout);
        printDetection(message);
        renderDetections();

        if (hudFaces) hudFaces.textContent = '1';

        if (!handVisible) {
            var greetings = ["Hello!", "Hi there!", "Hey!", "Nice to see you!", "Great to have you here!", "I see you", "Looking good!", "There you are!", "Howdy!", "Happy to see a face!", "Hi, friend!", "Face detected!", "Hello, human!"];
            var randomGreeting = greetings[Math.floor(Math.random() * greetings.length)];
            feedbackContentElement.innerHTML = '<p>' + randomGreeting + '</p>';
            handVisible = true;
        }

        detectionTimeout = setTimeout(function () {
            feedbackContentElement.innerHTML = '<p class="feedback-text">System response will appear here</p>';
            handVisible = false;
            if (hudFaces && !trackingRunning) hudFaces.textContent = '0';
            if (hudExpression && !trackingRunning) hudExpression.textContent = '--';
        }, 3000);
    });
}

async function initFaceTracking() {
    try {
        var vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/vision_bundle.mjs');
        var FaceLandmarker = vision.FaceLandmarker;
        var FilesetResolver = vision.FilesetResolver;
        var DrawingUtils = vision.DrawingUtils;

        var filesetResolver = await FilesetResolver.forVisionTasks(
            'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm'
        );

        faceLandmarker = await FaceLandmarker.createFromOptions(filesetResolver, {
            baseOptions: {
                modelAssetPath: 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task',
                delegate: 'GPU'
            },
            runningMode: 'VIDEO',
            numFaces: 2,
            minFaceDetectionConfidence: 0.5,
            minTrackingConfidence: 0.5,
            outputFaceBlendshapes: true
        });

        webcamVideo = document.createElement('video');
        webcamVideo.setAttribute('autoplay', '');
        webcamVideo.setAttribute('playsinline', '');
        webcamVideo.setAttribute('muted', '');

        var stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: 'user' },
            audio: false
        });

        webcamVideo.srcObject = stream;
        await webcamVideo.play();

        if (overlayCanvas) {
            overlayCanvas.width = webcamVideo.videoWidth || 640;
            overlayCanvas.height = webcamVideo.videoHeight || 480;
            overlayCanvas.style.display = 'block';
        }

        trackingRunning = true;
        var drawingUtils = new DrawingUtils(overlayCtx);
        requestAnimationFrame(function trackLoop(timestamp) {
            if (!trackingRunning) return;

            overlayCtx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
            overlayCtx.save();
            overlayCtx.scale(-1, 1);
            overlayCtx.drawImage(webcamVideo, -overlayCanvas.width, 0, overlayCanvas.width, overlayCanvas.height);
            overlayCtx.restore();

            if (faceLandmarker && webcamVideo.readyState >= 2) {
                var results;
                try {
                    results = faceLandmarker.detectForVideo(webcamVideo, timestamp);
                } catch (e) {
                    requestAnimationFrame(trackLoop);
                    return;
                }

                var numFaces = results.faceLandmarks ? results.faceLandmarks.length : 0;
                if (hudFaces) hudFaces.textContent = numFaces;

                if (numFaces > 0) {
                    for (var i = 0; i < numFaces; i++) {
                        var landmarks = results.faceLandmarks[i];
                        var mirrored = landmarks.map(function(p) {
                            return { x: 1 - p.x, y: p.y, z: p.z };
                        });

                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_TESSELATION, { color: '#C0C0C070', lineWidth: 1 });
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_FACE_OVAL, { color: '#E0E0E0', lineWidth: 2 });
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_LEFT_EYE, { color: '#30FF30', lineWidth: 1 });
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE, { color: '#30FF30', lineWidth: 1 });
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_LEFT_IRIS, { color: '#FF3030', lineWidth: 1 });
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_RIGHT_IRIS, { color: '#FF3030', lineWidth: 1 });
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_LIPS, { color: '#FF6090', lineWidth: 1 });
                    }

                    var expr = getExpression(results);
                    if (hudExpression) hudExpression.textContent = expr;

                    socket.emit('face_data', {
                        faces: numFaces,
                        expression: expr
                    });
                } else {
                    socket.emit('face_data', { faces: 0, expression: '' });
                }
            }

            requestAnimationFrame(trackLoop);
        });

        var iframeEl = document.getElementById('dynamicIframe');
        if (iframeEl) iframeEl.style.display = 'none';
        var placeholder = document.getElementById('videoPlaceholder');
        if (placeholder) placeholder.style.display = 'none';

    } catch (err) {
        console.log('Face mesh tracking not available: ' + err.message);
    }
}

function getExpression(results) {
    if (!results.faceBlendshapes || !results.faceBlendshapes[0]) return 'neutral';
    var shapes = results.faceBlendshapes[0].categories;
    var smile = 0, surprise = 0, brow = 0;
    for (var i = 0; i < shapes.length; i++) {
        var s = shapes[i];
        if (s.categoryName === 'mouthSmileLeft' || s.categoryName === 'mouthSmileRight') {
            smile += s.score;
        }
        if (s.categoryName === 'jawOpen') surprise += s.score;
        if (s.categoryName === 'browInnerUp') brow += s.score;
    }
    if (surprise > 0.5) return 'surprised';
    if (smile > 0.8) return 'happy';
    if (brow > 0.4) return 'angry';
    return 'neutral';
}

function printDetection(newDetection) {
    scans.unshift(newDetection);
    if (scans.length > MAX_RECENT_SCANS) { scans.pop(); }
}

function renderDetections() {
    if (!recentDetectionsElement) return;
    recentDetectionsElement.innerHTML = '';

    if (scans.length === 0) {
        recentDetectionsElement.innerHTML = '<li class="no-recent-scans">No face detected yet</li>';
        return;
    }

    scans.forEach(function (scan) {
        var li = document.createElement('li');
        li.className = 'detection-item';
        var content = scan.content || 'face';
        var confidence = scan.confidence ? (scan.confidence * 100).toFixed(0) + '%' : '';
        var time = scan.timestamp ? new Date(scan.timestamp).toLocaleTimeString() : '';
        li.innerHTML = '<span class="detection-label">' + content + '</span>' +
                       '<span class="detection-confidence">' + confidence + '</span>' +
                       '<span class="detection-time">' + time + '</span>';
        recentDetectionsElement.appendChild(li);
    });
}

function initializeConfidenceSlider() {
    var confidenceSlider = document.getElementById('confidenceSlider');
    var confidenceInput = document.getElementById('confidenceInput');
    var confidenceResetButton = document.getElementById('confidenceResetButton');

    if (!confidenceSlider) return;

    confidenceSlider.addEventListener('input', updateConfidenceDisplay);

    if (confidenceInput) {
        confidenceInput.addEventListener('change', function () {
            var value = parseFloat(confidenceInput.value);
            if (isNaN(value)) value = 0.5;
            if (value < 0) value = 0;
            if (value > 1) value = 1;
            confidenceSlider.value = value;
            confidenceInput.value = value.toFixed(2);
            updateConfidenceDisplay();
        });
    }

    if (confidenceResetButton) {
        confidenceResetButton.addEventListener('click', function () {
            confidenceSlider.value = '0.5';
            if (confidenceInput) confidenceInput.value = '0.50';
            updateConfidenceDisplay();
        });
    }

    updateConfidenceDisplay();
}

function updateConfidenceDisplay() {
    var confidenceSlider = document.getElementById('confidenceSlider');
    var confidenceInput = document.getElementById('confidenceInput');
    var confidenceValueDisplay = document.getElementById('confidenceValueDisplay');
    var sliderProgress = document.getElementById('sliderProgress');

    if (!confidenceSlider) return;

    var value = parseFloat(confidenceSlider.value);
    socket.emit('override_th', value);
    var percentage = (value - confidenceSlider.min) / (confidenceSlider.max - confidenceSlider.min) * 100;

    var displayValue = value.toFixed(2);
    if (confidenceValueDisplay) {
        confidenceValueDisplay.textContent = displayValue;
        confidenceValueDisplay.style.left = percentage + '%';
    }

    if (confidenceInput && document.activeElement !== confidenceInput) {
        confidenceInput.value = displayValue;
    }

    if (sliderProgress) {
        sliderProgress.style.width = percentage + '%';
    }
}
