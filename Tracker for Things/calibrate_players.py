import time
import pyautogui
import pytesseract
import cv2
import numpy as np
from pytesseract import Output
from pynput import mouse

pyautogui.FAILSAFE = False

# -----------------------------------------------------
# CONFIG
# -----------------------------------------------------

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

RIGHT_REGION = (1560, 688, 1111, 167)
LEFT_REGION  = (0, 400, 869, 1330)

POLL_INTERVAL = 0.02

# After YOU click (only after we auto-moved to a target), jump here:
NEW_BUTTON_X = 1134
NEW_BUTTON_Y = 1467

# If the mouse is landing too high/low under the name:
LEFT_CLICK_Y_OFFSET = 110

paused = False

# This prevents the click-listener from pausing you accidentally.
# We only allow click->redirect AFTER the script has moved to a target at least once.
armed_for_click = False

# Optional: turn these on/off
DEBUG_PRINT_RIGHT = True
DEBUG_PRINT_LEFT  = True


# -----------------------------------------------------
# CLICK LISTENER
# -----------------------------------------------------

def on_click(x, y, button, pressed):
    """
    Trigger ONLY on mouse button RELEASE, and ONLY if we are 'armed'
    (meaning: the script already moved the mouse to the target).
    """
    global paused, armed_for_click

    if not pressed and not paused and armed_for_click:
        time.sleep(0.01)  # let click register
        print(f"\n[CLICK] Release detected -> redirecting to NEW_BUTTON ({NEW_BUTTON_X}, {NEW_BUTTON_Y}) and pausing.\n")
        pyautogui.moveTo(NEW_BUTTON_X, NEW_BUTTON_Y, duration=0)
        paused = True
        armed_for_click = False  # disarm after use


listener = mouse.Listener(on_click=on_click)
listener.start()


# -----------------------------------------------------
# OCR HELPERS
# -----------------------------------------------------

def grab_region(region):
    x, y, w, h = region
    img = pyautogui.screenshot(region=(x, y, w, h))
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def ocr_lines(img):
    data = pytesseract.image_to_data(img, output_type=Output.DICT)
    results = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        conf = float(data["conf"][i]) if data["conf"][i] != "-1" else -1
        results.append((
            text,
            data["left"][i],
            data["top"][i],
            data["width"][i],
            data["height"][i],
            conf
        ))
    return results



# -----------------------------------------------------
# RIGHT SIDE — detect player token
# -----------------------------------------------------

import re

NAME_RE = re.compile(r"^([A-Z]\.?\s+)?[A-Z][a-z]+(\s+[A-Z][a-z]+)*$")  # allows "D. Hunter" or "DeAndre Hunter"

def extract_player_from_right():
    img = grab_region(RIGHT_REGION)
    words = ocr_lines(img)  # expects (text,x,y,w,h,conf)

    # --- group into lines by Y ---
    line_threshold = 18
    lines = []
    for text, x, y, w, h, conf in sorted(words, key=lambda t: t[2]):
        placed = False
        for line in lines:
            if abs(y - line["y"]) <= line_threshold:
                line["words"].append((text, x, y, w, h, conf))
                placed = True
                break
        if not placed:
            lines.append({"y": y, "words": [(text, x, y, w, h, conf)]})

    candidates = []
    for line in lines:
        line_words = sorted(line["words"], key=lambda t: t[1])
        line_text = " ".join(t[0] for t in line_words)

        # strip common stat separators
        name_part = line_text.split("·")[0].split("-")[0].split("|")[0].strip()

        # clean junk characters
        name_part = re.sub(r"[^A-Za-z\.\s']", "", name_part).strip()

        # compute "boldness" proxy: average word height
        avg_h = sum(t[4] for t in line_words) / max(1, len(line_words))
        avg_conf = sum(t[5] for t in line_words) / max(1, len(line_words))

        # only keep name-looking lines
        if NAME_RE.match(name_part) and len(name_part.split()) >= 2:
            candidates.append((avg_h, avg_conf, line["y"], name_part, line_text))

    if not candidates:
        print("[RIGHT OCR RAW] no name-like line found")
        return None

    # pick the biggest text (boldest). If tie, prefer higher up (smaller y).
    candidates.sort(key=lambda t: (-t[0], t[2]))
    best = candidates[0]
    print(f"[RIGHT OCR RAW] picked={best[3]!r} (avg_h={best[0]:.1f}) from line={best[4]!r}")
    return best[3]



# -----------------------------------------------------
# PARSE NAME
# -----------------------------------------------------

def parse_initial_and_last(player_name):
    if not player_name:
        return None, None

    cleaned = player_name.replace(".", " ").strip()
    tokens = cleaned.split()
    if not tokens:
        return None, None

    last_name = tokens[-1].lower()
    first_initial = tokens[0][0].lower() if len(tokens) >= 2 else None
    return first_initial, last_name


# -----------------------------------------------------
# LEFT SIDE — find matching card
# -----------------------------------------------------

def find_player_on_left(player_name):
    if not player_name:
        return None

    first_initial, last_name = parse_initial_and_last(player_name)
    if not last_name:
        return None

    img = grab_region(LEFT_REGION)
    words = ocr_lines(img)

    # Group words into lines (rows)
    lines = []
    words_sorted = sorted(words, key=lambda t: t[2])
    line_threshold = 20

    for text, x, y, w, h, conf in words_sorted:

        placed = False
        for line in lines:
            _, lx, ly, lw, lh = line[0]
            if abs(y - ly) <= line_threshold:
                line.append((text, x, y, w, h))
                placed = True
                break
        if not placed:
            lines.append([(text, x, y, w, h)])

    # Find last name in any line (optionally check initial nearby later)
    for line in lines:
        line_sorted = sorted(line, key=lambda t: t[1])

        for i, (text, x, y, w, h) in enumerate(line_sorted):
            if last_name not in text.lower():
                continue

            cx_local = x + w // 2
            cy_local = y + h // 2

            base_x, base_y, _, _ = LEFT_REGION
            cx = base_x + cx_local
            cy = base_y + cy_local + LEFT_CLICK_Y_OFFSET

            print(f"[LEFT MATCH FOUND] {player_name} -> ({cx}, {cy})")

            return cx, cy

    print(f"[LEFT MATCH FAIL] Could not find {player_name} in LEFT_REGION")

    return None


# -----------------------------------------------------
# MAIN LOOP
# -----------------------------------------------------

def main():
    global paused, armed_for_click

    print("Running — Ctrl+C to stop.")
    print("NOTE: Click-redirect+pause only activates AFTER the script auto-moves once.\n")

    last_player = None

    while True:
        try:
            if paused:
                time.sleep(0.1)
                continue

            player = extract_player_from_right()

            # Notification that right-side OCR is doing something:
            if DEBUG_PRINT_RIGHT:
                print(f"[RIGHT OCR] player={player!r}")

            # If OCR returns nothing, just keep looping
            if not player:
                time.sleep(POLL_INTERVAL)
                continue

            # Only act when it changes (prevents jitter).
            if player != last_player or last_player is None:
                pos = find_player_on_left(player)

                if DEBUG_PRINT_LEFT:
                    print(f"[LEFT MATCH] for {player!r} -> {pos}")

                if pos:
                    x, y = pos
                    print(f"[MOVE EXECUTING] moving mouse to ({x}, {y})")
                    pyautogui.moveTo(x, y, duration=0)

                    armed_for_click = True
                    print(f"[MOVE] moved to ({x}, {y}) and ARMED for click\n")

                    # ✅ Only lock in last_player AFTER success
                    last_player = player
                else:
                    print("[NO MOVE] Left-side match returned None")
                    armed_for_click = False

                    # ✅ Do NOT set last_player here, so it keeps retrying

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopped by user.")
            break


if __name__ == "__main__":
    main()
