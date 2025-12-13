document.addEventListener('DOMContentLoaded', () => {

    // Get UI elements
    const cameraSelect = document.getElementById('camera-select');
    const cameraFeed = document.getElementById('camera-feed');
    const captureBtn = document.getElementById('capture-image-btn');
    const resolutionSelect = document.getElementById('resolution-select');
    const shutterSpeedSelect = document.getElementById('shutter-speed-select');
    const autofocusCheckbox = document.getElementById('autofocus-checkbox');
    const manualFocusSlider = document.getElementById('manual-focus-slider');
    const manualFocusValue = document.getElementById('manual-focus-value');

    const resolutionDisplay = document.getElementById('resolution-display');
    const logArea = document.getElementById('log-area');

    // New UI Elements
    const recordingStatus = document.getElementById('recording-status');
    const galleryContainer = document.getElementById('gallery-container');
    const galleryPlaceholder = document.getElementById('gallery-placeholder');
    const deleteSelectedBtn = document.getElementById('delete-selected-btn');
    const selectedCountSpan = document.getElementById('selected-count');
    const selectAllBtn = document.getElementById('select-all-btn');
    const saveSettingsBtn = document.getElementById('save-settings-btn');

    // Hidden inputs (legacy support)
    const subfolderInput = document.getElementById('subfolder-input');
    const prefixInput = document.getElementById('prefix-input');
    const delayTimerCheckbox = document.getElementById('delay-timer-checkbox');
    const delayTimerInput = document.getElementById('delay-timer-input');

    let availableCameras = {};
    let isRecording = false;
    let knownFiles = new Set();
    let selectedFiles = new Set(); // Track selected files

    // --- Functions ---

    function logMessage(message, isError = false) {
        console.log(`[LOG] ${message}`);
        if (recordingStatus) {
            recordingStatus.textContent = message;
            recordingStatus.classList.toggle('text-red-400', isError);
            recordingStatus.classList.toggle('text-gray-400', !isError);
        }
        // Keep legacy log area updated just in case
        if (logArea) {
            const p = document.createElement('p');
            p.textContent = `> ${message}`;
            p.className = isError ? 'text-red-400' : 'text-gray-300';
            logArea.appendChild(p);
            logArea.scrollTop = logArea.scrollHeight;
        }
    }



    function loadCameras() {
        fetch('/api/cameras')
            .then(response => response.json())
            .then(data => {
                availableCameras = data;
                if (cameraSelect) {
                    cameraSelect.innerHTML = '<option value="">-- Select Camera --</option>';
                    for (const key in availableCameras) {
                        const option = document.createElement('option');
                        option.value = key;
                        option.textContent = availableCameras[key].friendly_name;
                        cameraSelect.appendChild(option);
                    }
                }
                logMessage('Ready');
            })
            .catch(error => {
                console.error('Error fetching cameras:', error);
                logMessage('Error loading cameras', true);
            });
    }

    function updateCameraFeed() {
        if (!cameraSelect || !cameraFeed) return;

        const selectedCameraPath = cameraSelect.value;
        const resolution = resolutionSelect ? resolutionSelect.value : '640x480';
        const shutterSpeed = shutterSpeedSelect ? shutterSpeedSelect.value : 'Auto';

        if (selectedCameraPath) {
            cameraFeed.src = `/video_feed?camera_path=${selectedCameraPath}&resolution=${resolution}&shutter_speed=${shutterSpeed}`;
            if (resolutionDisplay) resolutionDisplay.textContent = `Resolution: ${resolution}`;
            logMessage(`Feed active: ${availableCameras[selectedCameraPath].friendly_name}`);

            // Update preview status text if it exists
            const previewStatus = document.getElementById('preview-status');
            if (previewStatus) previewStatus.style.display = 'none';

        } else {
            cameraFeed.src = '/static/images/placeholder.svg';
            if (resolutionDisplay) resolutionDisplay.textContent = '';
            logMessage('Select a camera');
        }
    }

    async function updateShutterSpeedOptions(selectedCameraPath) {
        const response = await fetch(`/api/shutter_speed_range/${selectedCameraPath}`);
        const range = await response.json();

        if (range === "unavailable") {
            if (shutterSpeedSelect) {
                shutterSpeedSelect.innerHTML = '<option value="Auto">Unavailable</option>';
                shutterSpeedSelect.disabled = true;
            }
            return;
        }
        if (shutterSpeedSelect) shutterSpeedSelect.disabled = false;

        const [min, max] = range;
        shutterSpeedSelect.innerHTML = '<option value="Auto">Auto</option>';

        if (min === 0 && max === 0) {
            const defaultOptions = ['1/30s', '1/60s', '1/125s', '1/250s', '1/500s', '1/1000s'];
            defaultOptions.forEach(opt => {
                const option = document.createElement('option');
                option.value = opt;
                option.textContent = opt;
                if (shutterSpeedSelect) shutterSpeedSelect.appendChild(option);
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
                if (shutterSpeedSelect) shutterSpeedSelect.appendChild(option);
            }
        });
    }

    // --- Gallery Functions ---

    // --- Gallery Functions ---

    function updateDeleteButton() {
        const hasSelection = selectedFiles.size > 0;
        const totalItems = document.querySelectorAll('#gallery-container > div:not(#gallery-placeholder)').length;
        const allSelected = totalItems > 0 && selectedFiles.size === totalItems;

        if (hasSelection) {
            deleteSelectedBtn.classList.remove('hidden');
            selectedCountSpan.textContent = selectedFiles.size;
        } else {
            deleteSelectedBtn.classList.add('hidden');
        }

        // Handle Select All Button Visibility/Text
        // Only show Select All if there are items
        if (totalItems > 0) {
            selectAllBtn.classList.remove('hidden');
            if (allSelected) {
                selectAllBtn.textContent = 'Deselect All';
                selectAllBtn.onclick = () => deselectAll();
            } else {
                selectAllBtn.textContent = 'Select All';
                selectAllBtn.onclick = () => selectAll();
            }
        } else {
            selectAllBtn.classList.add('hidden');
        }
    }

    function selectAll() {
        const items = document.querySelectorAll('#gallery-container > div:not(#gallery-placeholder)');
        items.forEach(item => {
            const filename = item.dataset.filename;
            if (filename) {
                selectedFiles.add(filename);
                item.classList.add('ring-2', 'ring-accent-blue');
                const checkbox = item.querySelector('input[type="checkbox"]');
                if (checkbox) checkbox.checked = true;
                const checkboxContainer = item.querySelector('div.absolute');
                if (checkboxContainer) {
                    checkboxContainer.classList.remove('opacity-0');
                    checkboxContainer.classList.add('opacity-100');
                }
            }
        });
        updateDeleteButton();
    }

    function deselectAll() {
        selectedFiles.clear();
        const items = document.querySelectorAll('#gallery-container > div:not(#gallery-placeholder)');
        items.forEach(item => {
            item.classList.remove('ring-2', 'ring-accent-blue');
            const checkbox = item.querySelector('input[type="checkbox"]');
            if (checkbox) checkbox.checked = false;
            const checkboxContainer = item.querySelector('div.absolute');
            if (checkboxContainer) {
                checkboxContainer.classList.remove('opacity-100');
                checkboxContainer.classList.add('opacity-0');
            }
        });
        updateDeleteButton();
    }

    function toggleSelection(filename, cardElement, checkbox) {
        if (selectedFiles.has(filename)) {
            selectedFiles.delete(filename);
            cardElement.classList.remove('ring-2', 'ring-accent-blue');
            checkbox.checked = false;
            // We need to manage the container opacity manually here if we want instant feedback
            // logic in addToGallery handles hover, but for checked state:
            // already handled by onclick there with classes?
        } else {
            selectedFiles.add(filename);
            cardElement.classList.add('ring-2', 'ring-accent-blue');
            checkbox.checked = true;
        }
        updateDeleteButton();
    }

    function loadGallery() {
        if (!galleryContainer) return;

        fetch('/api/captures')
            .then(response => response.json())
            .then(files => {
                if (files.length > 0 && galleryPlaceholder) {
                    galleryPlaceholder.style.display = 'none';
                } else if (files.length === 0 && galleryPlaceholder) {
                    galleryPlaceholder.style.display = 'block'; // Show if empty
                }

                // Incremental update
                let hasNewFiles = false;
                files.forEach(file => {
                    if (!knownFiles.has(file)) {
                        knownFiles.add(file);
                        addToGallery(file); // Adds to top
                        hasNewFiles = true;
                    }
                });

                if (hasNewFiles || files.length > 0) {
                    updateDeleteButton(); // Refresh "Select All" visibility
                }

                // Note: If files were deleted from backend but still in knownFiles, we might need a full refresh logic eventually.
                // For now, we assume simple append-only or manual delete via UI.

            })
            .catch(err => console.error("Error loading gallery:", err));
    }

    function addToGallery(filename) {
        if (!galleryContainer) return;
        if (galleryPlaceholder) galleryPlaceholder.style.display = 'none';

        const url = `/captures/${filename}`;

        // Create Grid Item
        const galleryItem = document.createElement('div');
        // w-full to fill grid cell, relative for positioning checkbox/labels
        galleryItem.className = 'relative group bg-gray-800 rounded-xl overflow-hidden shadow-md hover:shadow-xl transition-all duration-200 border border-gray-700';
        galleryItem.dataset.filename = filename; // for easy finding later

        // Top Right Checkbox
        const checkboxContainer = document.createElement('div');
        checkboxContainer.className = "absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity";
        // If selected, it should be visible always
        if (selectedFiles.has(filename)) checkboxContainer.classList.remove('opacity-0');

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = "w-5 h-5 rounded border-gray-500 text-accent-blue focus:ring-accent-blue cursor-pointer";

        // Stop propagation so clicking checkbox doesn't trigger open image
        checkbox.onclick = (e) => {
            e.stopPropagation();
            toggleSelection(filename, galleryItem, checkbox);
            // Ensure visibility if checked
            if (checkbox.checked) {
                checkboxContainer.classList.remove('opacity-0');
                checkboxContainer.classList.add('opacity-100');
            } else {
                checkboxContainer.classList.remove('opacity-100');
                // Let hover handle it
                checkboxContainer.classList.add('opacity-0');
                checkboxContainer.classList.remove('opacity-0'); // Actually, let's just rely on group-hover if unchecked
            }
        };

        checkboxContainer.appendChild(checkbox);

        // Image
        const img = document.createElement('img');
        img.src = url;
        img.alt = filename;
        img.className = "w-full h-32 object-cover cursor-pointer hover:opacity-90 transition";
        img.onclick = () => window.open(url, '_blank');

        // Filename Label (Bottom)
        const label = document.createElement('div');
        label.className = "p-2 bg-gray-900 text-xs text-gray-400 truncate";
        label.textContent = filename.split('/').pop(); // Show only basename

        // Assemble
        galleryItem.appendChild(checkboxContainer);
        galleryItem.appendChild(img);
        galleryItem.appendChild(label);

        // Add to beginning of grid (Visual stack)
        // galleryContainer is a grid, order depends on DOM order. Prepending makes it first.
        if (galleryContainer.firstChild) {
            galleryContainer.insertBefore(galleryItem, galleryContainer.firstChild);
        } else {
            galleryContainer.appendChild(galleryItem);
        }

        // Limit to 20 items in DOM? User asked for "preview last 20 image".
        // Let's implement a hard limit of 20 items to keep it clean if requested, or just just keep adding.
        // The prompt said "preview last 20 image".
        // Let's trim the end if > 20.
        while (galleryContainer.children.length > 21) { // 20 items + placeholder (maybe)
            // Be careful about the placeholder.
            const lastChild = galleryContainer.lastElementChild;
            if (lastChild.id !== 'gallery-placeholder') {
                galleryContainer.removeChild(lastChild);
                // Also remove from knownFiles to allow re-adding if it somehow comes back as "new"? 
                // No, if we remove it from view, we don't want to re-add it immediately.
                // actually `knownFiles` prevents re-fetching old files.
            } else {
                break;
            }
        }
    }

    // --- Event Listeners ---

    if (cameraSelect) {
        cameraSelect.addEventListener('change', async () => {
            const selectedCameraPath = cameraSelect.value;
            if (selectedCameraPath) {
                if (resolutionSelect) {
                    const resolutionResponse = await fetch(`/api/resolutions?camera_path=${selectedCameraPath}`);
                    const resolutions = await resolutionResponse.json();
                    resolutionSelect.innerHTML = '';
                    resolutions.forEach(resolution => {
                        const option = document.createElement('option');
                        option.value = resolution;
                        option.textContent = resolution;
                        resolutionSelect.appendChild(option);
                    });
                }

                const cameraInfoResponse = await fetch(`/api/camera_info/${selectedCameraPath}`);
                const cameraInfo = await cameraInfoResponse.json();

                if (cameraInfo.type === 'pi' && cameraInfo.has_autofocus) {
                    if (autofocusCheckbox) {
                        autofocusCheckbox.disabled = false;
                        autofocusCheckbox.checked = true;
                    }
                    if (manualFocusSlider) manualFocusSlider.disabled = true;

                    const focusContainer = document.getElementById('focus-adjustment-container');
                    if (focusContainer) focusContainer.classList.add('opacity-50', 'pointer-events-none');
                } else {
                    if (autofocusCheckbox) {
                        autofocusCheckbox.disabled = true;
                        autofocusCheckbox.checked = false;
                    }
                    if (manualFocusSlider) manualFocusSlider.disabled = true;
                    if (manualFocusValue) manualFocusValue.textContent = 'N/A';

                    const focusContainer = document.getElementById('focus-adjustment-container');
                    if (focusContainer) focusContainer.classList.add('opacity-50', 'pointer-events-none');
                }

                await updateShutterSpeedOptions(selectedCameraPath);
                updateCameraFeed();

                // Set Active Camera Context
                fetch('/api/set_active_camera', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ camera_path: selectedCameraPath })
                }).catch(e => console.error("Error setting active context:", e));

            } else {
                updateCameraFeed();
            }
        });
    }

    if (resolutionSelect) resolutionSelect.addEventListener('change', updateCameraFeed);
    if (shutterSpeedSelect) shutterSpeedSelect.addEventListener('change', updateCameraFeed);

    if (autofocusCheckbox) {
        autofocusCheckbox.addEventListener('change', async () => {
            const selectedCameraPath = cameraSelect ? cameraSelect.value : null;
            if (!selectedCameraPath) return;

            const enableAutofocus = autofocusCheckbox.checked;
            if (manualFocusSlider) manualFocusSlider.disabled = enableAutofocus;

            // Update UI container style
            const focusContainer = document.getElementById('focus-adjustment-container');
            if (focusContainer) {
                if (enableAutofocus) {
                    focusContainer.classList.add('opacity-50', 'pointer-events-none');
                } else {
                    focusContainer.classList.remove('opacity-50', 'pointer-events-none');
                }
            }

            try {
                await fetch('/api/autofocus', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ camera_path: selectedCameraPath, enable: enableAutofocus }),
                });
                logMessage(`Autofocus ${enableAutofocus ? 'Enabled' : 'Disabled'}`);
            } catch (error) {
                console.error('Autofocus Error:', error);
                logMessage(`Error setting AF: ${error.message}`, true);
            }
        });
    }

    if (manualFocusSlider) {
        manualFocusSlider.addEventListener('input', () => {
            const focusValue = (manualFocusSlider.value / 100).toFixed(1);
            if (manualFocusValue) manualFocusValue.textContent = focusValue;
        });

        manualFocusSlider.addEventListener('change', async () => {
            const selectedCameraPath = cameraSelect ? cameraSelect.value : null;
            if (!selectedCameraPath) return;

            const focusValue = parseFloat((manualFocusSlider.value / 100).toFixed(1));
            fetch('/api/manual_focus', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ camera_path: selectedCameraPath, focus_value: focusValue }),
            });
        });
    }




    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', () => {
            const selectedCameraPath = cameraSelect ? cameraSelect.value : null;
            if (!selectedCameraPath) {
                logMessage('Select a camera first', true);
                return;
            }

            const resolution = resolutionSelect ? resolutionSelect.value : null;
            const shutterSpeed = shutterSpeedSelect ? shutterSpeedSelect.value : null;
            const autofocus = autofocusCheckbox ? autofocusCheckbox.checked : null;
            const prefix = prefixInput ? prefixInput.value : null;

            saveSettingsBtn.disabled = true;
            saveSettingsBtn.textContent = "Saving...";

            fetch('/api/save_camera_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    camera_path: selectedCameraPath,
                    resolution: resolution,
                    shutter_speed: shutterSpeed,
                    autofocus: autofocus,
                    prefix: prefix
                }),
            })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        logMessage(`Settings saved for ${selectedCameraPath}`);
                    } else {
                        logMessage(`Error saving settings: ${data.detail}`, true);
                    }
                })
                .catch(error => {
                    console.error('Save Settings Error:', error);
                    logMessage(`Error saving settings: ${error.message}`, true);
                })
                .finally(() => {
                    saveSettingsBtn.disabled = false;
                    saveSettingsBtn.innerHTML = `
                             <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                 <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path>
                             </svg>
                             Save Settings
                 `;
                });
        });
    }

    // --- Video Popup Logic ---
    function openVideoPopup() {
        const selectedCameraPath = cameraSelect ? cameraSelect.value : null;
        if (!selectedCameraPath) return;

        const modal = document.getElementById('video-popup-modal');
        const popupImg = document.getElementById('popup-video-feed');
        const popupName = document.getElementById('popup-camera-name');
        const popupDetails = document.getElementById('popup-camera-details');

        const resolution = resolutionSelect ? resolutionSelect.value : "Unknown";
        const shutter = shutterSpeedSelect ? shutterSpeedSelect.value : "Auto";
        const camName = cameraSelect.options[cameraSelect.selectedIndex].text;

        // Update Popup Content
        popupName.textContent = camName;
        popupDetails.textContent = `Resolution: ${resolution} | Shutter: ${shutter}`;

        // Set Source (Force reload)
        popupImg.src = `/video_feed?camera_path=${selectedCameraPath}&resolution=${resolution}&shutter_speed=${shutter}&t=${new Date().getTime()}`;

        // Show Modal
        modal.classList.remove('hidden');

        // --- Focus Slider Logic (Sync with Main Control) ---
        const focusControl = document.getElementById('popup-focus-control');
        const focusSlider = document.getElementById('popup-focus-slider');
        const focusValueDisplay = document.getElementById('popup-focus-value');

        // Check if manual focus is available and active (AF disabled)
        // Rely on the state of the main controls
        if (manualFocusSlider && !manualFocusSlider.disabled) {
            focusControl.classList.remove('hidden');
            focusSlider.value = manualFocusSlider.value;
            focusValueDisplay.textContent = (focusSlider.value / 100).toFixed(1);

            // Remove old listeners
            const newSlider = focusSlider.cloneNode(true);
            focusSlider.parentNode.replaceChild(newSlider, focusSlider);

            // Add new listeners
            newSlider.addEventListener('input', () => {
                focusValueDisplay.textContent = (newSlider.value / 100).toFixed(1);
                // Sync back to main UI
                if (manualFocusSlider) manualFocusSlider.value = newSlider.value;
                if (manualFocusValue) manualFocusValue.textContent = (newSlider.value / 100).toFixed(1);
            });

            newSlider.addEventListener('change', async () => {
                const val = parseFloat(newSlider.value);
                try {
                    await fetch('/api/manual_focus', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ camera_path: selectedCameraPath, focus_value: val / 100 })
                    });
                    if (manualFocusSlider) manualFocusSlider.value = val;
                } catch (e) {
                    console.error("Popup Focus Error:", e);
                }
            });
        } else {
            focusControl.classList.add('hidden');
        }
    }

    function closeVideoPopup() {
        const modal = document.getElementById('video-popup-modal');
        const popupImg = document.getElementById('popup-video-feed');
        modal.classList.add('hidden');
        popupImg.src = "";
    }

    // Bind to window for HTML access
    window.closeVideoPopup = closeVideoPopup;

    // Add Click listener to Main Feed
    if (cameraFeed) {
        cameraFeed.parentElement.onclick = () => {
            if (cameraSelect && cameraSelect.value) {
                openVideoPopup();
            }
        };
    }
    if (captureBtn) {
        captureBtn.addEventListener('click', () => {
            const selectedCameraPath = cameraSelect ? cameraSelect.value : null;
            if (!selectedCameraPath) {
                logMessage('Select a camera first', true);
                return;
            }

            // Visual feedback
            const originalText = captureBtn.innerHTML;
            captureBtn.innerHTML = 'Capturing...';
            captureBtn.disabled = true;

            const subfolder = subfolderInput ? subfolderInput.value : 'default';
            const prefix = prefixInput ? prefixInput.value : 'IMG';
            const resolution = resolutionSelect ? resolutionSelect.value : '1280x720';
            const shutterSpeed = shutterSpeedSelect ? shutterSpeedSelect.value : 'Auto';
            const autofocus = autofocusCheckbox ? autofocusCheckbox.checked : false;
            const manual_focus = manualFocusSlider ? parseFloat((manualFocusSlider.value / 100).toFixed(1)) : 0;
            const startTime = Date.now();

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
                    const endTime = Date.now();
                    console.log(`Capture API took ${endTime - startTime}ms`);

                    if (data.status === 'success') {
                        logMessage(`[WebUI] Saved: ${data.filename}`);
                        if (!knownFiles.has(data.filename)) {
                            knownFiles.add(data.filename);
                            addToGallery(data.filename);
                        }
                    } else {
                        logMessage(`Error: ${data.detail}`, true);
                    }
                })
                .catch(error => {
                    console.error('Capture Error:', error);
                    logMessage(`Capture failed: ${error.message || error}`, true);
                })
                .finally(() => {
                    captureBtn.innerHTML = originalText;
                    captureBtn.disabled = false;
                });
        });
    }

    // Ensure preview status is hidden when image loads
    if (cameraFeed) {
        cameraFeed.onload = () => {
            const previewStatus = document.getElementById('preview-status');
            if (previewStatus) {
                previewStatus.style.display = 'none';
            }
        };
    }

    // --- Delete Logic ---
    if (deleteSelectedBtn) {
        deleteSelectedBtn.addEventListener('click', async () => {
            if (selectedFiles.size === 0) return;

            if (!confirm(`Delete ${selectedFiles.size} images?`)) return;

            const filesToDelete = Array.from(selectedFiles);
            deleteSelectedBtn.disabled = true;
            deleteSelectedBtn.textContent = "Deleting...";

            try {
                const response = await fetch('/api/delete_images', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ filenames: filesToDelete })
                });
                const data = await response.json();

                if (data.status === 'success' || data.status === 'partial_success') {
                    // Remove from UI
                    filesToDelete.forEach(filename => {
                        // Find element
                        const el = document.querySelector(`div[data-filename="${filename}"]`);
                        if (el) el.remove();
                        selectedFiles.delete(filename);
                        knownFiles.delete(filename);
                    });

                    logMessage(`Deleted ${data.deleted_count} images.`);
                    updateDeleteButton();
                    deleteSelectedBtn.innerHTML = `<svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>Delete (<span id="selected-count">0</span>)`;

                    if (galleryContainer.children.length === 0 || (galleryContainer.children.length === 1 && galleryContainer.children[0].id === 'gallery-placeholder')) {
                        if (galleryPlaceholder) galleryPlaceholder.style.display = 'block';
                        // Hide Select All if empty
                        selectAllBtn.classList.add('hidden');
                    }

                    // Reload gallery to fill gaps if we want to maintain 20 items
                    loadGallery();

                } else {
                    console.error(`Delete failed: ${JSON.stringify(data.errors)}`);
                }
            } catch (err) {
                console.error("Delete error:", err);
            } finally {
                deleteSelectedBtn.disabled = false;
                // Reset button text if we still have items selected (which shouldn't happen if successful, but loop safety)
                if (selectedFiles.size > 0) {
                    deleteSelectedBtn.innerHTML = `<svg class="w-3 h-3 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>Delete (<span id="selected-count">${selectedFiles.size}</span>)`;
                }
            }
        });
    }


    // --- File Explorer Logic ---
    const changeDirBtn = document.getElementById('change-dir-btn');
    const explorerModal = document.getElementById('file-explorer-modal');
    const closeExplorerBtn = document.getElementById('close-explorer-btn');
    const cancelExplorerBtn = document.getElementById('cancel-explorer-btn');
    const selectFolderBtn = document.getElementById('select-folder-btn');
    const newFolderBtn = document.getElementById('new-folder-btn');
    const explorerList = document.getElementById('explorer-list');
    const explorerBreadcrumbs = document.getElementById('explorer-breadcrumbs');
    const currentSavePathDisplay = document.getElementById('current-save-path');

    let currentBrowsePath = "";

    function openFileExplorer() {
        explorerModal.classList.remove('hidden');
        loadDirectory("");
    }

    function closeFileExplorer() {
        explorerModal.classList.add('hidden');
    }

    async function loadDirectory(path) {
        currentBrowsePath = path;
        explorerBreadcrumbs.textContent = path ? `/${path}` : '/';
        explorerList.innerHTML = '<div class="text-center text-gray-500 py-4">Loading...</div>';

        try {
            const response = await fetch(`/api/list_directories?path=${encodeURIComponent(path)}`);
            if (!response.ok) throw new Error('Failed to load directories');
            const directories = await response.json();
            renderDirectoryList(directories);
        } catch (error) {
            console.error(error);
            explorerList.innerHTML = '<div class="text-center text-red-500 py-4">Error loading directories</div>';
        }
    }

    function renderDirectoryList(directories) {
        explorerList.innerHTML = '';

        // "Up" folder if not at root
        if (currentBrowsePath) {
            const parts = currentBrowsePath.split('/').filter(p => p);
            parts.pop();
            const parentPath = parts.join('/');

            const upDiv = document.createElement('div');
            upDiv.className = 'flex items-center p-3 hover:bg-gray-800 rounded-lg cursor-pointer transition';
            upDiv.innerHTML = `
                <svg class="w-6 h-6 text-gray-400 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                <span class="text-gray-300">..</span>
            `;
            upDiv.onclick = () => {
                loadDirectory(parentPath);
            };
            explorerList.appendChild(upDiv);
        }

        if (directories.length === 0) {
            const emptyMsg = document.createElement('div');
            emptyMsg.className = 'text-center text-gray-500 py-4 italic';
            emptyMsg.textContent = 'No subfolders';
            explorerList.appendChild(emptyMsg);
            return;
        }

        directories.forEach(dir => {
            const div = document.createElement('div');
            div.className = 'flex items-center justify-between p-3 hover:bg-gray-800 rounded-lg cursor-pointer transition group';

            // Left side: Icon + Name
            const leftDiv = document.createElement('div');
            leftDiv.className = 'flex items-center';

            const icon = document.createElement('div');
            icon.className = "mr-3 text-yellow-500 pointer-events-none";
            icon.innerHTML = `<svg class="w-6 h-6" fill="currentColor" viewBox="0 0 20 20"><path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z"></path></svg>`;

            const span = document.createElement('span');
            span.className = "text-gray-200 group-hover:text-white pointer-events-none";
            span.textContent = dir;

            leftDiv.appendChild(icon);
            leftDiv.appendChild(span);

            // Right side: Delete Button
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'ml-auto text-gray-500 hover:text-red-500 w-8 h-8 rounded hover:bg-gray-700 transition opacity-0 group-hover:opacity-100 focus:opacity-100 flex items-center justify-center';
            deleteBtn.title = "Delete Folder";
            deleteBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd" />
            </svg>`;

            deleteBtn.onclick = async (e) => {
                e.stopPropagation();
                e.preventDefault();

                const fullPath = currentBrowsePath ? `${currentBrowsePath}/${dir}` : dir;
                if (confirm(`Are you sure you want to delete "${dir}" and all its contents? This cannot be undone.`)) {
                    try {
                        const response = await fetch('/api/delete_directory', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ path: fullPath })
                        });

                        if (!response.ok) {
                            const data = await response.json();
                            throw new Error(data.detail || 'Failed to delete');
                        }

                        // Refresh
                        loadDirectory(currentBrowsePath);
                    } catch (error) {
                        console.error('Delete Error:', error);
                        alert(`Error deleting directory: ${error.message}`);
                    }
                }
            };

            div.appendChild(leftDiv);
            div.appendChild(deleteBtn);

            div.onclick = (e) => {
                e.preventDefault();
                const newPath = currentBrowsePath ? `${currentBrowsePath}/${dir}` : dir;
                loadDirectory(newPath);
            };
            explorerList.appendChild(div);
        });
    }

    async function createNewFolder() {
        const folderName = prompt("Enter new folder name:");
        if (!folderName) return;

        try {
            const response = await fetch('/api/create_directory', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ parent_path: currentBrowsePath, new_folder_name: folderName })
            });
            const data = await response.json();

            if (response.ok) {
                loadDirectory(currentBrowsePath); // Refresh
            } else {
                alert(`Error: ${data.detail}`);
            }
        } catch (error) {
            console.error(error);
            alert("Failed to create folder");
        }
    }

    if (changeDirBtn) {
        changeDirBtn.addEventListener('click', openFileExplorer);
        closeExplorerBtn.addEventListener('click', closeFileExplorer);
        cancelExplorerBtn.addEventListener('click', closeFileExplorer);

        newFolderBtn.addEventListener('click', createNewFolder);

        selectFolderBtn.addEventListener('click', () => {
            const selectedPath = currentBrowsePath || "default";
            if (subfolderInput) subfolderInput.value = selectedPath;
            if (currentSavePathDisplay) currentSavePathDisplay.textContent = `/${selectedPath}`;
            closeFileExplorer();
        });
    }

    // --- WebSocket for Real-time Updates ---
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        const ws = new WebSocket(wsUrl);
        const wsDot = document.getElementById('ws-status-dot');

        ws.onopen = () => {
            console.log("WebSocket connected");
            if (wsDot) {
                wsDot.classList.remove('disconnected');
                wsDot.classList.add('connected');
            }
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === 'new_file') {
                const source = data.source || "WS";
                if (source !== 'WebUI') {
                    logMessage(`[${source}] Saved: ${data.filename}`);
                }
                if (!knownFiles.has(data.filename)) {
                    knownFiles.add(data.filename);
                    addToGallery(data.filename);
                }
            } else if (data.type === 'mqtt_log') {
                const logBox = document.getElementById('mqtt-log-box');
                if (logBox) {
                    // Clear "Waiting..." placeholder if present
                    if (logBox.firstElementChild && logBox.firstElementChild.textContent.includes("Waiting for events")) {
                        logBox.innerHTML = '';
                    }

                    const div = document.createElement('div');
                    const now = new Date().toLocaleTimeString();
                    div.className = "mb-1 border-b border-gray-800 pb-1 break-words";
                    div.innerHTML = `<span class="text-gray-500 font-mono text-xs">[${now}]</span> <span class="text-blue-200">${data.message}</span>`;
                    logBox.appendChild(div);
                    logBox.scrollTop = logBox.scrollHeight;
                }
            }
        };

        ws.onclose = () => {
            console.log("WebSocket disconnected, retrying in 2s...");
            if (wsDot) {
                wsDot.classList.remove('connected');
                wsDot.classList.add('disconnected');
            }
            setTimeout(connectWebSocket, 2000);
        };

        ws.onerror = (err) => {
            console.error("WebSocket error:", err);
            ws.close();
        };
    }

    // --- Initial Load ---
    loadCameras();
    loadGallery();
    connectWebSocket();

    // Fallback polling (less frequent now)
    setInterval(loadGallery, 5000);


    // MQTT Status Polling
    function updateMqttStatus() {
        const mqttDot = document.getElementById('mqtt-status-dot');
        if (!mqttDot) return;

        fetch('/api/mqtt_status')
            .then(response => response.json())
            .then(data => {
                // console.log("MQTT Status Poll:", data); 
                if (data.connected) {
                    mqttDot.classList.remove('disconnected', 'bg-red-500');
                    mqttDot.classList.add('connected', 'bg-green-500');
                    mqttDot.title = "Connected";
                } else {
                    mqttDot.classList.remove('connected', 'bg-green-500');
                    mqttDot.classList.add('disconnected', 'bg-red-500');
                    mqttDot.title = "Disconnected";
                }
            })
            .catch(err => {
                console.error("Error fetching MQTT status:", err);
                mqttDot.classList.remove('connected', 'bg-green-500');
                mqttDot.classList.add('disconnected', 'bg-red-500');
            });
    }

    function loadMqttConfig() {
        fetch('/api/mqtt_config')
            .then(r => r.json())
            .then(config => {
                const brokerInput = document.getElementById('mqtt-broker');
                if (!brokerInput) return;

                brokerInput.value = config.broker || '';
                document.getElementById('mqtt-port').value = config.port || 1883;
                document.getElementById('mqtt-topic').value = config.topic || 'capture/trigger';
                document.getElementById('mqtt-username').value = config.username || '';
                document.getElementById('mqtt-password').value = config.password || '';
            })
            .catch(e => console.error("Failed to load MQTT config:", e));
    }

    const mqttForm = document.getElementById('mqtt-form');
    if (mqttForm) {
        const testBtn = document.getElementById('test-mqtt-btn');
        const testDot = document.getElementById('mqtt-test-dot');

        if (testBtn) {
            testBtn.addEventListener('click', () => {
                testBtn.disabled = true;
                testBtn.textContent = "Testing...";
                if (testDot) {
                    testDot.className = "w-3 h-3 rounded-full bg-yellow-500 animate-pulse transition-colors duration-300";
                    testDot.title = "Testing...";
                }

                fetch('/api/mqtt/test')
                    .then(r => r.json())
                    .then(data => {
                        if (data.status === 'connected') {
                            if (testDot) {
                                testDot.className = "w-3 h-3 rounded-full bg-green-500 transition-colors duration-300";
                                testDot.title = "Connected: " + data.detail;
                            }
                            logMessage("[WebUI] MQTT Test: Connected");
                        } else {
                            if (testDot) {
                                testDot.className = "w-3 h-3 rounded-full bg-red-500 transition-colors duration-300";
                                testDot.title = "Disconnected: " + data.detail;
                            }
                            logMessage("[WebUI] MQTT Test: Failed - " + data.detail, true);
                        }
                    })
                    .catch(e => {
                        console.error("MQTT Test Error:", e);
                        if (testDot) {
                            testDot.className = "w-3 h-3 rounded-full bg-red-500 transition-colors duration-300";
                            testDot.title = "Error: " + e.message;
                        }
                        logMessage("[WebUI] MQTT Test Error", true);
                    })
                    .finally(() => {
                        testBtn.disabled = false;
                        testBtn.textContent = "Test Connection";
                    });
            });
        }

        mqttForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const btn = document.getElementById('save-mqtt-btn');
            const originalText = btn.textContent;
            btn.disabled = true;
            btn.textContent = "Saving...";

            const payload = {
                broker: document.getElementById('mqtt-broker').value,
                port: parseInt(document.getElementById('mqtt-port').value),
                topic: document.getElementById('mqtt-topic').value,
                username: document.getElementById('mqtt-username').value,
                password: document.getElementById('mqtt-password').value
            };

            fetch('/api/mqtt_config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            })
                .then(r => r.json())
                .then(data => {
                    if (data.status === 'success') {
                        // Visual feedback
                        btn.textContent = "Saved!";
                        btn.classList.add('bg-green-600', 'border-green-600');
                        setTimeout(() => {
                            btn.textContent = originalText;
                            btn.classList.remove('bg-green-600', 'border-green-600');
                            btn.disabled = false;
                        }, 2000);
                        logMessage("[WebUI] MQTT Config Saved. Service restarting...");
                    } else {
                        alert("Error saving MQTT config");
                        btn.disabled = false;
                        btn.textContent = originalText;
                    }
                })
                .catch(e => {
                    console.error(e);
                    alert("Failed to save config");
                    btn.disabled = false;
                    btn.textContent = originalText;
                });
        });
    }

    updateMqttStatus(); // Initial check
    loadMqttConfig(); // Load settings
    setInterval(updateMqttStatus, 5000); // Poll every 5 seconds
    setInterval(updateMqttStatus, 5000); // Poll every 5 seconds
    loadCameras(); // Ensure this is called successfully
});