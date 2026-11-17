"""
Plotter.py  (headless 5-bar plotter driver - no pygame, no GUI)

5-bar linkage driver with:
 - adaptive sampling of SVG curves (fidelity scaling)
 - automatic SVG normalization (scale & center to drawing area)
 - pen-up between SVG subpaths, persistent trace, replay & clear
 - 12-bit DAC output over serial, debug log, configurable constants

The calibration constants (minA/maxA/minB/maxB, Force multipliers) are fixed
below. To re-tune them interactively, use the pygame GUI version in
debugScripts/Simulation.py and copy the values back here.

A few optional commands can be typed into the terminal while it runs
(type "help" for the list).

Usage:
    python3 Plotter.py                 # uses SVG_FILE below
    python3 Plotter.py path/to/file.svg
    python3 Plotter.py path/to/file.svg --exit-when-done   # used by main.py

Mostly made by ChatGPT
"""

import math, time, sys, threading, queue
from svgpathtools import svg2paths
from collections import deque
import numpy as np
import struct

# SERIAL CODE
# SERIAL CODE
# SERIAL CODE
# For controlling Arduino Due 12 bit DACs.
import serial

# SERIAL_PORT = 'Linux/thing/here'
# SERIAL_PORT = '/dev/ttyACM1'
SERIAL_PORT = '/dev/ttyACM1'
BAUD_RATE = 115200
ENABLE_SERIAL = True

# SERIAL SETUP
ser = None
if ENABLE_SERIAL:
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0)
        time.sleep(2)  # Give the Arduino time to reset
        print(f"Connected to {SERIAL_PORT}")
    except Exception as e:
        print(f"Serial error: {e}")
        ser = None

# END SERIAL CODE
# END SERIAL CODE
# END SERIAL CODE


# SVG_FILE = "/home/gula/Telautograph/XY_Plotter/rectangle.svg"    # file to load (if missing, fallback shape used)

SVG_FILE = "/home/gula/Telautograph/XY_Plotter/svgExamples/rectangle.svg"

# Optional: pass an SVG path on the command line to override SVG_FILE
_args = [a for a in sys.argv[1:] if not a.startswith("--")]
if _args:
    SVG_FILE = _args[0]

# When True, exit once the drawing is finished and the pen is back home,
# instead of waiting for more commands. Also turned on by --exit-when-done.
# In this mode a missing/unreadable SVG is an error (no fallback shape).
EXIT_WHEN_DONE = "--exit-when-done" in sys.argv


# runs in continuous loop when set to 1. For now, it only turns on one line of code in "While running: loop"
CALIBRATION_MODE = 0



# SVG_FILE = "/home/gula/Telautograph/XY_Plotter/output.svg"

# ---------------- USER-CONFIGURABLE CONSTANTS ----------------
# FPS = 60
FPS = 60

# Canvas size / scale used when the trace is saved to an SVG ("save" command).
SCREEN_W, SCREEN_H = 1000, 750
PX_PER_CM = 50

# Valid drawing area
RECT_W_CM, RECT_H_CM = 5.0, 2.0

# Bar Lengths (in cm) – tweak here
L1 = 3.75  # Base A segment 1
L2 = 4.75  # Base A segment 2
L3 = 3.75  # Base B segment 1
L4 = 4.75  # Base B segment 2

BASE_A_X = -RECT_W_CM +0.75 # Base A X
BASE_A_Y = -RECT_H_CM +3 #/ 2 + 0  # Base A Y

BASE_B_X = RECT_W_CM -0.75
BASE_B_Y = -RECT_H_CM +3

# Calibrated min and max base angles (degrees).
# Used with map_to_255() to calculate ForceA and ForceB to operate DACs.
# Re-tune with debugScripts/Simulation.py if the hardware changes.
minA = 93
maxA = 23
minB = -200
maxB = -300

# Calibrated output scaling applied to ForceA / ForceB before sending to the DACs
ForceA_Multiplier = 1
ForceB_Multiplier = 1

# This is almost certainly a horrible way of doing this.
bitMax = 4095
bitMin = 0

# Motion & sampling parameters
STEP_SIZE_CM = 0.05             # pen step per frame in cm
SAMPLES_PER_UNIT = 0.12         # sampling density: samples per SVG unit length (increase for higher fidelity)
MIN_SAMPLES_PER_SEGMENT = 4     # minimum samples per segment

# Debug
DEBUG_LINES = 18                # number of debug-log lines kept (shown by the "status" command)

# Headless-only options
ENABLE_CONSOLE_COMMANDS = True  # read commands (replay, pause, status...) from stdin
PRINT_LOG_MESSAGES = True       # echo debug-log messages to the terminal as they happen
TRACE_SVG_FILE = "trace.svg"    # where the "save" command writes the drawn trace

# ---------------- Derived / init ----------------
CENTER_X, CENTER_Y = SCREEN_W // 2, SCREEN_H // 2
rect_left, rect_right = -RECT_W_CM / 2, RECT_W_CM / 2
# rect_top, rect_bottom = -RECT_H_CM / 2, RECT_H_CM / 2
rect_top, rect_bottom = -RECT_H_CM / 2 -2, RECT_H_CM / 2
baseA = (BASE_A_X, BASE_A_Y)
baseB = (BASE_B_X, BASE_B_Y)


# ---------------- Debug log ----------------
debug_log = deque(maxlen=DEBUG_LINES)
_last_log_msg = None
def log(s):
    global _last_log_msg
    debug_log.appendleft(f"[{time.strftime('%H:%M:%S')}] {s}")
    # Echo to terminal, but don't spam the same message every frame
    if PRINT_LOG_MESSAGES and s != _last_log_msg:
        print(f"[LOG] {s}")
    _last_log_msg = s

log(f"BaseA: {baseA[0]:.2f},{baseA[1]:.2f} cm")
log(f"BaseB: {baseB[0]:.2f},{baseB[1]:.2f} cm")

# ---------------- Geometry helpers ----------------
def cm_to_px(val_cm):
    return int(round(val_cm * PX_PER_CM))

def to_screen(pt_cm):
    x_cm, y_cm = pt_cm
    sx = CENTER_X + cm_to_px(x_cm)
    # sy = CENTER_Y - cm_to_px(y_cm)   # note: screen y is down, our y is up
    sy = CENTER_Y + cm_to_px(y_cm)
    return (sx, sy)

# ---------------- Kinematics ----------------
def two_link_ik(base, l1, l2, target):
    bx, by = base
    tx, ty = target
    dx, dy = tx - bx, ty - by
    r = math.hypot(dx, dy)
    if r > l1 + l2 or r < abs(l1 - l2) or r == 0:
        return None
    alpha = math.atan2(dy, dx)
    cos_beta = (l1*l1 + r*r - l2*l2) / (2 * l1 * r)
    cos_beta = max(-1.0, min(1.0, cos_beta))
    beta = math.acos(cos_beta)
    s1 = alpha + beta
    s2 = alpha - beta
    cos_gamma = (l1*l1 + l2*l2 - r*r) / (2 * l1 * l2)
    cos_gamma = max(-1.0, min(1.0, cos_gamma))
    gamma = math.acos(cos_gamma)
    e1 = s1 - (math.pi - gamma)
    e2 = s2 - (math.pi - gamma)
    return ((s1, e1), (s2, e2))

def forward_two_link(base, l1, l2, shoulder, elbow):
    bx, by = base
    jx = bx + l1 * math.cos(shoulder)
    jy = by + l1 * math.sin(shoulder)
    ex = jx + l2 * math.cos(elbow)
    ey = jy + l2 * math.sin(elbow)
    return (jx, jy), (ex, ey)

def choose_solution(sols, base, l1, l2):
    (s1,e1),(s2,e2) = sols
    j1,_ = forward_two_link(base,l1,l2,s1,e1)
    j2,_ = forward_two_link(base,l1,l2,s2,e2)
    # choose elbow-down (larger world y) for consistent look
    return (s1,e1,j1) if j1[1] > j2[1] else (s2,e2,j2)

# ---------------- SVG loader with adaptive sampling & normalization ----------------
def adaptive_sample_path(path_obj, samples_per_unit=SAMPLES_PER_UNIT, min_per_seg=MIN_SAMPLES_PER_SEGMENT):
    """Return a list of (x,y) points sampled along the path_obj segments (SVG coordinates)."""
    pts = []
    for seg in path_obj:
        try:
            seg_len = seg.length(error=1e-4)
        except Exception:
            # fallback estimate by sampling endpoints
            p0 = seg.point(0); p1 = seg.point(1)
            seg_len = abs(p1 - p0)
        n = max(min_per_seg, int(max(1, round(seg_len * samples_per_unit))))
        for i in range(n):
            z = seg.point(i / (n - 1) if n>1 else 0.0)
            pts.append((z.real, z.imag))
    return pts

def load_and_normalize_svg(filename):
    """Load SVG, adaptively sample segments, and normalize to drawing rectangle in cm.
       Returns a flat list of points with None separators between subpaths.
    """
    print("load_and_normalize_svg() called")
    try:
        print("load_and_normalize_svg() try")
        paths, _ = svg2paths(filename)
        print("load_and_normalize_svg() try complete")
        print("paths = ", paths)
        print("_ = ", _)
    except Exception as e:
        print(f"load_and_normalize_svg() SVG load failed: {e}")
        log(f"load_and_normalize_svg() SVG load failed: {e}")
        return []

    all_points_svg = []   # in SVG units (as returned by svgpathtools)
    # sample each Path (which may contain multiple segments)
    for path_obj in paths:
        sampled = adaptive_sample_path(path_obj)
        if len(sampled) > 0:
            # svg y axis is downward; keep as-is for now and flip on normalization
            all_points_svg.extend(sampled)
            all_points_svg.append(None)  # separator between top-level paths

    # remove trailing None
    if len(all_points_svg) and all_points_svg[-1] is None:
        all_points_svg.pop()

    if not all_points_svg:
        return []

    # compute bounding box of non-None points
    xs = [pt[0] for pt in all_points_svg if pt is not None]
    ys = [pt[1] for pt in all_points_svg if pt is not None]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    svg_w, svg_h = maxx - minx, maxy - miny
    if svg_w == 0 or svg_h == 0:
        log("SVG has zero width or height — can't normalize.")
        return []

    # target drawing box in cm (apply margin)
    margin = 0.92
    target_w, target_h = RECT_W_CM * margin, RECT_H_CM * margin

    # determine scale: SVG units -> cm
    scale = min(target_w / svg_w, target_h / svg_h)

    # center offsets
    cx_svg = minx + svg_w / 2.0
    cy_svg = miny + svg_h / 2.0

    normalized = []
    for pt in all_points_svg:
        if pt is None:
            normalized.append(None)
        else:
            sx, sy = pt
            # convert svg coords to centered coordinates, scale to cm, and flip Y
            nx = (sx - cx_svg) * scale
            ny = - (sy - cy_svg) * scale   # flip Y (SVG down -> plot up)
            normalized.append((nx, ny))
    log(f"SVG normalized: scale={scale:.6f} (svg_w={svg_w:.2f}, svg_h={svg_h:.2f})")
    return normalized

# ---------------- Fallback shape if no SVG ----------------
def fallback_shape():
    # ellipse scaled to fit rectangle visually
    pts = []
    for a in np.linspace(0, 2*math.pi, 300):
        x = 1.8 * math.cos(a)
        y = 0.6 * math.sin(a)
        pts.append((x, y))
    pts.append(None)
    pts.append((rect_left, rect_bottom))  # return home marker
    return pts

# ---------------- Load path ----------------
path = load_and_normalize_svg(SVG_FILE)
print(path)
if not path:
    if EXIT_WHEN_DONE:
        print(f"ERROR: could not load SVG {SVG_FILE!r}; nothing to plot.")
        if ser and ser.is_open:
            ser.close()
        sys.exit(1)
    log("Using fallback shape.")
    path = fallback_shape()

# ---------------- Angle mapping helpers (to 0-255) & gradient ----------------
def compute_angle_range(base, l_prox, l_dist, step=0.25):
    angles = []
    # sample interior of drawing rectangle to discover feasible angles
    xs = np.arange(rect_left, rect_right + 1e-9, step)
    ys = np.arange(rect_top, rect_bottom + 1e-9, step)
    for x in xs:
        for y in ys:
            ik = two_link_ik(base, l_prox, l_dist, (x, y))
            if ik:
                for s,e in ik:
                    angles.append(s)
    if not angles:
        return (-math.pi, math.pi)
    return min(angles), max(angles)

def map_angle_to_255(angle, min_a, max_a):
    # clamp and map
    if max_a == min_a:
        return 128
    v = (angle - min_a) / (max_a - min_a)
    v = max(0.0, min(1.0, v))
    return int(round(v * 255))

def map_angle_to_4095(angle, min_a, max_a):
    # clamp and map
    if max_a == min_a:
        return 2048
    v = (angle - min_a) / (max_a - min_a)
    v = max(0.0, min(1.0, v))
    return int(round(v * 4095))

def map_to_255(value, min_val, max_val):
    """
    Maps a number within [min_val, max_val] to a value in [bitMax, 0]
    (12-bit, inverted). Name kept from the original 8-bit version.
    """
    # 8 bit / 255-0 versions removed; see git history.
    #12 bit code
    #4095-0 code
    if max_val == min_val:
        return bitMax  # avoid division by zero
    normalized = (value - min_val) / (max_val - min_val)
    scaled = int(round((1 - normalized) * bitMax))
    return max(0, min(4095, scaled))  # clamp to [0,4095]

# ---------------- State ----------------
def reset():
    global pen, trace, path_idx, pen_down, finished
    pen = (rect_left, rect_bottom)   # lower-left corner in cm
    trace = []
    path_idx = 0
    pen_down = False
    finished = False
    log("Replay initiated.")
reset()


def operate_DAC(baseA_val, baseB_val, pen_down, energize):
    """
    Send 12-bit DAC values and pen state over serial to the Arduino Due.

    Args:
        baseA_val (int): Value for DAC1 (0–4095)
        baseB_val (int): Value for DAC2 (0–4095)
        pen_down (bool or int): 1 if pen is down, 0 if up
        energize (bool): energize state
    """
    print(baseA_val, baseB_val, pen_down, energize)
    if ser and ser.is_open:
        try:
            # Clamp to valid 12-bit range
            baseA_val = max(0, min(4095, int(baseA_val)))
            baseB_val = max(0, min(4095, int(baseB_val)))
            # pen_state = 1 if pen_down else 0
            pen_state = 0 if pen_down else 1
            energize_state = 0 if energize else 1
            # === Option 1: ASCII protocol (readable, easy to debug) ===
            # Format: "baseA,baseB,pen\n"
            msg = f"{baseA_val},{baseB_val},{pen_state},{energize_state}\n"
            ser.write(msg.encode('ascii'))

            # === Option 2 (optional): binary protocol (faster, compact) ===
            # If you want binary 12-bit transmission instead:
            # packet = struct.pack('<HHB', baseA_val, baseB_val, pen_state)
            # ser.write(packet)

            # === Debug output ===
            print(f"Sent to Arduino → A:{baseA_val:4d}  B:{baseB_val:4d}  Pen:{pen_state}")
        except Exception as e:
            print(f"Serial send error: {e}")


# ---------------- Console commands ----------------
HELP_TEXT = """
Commands (type and press Enter):
  replay | r     restart the drawing from the beginning
  clear  | c     clear the trace
  pause  | p     pause / resume
  status | s     print positions, angles, DAC values and the debug log
  save           write the drawn trace to TRACE_SVG_FILE
  quit   | q     exit (Ctrl+C also works)
  help   | h     show this help
"""

command_queue = queue.Queue()

def _stdin_reader():
    """Background thread: read lines from stdin and queue each word as a command."""
    while True:
        try:
            line = sys.stdin.readline()
        except Exception:
            return
        if line == "":      # EOF (e.g. stdin not attached) - stop reading
            return
        for word in line.split():
            command_queue.put(word.strip().lower())

def print_status():
    lines = [
        "---------------- STATUS ----------------",
        f"Pen Status: {'DOWN' if pen_down else 'UP'}",
        f"Energized: {energize}",
        f"Speed (FPS): {FPS}",
        f"Paused: {pause}",
        f"Path progress: {min(path_idx, len(path))}/{len(path)} points, trace = {sum(p is not None for p in trace)} points",
    ]
    if hud is None:
        lines.append("IK unreachable for current pen position")
    else:
        lines += [
            f"J1: {hud['jL'][0]:.2f},{hud['jL'][1]:.2f} cm",
            f"J2: {hud['jR'][0]:.2f},{hud['jR'][1]:.2f} cm",
            f"Pen: {pen[0]:.2f},{pen[1]:.2f} cm",
            f"Base A angle: {math.degrees(hud['sL']):.1f}°",
            f"Base B angle: {math.degrees(hud['sR']):.1f}°",
            f"Dists: A={math.hypot(pen[0]-baseA[0], pen[1]-baseA[1]):.2f}cm, B={math.hypot(pen[0]-baseB[0], pen[1]-baseB[1]):.2f}cm",
            f"Mapped: A={hud['baseA_val']}, B={hud['baseB_val']}",
            "",
            f"minA = {minA}",
            f"maxA = {maxA}",
            f"minB = {minB}",
            f"maxB = {maxB}",
            "",
            f"ForceA_Multiplier= {ForceA_Multiplier}",
            f"ForceB_Multiplier= {ForceB_Multiplier}",
            f"forceA = {hud['ForceA']}",
            f"forceB = {hud['ForceB']}",
        ]
    lines.append("Debug Log:")
    lines += [f"  {msg}" for msg in debug_log]
    lines.append("----------------------------------------")
    print("\n".join(lines))

def save_trace_svg(filename=TRACE_SVG_FILE):
    """Write the drawing rectangle, bases and current trace to an SVG (screen coordinates)."""
    top_left = to_screen((rect_left, rect_top + RECT_H_CM))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SCREEN_W}" height="{SCREEN_H}" '
        f'viewBox="0 0 {SCREEN_W} {SCREEN_H}">',
        f'<rect width="{SCREEN_W}" height="{SCREEN_H}" fill="rgb(22,22,28)"/>',
        f'<rect x="{top_left[0]}" y="{top_left[1]}" width="{cm_to_px(RECT_W_CM)}" height="{cm_to_px(RECT_H_CM)}" '
        f'fill="rgb(38,38,46)" stroke="rgb(200,200,200)" stroke-width="2"/>',
    ]
    for b in (baseA, baseB):
        bx, by = to_screen(b)
        parts.append(f'<circle cx="{bx}" cy="{by}" r="6" fill="rgb(200,80,80)"/>')
    # One polyline per pen-down stroke (None marks where the pen was lifted)
    strokes = [[]]
    for p in trace:
        if p is None:
            strokes.append([])
        else:
            strokes[-1].append(p)
    for stroke in strokes:
        if len(stroke) > 1:
            pts = " ".join(f"{x},{y}" for x, y in (to_screen(p) for p in stroke))
            parts.append(f'<polyline points="{pts}" fill="none" stroke="rgb(100,255,140)" stroke-width="2"/>')
    parts.append("</svg>")
    try:
        with open(filename, "w") as f:
            f.write("\n".join(parts))
        log(f"Trace saved to {filename} ({sum(p is not None for p in trace)} points).")
    except Exception as e:
        log(f"Trace save failed: {e}")

def handle_command(cmd):
    """Apply one console command."""
    global running, pause

    if cmd in ("q", "quit", "exit"):
        running = False
    elif cmd in ("r", "replay"):
        reset()
    elif cmd in ("c", "clear"):
        trace.clear()
        log("Trace cleared.")
    elif cmd in ("p", "pause"):
        pause = not pause
        print("Paused (type 'p' to resume)" if pause else "Resumed")
    elif cmd in ("s", "status"):
        print_status()
    elif cmd == "save":
        save_trace_svg()
    elif cmd in ("h", "help", "?"):
        print(HELP_TEXT)
    else:
        print(f"Unknown command: {cmd!r} (type 'help' for a list)")


# ---------------- Main Loop ----------------
running = True
pause = False
energize = False
hud = None                      # last computed kinematics/DAC values (for "status")
sL = sR = None                  # last valid base angles (kept if IK fails)

if ENABLE_CONSOLE_COMMANDS:
    threading.Thread(target=_stdin_reader, daemon=True).start()
    print(HELP_TEXT)

next_frame = time.perf_counter()
try:
    while running:
        # ---------------- Console commands ----------------
        while not command_queue.empty():
            handle_command(command_queue.get_nowait())
            if not running:
                break
        if not running:
            break

        if pause:
            time.sleep(0.05)
            next_frame = time.perf_counter()
            continue

        # ---------------- Pen motion (pen-up between subpaths) ----------------
        if path_idx < len(path):
            # Skip consecutive None separators and ensure pen is up during travel between strokes
            while path_idx < len(path) and path[path_idx] is None:
                if pen_down:
                    pen_down = False
                    log("Pen lifted (end of stroke).")
                path_idx += 1

            if path_idx < len(path):
                target = path[path_idx]
                # target is a (x,y) in cm in normalized coordinates
                dx = target[0] - pen[0]; dy = target[1] - pen[1]
                dist = math.hypot(dx, dy)
                if not pen_down:
                    # traveling (pen up) to stroke start
                    if dist <= STEP_SIZE_CM:
                        pen = target
                        pen_down = True
                        path_idx += 1
                        trace.append(None)   # stroke break (pen was up)
                        log(f"Pen lowered at start of stroke: {pen}")
                    else:
                        pen = (pen[0] + dx / dist * STEP_SIZE_CM, pen[1] + dy / dist * STEP_SIZE_CM)
                else:
                    # drawing (pen down) through consecutive points until next None
                    if dist <= STEP_SIZE_CM:
                        pen = target
                        path_idx += 1
                        trace.append(pen)
                    else:
                        new_pos = (pen[0] + dx / dist * STEP_SIZE_CM, pen[1] + dy / dist * STEP_SIZE_CM)
                        trace.append(new_pos)
                        pen = new_pos
        else:
            # finished path; return home with pen up
            home = (rect_left, rect_bottom)
            dx = home[0] - pen[0]; dy = home[1] - pen[1]
            dist = math.hypot(dx, dy)
            if dist > STEP_SIZE_CM:
                if pen_down:
                    pen_down = False
                    log("Pen lifted (returning home).")
                pen = (pen[0] + dx / dist * STEP_SIZE_CM, pen[1] + dy / dist * STEP_SIZE_CM)
                energize = False
                if CALIBRATION_MODE == 1:
                    reset()
            else:
                pen_down = False
                finished = True

        # ---------------- Kinematics ----------------
        ikL = two_link_ik(baseA, L1, L2, pen)
        ikR = two_link_ik(baseB, L3, L4, pen)
        if not ikL or not ikR:
            # unreachable — log and keep the last valid angles
            log("Target unreachable by one or both chains.")
            hud = None
        else:
            sL,eL,jL = choose_solution(ikL, baseA, L1, L2)
            sR,eR,jR = choose_solution(ikR, baseB, L3, L4)

        if sL is not None and sR is not None:
            # ---------------- Servo mapping ----------------
            baseA_val = map_angle_to_4095(sL, minA, maxA) if ikL else 0
            baseB_val = map_angle_to_4095(sR, minB, maxB) if ikR else 0

            ForceA = map_to_255(math.degrees(sL), minA, maxA)
            ForceB = map_to_255(math.degrees(sR), minB, maxB)

            if ikL and ikR:
                hud = dict(sL=sL, sR=sR, jL=jL, jR=jR, baseA_val=baseA_val, baseB_val=baseB_val,
                           ForceA=ForceA, ForceB=ForceB)

            # DAC control function
            operate_DAC(ForceA*ForceA_Multiplier, ForceB*ForceB_Multiplier, pen_down, energize)

        if finished and EXIT_WHEN_DONE:
            log("Drawing finished.")
            break

        # ---------------- Frame timing (replaces clock.tick(FPS)) ----------------
        next_frame += 1.0 / FPS
        delay = next_frame - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        else:
            next_frame = time.perf_counter()   # running behind; don't try to catch up

except KeyboardInterrupt:
    print("\nInterrupted (Ctrl+C).")
finally:
    if ser and ser.is_open:
        ser.close()
