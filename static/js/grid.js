document.addEventListener('DOMContentLoaded', async () => {
    const cameraGrid = document.getElementById('camera-grid');
    const captureAllBtn = document.getElementById('capture-all-btn');
    const prefixInput = document.getElementById('prefix-input');
    const delayTimerCheckbox = document.getElementById('delay-timer-checkbox');
    const delayTimerInput = document.getElementById('delay-timer-input');

    const modal = document.getElementById('preview-modal');
    const modalClose = document.querySelector('.close');
    const modalControls = document.getElementById('modal-controls');

    function closeModal() {
        const controls = modalControls.querySelector('.camera-controls');
        if (controls) {
            const originalParentId = controls.dataset.originalParent;
            const originalParent = document.getElementById(originalParentId);
            if (originalParent) {
                originalParent.appendChild(controls);
            }
        }
        modal.style.display = "none";
        modalControls.innerHTML = ''; // Clear the controls from the modal
    }

    if(modalClose) {
        modalClose.addEventListener('click', closeModal);
    }

    if(modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
    }

    if(delayTimerCheckbox) {
        delayTimerCheckbox.addEventListener('change', () => {
            delayTimerInput.disabled = !delayTimerCheckbox.checked;
        });
    }

    try {
        const response = await fetch(`/api/cameras?t=${new Date().getTime()}`);
        const availableCameras = await response.json();

        if (Object.keys(availableCameras).length === 0) {
            cameraGrid.innerHTML = '<p class="no-cameras">No cameras detected.</p>';
            captureAllBtn.disabled = true;
            return;
        }

        cameraGrid.innerHTML = ''; // Clear "Detecting cameras..." message

        for (const camPath in availableCameras) {
            const cameraInfo = availableCameras[camPath];
            const cameraContainer = document.createElement('div');
            cameraContainer.className = 'camera-container';
            cameraContainer.dataset.cameraPath = camPath;
            cameraContainer.id = `camera-container-${camPath}`;

            const previewDiv = document.createElement('div');
            previewDiv.className = 'camera-preview';

            const autofocusStatus = document.createElement('div');
            autofocusStatus.className = 'autofocus-status';
            previewDiv.appendChild(autofocusStatus);

            const cameraTitle = document.createElement('h2');
            cameraTitle.textContent = cameraInfo.friendly_name;
            previewDiv.appendChild(cameraTitle);

            const img = document.createElement('img');
            img.src = `/video_feed?camera_path=${camPath}`;
            img.alt = `Camera ${cameraInfo.friendly_name} Feed`;
            img.onerror = () => {
                cameraContainer.style.display = 'none';
            };
            previewDiv.appendChild(img);

            previewDiv.addEventListener('click', () => {
                const modal = document.getElementById('preview-modal');
                const modalImg = document.getElementById('modal-image');
                const modalControls = document.getElementById('modal-controls');
                const controls = cameraContainer.querySelector('.camera-controls');
                const resolutionSelect = cameraContainer.querySelector('.resolution-select');
                const modalResolutionDisplay = document.getElementById('modal-resolution-display');

                // Store original parent
                controls.dataset.originalParent = cameraContainer.id;
                
                modalControls.appendChild(controls);
                modal.style.display = "block";
                modalImg.src = img.src;
                if(modalResolutionDisplay) {
                    modalResolutionDisplay.textContent = resolutionSelect.value;
                }
            });

            const controlsContainer = document.createElement('div');
            controlsContainer.className = 'camera-controls';

            // Resolution
            const resolutionDiv = document.createElement('div');
            resolutionDiv.className = 'control-group';
            const resolutionLabel = document.createElement('label');
            resolutionLabel.textContent = 'Resolution:';
            const resolutionSelect = document.createElement('select');
            resolutionSelect.className = 'resolution-select';
            resolutionDiv.appendChild(resolutionLabel);
            resolutionDiv.appendChild(resolutionSelect);
            controlsContainer.appendChild(resolutionDiv);

            // Shutter Speed
            const shutterDiv = document.createElement('div');
            shutterDiv.className = 'control-group';
            const shutterLabel = document.createElement('label');
            shutterLabel.textContent = 'Shutter Speed:';
            const shutterSelect = document.createElement('select');
            shutterSelect.className = 'shutter-speed-select';
            shutterDiv.appendChild(shutterLabel);
            shutterDiv.appendChild(shutterSelect);
            controlsContainer.appendChild(shutterDiv);

            updateShutterSpeedOptions(shutterSelect, camPath);

            shutterSelect.addEventListener('change', () => {
                const selectedShutterSpeed = shutterSelect.value;
                const selectedResolution = resolutionSelect.value;
                img.src = `/video_feed?camera_path=${camPath}&resolution=${selectedResolution}&shutter_speed=${selectedShutterSpeed}`;
            });

            // Autofocus
            const autofocusDiv = document.createElement('div');
            autofocusDiv.className = 'control-group';
            const autofocusLabel = document.createElement('label');
            autofocusLabel.textContent = 'Autofocus:';
            const autofocusCheckbox = document.createElement('input');
            autofocusCheckbox.type = 'checkbox';
            autofocusCheckbox.className = 'autofocus-checkbox';
            autofocusCheckbox.checked = true;
            autofocusDiv.appendChild(autofocusLabel);
            autofocusDiv.appendChild(autofocusCheckbox);
            controlsContainer.appendChild(autofocusDiv);

            // Manual Focus
            const manualFocusDiv = document.createElement('div');
            manualFocusDiv.className = 'control-group';
            const manualFocusLabel = document.createElement('label');
            manualFocusLabel.textContent = 'Manual Focus:';
            const manualFocusSlider = document.createElement('input');
            manualFocusSlider.type = 'range';
            manualFocusSlider.className = 'manual-focus-slider';
            manualFocusSlider.min = 0;
            manualFocusSlider.max = 1000;
            manualFocusSlider.value = 0;
            manualFocusSlider.disabled = autofocusCheckbox.checked;
            const manualFocusValue = document.createElement('span');
            manualFocusValue.className = 'manual-focus-value';
            manualFocusValue.textContent = '0.0';
            manualFocusDiv.appendChild(manualFocusLabel);
            manualFocusDiv.appendChild(manualFocusSlider);
            manualFocusDiv.appendChild(manualFocusValue);
            controlsContainer.appendChild(manualFocusDiv);

            // Subfolder Input for each camera
            const subfolderDiv = document.createElement('div');
            subfolderDiv.className = 'control-group';
            const subfolderLabel = document.createElement('label');
            subfolderLabel.textContent = 'Subfolder:';
            const subfolderInput = document.createElement('input');
            subfolderInput.type = 'text';
            subfolderInput.className = 'camera-subfolder-input'; // New class to easily select these inputs
            const safeFolderName = cameraInfo.friendly_name.replace(/[^a-zA-Z0-9_.-]/g, '_');
            subfolderInput.value = safeFolderName; // Default value
            subfolderDiv.appendChild(subfolderLabel);
            subfolderDiv.appendChild(subfolderInput);
            controlsContainer.appendChild(subfolderDiv);

            const resolutionDisplay = document.createElement('div');
            resolutionDisplay.className = 'resolution-display';
            previewDiv.appendChild(resolutionDisplay);

            resolutionSelect.addEventListener('change', () => {
                const selectedResolution = resolutionSelect.value;
                const selectedShutterSpeed = shutterSelect.value;
                resolutionDisplay.textContent = selectedResolution;
                img.src = `/video_feed?camera_path=${camPath}&resolution=${selectedResolution}&shutter_speed=${selectedShutterSpeed}`;

                const modalResolutionDisplay = document.getElementById('modal-resolution-display');
                if (modalResolutionDisplay) {
                    modalResolutionDisplay.textContent = selectedResolution;
                }
            });

            // Fetch camera info to disable controls if not supported
            fetch(`/api/camera_info/${camPath}?t=${new Date().getTime()}`)
                .then(res => res.json())
                .then(info => {
                    const autofocusStatus = cameraContainer.querySelector('.autofocus-status');
                    if (info.has_autofocus) {
                        autofocusStatus.textContent = 'AF';
                        autofocusStatus.classList.add('af-available');
                    } else {
                        autofocusStatus.textContent = 'No AF';
                        autofocusStatus.classList.add('af-unavailable');
                        autofocusCheckbox.disabled = true;
                        manualFocusSlider.disabled = true;
                    }
                });

            cameraContainer.appendChild(previewDiv);
            cameraContainer.appendChild(controlsContainer);
            cameraGrid.appendChild(cameraContainer);

            // Populate resolutions
            fetch(`/api/resolutions?camera_path=${camPath}&t=${new Date().getTime()}`)
                .then(res => res.json())
                .then(resolutions => {
                    resolutions.forEach(res => {
                        const option = document.createElement('option');
                        option.value = res;
                        option.textContent = res;
                        resolutionSelect.appendChild(option);
                    });
                    if (resolutions.includes("1280x720")) {
                        resolutionSelect.value = "1280x720";
                    } else if (resolutions.length > 0) {
                        resolutionSelect.value = resolutions[0];
                    }
                    resolutionDisplay.textContent = resolutionSelect.value;
                    img.src = `/video_feed?camera_path=${camPath}&resolution=${resolutionSelect.value}`;
                });

            // Add event listeners for focus controls
            autofocusCheckbox.addEventListener('change', () => {
                manualFocusSlider.disabled = autofocusCheckbox.checked;
                fetch('/api/autofocus', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ camera_path: camPath, enable: autofocusCheckbox.checked })
                });
            });

            manualFocusSlider.addEventListener('input', () => {
                const focusValue = manualFocusSlider.value;
                manualFocusValue.textContent = (focusValue / 100).toFixed(1);
                fetch('/api/manual_focus', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ camera_path: camPath, focus_value: focusValue / 100 })
                });
            });
        }

        if(captureAllBtn) {
            captureAllBtn.addEventListener('click', async () => {
                if (delayTimerCheckbox.checked) {
                    let countdown = parseInt(delayTimerInput.value, 10);
                    logMessage(`Starting capture in ${countdown} seconds...`);
                    const originalBtnText = captureAllBtn.textContent;
                    captureAllBtn.disabled = true;
                    const countdownInterval = setInterval(() => {
                        countdown--;
                        captureAllBtn.textContent = countdown;
                        if (countdown <= 0) {
                            clearInterval(countdownInterval);
                            captureAllBtn.textContent = originalBtnText;
                            captureAllBtn.disabled = false;
                            performCapture();
                        }
                    }, 1000);
                } else {
                    performCapture();
                }
            });
        }

        async function performCapture() {
            logMessage('Capturing images from all active cameras...');
            captureAllBtn.disabled = true;

            const captureRequests = [];
            document.querySelectorAll('.camera-container').forEach(container => {
                const camPath = container.dataset.cameraPath;
                const resolution = container.querySelector('.resolution-select').value;
                const shutterSpeed = container.querySelector('.shutter-speed-select').value;
                const autofocus = container.querySelector('.autofocus-checkbox').checked;
                const manualFocus = container.querySelector('.manual-focus-slider').value;

                const subfolder = container.querySelector('.camera-subfolder-input').value; // Get per-camera subfolder

                captureRequests.push({
                    camera_path: camPath,
                    resolution: resolution,
                    shutter_speed: shutterSpeed,
                    autofocus: autofocus,
                    manual_focus: manualFocus,
                    subfolder: subfolder // Add subfolder to the request
                });
            });

            try {
                const captureResponse = await fetch('/api/capture_all', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        prefix: prefixInput.value,
                        captures: captureRequests
                    }),
                });
                const captureData = await captureResponse.json();

                if (captureData.status === 'success') {
                    logMessage(captureData.message);
                    logMessage(`Captured files: ${captureData.captured_files.join(', ')}`);
                } else {
                    logMessage(`Error: ${captureData.detail}`, true);
                }
            } catch (error) {
                console.error('Fetch Error:', error);
                logMessage('Error connecting to server for capture.', true);
            } finally {
                captureAllBtn.disabled = false;
            }
        }

    } catch (error) {
        console.error('Error fetching cameras:', error);
        logMessage(`Error loading cameras: ${error.message}`, true);
        if(cameraGrid) {
            cameraGrid.innerHTML = '<p class="no-cameras">Error loading cameras. Please check the log box for details.</p>';
        }
        if(captureAllBtn) {
            captureAllBtn.disabled = true;
        }
    }
});

function logMessage(message, isError = false) {
    const logArea = document.getElementById('log-area');
    if(logArea) {
        const p = document.createElement('p');
        const timestamp = new Date().toLocaleTimeString();
        p.textContent = `[${timestamp}] ${message}`;
        if (isError) {
            p.classList.add('error');
        }
        logArea.appendChild(p);
        logArea.scrollTop = logArea.scrollHeight; // Auto-scroll to bottom
    }
}

async function updateShutterSpeedOptions(shutterSelect, camPath) {
    const response = await fetch(`/api/shutter_speed_range/${camPath}`);
    const range = await response.json();
    const [min, max] = range;

    shutterSelect.innerHTML = '<option value="Auto">Auto</option>';

    if (min === 0 && max === 0) {
        // No specific range, use default options
        const defaultOptions = ['1/30s', '1/60s', '1/125s', '1/250s', '1/500s', '1/1000s'];
        defaultOptions.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            shutterSelect.appendChild(option);
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
            shutterSelect.appendChild(option);
        }
    });
}