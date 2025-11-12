document.addEventListener('DOMContentLoaded', () => {
    const viewToggleCheckbox = document.getElementById('view-toggle-checkbox');

    if (viewToggleCheckbox) {
        viewToggleCheckbox.addEventListener('change', () => {
            if (viewToggleCheckbox.checked) {
                window.location.href = '/grid';
            } else {
                window.location.href = '/';
            }
        });
    }

    // Get UI elements
    const cameraSelect = document.getElementById('camera-select');
    const cameraFeed = document.getElementById('camera-feed');
    const subfolderInput = document.getElementById('subfolder-input');
    const captureBtn = document.getElementById('capture-image-btn');
    const resolutionSelect = document.getElementById('resolution-select');
    const shutterSpeedSelect = document.getElementById('shutter-speed-select');
    const autofocusCheckbox = document.getElementById('autofocus-checkbox');
    const manualFocusSlider = document.getElementById('manual-focus-slider');
    const manualFocusValue = document.getElementById('manual-focus-value');
    const resolutionDisplay = document.getElementById('resolution-display');
    const prefixInput = document.getElementById('prefix-input');
    const delayTimerCheckbox = document.getElementById('delay-timer-checkbox');
    const delayTimerInput = document.getElementById('delay-timer-input');
    const logArea = document.getElementById('log-area');

    let availableCameras = {};

    // --- Functions ---

    function logMessage(message, isError = false) {
        const p = document.createElement('p');
        const timestamp = new Date().toLocaleTimeString();
        p.textContent = `[${timestamp}] ${message}`;
        if (isError) {
            p.classList.add('error');
        }
        logArea.appendChild(p);
        logArea.scrollTop = logArea.scrollHeight; // Auto-scroll to bottom
    }

    function loadCameras() {
        fetch('/api/cameras')
            .then(response => response.json())
            .then(data => {
                availableCameras = data;
                cameraSelect.innerHTML = '<option value="">-- Please select a camera --</option>';
                for (const key in availableCameras) {
                    const option = document.createElement('option');
                    option.value = key;
                    option.textContent = availableCameras[key].friendly_name;
                    cameraSelect.appendChild(option);
                }
                logMessage('Camera list loaded successfully');
            })
            .catch(error => {
                console.error('Error fetching cameras:', error);
                logMessage('Error: Could not load camera list', true);
            });
    }

    function updateCameraFeed() {
        const selectedCameraPath = cameraSelect.value;
        const resolution = resolutionSelect.value;
        const shutterSpeed = shutterSpeedSelect.value;

        if (selectedCameraPath) {
            cameraFeed.src = `/video_feed?camera_path=${selectedCameraPath}&resolution=${resolution}&shutter_speed=${shutterSpeed}`;
            cameraFeed.style.display = 'block';
            resolutionDisplay.textContent = `Resolution: ${resolution}`;
            logMessage(`Displaying feed from: ${availableCameras[selectedCameraPath].friendly_name}`);
        } else {
            cameraFeed.src = '/static/images/placeholder.svg';
            cameraFeed.style.display = 'block';
            resolutionDisplay.textContent = '';
            logMessage('Please select a camera');
        }
    }

    // --- Event Listeners ---

    async function updateShutterSpeedOptions(selectedCameraPath) {
        const response = await fetch(`/api/shutter_speed_range/${selectedCameraPath}`);
        const range = await response.json();

        if (range === "unavailable") {
            shutterSpeedSelect.innerHTML = '<option value="Auto">Unavailable</option>';
            shutterSpeedSelect.disabled = true;
            return;
        }
        shutterSpeedSelect.disabled = false;


        const [min, max] = range;

        shutterSpeedSelect.innerHTML = '<option value="Auto">Auto</option>';

        if (min === 0 && max === 0) {
            // No specific range, use default options
            const defaultOptions = ['1/30s', '1/60s', '1/125s', '1/250s', '1/500s', '1/1000s'];
            defaultOptions.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt;
                option.textContent = opt;
                shutterSpeedSelect.appendChild(option);
            });
            return;
        }

        const commonDenominators = [30, 60, 125, 250, 500, 1000, 2000, 4000, 8000];
        
        commonDenominators.forEach(den => {
            if (den >= min && den <= max) {
                const option = document.createElement('option');
                const value = `1/${den}s`;
                option.value = value;
                option.textContent = value;
                shutterSpeedSelect.appendChild(option);
            }
        });
    }

    cameraSelect.addEventListener('change', async () => {
        const selectedCameraPath = cameraSelect.value;
        if (selectedCameraPath) {
            // Fetch resolutions
            const resolutionResponse = await fetch(`/api/resolutions?camera_path=${selectedCameraPath}`);
            const resolutions = await resolutionResponse.json();
            resolutionSelect.innerHTML = '';
            resolutions.forEach(resolution => {
                const option = document.createElement('option');
                option.value = resolution;
                option.textContent = resolution;
                resolutionSelect.appendChild(option);
            });

            // Fetch camera info for autofocus capabilities
            const cameraInfoResponse = await fetch(`/api/camera_info/${selectedCameraPath}`);
            const cameraInfo = await cameraInfoResponse.json();

            if (cameraInfo.type === 'pi' && cameraInfo.has_autofocus) {
                autofocusCheckbox.disabled = false;
                manualFocusSlider.disabled = !autofocusCheckbox.checked; // Enable slider only if autofocus is off
                autofocusCheckbox.checked = true; // Default to autofocus on for PiCameras with AF
            } else {
                autofocusCheckbox.disabled = true;
                autofocusCheckbox.checked = false; // Uncheck if no autofocus
                manualFocusSlider.disabled = true;
                manualFocusValue.textContent = 'N/A';
            }

            await updateShutterSpeedOptions(selectedCameraPath);

            updateCameraFeed();
        } else {
            updateCameraFeed();
            autofocusCheckbox.disabled = true;
            autofocusCheckbox.checked = false;
            manualFocusSlider.disabled = true;
            manualFocusValue.textContent = 'N/A';
        }
    });

    resolutionSelect.addEventListener('change', updateCameraFeed);
    shutterSpeedSelect.addEventListener('change', updateCameraFeed);

    autofocusCheckbox.addEventListener('change', async () => {
        const selectedCameraPath = cameraSelect.value;
        if (!selectedCameraPath) {
            logMessage('Please select a camera first.', true);
            autofocusCheckbox.checked = !autofocusCheckbox.checked; // Revert checkbox state
            return;
        }

        const enableAutofocus = autofocusCheckbox.checked;
        
        // Immediately update UI state
        manualFocusSlider.disabled = enableAutofocus;
        autofocusCheckbox.disabled = true; // Disable checkbox during API call
        manualFocusSlider.disabled = true; // Disable slider during API call

        try {
            const response = await fetch('/api/autofocus', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera_path: selectedCameraPath, enable: enableAutofocus }),
            });
            const data = await response.json();

            if (data.status === 'success') {
                logMessage(data.message);
            } else {
                logMessage(`Error: ${data.detail}`, true);
                autofocusCheckbox.checked = !autofocusCheckbox.checked; // Revert checkbox state on error
                manualFocusSlider.disabled = autofocusCheckbox.checked; // Revert slider state
            }
        } catch (error) {
            console.error('Fetch Error:', error);
            logMessage('Error connecting to server.', true);
            autofocusCheckbox.checked = !autofocusCheckbox.checked; // Revert checkbox state on error
            manualFocusSlider.disabled = autofocusCheckbox.checked; // Revert slider state
        } finally {
            autofocusCheckbox.disabled = false; // Re-enable checkbox
            manualFocusSlider.disabled = autofocusCheckbox.checked; // Set final slider state based on checkbox
        }
    });

    manualFocusSlider.addEventListener('input', () => {
        const focusValue = (manualFocusSlider.value / 100).toFixed(1);
        manualFocusValue.textContent = focusValue;
    });

    manualFocusSlider.addEventListener('change', async () => {
        const selectedCameraPath = cameraSelect.value;
        if (!selectedCameraPath) {
            logMessage('Please select a camera first.', true);
            return;
        }

        const cameraInfoResponse = await fetch(`/api/camera_info/${selectedCameraPath}`);
        const cameraInfo = await cameraInfoResponse.json();

        if (cameraInfo.type === 'pi' && !cameraInfo.has_autofocus) {
            logMessage('This PiCamera does not support autofocus, so manual focus is not available.', true);
            manualFocusSlider.disabled = true; // Ensure it's disabled
            return;
        }

        if (!selectedCameraPath.startsWith('pi_')) {
            logMessage('Please select a PiCamera first to adjust manual focus.', true);
            return;
        }

        const focusValue = parseFloat((manualFocusSlider.value / 100).toFixed(1));
        fetch('/api/manual_focus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ camera_path: selectedCameraPath, focus_value: focusValue }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                logMessage(data.message);
            } else {
                logMessage(`Error: ${data.detail}`, true);
            }
        })
        .catch(error => {
            console.error('Fetch Error:', error);
            logMessage('Error connecting to server.', true);
        });
    });

    delayTimerCheckbox.addEventListener('change', () => {
        delayTimerInput.disabled = !delayTimerCheckbox.checked;
    });

    captureBtn.addEventListener('click', () => {
        const selectedCameraPath = cameraSelect.value;
        const subfolder = subfolderInput.value;
        const prefix = prefixInput.value;
        const resolution = resolutionSelect.value;
        const shutterSpeed = shutterSpeedSelect.value;

        if (!selectedCameraPath) {
            logMessage('Please select a camera before capturing', true);
            return;
        }

        if (delayTimerCheckbox.checked) {
            let delay = parseInt(delayTimerInput.value, 10);
            if (isNaN(delay) || delay <= 0) {
                logMessage('Please set a valid delay time', true);
                return;
            }

            captureBtn.disabled = true;
            const countdownInterval = setInterval(() => {
                logMessage(`Capturing in ${delay} seconds...`);
                delay--;
                if (delay < 0) {
                    clearInterval(countdownInterval);
                    captureImage(selectedCameraPath, subfolder, prefix, resolution, shutterSpeed);
                    captureBtn.disabled = false;
                }
            }, 1000);
        } else {
            captureImage(selectedCameraPath, subfolder, prefix, resolution, shutterSpeed);
        }
    });

    function captureImage(selectedCameraPath, subfolder, prefix, resolution, shutterSpeed) {
        logMessage('Capturing image...');

        const autofocus = autofocusCheckbox.checked;
        const manual_focus = parseFloat((manualFocusSlider.value / 100).toFixed(1));

        fetch('/api/capture', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                camera_path: selectedCameraPath, 
                subfolder: subfolder, 
                prefix: prefix, 
                resolution: resolution, 
                shutter_speed: shutterSpeed,
                autofocus: autofocus,
                manual_focus: manual_focus
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                logMessage(data.message);
                if (data.capture_count !== undefined) {
                    logMessage(`Total images captured: ${data.capture_count}`);
                }
            } else {
                logMessage(`Error: ${data.detail}`, true);
            }
        })
        .catch(error => {
            console.error('Fetch Error:', error);
            logMessage('Error connecting to server', true);
        });
    }

    // --- Initial Load ---
    loadCameras();
});