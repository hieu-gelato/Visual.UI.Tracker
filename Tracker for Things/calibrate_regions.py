import time
import pyautogui
from pynput import mouse

points = []
done = False

print("Calibration tool")
print("1) Move mouse to TOP-LEFT corner of the region and LEFT-CLICK.")
print("2) Move mouse to BOTTOM-RIGHT corner of the region and LEFT-CLICK.")
print("Press ESC by slamming mouse to a corner if needed (failsafe), or Ctrl+C.\n")

def on_click(x, y, button, pressed):
    global done
    if pressed:
        points.append((x, y))
        print(f"Captured point #{len(points)}: ({x}, {y})")
        if len(points) >= 2:
            done = True
            return False  # stop listener

with mouse.Listener(on_click=on_click) as listener:
    while not done:
        time.sleep(0.01)
    listener.stop()

(x1, y1), (x2, y2) = points[0], points[1]
x = min(x1, x2)
y = min(y1, y2)
w = abs(x2 - x1)
h = abs(y2 - y1)

print("\n✅ REGION (x, y, width, height):")
print(f"({x}, {y}, {w}, {h})")

print("\nPaste into your code like:")
print(f"REGION = ({x}, {y}, {w}, {h})")
