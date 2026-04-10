// SPDX-FileCopyrightText: Copyright (C) 2025 ARDUINO SA <http://www.arduino.cc>
//
// SPDX-License-Identifier: MPL-2.0

const recentDetectionsElement = document.getElementById('recentDetections');
const feedbackContentElement = document.getElementById('feedback-content');
const MAX_RECENT_SCANS = 5;
let scans = [];
const socket = io(`http://${window.location.host}`); // Initialize socket.io connection
let errorContainer = document.getElementById('error-container');
let handVisible = false;

// Start the application
document.addEventListener('DOMContentLoaded', () => {
    initSocketIO();
    initializeConfidenceSlider();
    feedbackContentElement.innerHTML = `
        <img src="img/stars.svg" alt="Stars">
        <p class="feedback-text">System response will appear here</p>
    `;
    handVisible = false;
    renderDetections();

    // Popover logic
    const confidencePopoverText = "Minimum confidence score for detected faces. Lower values show more results but may include false positives.";
    const feedbackPopoverText = "When camera detects a face, an animation will appear here.";

    document.querySelectorAll('.info-btn.confidence').forEach(img => {
        const popover = img.nextElementSibling;
        img.addEventListener('mouseenter', () => {
            popover.textContent = confidencePopoverText;
            popover.style.display = 'block';
        });
        img.addEventListener('mouseleave', () => {
            popover.style.display = 'none';
        });
    });

    document.querySelectorAll('.info-btn.feedback').forEach(img => {
        const popover = img.nextElementSibling;
        img.addEventListener('mouseenter', () => {
            popover.textContent = feedbackPopoverText;
            popover.style.display = 'block';
        });
        img.addEventListener('mouseleave', () => {
            popover.style.display = 'none';
        });
    });
});

function initSocketIO() {
    let detectionTimeout;

    socket.on('connect', () => {
        if (errorContainer) {
            errorContainer.style.display = 'none';
            errorContainer.textContent = '';
        }
    });

    socket.on('disconnect', () => {
        if (errorContainer) {
            errorContainer.textContent = 'Connection to the board lost. Please check the connection.';
            errorContainer.style.display = 'block';
        }
    });

    socket.on('detection', async (message) => {
        clearTimeout(detectionTimeout);
        printDetection(message);
        renderDetections();

        if (!handVisible) {
            const greetings = ["Hello!", "Hi there!", "Hey!", "Nice to see you!", "Great to have you here!", "I see you", "Looking good!", "There you are!", "Howdy!", "Happy to see a face!", "Hi, friend!", "Face detected!", "Hello, human!"];
            const randomGreeting = greetings[Math.floor(Math.random() * greetings.length)];
            const greetingImg = document.createElement('img');
            greetingImg.src = 'img/hand.gif';
            greetingImg.alt = 'Hand';
            const greetingP = document.createElement('p');
            greetingP.textContent = randomGreeting;
            feedbackContentElement.textContent = '';
            feedbackContentElement.appendChild(greetingImg);
            feedbackContentElement.appendChild(greetingP);
            handVisible = true;
        }

        detectionTimeout = setTimeout(() => {
            feedbackContentElement.innerHTML = `
                <img src="img/stars.svg" alt="Stars">
                <p class="feedback-text">System response will appear here</p>
            `;
            handVisible = false;
        }, 3000); // Revert after 3 seconds of no detections
    });

}

function printDetection(newDetection) {
    scans.unshift(newDetection);
    if (scans.length > MAX_RECENT_SCANS) { scans.pop(); }
}

// Function to render the list of scans
function renderDetections() {
    // Clear the list
    recentDetectionsElement.replaceChildren();

    if (scans.length === 0) {
        const noScans = document.createElement('div');
        noScans.className = 'no-recent-scans';
        const img = document.createElement('img');
        img.src = './img/no-face.svg';
        const label = document.createTextNode('No face detected yet');
        noScans.appendChild(img);
        noScans.appendChild(label);
        recentDetectionsElement.appendChild(noScans);
        return;
    }

    scans.forEach((scan) => {
        const row = document.createElement('div');
        row.className = 'scan-container';

        // Create a container for content and time
        const cellContainer = document.createElement('span');
        cellContainer.className = 'scan-cell-container cell-border';

        // Content (text + icon)
        const contentText = document.createElement('span');
        contentText.className = 'scan-content';
                const value = scan.confidence;
                const result = Math.floor(value * 1000) / 10;
        contentText.textContent = `${result}% - Face`;

        // Time
        const timeText = document.createElement('span');
        timeText.className = 'scan-content-time';
        timeText.textContent = new Date(scan.timestamp).toLocaleString('it-IT').replace(',', ' -');

        // Append content and time to the container
        cellContainer.appendChild(contentText);
        cellContainer.appendChild(timeText);

        row.appendChild(cellContainer);
        recentDetectionsElement.appendChild(row);
    });
}


function initializeConfidenceSlider() {
    const confidenceSlider = document.getElementById('confidenceSlider');
    const confidenceInput = document.getElementById('confidenceInput');
    const confidenceResetButton = document.getElementById('confidenceResetButton');

    confidenceSlider.addEventListener('input', updateConfidenceDisplay);
    confidenceInput.addEventListener('input', handleConfidenceInputChange);
    confidenceInput.addEventListener('blur', validateConfidenceInput);
    updateConfidenceDisplay();

    confidenceResetButton.addEventListener('click', (e) => {
        if (e.target.classList.contains('reset-icon') || e.target.closest('.reset-icon')) {
            resetConfidence();
        }
    });
}

function handleConfidenceInputChange() {
    const confidenceInput = document.getElementById('confidenceInput');
    const confidenceSlider = document.getElementById('confidenceSlider');

    let value = parseFloat(confidenceInput.value);

    if (isNaN(value)) value = 0.5;
    if (value < 0) value = 0;
    if (value > 1) value = 1;

    confidenceSlider.value = value;
    updateConfidenceDisplay();
}

function validateConfidenceInput() {
    const confidenceInput = document.getElementById('confidenceInput');
    let value = parseFloat(confidenceInput.value);

    if (isNaN(value)) value = 0.5;
    if (value < 0) value = 0;
    if (value > 1) value = 1;

    confidenceInput.value = value.toFixed(2);

    handleConfidenceInputChange();
}

function updateConfidenceDisplay() {
    const confidenceSlider = document.getElementById('confidenceSlider');
    const confidenceInput = document.getElementById('confidenceInput');
    const confidenceValueDisplay = document.getElementById('confidenceValueDisplay');
    const sliderProgress = document.getElementById('sliderProgress');

    const value = parseFloat(confidenceSlider.value);
    socket.emit('override_th', value); // Send confidence to backend
    const percentage = (value - confidenceSlider.min) / (confidenceSlider.max - confidenceSlider.min) * 100;

    const displayValue = value.toFixed(2);
    confidenceValueDisplay.textContent = displayValue;

    if (document.activeElement !== confidenceInput) {
        confidenceInput.value = displayValue;
    }

    sliderProgress.style.width = percentage + '%';
    confidenceValueDisplay.style.left = percentage + '%';
}

function resetConfidence() {
    const confidenceSlider = document.getElementById('confidenceSlider');
    const confidenceInput = document.getElementById('confidenceInput');

    confidenceSlider.value = '0.5';
    confidenceInput.value = '0.50';
    updateConfidenceDisplay();
}

// ========== WOJO ADDITION: MediaPipe Face Mesh Overlay ==========
(async function initFaceMeshOverlay() {
    const overlay = document.getElementById('meshOverlay');
    if (!overlay) return;
    const ctx = overlay.getContext('2d');

    try {
        const vision = await import('https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/vision_bundle.mjs');
        const { FaceLandmarker, FilesetResolver, DrawingUtils } = vision;

        const filesetResolver = await FilesetResolver.forVisionTasks(
            'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22/wasm'
        );

        const faceLandmarker = await FaceLandmarker.createFromOptions(filesetResolver, {
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

        const video = document.createElement('video');
        video.setAttribute('autoplay', '');
        video.setAttribute('playsinline', '');
        video.setAttribute('muted', '');

        const stream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: 'user' },
            audio: false
        });
        video.srcObject = stream;
        await video.play();

        overlay.width = video.videoWidth || 640;
        overlay.height = video.videoHeight || 480;
        overlay.style.display = 'block';

        const drawingUtils = new DrawingUtils(ctx);

        function trackLoop(timestamp) {
            ctx.clearRect(0, 0, overlay.width, overlay.height);

            ctx.save();
            ctx.scale(-1, 1);
            ctx.drawImage(video, -overlay.width, 0, overlay.width, overlay.height);
            ctx.restore();

            if (video.readyState >= 2) {
                let results;
                try {
                    results = faceLandmarker.detectForVideo(video, timestamp);
                } catch (e) {
                    requestAnimationFrame(trackLoop);
                    return;
                }

                if (results.faceLandmarks) {
                    for (let i = 0; i < results.faceLandmarks.length; i++) {
                        const mirrored = results.faceLandmarks[i].map(p => ({x: 1 - p.x, y: p.y, z: p.z}));

                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_TESSELATION, {color: '#C0C0C070', lineWidth: 1});
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_FACE_OVAL, {color: '#E0E0E0', lineWidth: 2});
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_LEFT_EYE, {color: '#30FF30', lineWidth: 1});
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_RIGHT_EYE, {color: '#30FF30', lineWidth: 1});
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_LEFT_IRIS, {color: '#FF3030', lineWidth: 1});
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_RIGHT_IRIS, {color: '#FF3030', lineWidth: 1});
                        drawingUtils.drawConnectors(mirrored, FaceLandmarker.FACE_LANDMARKS_LIPS, {color: '#FF6090', lineWidth: 1});
                    }

                    if (results.faceBlendshapes && results.faceBlendshapes[0]) {
                        const shapes = results.faceBlendshapes[0].categories;
                        let smile = 0, surprise = 0, brow = 0;
                        for (const s of shapes) {
                            if (s.categoryName === 'mouthSmileLeft' || s.categoryName === 'mouthSmileRight') smile += s.score;
                            if (s.categoryName === 'jawOpen') surprise += s.score;
                            if (s.categoryName === 'browInnerUp') brow += s.score;
                        }
                        let expr = 'neutral';
                        if (surprise > 0.5) expr = 'surprised';
                        else if (smile > 0.8) expr = 'happy';
                        else if (brow > 0.4) expr = 'angry';

                        socket.emit('face_data', {faces: results.faceLandmarks.length, expression: expr});
                    }
                }
            }

            requestAnimationFrame(trackLoop);
        }

        const iframeEl = document.getElementById('dynamicIframe');
        const placeholder = document.getElementById('videoPlaceholder');
        if (iframeEl) iframeEl.style.display = 'none';
        if (placeholder) placeholder.style.display = 'none';

        requestAnimationFrame(trackLoop);
        console.log('Face mesh overlay initialized successfully');

    } catch (err) {
        console.log('Face mesh overlay not available (getUserMedia/MediaPipe): ' + err.message);
        console.log('Falling back to brick camera iframe');
    }
})();