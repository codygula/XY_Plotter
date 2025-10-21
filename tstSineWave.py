import serial
import math
import time
import sys

# ========= CONFIGURATION =========
PORT = "/dev/ttyACM0"   # Change to your Arduino port (e.g., 'COM3' on Windows)
BAUDRATE = 115200
FREQ_HZ = 0.5           # Frequency of sine wave (Hz)
AMPLITUDE = 127.5       # 127.5 gives full swing between 0–255
OFFSET = 127.5
UPDATE_RATE = 100       # samples per second (sine wave resolution)
PEN_TOGGLE_INTERVAL = 5 # seconds between pen_up/pen_down toggles
# =================================

def send_to_arduino(baseA_val, baseB_val, pen_down, ser):
    """
    Send 3 bytes to Arduino Due:
      [BaseA, BaseB, pen_down]
    Values should be in 0–255 range.
    """
    baseA_val = int(max(0, min(255, baseA_val)))
    baseB_val = int(max(0, min(255, baseB_val)))
    pen_down = 1 if pen_down else 0
    try:
        ser.write(bytes([baseA_val, baseB_val, pen_down]))
    except serial.SerialException as e:
        print(f"Serial write error: {e}")

def main():
    try:
        ser = serial.Serial(PORT, BAUDRATE, timeout=1)
        time.sleep(2)  # Give Arduino time to reset
        print("Connected to Arduino on", PORT)
    except serial.SerialException:
        print(f"Could not open serial port {PORT}")
        sys.exit(1)

    start_time = time.time()
    last_pen_toggle = start_time
    pen_down = False

    print("Generating 1 Hz sine waves on DAC1 & DAC2... Press Ctrl+C to stop.")

    try:
        while True:
            t = time.time() - start_time

            # Generate two 1 Hz sine waves 180° out of phase
            baseA_val = OFFSET + AMPLITUDE * math.sin(2 * math.pi * FREQ_HZ * t)
            baseB_val = OFFSET + AMPLITUDE * math.sin(2 * math.pi * FREQ_HZ * t + math.pi)

            # Toggle pen_down every few seconds
            if t - last_pen_toggle > PEN_TOGGLE_INTERVAL:
                pen_down = not pen_down
                last_pen_toggle = t
                print(f"Pen {'DOWN' if pen_down else 'UP'}")

            # Send values
            send_to_arduino(baseA_val, baseB_val, pen_down, ser)

            time.sleep(1 / UPDATE_RATE)

    except KeyboardInterrupt:
        print("\nStopping waveform output.")
    finally:
        send_to_arduino(0, 0, 0, ser)
        ser.close()

if __name__ == "__main__":
    main()
