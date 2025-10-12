"""
five_bar_plotter_adaptive_svg.py

5-bar linkage simulator with:
 - adaptive sampling of SVG curves (fidelity scaling)
 - automatic SVG normalization (scale & center to drawing area)
 - pen-up between SVG subpaths, persistent trace, replay & clear
 - servo 0-255 bars, debug HUD, configurable constants

Mostly made by ChatGPT 
"""

import pygame, math, time
from svgpathtools import svg2paths
from collections import deque
import numpy as np

# For controlling Arduino Due 12 bit DACs.
import serial

# ---------------- USER-CONFIGURABLE CONSTANTS ----------------
FPS = 60
SCREEN_W, SCREEN_H = 1000, 750
PX_PER_CM = 50

# Valid drawing area
RECT_W_CM, RECT_H_CM = 5.0, 2.0


# # Bar lengths (cm)
# L1 = 6.0
# L2 = 6.0
# L3 = 6.0
# L4 = 6.0

# Bar Lengths (in cm) – tweak here
L1 = 3.75  # Base A segment 1
L2 = 4.75  # Base A segment 2
L3 = 3.75  # Base B segment 1
L4 = 4.75  # Base B segment 2

# # Base positions (cm)
# BASE_A_X = -RECT_W_CM / 2 - 0.5
# BASE_A_Y = -RECT_H_CM / 2 - 1.0
# BASE_B_X = RECT_W_CM / 2 + 0.5
# BASE_B_Y = -RECT_H_CM / 2 - 1.0

BASE_A_X = -RECT_W_CM +0.75 # Base A X
BASE_A_Y = -RECT_H_CM +3 #/ 2 + 0  # Base A Y

BASE_B_X = RECT_W_CM -0.75  
BASE_B_Y = -RECT_H_CM +3


# Motion & sampling parameters
STEP_SIZE_CM = 0.05             # pen step per frame in cm
SAMPLES_PER_UNIT = 0.12         # sampling density: samples per SVG unit length (increase for higher fidelity)
MIN_SAMPLES_PER_SEGMENT = 4     # minimum samples per segment
SVG_FILE = "/home/gula/Telautograph/XY_Plotter/line-3-svgrepo-com.svg"        # file to load (if missing, fallback shape used)

# Debug / UI
DEBUG_LINES = 18
BAR_WIDTH_PX = 260

# ---------------- Derived / init ----------------
CENTER_X, CENTER_Y = SCREEN_W // 2, SCREEN_H // 2
rect_left, rect_right = -RECT_W_CM / 2, RECT_W_CM / 2
# rect_top, rect_bottom = -RECT_H_CM / 2, RECT_H_CM / 2
rect_top, rect_bottom = -RECT_H_CM / 2 -2, RECT_H_CM / 2
baseA = (BASE_A_X, BASE_A_Y)
baseB = (BASE_B_X, BASE_B_Y)

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("5-Bar Linkage")
clock = pygame.time.Clock()
font = pygame.font.SysFont("consolas", 16)

# added this
Default_angle_A = 113.5
Default_angle_B = -223.1

# ---------------- Debug log ----------------
debug_log = deque(maxlen=DEBUG_LINES)
def log(s):
    debug_log.appendleft(f"[{time.strftime('%H:%M:%S')}] {s}")

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

# def to_screen(pt): x, y = pt; return CENTER_X + cm_to_px(x), CENTER_Y + cm_to_px(y)

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
    try:
        paths, _ = svg2paths(filename)
    except Exception as e:
        log(f"SVG load failed: {e}")
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
if not path:
    log("Using fallback shape.")
    path = fallback_shape()

# ---------------- UI Elements ----------------
replay_btn = pygame.Rect(20, SCREEN_H - 60, 100, 35)
clear_btn  = pygame.Rect(140, SCREEN_H - 60, 100, 35)

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

minA, maxA = compute_angle_range(baseA, L1, L2)
minB, maxB = compute_angle_range(baseB, L3, L4)

def map_angle_to_255(angle, min_a, max_a):
    # clamp and map
    if max_a == min_a:
        return 128
    v = (angle - min_a) / (max_a - min_a)
    v = max(0.0, min(1.0, v))
    return int(round(v * 255))

def gradient_color(v):
    # v: 0..255 -> blue->green->red
    if v < 128:
        r = 0
        g = int(2 * v)
        b = 255 - g
    else:
        r = int(2 * (v - 128))
        g = 255 - r
        b = 0
    return (r, g, b)

# ---------------- State ----------------
def reset():
    global pen, trace, path_idx, pen_down
    pen = (rect_left, rect_bottom)   # lower-left corner in cm
    trace = []
    path_idx = 0
    pen_down = False
    log("Replay initiated.")
reset()


def operate_DAC(Aval, Bval, penlift=False):
    print(Aval, Bval, penlift)
    serial.send(Aval, Bval, penlift)

# ---------------- Main Loop ----------------
running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
        elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            running = False
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if replay_btn.collidepoint(ev.pos):
                reset()
            elif clear_btn.collidepoint(ev.pos):
                trace.clear()
                log("Trace cleared.")

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
        else:
            pen_down = False

    # ---------------- Kinematics ----------------
    ikL = two_link_ik(baseA, L1, L2, pen)
    ikR = two_link_ik(baseB, L3, L4, pen)
    if not ikL or not ikR:
        # unreachable — log once and skip drawing update for this frame
        log("Target unreachable by one or both chains.")
        # continue to draw rest of UI but skip joint drawing
    else:
        sL,eL,jL = choose_solution(ikL, baseA, L1, L2)
        sR,eR,jR = choose_solution(ikR, baseB, L3, L4)

    # ---------------- Servo mapping ----------------
    baseA_val = map_angle_to_255(sL, minA, maxA) if ikL else 0
    baseB_val = map_angle_to_255(sR, minB, maxB) if ikR else 0

    # Added this
    ForceA = Default_angle_A - math.degrees(sL)
    ForceB = Default_angle_B - math.degrees(sR)

    # ---------------- Drawing ----------------
    screen.fill((22,22,28))
    # draw valid rectangle (centered at (0,0) in cm coordinates)
    top_left = to_screen((rect_left, rect_top + RECT_H_CM))
    rect_w = cm_to_px(RECT_W_CM)
    rect_h = cm_to_px(RECT_H_CM)
    rect_rect = pygame.Rect(top_left[0], top_left[1], rect_w, rect_h)
    pygame.draw.rect(screen, (38,38,46), rect_rect)
    pygame.draw.rect(screen, (200,200,200), rect_rect, 2)

    # draw trace
    if len(trace) > 1:
        pts = [to_screen(p) for p in trace]
        pygame.draw.lines(screen, (100,255,140), False, pts, 2)

    # draw bases and links if ik available
    if ikL and ikR:
        # left chain
        left_base_screen = to_screen(baseA)
        left_joint_screen = to_screen(jL)
        pen_screen = to_screen(pen)
        pygame.draw.circle(screen, (200,80,80), left_base_screen, 6)
        pygame.draw.line(screen, (120,200,255), left_base_screen, left_joint_screen, 5)
        pygame.draw.circle(screen, (255,200,70), left_joint_screen, 5)
        pygame.draw.line(screen, (120,200,255), left_joint_screen, pen_screen, 4)

        # right chain
        right_base_screen = to_screen(baseB)
        right_joint_screen = to_screen(jR)
        pygame.draw.circle(screen, (200,80,80), right_base_screen, 6)
        pygame.draw.line(screen, (120,200,255), right_base_screen, right_joint_screen, 5)
        pygame.draw.circle(screen, (255,200,70), right_joint_screen, 5)
        pygame.draw.line(screen, (120,200,255), right_joint_screen, pen_screen, 4)

        # pen
        pygame.draw.circle(screen, (255,80,120), pen_screen, 5)
        # pen outline if up
        if not pen_down:
            pygame.draw.circle(screen, (255,255,255), pen_screen, 6, 1)

        # label joints and link lengths near them
        screen.blit(font.render(f"L1={L1:.2f}cm", True, (220,220,220)), (left_base_screen[0]-40, left_base_screen[1]+10))
        screen.blit(font.render(f"L2={L2:.2f}cm", True, (220,220,220)), (left_joint_screen[0]-40, left_joint_screen[1]+10))
        screen.blit(font.render(f"L3={L3:.2f}cm", True, (220,220,220)), (right_base_screen[0]-10, right_base_screen[1]+10))
        screen.blit(font.render(f"L4={L4:.2f}cm", True, (220,220,220)), (right_joint_screen[0]-10, right_joint_screen[1]+10))

        # coordinates display small
        info_x = SCREEN_W - 320; info_y = 10
        info = [
            f"J1: {jL[0]:.2f},{jL[1]:.2f} cm",
            f"J2: {jR[0]:.2f},{jR[1]:.2f} cm",
            f"Pen: {pen[0]:.2f},{pen[1]:.2f} cm",
            f"Base A angle: {math.degrees(sL):.1f}°",
            f"Base B angle: {math.degrees(sR):.1f}°",
            f"forceA = {ForceA}",
            f"forceB = {ForceB}",
            f"Dists: A={math.hypot(pen[0]-baseA[0], pen[1]-baseA[1]):.2f}cm, B={math.hypot(pen[0]-baseB[0], pen[1]-baseB[1]):.2f}cm",
            f"Mapped: A={baseA_val}, B={baseB_val}",
            "Pen: " + ("DOWN" if pen_down else "UP")
        ]
        for i, line in enumerate(info):
            screen.blit(font.render(line, True, (220,220,220)), (info_x, info_y + 18 * i))

    else:
        screen.blit(font.render("IK unreachable for current pen position", True, (255,120,120)), (20, 140))

    # Buttons
    pygame.draw.rect(screen, (80,150,255), replay_btn)
    pygame.draw.rect(screen, (255,120,80), clear_btn)
    screen.blit(font.render("Replay", True, (255,255,255)), (replay_btn.x+20, replay_btn.y+8))
    screen.blit(font.render("Clear", True, (255,255,255)), (clear_btn.x+30, clear_btn.y+8))

    # Servo Bars (visualize mapped 0-255)
    def draw_bar(x, y, value, label):
        color = gradient_color(value)
        pygame.draw.rect(screen, (50,50,50), (x, y, BAR_WIDTH_PX, 18))
        pygame.draw.rect(screen, color, (x, y, int(value/255.0*BAR_WIDTH_PX), 18))
        pygame.draw.rect(screen, (255,255,255), (x, y, BAR_WIDTH_PX, 18), 1)
        screen.blit(font.render(f"{label}: {value}", True, (255,255,255)), (x + BAR_WIDTH_PX + 8, y - 2))

    draw_bar(20, 20, baseA_val, "Base A")
    draw_bar(20, 50, baseB_val, "Base B")
    screen.blit(font.render(f"Pen Status: {'DOWN' if pen_down else 'UP'}", True, ((0,255,0) if pen_down else (255,160,160))), (20, 85))
    screen.blit(font.render(f"Current Status: ", True, (255,255,140)), (20, 100))
    screen.blit(font.render(f"Speed: ", True, (255,255,140)), (20, 115))

    # DAC control function
    operate_DAC(baseA_val, baseB_val, pen_down)

    # Debug log (right side)
    dbg_x = SCREEN_W - 360; dbg_y = 220
    screen.blit(font.render("Debug Log:", True, (255,255,140)), (dbg_x, dbg_y))
    for i, msg in enumerate(debug_log):
        screen.blit(font.render(msg, True, (200,200,200)), (dbg_x, dbg_y + 18 * (i + 1)))

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
