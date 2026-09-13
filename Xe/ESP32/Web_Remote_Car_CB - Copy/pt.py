import serial
import serial.tools.list_ports
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import sys
from collections import deque
import re

MAX_POINTS = 300
SERIAL_BAUD = 115200

def find_esp32_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        if 'USB' in port.description or 'CH340' in port.description or 'CP210x' in port.description:
            return port.device
    return None

port = find_esp32_port()
if port is None:
    print("❌ Không tìm thấy cổng ESP32.")
    sys.exit(1)

try:
    ser = serial.Serial(port, SERIAL_BAUD, timeout=1)
    time.sleep(2)
    print(f"✅ Kết nối {port}")
except Exception as e:
    print(f"❌ Lỗi mở cổng: {e}")
    sys.exit(1)

time_data = deque(maxlen=MAX_POINTS)
speed_real = deque(maxlen=MAX_POINTS)
speed_target = deque(maxlen=MAX_POINTS)
speed_original = deque(maxlen=MAX_POINTS)
steer_real = deque(maxlen=MAX_POINTS)
steer_target = deque(maxlen=MAX_POINTS)

start_time = time.time()

def update_plot(frame):
    while ser.in_waiting:
        line = ser.readline().decode('utf-8', errors='ignore').strip()
        if not line.startswith('FB:'):
            continue
        
        # Dùng regex để lấy số thực (kể cả dấu âm)
        s = re.search(r'TocDo=(-?\d+\.?\d*)', line)
        a = re.search(r'GocLai=(-?\d+\.?\d*)', line)
        t = re.search(r'RampTocDo=(-?\d+\.?\d*)', line)
        g = re.search(r'Setpoint=(-?\d+\.?\d*)', line)
        u = re.search(r'SetpointGocLai=(-?\d+\.?\d*)', line)
        
        s_val = float(s.group(1)) if s else 0.0
        a_val = float(a.group(1)) if a else 0.0
        t_val = float(t.group(1)) if t else 0.0
        g_val = float(g.group(1)) if g else 0.0
        u_val = float(u.group(1)) if u else 0.0
        
        now = time.time() - start_time
        time_data.append(now)
        speed_real.append(s_val)
        speed_target.append(t_val)
        speed_original.append(g_val)
        steer_real.append(a_val)
        steer_target.append(u_val)
        print(f"Time={now:.1f}s | TocDo={s_val:.2f} RampTocDo={t_val:.2f} Setpoint={g_val:.2f} GocLai={a_val:.1f} SetpointGocLai={u_val:.1f}")

    if time_data:
        t_arr = list(time_data)
        ax1.clear()
        ax2.clear()
        ax1.plot(t_arr, speed_real, 'b-', label='Real (S)')
        ax1.plot(t_arr, speed_target, 'r--', label='Target (T)')
        ax1.plot(t_arr, speed_original, 'c:', label='Original (G)')
        ax1.set_ylabel('Speed (m/s)')
        ax1.legend()
        ax1.grid(True)
        ax2.plot(t_arr, steer_real, 'g-', label='Real (A)')
        ax2.plot(t_arr, steer_target, 'm--', label='Target (U)')
        ax2.set_ylabel('Steering (deg)')
        ax2.legend()
        ax2.grid(True)

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
ani = animation.FuncAnimation(fig, update_plot, interval=100)
plt.show()