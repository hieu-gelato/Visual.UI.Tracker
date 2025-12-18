import pyautogui
import cv2
import numpy as np

# TRY YOUR RIGHT REGION HERE
REGION = (7622, 1534, 1116, 442)

img = pyautogui.screenshot(region=REGION)
img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

cv2.imshow("REGION TEST", img)
cv2.waitKey(0)
cv2.destroyAllWindows()
