// SPDX-FileCopyrightText: Copyright (C) 2025 Wojo
//
// SPDX-License-Identifier: MIT

const recentDetectionsElement = document.getElementById('recentDetections');
const feedbackContentElement = document.getElementById('feedback-content');
const statusBadge = document.getElementById('statusBadge');
const MAX_RECENT_SCANS = 8;
let scans = [];
const socket = io(`http://${window.location.host}`);
let errorContainer = document.getElementById('error-container');
let faceVisible = false;

document.addEventListener('DOMContentLoaded', () => {
    initSocketIO();
    initializeConfidenceSlider();
    feedbackContentElement.innerHTML = `<p class="feedback-text">System response will appear here</p>`;
    faceVisible = false;
    renderDetections();
});

function initSocketIO() {
    let detectionTimeout;

    socket.on('connect', () => {
        statusBadge.textContent = 'Connected';
        statusBadge.className = 'status-badge connected';
        if (errorContainer) {
            errorContainer.style.display = 'none';
            errorContainer.textContent = '';
        }
    });

    socket.on('disconnect', () => {
        statusBadge.textContent = 'Disconnected';
        statusBadge.className = 'status-badge';
        if (errorContainer) {
            errorContainer.textContent = 'Connection to the board lost. Please check the connection.';
            errorContainer.style.display = 'block';
        }
    });

    socket.on('detection', (message) => {
        clearTimeout(detectionTimeout);
        statusBadge.textContent = 'Face Detected';
        statusBadge.className = 'status-badge active';
        printDetection(message);
        renderDetections();

        if (!faceVisible) {
            const greetings = [
                "Hello!", "Hi there!", "Hey!", "Nice to see you!",
                "Looking good!", "There you are!", "Howdy!",
                "Face detected!", "Hello, human!", "I see you!"
            ];
            const randomGreeting = greetings[Math.floor(Math.random() * greetings.length)];
            feedbackContentElement.innerHTML = `
                <p class="greeting-text">${randomGreeting}</p>
            `;
            faceVisible = true;
        }

        detectionTimeout = setTimeout(() => {
            feedbackContentElement.innerHTML = `<p class="feedback-text">System response will appear here</p>`;
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
        recentDetectionsElement.innerHTML = `
            <div class="no-recent-scans">
                No face detected yet
            </div>
        `;
        return;
    }

    scans.forEach((scan) => {
        const row = document.createElement('div');
        row.className = 'scan-container';

        const cellContainer = document.createElement('span');
        cellContainer.className = 'scan-cell-container cell-border';

        const contentText = document.createElement('span');
        contentText.className = 'scan-content';
        const value = scan.confidence;
        const result = Math.floor(value * 1000) / 10;
        contentText.innerHTML = `${result}% — ${scan.content || 'Face'}`;

        const timeText = document.createElement('span');
        timeText.className = 'scan-content-time';
        timeText.textContent = new Date(scan.timestamp).toLocaleTimeString();

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
    socket.emit('override_th', value);
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
