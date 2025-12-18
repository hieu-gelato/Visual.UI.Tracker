import pyautogui
import time

print("Move your mouse anywhere — coordinates will print every 0.1s.")
print("Press CTRL + C in the console to stop.\n")

try:
    while True:
        x, y = pyautogui.position()
        print(f"X={x}, Y={y}")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("Stopped.")

