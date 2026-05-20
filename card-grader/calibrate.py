import cv2
import numpy as np
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Let's test with the front image first
img_path = os.path.join(SCRIPT_DIR, "cubone-back.jpg")
image = cv2.imread(img_path)

if image is None:
    print("Could not load image. Check the path.")
    exit()

# Your phone photos are likely huge (e.g., 4000x3000 pixels).
# We need to scale it down so the popup window actually fits on your computer screen.
scale = 800 / image.shape[0]
resized_img = cv2.resize(image, (int(image.shape[1] * scale), 800))

# Convert to grayscale and blur slightly
gray = cv2.cvtColor(resized_img, cv2.COLOR_BGR2GRAY)
blurred = cv2.GaussianBlur(gray, (7, 7), 0)

# This function runs every time you move the slider


def on_trackbar(val):
    # Apply the threshold value from the slider
    _, thresh = cv2.threshold(blurred, val, 255, cv2.THRESH_BINARY)
    cv2.imshow("Threshold Calibration", thresh)


# Create the window and the slider
cv2.namedWindow("Threshold Calibration")
# We start the slider at 40 (our old guess), with a max of 255
cv2.createTrackbar("Threshold Value",
                   "Threshold Calibration", 40, 255, on_trackbar)

# Force the window to show up initially
on_trackbar(40)

print("Adjust the slider until the card is solid WHITE and the mat is solid BLACK.")
print("Take note of the number on the slider when it looks perfect!")
print("Press 'q' or 'ESC' on your keyboard to close the window.")

# Keep the window open until you press 'q' or escape
while True:
    key = cv2.waitKey(1) & 0xFF
    if key == 27 or key == ord('q'):
        break

cv2.destroyAllWindows()
