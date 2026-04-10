var recentDetectionsElement = document.getElementById('recentDetections');
var feedbackContentElement = document.getElementById('feedback-content');
var hudFaces = document.getElementById('hudFaces');
var hudExpression = document.getElementById('hudExpression');
var errorContainer = document.getElementById('error-container');
var MAX_RECENT_SCANS = 5;
var scans = [];
var socket = io('http://' + window.location.host);
var handVisible = false;

initSocketIO();
initializeConfidenceSlider();
renderDetections();

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
        if (hudExpression) hudExpression.textContent = message.content || 'face';

        if (!handVisible) {
            var greetings = ["Hello!", "Hi there!", "Hey!", "Nice to see you!", "Great to have you here!", "I see you", "Looking good!", "There you are!", "Howdy!", "Happy to see a face!", "Hi, friend!", "Face detected!", "Hello, human!"];
            var randomGreeting = greetings[Math.floor(Math.random() * greetings.length)];
            feedbackContentElement.innerHTML = '<p>' + randomGreeting + '</p>';
            handVisible = true;
        }

        detectionTimeout = setTimeout(function () {
            feedbackContentElement.innerHTML = '<p class="feedback-text">System response will appear here</p>';
            handVisible = false;
            if (hudFaces) hudFaces.textContent = '0';
            if (hudExpression) hudExpression.textContent = '--';
        }, 3000);
    });

    socket.on('face_data_ack', function (data) {
        if (data && hudExpression) {
            hudExpression.textContent = data.expression || '--';
        }
    });
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
