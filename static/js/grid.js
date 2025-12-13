document.addEventListener('DOMContentLoaded', async () => {
    const camerasContainer = document.getElementById('cameras-container');
    const captureAllBtn = document.getElementById('capture-all-btn');
    const prefixInput = document.getElementById('prefix-input');
    const delayTimerCheckbox = document.getElementById('delay-timer-checkbox');
    const delayTimerInput = document.getElementById('delay-timer-input');
    const logArea = document.getElementById('log-area');

    let availableCameras = {};

    // Reset Context to Global (Multi-Camera)
    fetch('/api/set_active_camera', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera_path: null })
    }).catch(e => console.error("Error resetting active context:", e));

    // --- Logging Function ---
    function logMessage(message, isError = false) {
        if (logArea) {
            const p = document.createElement('p');
            const timestamp = new Date().toLocaleTimeString();
            p.textContent = `[${timestamp}] ${message}`;
            p.className = isError ? 'text-red-400' : 'text-gray-300';
            logArea.appendChild(p);
            logArea.scrollTop = logArea.scrollHeight;
        }
        console.log(`[LOG] ${message}`);
    }

    // --- File Explorer Logic ---
    const explorerModal = document.getElementById('file-explorer-modal');
    const closeExplorerBtn = document.getElementById('close-explorer-btn');
    const cancelExplorerBtn = document.getElementById('cancel-explorer-btn');
    const selectFolderBtn = document.getElementById('select-folder-btn');
    const newFolderBtn = document.getElementById('new-folder-btn');
    const explorerList = document.getElementById('explorer-list');
    const explorerBreadcrumbs = document.getElementById('explorer-breadcrumbs');

    let currentBrowsePath = "";
    let targetCameraId = null; // To track which camera requested the change

    function openFileExplorer(safeId) {
        targetCameraId = safeId;
        explorerModal.classList.remove('hidden');
        loadDirectory("");
    }
    window.openFileExplorer = openFileExplorer;

    function closeFileExplorer() {
        explorerModal.classList.add('hidden');
        targetCameraId = null;
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
            // Calculate parent path for display
            const parts = currentBrowsePath.split('/').filter(p => p);
            parts.pop();
            const parentPath = parts.join('/');

            const upDiv = document.createElement('div');
            upDiv.className = 'flex items-center p-3 hover:bg-gray-800 rounded-lg cursor-pointer transition';
            // Add pointer-events-none to children to ensure click hits the div
            upDiv.innerHTML = `
                <svg class="w-6 h-6 text-gray-400 mr-3 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg>
                <span class="text-gray-300 pointer-events-none">.. (Up to /${parentPath})</span>
            `;

            upDiv.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                loadDirectory(parentPath);
            });

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

                        logMessage(`Deleted directory: ${fullPath}`);
                        loadDirectory(currentBrowsePath); // Refresh
                    } catch (error) {
                        console.error('Delete Error:', error);
                        alert(`Error deleting directory: ${error.message}`);
                    }
                }
            };

            div.appendChild(leftDiv);
            div.appendChild(deleteBtn);

            div.onclick = (e) => {
                // Only navigate if the click wasn't on the delete button (handled by stopPropagation, but safe to check)
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

    // Modal Event Listeners
    if (closeExplorerBtn) closeExplorerBtn.onclick = closeFileExplorer;
    if (cancelExplorerBtn) cancelExplorerBtn.onclick = closeFileExplorer;
    if (newFolderBtn) newFolderBtn.onclick = createNewFolder;

    if (selectFolderBtn) {
        selectFolderBtn.onclick = () => {
            if (targetCameraId) {
                const display = document.getElementById(`save-location-display-${targetCameraId}`);
                const input = document.getElementById(`save-location-${targetCameraId}`);

                // Use "default" if root is selected, otherwise the path
                const selectedPath = currentBrowsePath || "default";

                if (display) display.textContent = `/${selectedPath}`;
                if (input) input.value = selectedPath;

                showMessage(targetCameraId, "Save location updated");
            }
            closeFileExplorer();
        };
    }

    // --- Core Logic ---

    async function loadCameras() {
        try {
            const response = await fetch(`/api/cameras?t=${new Date().getTime()}`);
            availableCameras = await response.json();

            if (Object.keys(availableCameras).length === 0) {
                camerasContainer.innerHTML = '<div class="col-span-full text-center py-12"><p class="text-xl text-gray-400">No cameras detected.</p></div>';
                captureAllBtn.disabled = true;
                return;
            }

            renderAllCameras();
            logMessage(`Detected ${Object.keys(availableCameras).length} cameras.`);

        } catch (error) {
            console.error('Error fetching cameras:', error);
            logMessage(`Error loading cameras: ${error.message}`, true);
            camerasContainer.innerHTML = '<div class="col-span-full text-center py-12"><p class="text-xl text-red-400">Error loading cameras.</p></div>';
        }
    }

    function renderAllCameras() {
        camerasContainer.innerHTML = '';

        for (const camPath in availableCameras) {
            const cam = availableCameras[camPath];
            // Use a safe ID for DOM elements
            const safeId = camPath.replace(/[^a-zA-Z0-9]/g, '_');

            // Default values if not present (though they should be from API)
            const resolution = "1280x720"; // Default, will be updated by API call
            const shutterSpeed = "Auto";
            const defaultSavePath = cam.friendly_name.replace(/[^a-zA-Z0-9_.-]/g, '_');

            const card = document.createElement('div');
            card.className = "bg-gray-800 p-6 rounded-xl shadow-2xl flex flex-col gap-4 border border-gray-700";
            card.id = `camera-module-${safeId}`;
            card.dataset.cameraPath = camPath;

            card.innerHTML = `
                <h2 class="text-xl font-bold text-white text-center border-b border-gray-700 pb-3 mb-2">
                    ${cam.friendly_name}
                </h2>

                <!-- Video Preview Box -->
                <div id="preview-box-${safeId}" 
                     class="w-full preview-box rounded-lg relative overflow-hidden bg-black cursor-pointer hover:border-blue-400 hover:shadow-[0_0_25px_rgba(59,130,246,0.6)] transition duration-300"
                     onclick="openVideoPopup('${camPath}', '${safeId}')"
                     title="Click to expand">
                    <img id="feed-${safeId}" src="/video_feed?camera_path=${camPath}" class="w-full h-full object-contain" alt="Live Feed">
                    
                    <div class="absolute top-2 left-2 bg-gray-900/80 px-3 py-1 rounded-lg text-xs font-medium backdrop-blur-sm border border-gray-700 pointer-events-none">
                        Focus: <span id="preview-focus-status-${safeId}" class="text-yellow-400">Loading...</span>
                    </div>
                    
                    <div class="absolute bottom-0 left-0 right-0 bg-gray-900/90 px-3 py-2 text-xs text-gray-300 flex justify-between items-center backdrop-blur-sm border-t border-gray-700 pointer-events-none">
                        <span>Res: <span id="preview-resolution-${safeId}">...</span></span>
                        <span>Shutter: <span id="preview-shutter-${safeId}">...</span></span>
                    </div>
                    
                    <!-- Expand Icon Overlay -->
                    <div class="absolute inset-0 flex items-center justify-center opacity-0 hover:opacity-100 transition duration-300 bg-black/20">
                         <svg class="w-12 h-12 text-white drop-shadow-lg" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4"></path></svg>
                    </div>
                </div>

                <!-- Configuration Form -->
                <div class="space-y-4">

                    <!-- Save Location -->
                    <div>
                        <label class="block text-sm font-medium text-gray-400 mb-1">Save Location</label>
                        <div class="flex items-center gap-2">
                            <div class="flex-grow bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-gray-300 truncate"
                                id="save-location-display-${safeId}">
                                /${defaultSavePath}
                            </div>
                            <button class="bg-gray-700 hover:bg-gray-600 text-white p-2 rounded-lg transition duration-150 w-auto border-none flex-shrink-0"
                                    onclick="openFileExplorer('${safeId}')"
                                    title="Change Save Location">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"></path></svg>
                            </button>
                        </div>
                        <input type="hidden" id="save-location-${safeId}" value="${defaultSavePath}">
                    </div>

                    <!-- Image Prefix -->
                    <div>
                        <label for="prefix-${safeId}" class="block text-sm font-medium text-gray-400 mb-1">Prefix</label>
                        <input type="text" id="prefix-${safeId}" value="IMG" placeholder="IMG"
                               class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 text-white transition duration-150">
                    </div>

                    <!-- Resolution & Shutter Speed -->
                    <div class="grid grid-cols-2 gap-4">
                        
                        <!-- Resolution -->
                        <div>
                            <label for="resolution-${safeId}" class="block text-sm font-medium text-gray-400 mb-1">
                                Resolution
                            </label>
                            <select id="resolution-${safeId}" 
                                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 text-white transition duration-150 appearance-none cursor-pointer">
                                <!-- Populated via JS -->
                            </select>
                        </div>

                        <!-- Shutter Speed -->
                        <div>
                            <label for="shutter-speed-${safeId}" class="block text-sm font-medium text-gray-400 mb-1">
                                Shutter Speed
                            </label>
                            <select id="shutter-speed-${safeId}" 
                                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg focus:ring-blue-500 focus:border-blue-500 text-white transition duration-150 appearance-none cursor-pointer">
                                <!-- Populated via JS -->
                            </select>
                        </div>
                    </div>
                    
                    <!-- Autofocus Switch & Focus Adjustment -->
                    <div class="p-4 bg-gray-700/50 rounded-lg border border-gray-600">
                        <div class="flex items-center justify-between mb-3">
                            <label for="autofocus-${safeId}" class="text-sm font-medium text-gray-400 flex items-center">
                                <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                                  <path d="M10 12a2 2 0 100-4 2 2 0 000 4z" />
                                  <path fill-rule="evenodd" d="M.458 10C1.732 5.943 5.522 3 10 3s8.268 2.943 9.542 7c-1.274 4.057-5.064 7-9.542 7S1.732 14.057.458 10zM14 10a4 4 0 11-8 0 4 4 0 018 0z" clip-rule="evenodd" />
                                </svg>
                                Autofocus (AF)
                            </label>
                            
                            <!-- Toggle Switch -->
                            <label class="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" id="autofocus-${safeId}" class="sr-only peer autofocus-toggle" checked>
                                <div class="w-11 h-6 bg-gray-600 rounded-full peer peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-800 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                            </label>
                        </div>
                        
                        <div id="focus-adjustment-container-${safeId}" class="opacity-50 pointer-events-none transition duration-300">
                            <label for="focus-adjustment-${safeId}" class="block text-sm font-medium text-gray-400 mb-1">
                                Manual Focus Adjustment
                            </label>
                            <input type="range" id="focus-adjustment-${safeId}" min="0" max="1000" value="0" 
                                   class="w-full h-2 bg-gray-600 rounded-lg appearance-none cursor-pointer range-lg transition duration-150" disabled>
                            <div class="flex justify-between text-xs mt-1 text-gray-500">
                                <span>Near (0)</span>
                                <span>Far (1000)</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Message Box -->
                    <div id="message-box-${safeId}" class="hidden bg-green-900/50 border-l-4 border-green-500 text-green-100 p-3 rounded-lg text-sm transition-all duration-300">
                        Configuration Updated!
                    </div>

                </div>
            `;

            camerasContainer.appendChild(card);

            // Initialize Controls
            initializeCameraControls(camPath, safeId);
        }
    }

    async function initializeCameraControls(camPath, safeId) {
        const resolutionSelect = document.getElementById(`resolution-${safeId}`);
        const shutterSelect = document.getElementById(`shutter-speed-${safeId}`);
        const autofocusCheckbox = document.getElementById(`autofocus-${safeId}`);
        const manualFocusSlider = document.getElementById(`focus-adjustment-${safeId}`);
        const feedImg = document.getElementById(`feed-${safeId}`);

        // 1. Populate Resolutions
        try {
            const resResponse = await fetch(`/api/resolutions?camera_path=${camPath}`);
            const resolutions = await resResponse.json();
            resolutions.forEach(res => {
                const opt = document.createElement('option');
                opt.value = res;
                opt.textContent = res;
                resolutionSelect.appendChild(opt);
            });
            // Set default if available
            if (resolutions.includes("1280x720")) resolutionSelect.value = "1280x720";
        } catch (e) { console.error(e); }

        // 2. Populate Shutter Speeds
        try {
            const shutterResponse = await fetch(`/api/shutter_speed_range/${camPath}`);
            const range = await shutterResponse.json();
            const [min, max] = range;

            shutterSelect.innerHTML = '<option value="Auto">Auto</option>';

            if (min === 0 && max === 0) {
                ['1/30s', '1/60s', '1/125s', '1/250s', '1/500s', '1/1000s'].forEach(opt => {
                    const el = document.createElement('option');
                    el.value = opt;
                    el.textContent = opt;
                    shutterSelect.appendChild(el);
                });
            } else {
                [30, 60, 125, 250, 500, 1000, 2000, 4000, 8000].forEach(den => {
                    if (den >= min && den <= max) {
                        const el = document.createElement('option');
                        el.value = `1/${den}s`;
                        el.textContent = `1/${den}s`;
                        shutterSelect.appendChild(el);
                    }
                });
            }
        } catch (e) { console.error(e); }

        // 3. Check Camera Info (Autofocus support)
        try {
            const infoResponse = await fetch(`/api/camera_info/${camPath}`);
            const info = await infoResponse.json();

            if (!info.has_autofocus) {
                autofocusCheckbox.disabled = true;
                autofocusCheckbox.checked = false;
                manualFocusSlider.disabled = true;
                document.getElementById(`preview-focus-status-${safeId}`).textContent = "No AF";
                document.getElementById(`preview-focus-status-${safeId}`).className = "text-gray-500";
            } else {
                // Initial state update
                updateFocusUI(safeId, true);
            }
        } catch (e) { console.error(e); }

        // --- Event Listeners ---

        // Resolution Change
        resolutionSelect.addEventListener('change', () => {
            updatePreview(camPath, safeId);
            showMessage(safeId, "Resolution updated");
        });

        // Shutter Speed Change
        shutterSelect.addEventListener('change', () => {
            updatePreview(camPath, safeId);
            showMessage(safeId, "Shutter speed updated");
        });

        // Autofocus Toggle
        autofocusCheckbox.addEventListener('change', async () => {
            const isAF = autofocusCheckbox.checked;
            updateFocusUI(safeId, isAF);

            try {
                await fetch('/api/autofocus', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ camera_path: camPath, enable: isAF })
                });
                showMessage(safeId, `Autofocus ${isAF ? 'Enabled' : 'Disabled'}`);
            } catch (e) { logMessage(`Error setting AF: ${e.message}`, true); }
        });

        // Manual Focus
        manualFocusSlider.addEventListener('input', () => {
            document.getElementById(`preview-focus-status-${safeId}`).textContent = `MF @ ${(manualFocusSlider.value / 100).toFixed(1)}`;
        });

        manualFocusSlider.addEventListener('change', async () => {
            const val = parseFloat(manualFocusSlider.value);
            try {
                await fetch('/api/manual_focus', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ camera_path: camPath, focus_value: val / 100 })
                });
                showMessage(safeId, "Focus updated");
            } catch (e) { logMessage(`Error setting focus: ${e.message}`, true); }
        });

        // Initial Preview Update
        updatePreview(camPath, safeId);
    }

    function updateFocusUI(safeId, isAF) {
        const container = document.getElementById(`focus-adjustment-container-${safeId}`);
        const slider = document.getElementById(`focus-adjustment-${safeId}`);
        const status = document.getElementById(`preview-focus-status-${safeId}`);

        if (isAF) {
            container.classList.add('opacity-50', 'pointer-events-none');
            slider.disabled = true;
            status.textContent = "AF ACTIVE";
            status.className = "text-green-400";
        } else {
            container.classList.remove('opacity-50', 'pointer-events-none');
            slider.disabled = false;
            status.textContent = `MF @ ${(slider.value / 100).toFixed(1)}`;
            status.className = "text-yellow-400";
        }
    }

    function updatePreview(camPath, safeId) {
        const res = document.getElementById(`resolution-${safeId}`).value;
        const shutter = document.getElementById(`shutter-speed-${safeId}`).value;
        const img = document.getElementById(`feed-${safeId}`);

        img.src = `/video_feed?camera_path=${camPath}&resolution=${res}&shutter_speed=${shutter}&t=${new Date().getTime()}`;

        document.getElementById(`preview-resolution-${safeId}`).textContent = res;
        document.getElementById(`preview-shutter-${safeId}`).textContent = shutter;
    }

    function showMessage(safeId, text) {
        const box = document.getElementById(`message-box-${safeId}`);
        box.textContent = text;
        box.classList.remove('hidden');
        setTimeout(() => box.classList.add('hidden'), 2000);
    }

    // --- Capture Logic ---

    if (delayTimerCheckbox) {
        delayTimerCheckbox.addEventListener('change', () => {
            delayTimerInput.disabled = !delayTimerCheckbox.checked;
        });
    }

    captureAllBtn.addEventListener('click', async () => {
        if (delayTimerCheckbox.checked) {
            let countdown = parseInt(delayTimerInput.value, 10);
            logMessage(`Starting capture in ${countdown} seconds...`);
            const originalText = captureAllBtn.innerHTML;
            captureAllBtn.disabled = true;

            const interval = setInterval(() => {
                countdown--;
                captureAllBtn.textContent = `Starting in ${countdown}...`;
                if (countdown <= 0) {
                    clearInterval(interval);
                    captureAllBtn.innerHTML = originalText;
                    captureAllBtn.disabled = false;
                    performCapture();
                }
            }, 1000);
        } else {
            performCapture();
        }
    });

    async function performCapture() {
        logMessage("[WebUI] Initiating capture sequence...");
        captureAllBtn.disabled = true;
        const originalText = captureAllBtn.innerHTML;
        captureAllBtn.textContent = "Capturing...";

        const captures = [];

        // Gather settings from each card
        document.querySelectorAll('[id^="camera-module-"]').forEach(card => {
            const camPath = card.dataset.cameraPath;
            const safeId = card.id.replace('camera-module-', '');

            captures.push({
                camera_path: camPath,
                resolution: document.getElementById(`resolution-${safeId}`).value,
                shutter_speed: document.getElementById(`shutter-speed-${safeId}`).value,
                autofocus: document.getElementById(`autofocus-${safeId}`).checked,
                manual_focus: parseFloat(document.getElementById(`focus-adjustment-${safeId}`).value) / 100,
                subfolder: document.getElementById(`save-location-${safeId}`).value,
                prefix: document.getElementById(`prefix-${safeId}`).value
            });
        });

        try {
            const response = await fetch('/api/capture_all', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    prefix: prefixInput.value,
                    captures: captures
                })
            });
            const data = await response.json();

            if (data.status === 'success') {
                // Detailed logs come from WS, just show summary here
                logMessage(`[WebUI] ${data.message}`);
            } else {
                logMessage(`[WebUI] Capture failed: ${data.detail}`, true);
            }
        } catch (e) {
            logMessage(`[WebUI] Network error during capture: ${e.message}`, true);
        } finally {
            captureAllBtn.innerHTML = originalText;
            captureAllBtn.disabled = false;
        }
    }

    // --- MQTT & WebSocket Logic ---

    function updateMqttStatus() {
        const mqttDot = document.getElementById('mqtt-status-dot');
        if (!mqttDot) return;

        fetch('/api/mqtt_status')
            .then(response => response.json())
            .then(data => {
                if (data.connected) {
                    mqttDot.classList.remove('disconnected');
                    mqttDot.classList.add('connected');
                } else {
                    mqttDot.classList.remove('connected');
                    mqttDot.classList.add('disconnected');
                }
            })
            .catch(err => {
                console.error("Error fetching MQTT status:", err);
                mqttDot.classList.remove('connected');
                mqttDot.classList.add('disconnected');
            });
    }

    let ws = null;
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        ws = new WebSocket(wsUrl);
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
                // Log all new files, including WebUI, to show individual file progress
                logMessage(`[${source}] Saved: ${data.filename}`);
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


    // --- Video Popup Logic ---
    function openVideoPopup(camPath, safeId) {
        const modal = document.getElementById('video-popup-modal');
        const popupImg = document.getElementById('popup-video-feed');
        const popupName = document.getElementById('popup-camera-name');
        const popupDetails = document.getElementById('popup-camera-details');

        // Get current settings from the card
        const resolution = document.getElementById(`resolution-${safeId}`).value;
        const shutter = document.getElementById(`shutter-speed-${safeId}`).value;
        const camName = document.querySelector(`#camera-module-${safeId} h2`).textContent.trim();

        // Update Popup Content
        popupName.textContent = camName;
        popupDetails.textContent = `Resolution: ${resolution} | Shutter: ${shutter}`;

        // Set Source (Force reload with timestamp)
        popupImg.src = `/video_feed?camera_path=${camPath}&resolution=${resolution}&shutter_speed=${shutter}&t=${new Date().getTime()}`;

        // Show Modal
        modal.classList.remove('hidden');

        // --- Focus Slider Logic ---
        const focusControl = document.getElementById('popup-focus-control');
        const focusSlider = document.getElementById('popup-focus-slider');
        const focusValueDisplay = document.getElementById('popup-focus-value');

        // Find corresponding controls in main card
        const mainCardSlider = document.getElementById(`focus-adjustment-${safeId}`);
        const mainCardAFCheckbox = document.getElementById(`autofocus-${safeId}`);

        // Determine visibility and state
        if (mainCardSlider && !mainCardSlider.disabled && mainCardAFCheckbox && !mainCardAFCheckbox.checked) {
            focusControl.classList.remove('hidden');
            focusSlider.value = mainCardSlider.value;
            focusValueDisplay.textContent = (focusSlider.value / 100).toFixed(1);

            // Remove old listeners to avoid duplicates (naive approach)
            const newSlider = focusSlider.cloneNode(true);
            focusSlider.parentNode.replaceChild(newSlider, focusSlider);

            // Add new listeners
            newSlider.addEventListener('input', () => {
                focusValueDisplay.textContent = (newSlider.value / 100).toFixed(1);
                // Sync back to main card UI instantly for feedback
                if (mainCardSlider) mainCardSlider.value = newSlider.value;
                // Update Preview Text status
                const status = document.getElementById(`preview-focus-status-${safeId}`);
                if (status) status.textContent = `MF @ ${(newSlider.value / 100).toFixed(1)}`;
            });

            newSlider.addEventListener('change', async () => {
                const val = parseFloat(newSlider.value);
                try {
                    await fetch('/api/manual_focus', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ camera_path: camPath, focus_value: val / 100 })
                    });
                    // Trigger change on main card logic to ensure consistency if needed? 
                    // No, simpler to just start the request here.
                    // But we should visually sync fully.
                    if (mainCardSlider) {
                        mainCardSlider.value = val;
                        // If main card has change listener, might want to trigger it? No, avoid double request.
                    }
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
        popupImg.src = ""; // Stop stream
    }

    // Export to window for inline onclick
    window.openVideoPopup = openVideoPopup;
    window.closeVideoPopup = closeVideoPopup;

    // Start
    loadCameras();
    updateMqttStatus();
    setInterval(updateMqttStatus, 5000);
    connectWebSocket();
});