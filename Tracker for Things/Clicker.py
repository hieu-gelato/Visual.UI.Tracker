# click_redirect.py

import time
import pyautogui
from pynput import mouse

pyautogui.FAILSAFE = False

# After YOU click on the original target, mouse will auto-move here
NEW_BUTTON_X = 1060  # change to your actual X
NEW_BUTTON_Y = 1390  # change to your actual Y


def on_click(x, y, button, pressed):

    if not pressed:
        # tiny delay to let the click fully process
        time.sleep(0.01)

        # Now jump to the secondary button position
        pyautogui.moveTo(NEW_BUTTON_X, NEW_BUTTON_Y, duration=0)
        print(f"\n>>> Redirected after click to ({NEW_BUTTON_X}, {NEW_BUTTON_Y}). Exiting.\n")

        # Returning False stops the listener (and ends the script)
        return False


def main():
    print("Click redirect script running. Click anywhere to trigger redirect.")
    with mouse.Listener(on_click=on_click) as listener:
        listener.join()
    print("Click redirect script finished.")


if __name__ == "__main__":
    main()
