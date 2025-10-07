import pygame, math, time
from svgpathtools import svg2paths
import numpy as np
from collections import deque

# ---------- USER-CONFIGURABLE CONSTANTS ----------

SVG_PATH = "/home/gula/Telautograph/XY_Plotter/photo-camera-svgrepo-com.svg"

# Screen & Drawing Area
FPS = 60
SCREEN_W, SCREEN_H = 1000, 750
PX_PER_CM = 50
RECT_W_CM, RECT_H_CM = 5.0, 2.0    # Valid drawing area in cm

# Bar Lengths (in cm) – tweak here
L1 = 3.75  # Base A segment 1
L2 = 4.75  # Base A segment 2
L3 = 3.75  # Base B segment 1
L4 = 4.75  # Base B segment 2

# Base Locations (in cm) – tweak here
# BASE_A_X = -RECT_W_CM / 2 - 0.5  # Base A X
# BASE_A_Y = -RECT_H_CM / 2 - 1.0  # Base A Y
# BASE_B_X = RECT_W_CM / 2 + 0.5   # Base B X
# BASE_B_Y = -RECT_H_CM / 2 - 1.0  # Base B Y

BASE_A_X = -RECT_W_CM +0.75 # Base A X
BASE_A_Y = -RECT_H_CM +3 #/ 2 + 0  # Base A Y

BASE_B_X = RECT_W_CM -0.75  
BASE_B_Y = -RECT_H_CM +3

# Motion Parameters
STEP_SIZE_CM = 0.05
SAMPLES_PER_CURVE = 150
DEBUG_LINES = 16

# ---------- DERIVED VALUES ----------
CENTER_X, CENTER_Y = SCREEN_W // 2, SCREEN_H // 2
rect_left, rect_right = -RECT_W_CM / 2, RECT_W_CM / 2
rect_top, rect_bottom = -RECT_H_CM / 2, RECT_H_CM / 2
baseA = (BASE_A_X, BASE_A_Y)
baseB = (BASE_B_X, BASE_B_Y)

# added this
Default_angle_A = 113.5
Default_angle_B = -223.1

# ---------- Pygame Setup ----------
pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("5-Bar Linkage (Configurable Constants)")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 20)

# ---------- Helper Functions ----------
def cm_to_px(v): return int(round(v * PX_PER_CM))
def to_screen(pt): x, y = pt; return CENTER_X + cm_to_px(x), CENTER_Y + cm_to_px(y)

def two_link_ik(base, l1, l2, target):
   
    bx, by = base; tx, ty = target
    dx, dy = tx - bx, ty - by
    r = math.hypot(dx, dy)
    if r > l1 + l2 or r < abs(l1 - l2): return None
    a = math.atan2(dy, dx)
    cosb = (l1**2 + r**2 - l2**2) / (2 * l1 * r)
    cosb = max(-1, min(1, cosb))
    b = math.acos(cosb)
    s1, s2 = a + b, a - b
    cosg = (l1**2 + l2**2 - r**2) / (2 * l1 * l2)
    cosg = max(-1, min(1, cosg))
    g = math.acos(cosg)
    e1, e2 = s1 - (math.pi - g), s2 - (math.pi - g)
    return ((s1, e1), (s2, e2))

def forward(base, l1, l2, s, e):
    bx, by = base
    j = (bx + l1 * math.cos(s), by + l1 * math.sin(s))
    end = (j[0] + l2 * math.cos(e), j[1] + l2 * math.sin(e))
    return j, end

def choose_solution(solns, base, l1, l2):
    
    (s1, e1), (s2, e2) = solns
    j1, _ = forward(base, l1, l2, s1, e1)
    j2, _ = forward(base, l1, l2, s2, e2)
    return (s1, e1, j1) if j1[1] > j2[1] else (s2, e2, j2)

def load_svg_points(filename):
    print("load_svg_points() called! ", filename, " type = ", type(filename))

    paths, attributes = svg2paths(filename)
    print("paths = ", paths, " type = ", type(paths))
    print("attributes = ", attributes, " type = ", type(attributes))
    points = []
    for p in paths:
        print("Outer for loop!  for p in paths: ", p)
        for t in np.linspace(0, 1, SAMPLES_PER_CURVE):
            print("inner for loop!!!! for t in np.linspace(0, 1, SAMPLES_PER_CURVE):", t)
            z = p.point(t)
            points.append((z.real, z.imag))
        print("Points = ", points)
        # points.append(None)
    xs = [x for x, y in points if x is not None]
    ys = [y for x, y in points if y is not None]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    s = min(RECT_W_CM / w, RECT_H_CM / h) * 0.9
    return [None if pt is None else
            ((pt[0] - (min(xs) + w / 2)) * s,
            (pt[1] - (min(ys) + h / 2)) * s)
            for pt in points]


try:
    print("Try")
    path = load_svg_points(SVG_PATH)
    print("Tried")
except Exception as e:
    print("exception = ", e)
    circle = [(math.cos(a) * 2, math.sin(a) * 0.8) for a in np.linspace(0, 2 * math.pi, 200)]
    path = circle + [None, (rect_left, rect_bottom)]

# ---------- Buttons ----------
replay_btn = pygame.Rect(20, SCREEN_H - 60, 100, 35)
clear_btn = pygame.Rect(140, SCREEN_H - 60, 100, 35)

# ---------- Debug Utilities ----------
debug_log = deque(maxlen=DEBUG_LINES)
def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    debug_log.appendleft(f"[{timestamp}] {msg}")

def compute_angle_range(base, l1, l2, step=0.25):
    angles = []
    for x in np.arange(rect_left, rect_right, step):
        for y in np.arange(rect_top, rect_bottom, step):
            ik = two_link_ik(base, l1, l2, (x, y))
            if ik:
                for s, e in ik:
                    angles.append(s)
    return min(angles), max(angles)

minA, maxA = compute_angle_range(baseA, L1, L2)
minB, maxB = compute_angle_range(baseB, L3, L4)

def map_angle_to_255(angle, min_a, max_a):
    return int((angle - min_a) / (max_a - min_a) * 255)

# def Base_A_force(angle, min_a, max_a):
#     return int((angle - min_a) / (max_a - min_a) * 255)

# def Base_B_force(angle, min_a, max_a):
#     return int((angle - min_a) / (max_a - min_a) * 255)

# def gradient_color(value):
#     if value < 128:
#         r = 0; g = int(2 * value); b = 255 - g
#     else:
#         r = int(2 * (value - 128)); g = 255 - r; b = 0
#     return r, g, b

def draw_bar(x, y, value, label):
    # color = gradient_color(value)
    color = "red"
    pygame.draw.rect(screen, (50, 50, 50), (x, y, 260, 20))
    pygame.draw.rect(screen, color, (x, y, value, 20))
    # pygame.draw.rect(screen, (x, y, value, 20))
    pygame.draw.rect(screen, (255, 255, 255), (x, y, 260, 20), 2)
    screen.blit(font.render(f"{label}: {value}", True, (255, 255, 255)), (x + 100, y - 18))

# ---------- State ----------
def reset():
    global pen, trace, path_idx, pen_down
    pen = (rect_left, rect_bottom)
    trace = []
    path_idx = 0
    pen_down = False
    log("Replay initiated.")
reset()

# ---------- Main Loop ----------
running = True
while running:
    for e in pygame.event.get():
        if e.type == pygame.QUIT: running = False
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE: running = False
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if replay_btn.collidepoint(e.pos): reset()
            elif clear_btn.collidepoint(e.pos):
                trace.clear(); log("Trace cleared.")

    if path_idx < len(path):
        target = path[path_idx]
        if target is None:
            pen_down = False; path_idx += 1; log("Pen lifted.")
        else:
            pen_down = True
            dx, dy = target[0] - pen[0], target[1] - pen[1]
            dist = math.hypot(dx, dy)
            if dist < STEP_SIZE_CM:
                pen = target; path_idx += 1; log(f"Pen reached {pen}.")
            else:
                pen = (pen[0] + dx / dist * STEP_SIZE_CM,
                       pen[1] + dy / dist * STEP_SIZE_CM)
    else:
        dx, dy = rect_left - pen[0], rect_bottom - pen[1]
        if math.hypot(dx, dy) > STEP_SIZE_CM:
            pen = (pen[0] + dx / math.hypot(dx, dy) * STEP_SIZE_CM,
                   pen[1] + dy / math.hypot(dx, dy) * STEP_SIZE_CM)

    if pen_down: trace.append(pen)

    ikL = two_link_ik(baseA, L1, L2, pen)
    ikR = two_link_ik(baseB, L3, L4, pen)
    if not ikL or not ikR: continue
    sL, eL, jL = choose_solution(ikL, baseA, L1, L2)
    sR, eR, jR = choose_solution(ikR, baseB, L3, L4)

    baseA_val = map_angle_to_255(sL, minA, maxA)
    baseB_val = map_angle_to_255(sR, minB, maxB)


    # Added this
    ForceA = Default_angle_A - math.degrees(sL)
    ForceB = Default_angle_B - math.degrees(sR)

    screen.fill((25, 25, 35))
    rect_screen = pygame.Rect(CENTER_X + cm_to_px(rect_left), CENTER_Y + cm_to_px(rect_top),
                              cm_to_px(RECT_W_CM), cm_to_px(RECT_H_CM))
    pygame.draw.rect(screen, (50, 50, 60), rect_screen)
    pygame.draw.rect(screen, (200, 200, 200), rect_screen, 2)

    if len(trace) > 1:
        pygame.draw.lines(screen, (100, 255, 100), False, [to_screen(p) for p in trace], 2)

    pygame.draw.line(screen, (120, 200, 255), to_screen(baseA), to_screen(jL), 4)
    pygame.draw.line(screen, (120, 200, 255), to_screen(jL), to_screen(pen), 3)
    pygame.draw.line(screen, (120, 200, 255), to_screen(baseB), to_screen(jR), 4)
    pygame.draw.line(screen, (120, 200, 255), to_screen(jR), to_screen(pen), 3)

    for label, pt in [("BaseA", baseA), ("J1", jL), ("Pen", pen), ("BaseB", baseB), ("J2", jR)]:
        sx, sy = to_screen(pt)
        pygame.draw.circle(screen, (255, 200, 70), (sx, sy), 5)
        screen.blit(font.render(label, True, (255, 255, 255)), (sx + 5, sy - 10))

    # Buttons
    pygame.draw.rect(screen, (80, 150, 255), replay_btn)
    pygame.draw.rect(screen, (255, 120, 80), clear_btn)
    screen.blit(font.render("Replay", True, (255, 255, 255)), (replay_btn.x + 15, replay_btn.y + 7))
    screen.blit(font.render("Clear", True, (255, 255, 255)), (clear_btn.x + 25, clear_btn.y + 7))

    # Servo Bars
    draw_bar(20, 20, baseA_val, "Base A")
    draw_bar(20, 60, baseB_val, "Base B")

    # Debug Log
    info_x=SCREEN_W-260; info_y=10
    info=[
        f"L1,L2,L3,L4: {L1},{L2},{L3},{L4}",
        f"J1: {jL[0]:.2f},{jL[1]:.2f}",
        f"J2: {jR[0]:.2f},{jR[1]:.2f}",
        f"Pen: {pen[0]:.2f},{pen[1]:.2f}",
        f"BaseA: {baseA[0]:.2f},{baseA[1]:.2f}",
        f"BaseB: {baseB[0]:.2f},{baseB[1]:.2f}",
        f"Base A angle: {math.degrees(sL):.1f}°",
        f"Base B angle: {math.degrees(sR):.1f}°",
        f"forceA = {ForceA}",
        f"forceB = {ForceB}",
        "Pen: " + ("DOWN" if pen_down else "UP")
    ]
    for i,line in enumerate(info):
        screen.blit(font.render(line,True,(220,220,220)),(info_x,info_y+20*i))

    dbg_y=info_y+20*len(info)+20
    screen.blit(font.render("Debug Log:",True,(255,255,100)),(info_x,dbg_y))
    for i,msg in enumerate(debug_log):
        screen.blit(font.render(msg,True,(180,180,180)),(info_x,dbg_y+20*(i+1)))

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
