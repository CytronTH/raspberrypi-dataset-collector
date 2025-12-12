import psutil
import shutil
import subprocess

def get_cpu_usage():
    """Returns CPU usage percentage."""
    return psutil.cpu_percent(interval=None)

def get_ram_usage():
    """Returns RAM usage (Used MB, Total MB, Percent)."""
    mem = psutil.virtual_memory()
    return {
        "used": mem.used // (1024 * 1024),
        "total": mem.total // (1024 * 1024),
        "percent": mem.percent
    }

def get_disk_usage(path="/"):
    """Returns Disk usage for the given path (Used GB, Total GB, Percent)."""
    usage = shutil.disk_usage(path)
    return {
        "used": usage.used // (1024 * 1024 * 1024),
        "total": usage.total // (1024 * 1024 * 1024),
        "percent": round((usage.used / usage.total) * 100, 1)
    }

def get_cpu_temp():
    """Returns CPU temperature in Celsius."""
    try:
        # Try retrieving standard thermal zone temp
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            temp = int(f.read()) / 1000.0
        return round(temp, 1)
    except FileNotFoundError:
        # Fallback to vcgencmd (Raspberry Pi specific)
        try:
            output = subprocess.check_output(["vcgencmd", "measure_temp"]).decode()
            return float(output.replace("temp=", "").replace("'C\n", ""))
        except Exception:
            return None

def get_system_stats():
    """Aggregates all system stats."""
    return {
        "cpu": get_cpu_usage(),
        "ram": get_ram_usage(),
        "disk": get_disk_usage("/home/pi"),
        "temp": get_cpu_temp()
    }
