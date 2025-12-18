document.addEventListener('DOMContentLoaded', () => {
    // --- Hardware Stats ---
    const cpuStat = document.getElementById('cpu-stat');
    const ramStat = document.getElementById('ram-stat');
    const tempStat = document.getElementById('temp-stat');

    async function updateStats() {
        try {
            const response = await fetch('/api/system_stats');
            if (!response.ok) return;
            const data = await response.json();

            // Smart Sidebar: Hide Grid View if only 1 camera
            const gridNavItem = document.getElementById('nav-grid-item');
            if (gridNavItem) {
                if (data.camera_count !== undefined && data.camera_count <= 1) {
                    gridNavItem.style.display = 'none';
                } else {
                    gridNavItem.style.display = 'block';
                }
            }

            // CPU
            if (cpuStat) {
                cpuStat.textContent = data.cpu.toFixed(1);
                if (data.cpu > 80) cpuStat.className = 'text-red-500 font-bold';
                else if (data.cpu > 50) cpuStat.className = 'text-yellow-400';
                else cpuStat.className = 'text-blue-400';
            }

            // RAM
            if (ramStat) {
                ramStat.textContent = data.ram.percent.toFixed(1);
                if (data.ram.percent > 90) ramStat.className = 'text-red-500 font-bold';
                else ramStat.className = 'text-purple-400';
            }

            // Temp
            if (tempStat) {
                if (data.temp !== null) {
                    tempStat.textContent = data.temp.toFixed(1);
                    if (data.temp > 80) tempStat.className = 'text-red-500 font-bold blink';
                    else if (data.temp > 65) tempStat.className = 'text-yellow-400';
                    else tempStat.className = 'text-green-400';
                } else {
                    tempStat.textContent = "N/A";
                }
            }

        } catch (error) {
            console.warn("Failed to fetch system stats:", error);
        }
    }

    // Adjust polling based on performance mode
    const isLowPerf = document.body.classList.contains('perf-low');
    const intervalTime = isLowPerf ? 5000 : 2000;

    // Update every X seconds
    setInterval(updateStats, intervalTime);
    updateStats(); // Initial call


    // --- MQTT Status Polling ---
    function updateMqttStatus() {
        const mqttDot = document.getElementById('mqtt-status-dot');
        if (!mqttDot) return;

        fetch('/api/mqtt_status')
            .then(response => response.json())
            .then(data => {
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
                // console.error("Error fetching MQTT status:", err); 
                // Don't spam console
                mqttDot.classList.remove('connected', 'bg-green-500');
                mqttDot.classList.add('disconnected', 'bg-red-500');
            });
    }

    setInterval(updateMqttStatus, 5000);
    updateMqttStatus();

    // --- WebSocket Status Logic (Global) ---
    // This maintains a WS connection specifically for the status dot.
    // Pages like index.html/grid.html might open their own connection for data.
    // This ensures status dot works on "static" pages like SFTP or Config Editor.

    // Check if another script has already claimed WS handling (optional optimization)
    // For now, allow parallel connection to ensure reliability independently.

    function connectGlobalWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        // Use a distinct variable to avoid conflict if other scripts use window.ws
        const monitorWs = new WebSocket(wsUrl);
        const wsDot = document.getElementById('ws-status-dot');

        monitorWs.onopen = () => {
            if (wsDot) {
                wsDot.classList.remove('disconnected');
                wsDot.classList.add('connected');
            }
        };

        monitorWs.onclose = () => {
            if (wsDot) {
                wsDot.classList.remove('connected');
                wsDot.classList.add('disconnected');
            }
            setTimeout(connectGlobalWebSocket, 5000); // Retry slower
        };

        monitorWs.onerror = (err) => {
            monitorWs.close();
        };

        // We don't need onmessage for status, unless we want to catch 'pong'
    }

    connectGlobalWebSocket();
});
