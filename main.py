"""
main.py - Telautograph XY plotter controller.

Started automatically on boot by systemd (see xy_plotter.service / README).

1. startup()   - runs ONCE at power-on to set up the plotter.
2. main_loop() - runs forever: waits for a text command over serial or WiFi,
                 turns the text into an SVG (Text_to_svg.py), plots it
                 (Plotter.py), then goes back to waiting.

Sending commands:
  WiFi:   connect to TCP port NETWORK_PORT on the Pi and send one line of text
          (one message per connection), e.g. from another computer:
              echo "HELLO WORLD" | nc <pi-address> 5000
  Serial: send one line of text (ending with a newline) to COMMAND_SERIAL_PORT.

  Use "\\n" (backslash n) inside a message for a line break.
  Replies sent back to the sender: "QUEUED" when received, "PLOTTING" when
  the drawing starts, then "DONE" or "ERROR: ...".
"""

import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time

from Text_to_svg import text_to_svg

# ---------------- USER-CONFIGURABLE CONSTANTS ----------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

SETTINGS_FILE = os.path.join(SCRIPT_DIR, "settings.json")

# Serial command input. This must NOT be the Arduino DAC port used by
# Plotter.py (SERIAL_PORT = '/dev/ttyACM1'). '/dev/serial0' is the Pi's
# GPIO UART (pins 8/10); use e.g. '/dev/ttyUSB0' for a USB-serial adapter.
ENABLE_SERIAL_COMMANDS = True
COMMAND_SERIAL_PORT = "/dev/serial0"
COMMAND_BAUD_RATE = 115200

# WiFi / network command input (plain TCP, one line of text per command)
ENABLE_NETWORK_COMMANDS = True
NETWORK_HOST = "0.0.0.0"          # listen on all interfaces
NETWORK_PORT = 5000

# Text -> SVG settings (same values as the Text_to_svg.py example)
SVG_OUTPUT_FILE = os.path.join(SCRIPT_DIR, "output.svg")
SVG_WIDTH = 500
SVG_HEIGHT = 200
CHAR_WIDTH = 10
LINE_HEIGHT = 15
TEXT_SCALE = 5

MAX_TEXT_LENGTH = 200             # ignore commands longer than this

# Plotter.py is run as a separate process for each job. Its per-frame output
# goes to this file (overwritten each job) instead of the system log.
PLOTTER_SCRIPT = os.path.join(SCRIPT_DIR, "Plotter.py")
PLOTTER_LOG_FILE = os.path.join(SCRIPT_DIR, "plotter_last_run.log")


# ---------------- Settings ----------------
data = {}
try:
    with open(SETTINGS_FILE, 'r') as file:
        data = json.load(file)
        print(data)
except FileNotFoundError:
    print(f"Error: The file '{SETTINGS_FILE}' was not found.")
except json.JSONDecodeError:
    print("Error: Failed to decode JSON from the file.")


LimitA = 0
LimitPaperAdvance = 0


def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ---------------- Hardware functions (to be filled in) ----------------
def alarm():
    pass

def backlight(status):
    pass

def paperFeed():
    pass

def paperTakeUp():
    if data.get("PaperTakeUpMode") == False:
        print("FALSE!!!")
    # pass

def inkPump():
    pass


# ---------------- Command sources ----------------
# Every command source puts (text, reply_function) on this queue. The main
# loop takes them off one at a time, so only one drawing runs at once.
command_queue = queue.Queue()


def submit(text, reply):
    """Queue a command from any source (rejects it right away if too long)."""
    if len(text) > MAX_TEXT_LENGTH:
        log(f"Command too long ({len(text)} characters), ignored.")
        reply(f"ERROR: text longer than {MAX_TEXT_LENGTH} characters")
        return
    command_queue.put((text, reply))
    reply("QUEUED")


def serial_listener():
    """Read lines of text from COMMAND_SERIAL_PORT. Reconnects if unplugged."""
    import serial
    last_error = None
    while True:
        try:
            with serial.Serial(COMMAND_SERIAL_PORT, COMMAND_BAUD_RATE, timeout=1) as port:
                log(f"Listening for serial commands on {COMMAND_SERIAL_PORT}")
                last_error = None
                buffer = b""
                while True:
                    buffer += port.read(port.in_waiting or 1)
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        text = line.decode("utf-8", errors="replace").strip()
                        if text:
                            def reply(msg, port=port):
                                try:
                                    port.write((msg + "\n").encode("utf-8"))
                                except Exception:
                                    pass
                            submit(text, reply)
        except Exception as e:
            if str(e) != last_error:          # don't repeat the same error every 10 s
                log(f"Serial command port error ({COMMAND_SERIAL_PORT}): {e}. Retrying every 10 s.")
                last_error = str(e)
            time.sleep(10)


def handle_network_client(conn, addr):
    """One command per connection: read one line of text, keep the connection
    open until that drawing is finished (sending the replies), then close.
    Works with  echo "TEXT" | nc <pi-address> 5000"""
    log(f"Network client connected: {addr[0]}")
    finished = threading.Event()
    with conn:
        def reply(msg):
            try:
                conn.sendall((msg + "\n").encode("utf-8"))
            except Exception:
                pass
            if msg == "DONE" or msg.startswith("ERROR"):
                finished.set()
        try:
            conn.settimeout(30)              # give up on clients that never send a line
            buffer = b""
            while b"\n" not in buffer and len(buffer) < 4096:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                buffer += chunk
            text = buffer.split(b"\n", 1)[0].decode("utf-8", errors="replace").strip()
            if text:
                submit(text, reply)
                finished.wait()              # stay connected until the drawing is done
        except Exception as e:
            log(f"Network client error ({addr[0]}): {e}")
    log(f"Network client disconnected: {addr[0]}")


def network_listener():
    """Accept TCP connections on NETWORK_PORT (WiFi / Ethernet)."""
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((NETWORK_HOST, NETWORK_PORT))
                server.listen()
                log(f"Listening for network commands on port {NETWORK_PORT}")
                while True:
                    conn, addr = server.accept()
                    threading.Thread(target=handle_network_client, args=(conn, addr), daemon=True).start()
        except Exception as e:
            log(f"Network listener error: {e}. Retrying in 10 s.")
            time.sleep(10)


# ---------------- Plotting ----------------
def plot_text(text):
    """Turn text into an SVG and draw it. Returns None on success, or an error message."""
    text = text.replace("\\n", "\n")    # allow "\n" in commands for line breaks

    try:
        text_to_svg(text, SVG_OUTPUT_FILE, width=SVG_WIDTH, height=SVG_HEIGHT,
                    char_width=CHAR_WIDTH, line_height=LINE_HEIGHT, scale=TEXT_SCALE)
    except Exception as e:
        return f"Text_to_svg failed: {e}"

    log(f"Plotting... (Plotter.py output in {PLOTTER_LOG_FILE})")
    try:
        with open(PLOTTER_LOG_FILE, "w") as plot_log:
            result = subprocess.run(
                [sys.executable, "-u", PLOTTER_SCRIPT, SVG_OUTPUT_FILE, "--exit-when-done"],
                cwd=SCRIPT_DIR, stdin=subprocess.DEVNULL,
                stdout=plot_log, stderr=subprocess.STDOUT)
    except Exception as e:
        return f"Could not start Plotter.py: {e}"
    if result.returncode != 0:
        return f"Plotter.py exited with code {result.returncode} (see {PLOTTER_LOG_FILE})"
    return None


# ---------------- Loop 1: runs once at power-on ----------------
def startup():
    log("Startup: setting up XY plotter")
    # Add plotter setup here, e.g.:
    # backlight(data.get("BackLightMode"))
    # paperTakeUp()
    # inkPump()

    if ENABLE_SERIAL_COMMANDS:
        threading.Thread(target=serial_listener, daemon=True).start()
    if ENABLE_NETWORK_COMMANDS:
        threading.Thread(target=network_listener, daemon=True).start()
    log("Startup complete")


# ---------------- Loop 2: runs forever ----------------
def main_loop():
    while True:
        log("Waiting for command...")
        text, reply = command_queue.get()     # blocks until a command arrives

        log(f"Received command: {text!r}")
        reply("PLOTTING")
        error = plot_text(text)
        if error:
            log(f"ERROR: {error}")
            reply(f"ERROR: {error}")
        else:
            log("Done.")
            reply("DONE")


if __name__ == "__main__":
    startup()
    try:
        main_loop()
    except KeyboardInterrupt:
        log("Stopped (Ctrl+C).")
