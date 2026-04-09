// SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
//
// SPDX-License-Identifier: MIT
//
// Wojo's Face Outline Demo — Frontend Logic
// Arduino Uno Q | Qualcomm QRB2210 | Arduino App Lab
//
// Connects to the WebUI brick via Socket.IO to display real-time
// face detection results from the VideoObjectDetection brick.

const recentDetectionsElement = document.getElementById('recentDetections');
const feedbackContentElement = document.getElementById('feedback-content');
const statusBadge = document.getElementById('statusBadge');
const MAX_RECENT_SCANS = 8;
let scans = [];
const socket = io();
let errorContainer = document.getElementById('error-container');
let faceVisible = false;

document.addEventListener('DOMContentLoaded', function() {
    initSocketIO();
    initializeConfidenceSlider();
    feedbackContentElement.innerHTML = '<p class="feedback-text">System response will appear here</p>';
    faceVisible = false;
    renderDetections();
});

function initSocketIO() {
    let detectionTimeout;

    socket.on('connect', function() {
        statusBadge.textContent = 'Connected';
        statusBadge.className = 'status-badge connected';
        if (errorContainer) {
            errorContainer.style.display = 'none';
            errorContainer.textContent = '';
        }
    });

    socket.on('disconnect', function() {
        statusBadge.textContent = 'Disconnected';
        statusBadge.className = 'status-badge';
        if (errorContainer) {
            errorContainer.textContent = 'Connection to the board lost. Please check the connection.';
            errorContainer.style.display = 'block';
        }
    });

    socket.on('face_count', function(data) {
        var countEl = document.getElementById('faceCountNumber');
        if (countEl) {
            countEl.textContent = data.count;
            countEl.className = 'face-count-number' + (data.count > 0 ? ' active' : '');
        }
    });

    socket.on('detection', function(message) {
        clearTimeout(detectionTimeout);
        statusBadge.textContent = 'Face Detected';
        statusBadge.className = 'status-badge active';
        printDetection(message);
        renderDetections();

        if (!faceVisible) {
            var greetings = [
                "Hello!", "Hi there!", "Hey!", "Nice to see you!",
                "Looking good!", "There you are!", "Howdy!",
                "Face detected!", "Hello, human!", "I see you!"
            ];
            var randomGreeting = greetings[Math.floor(Math.random() * greetings.length)];
            var greetingEl = document.createElement('p');
            greetingEl.className = 'greeting-text';
            greetingEl.textContent = randomGreeting;
            feedbackContentElement.replaceChildren(greetingEl);
            faceVisible = true;
        }

        detectionTimeout = setTimeout(function() {
            var feedbackEl = document.createElement('p');
            feedbackEl.className = 'feedback-text';
            feedbackEl.textContent = 'System response will appear here';
            feedbackContentElement.replaceChildren(feedbackEl);
            faceVisible = false;
            statusBadge.textContent = 'Scanning...';
            statusBadge.className = 'status-badge scanning';
        }, 3000);
    });
}

function printDetection(newDetection) {
    scans.unshift(newDetection);
    if (scans.length > MAX_RECENT_SCANS) { scans.pop(); }
}

function renderDetections() {
    recentDetectionsElement.innerHTML = '';

    if (scans.length === 0) {
        recentDetectionsElement.innerHTML =
            '<div class="no-recent-scans">No face detected yet</div>';
        return;
    }

    scans.forEach(function(scan) {
        var row = document.createElement('div');
        row.className = 'scan-container';

        var cellContainer = document.createElement('span');
        cellContainer.className = 'scan-cell-container cell-border';

        var contentText = document.createElement('span');
        contentText.className = 'scan-content';
        var value = scan.confidence;
        var result = Math.floor(value * 1000) / 10;
        contentText.textContent = result + '% \u2014 ' + (scan.content || 'Face');

        var timeText = document.createElement('span');
        timeText.className = 'scan-content-time';
        timeText.textContent = new Date(scan.timestamp).toLocaleTimeString();

        cellContainer.appendChild(contentText);
        cellContainer.appendChild(timeText);

        row.appendChild(cellContainer);
        recentDetectionsElement.appendChild(row);
    });
}

function initializeConfidenceSlider() {
    var confidenceSlider = document.getElementById('confidenceSlider');
    var confidenceInput = document.getElementById('confidenceInput');
    var confidenceResetButton = document.getElementById('confidenceResetButton');

    confidenceSlider.addEventListener('input', updateConfidenceDisplay);
    confidenceInput.addEventListener('input', handleConfidenceInputChange);
    confidenceInput.addEventListener('blur', validateConfidenceInput);
    updateConfidenceDisplay();

    confidenceResetButton.addEventListener('click', function(e) {
        if (e.target.classList.contains('reset-icon') || e.target.closest('.reset-icon')) {
            resetConfidence();
        }
    });
}

function handleConfidenceInputChange() {
    var confidenceInput = document.getElementById('confidenceInput');
    var confidenceSlider = document.getElementById('confidenceSlider');

    var value = parseFloat(confidenceInput.value);

    if (isNaN(value)) value = 0.5;
    if (value < 0) value = 0;
    if (value > 1) value = 1;

    confidenceSlider.value = value;
    updateConfidenceDisplay();
}

function validateConfidenceInput() {
    var confidenceInput = document.getElementById('confidenceInput');
    var value = parseFloat(confidenceInput.value);

    if (isNaN(value)) value = 0.5;
    if (value < 0) value = 0;
    if (value > 1) value = 1;

    confidenceInput.value = value.toFixed(2);
    handleConfidenceInputChange();
}

function updateConfidenceDisplay() {
    var confidenceSlider = document.getElementById('confidenceSlider');
    var confidenceInput = document.getElementById('confidenceInput');
    var confidenceValueDisplay = document.getElementById('confidenceValueDisplay');
    var sliderProgress = document.getElementById('sliderProgress');

    var value = parseFloat(confidenceSlider.value);
    socket.emit('override_th', value);
    var percentage = (value - confidenceSlider.min) / (confidenceSlider.max - confidenceSlider.min) * 100;

    var displayValue = value.toFixed(2);
    confidenceValueDisplay.textContent = displayValue;

    if (document.activeElement !== confidenceInput) {
        confidenceInput.value = displayValue;
    }

    sliderProgress.style.width = percentage + '%';
    confidenceValueDisplay.style.left = percentage + '%';
}

function resetConfidence() {
    var confidenceSlider = document.getElementById('confidenceSlider');
    var confidenceInput = document.getElementById('confidenceInput');

    confidenceSlider.value = '0.5';
    confidenceInput.value = '0.50';
    updateConfidenceDisplay();
}
