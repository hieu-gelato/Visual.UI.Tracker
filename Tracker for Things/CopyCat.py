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

import re
from difflib import SequenceMatcher

PLAYERS_LIST = [
    # Enter player names as stated here for example "Hieu Nguyen"
]



def norm(s: str) -> str:
    # keep letters/spaces only, lowercase, remove accents-ish punctuation impact
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z\s]", " ", s)).strip().lower()

PLAYER_LIST_NORM = [(p, norm(p)) for p in PLAYER_LIST]

def best_player_match(text: str, min_score: float = 0.72):
    t = norm(text)
    best_score = 0.0
    best_name = None
    for original, pn in PLAYER_LIST_NORM:
        score = SequenceMatcher(None, t, pn).ratio()
        if score > best_score:
            best_score = score
            best_name = original
    return best_name if best_score >= min_score else None, best_score


pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

RIGHT_REGION = (1559, 778, 1113, 304)
LEFT_REGION  = (81, 368, 806, 1260)

POLL_INTERVAL = 0.02

# After YOU click (only after we auto-moved to a target), jump here:
NEW_BUTTON_X = 1054
NEW_BUTTON_Y = 1315

# If the mouse is landing too high/low under the name:
LEFT_CLICK_Y_OFFSET = 85

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
        results.append((
            text,
            data["left"][i],
            data["top"][i],
            data["width"][i],
            data["height"][i]
        ))
    return results


# -----------------------------------------------------
# RIGHT SIDE — detect player token
# -----------------------------------------------------

def extract_player_from_right():
    img = grab_region(RIGHT_REGION)
    words = ocr_lines(img)

    # Handle both 5-field and 6-field outputs
    def unpack(w):
        if len(w) == 6:
            return w
        text, x, y, ww, hh = w
        return text, x, y, ww, hh, -1

    words6 = [unpack(w) for w in words]

    # Group words into lines by Y
    line_threshold = 18
    lines = []
    for text, x, y, w, h, conf in sorted(words6, key=lambda t: t[2]):
        placed = False
        for line in lines:
            if abs(y - line["y"]) <= line_threshold:
                line["words"].append((text, x, y, w, h, conf))
                placed = True
                break
        if not placed:
            lines.append({"y": y, "words": [(text, x, y, w, h, conf)]})

    best = (-1.0, 10**9, None, None)  # (score, y, matched_name, name_part)

    for line in sorted(lines, key=lambda L: L["y"]):
        line_words = sorted(line["words"], key=lambda t: t[1])  # by X
        line_text = " ".join(t[0] for t in line_words)

        # ✅ ONLY take the name portion (before stats)
        name_part = line_text.split("·")[0].split("-")[0].strip()

        matched_name, score = best_player_match(name_part, min_score=0.72)
        if matched_name:
            # ✅ prefer higher score; if tied, prefer TOP line (smaller y)
            if (score > best[0]) or (abs(score - best[0]) < 0.02 and line["y"] < best[1]):
                best = (score, line["y"], matched_name, name_part)

    if best[2]:
        print(f"[RIGHT OCR RAW] name_part={best[3]!r} -> matched={best[2]!r} score={best[0]:.2f}")
        return best[2]

    print("[RIGHT OCR RAW] no slate match found")
    return None


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

    for text, x, y, w, h in words_sorted:
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
