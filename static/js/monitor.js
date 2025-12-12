document.addEventListener('DOMContentLoaded', () => {
    const cpuStat = document.getElementById('cpu-stat');
    const ramStat = document.getElementById('ram-stat');
    const tempStat = document.getElementById('temp-stat');

    async function updateStats() {
        try {
            const response = await fetch('/api/system_stats');
            if (!response.ok) return;
            const data = await response.json();

            // CPU
            cpuStat.textContent = data.cpu.toFixed(1);
            if (data.cpu > 80) cpuStat.className = 'text-red-500 font-bold';
            else if (data.cpu > 50) cpuStat.className = 'text-yellow-400';
            else cpuStat.className = 'text-blue-400';

            // RAM
            ramStat.textContent = data.ram.percent.toFixed(1);
            if (data.ram.percent > 90) ramStat.className = 'text-red-500 font-bold';
            else ramStat.className = 'text-purple-400';

            // Temp
            if (data.temp !== null) {
                tempStat.textContent = data.temp.toFixed(1);
                if (data.temp > 80) tempStat.className = 'text-red-500 font-bold blink';
                else if (data.temp > 65) tempStat.className = 'text-yellow-400';
                else tempStat.className = 'text-green-400';
            } else {
                tempStat.textContent = "N/A";
            }

        } catch (error) {
            console.warn("Failed to fetch system stats:", error);
        }
    }

    // Update every 2 seconds
    setInterval(updateStats, 2000);
    updateStats(); // Initial call
});
