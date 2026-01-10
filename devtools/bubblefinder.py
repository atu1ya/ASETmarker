import cv2

# Load image
img = cv2.imread("C:/Users/atuly/Documents/GitHub/OMRChecker/inputs/Reading/reading.png")
if img is None:
    raise FileNotFoundError("Could not load image")

clone = img.copy()

# Globals for rectangle drawing and zoom
drawing = False
rect_start = None
rect_end = None

zoom_img = None
zoom_origin = (0, 0)   # top left of zoomed region in original image
zoom_factor = 3.0      # how much to zoom in

def sheet_callback(event, x, y, flags, param):
    """
    Mouse callback for the main 'sheet' window.
    Supports:
      - click to print coordinates
      - click and drag to select a rectangle and open a zoomed view
    """
    global drawing, rect_start, rect_end, clone, zoom_img, zoom_origin

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        rect_start = (x, y)
        rect_end = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        rect_end = (x, y)
        temp = clone.copy()
        cv2.rectangle(temp, rect_start, rect_end, (0, 255, 0), 2)
        cv2.imshow("sheet", temp)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        rect_end = (x, y)

        x1, y1 = rect_start
        x2, y2 = rect_end
        x_min, x_max = sorted([x1, x2])
        y_min, y_max = sorted([y1, y2])

        # If it was just a click (very small rect), treat it as a simple coordinate print
        if abs(x_max - x_min) < 3 and abs(y_max - y_min) < 3:
            print(f"Clicked at: ({x}, {y})")
            cv2.imshow("sheet", clone)
            return

        w = x_max - x_min
        h = y_max - y_min
        print(f"Selected rectangle: ({x_min}, {y_min}) to ({x_max}, {y_max}) size {w}x{h}")

        roi = clone[y_min:y_max, x_min:x_max]
        if roi.size == 0:
            cv2.imshow("sheet", clone)
            return

        zoom_origin = (x_min, y_min)
        zoom_img = cv2.resize(
            roi,
            None,
            fx=zoom_factor,
            fy=zoom_factor,
            interpolation=cv2.INTER_NEAREST
        )

        cv2.namedWindow("zoom", cv2.WINDOW_NORMAL)
        cv2.imshow("zoom", zoom_img)
        cv2.setMouseCallback("zoom", zoom_callback)

        # Restore main view without the temporary rectangle
        cv2.imshow("sheet", clone)


def zoom_callback(event, x, y, flags, param):
    """
    Mouse callback for the 'zoom' window.
    Converts clicks in the zoomed image back to original coordinates.
    """
    global zoom_img, zoom_origin, zoom_factor

    if zoom_img is None:
        return

    if event == cv2.EVENT_LBUTTONDOWN:
        ox = int(x / zoom_factor) + zoom_origin[0]
        oy = int(y / zoom_factor) + zoom_origin[1]
        print(f"Zoom click at: ({x}, {y})  -> original coords: ({ox}, {oy})")


# Main window settings
cv2.namedWindow("sheet", cv2.WINDOW_NORMAL)
cv2.resizeWindow("sheet", 1200, 1600)
cv2.setMouseCallback("sheet", sheet_callback)

# Show original image once
cv2.imshow("sheet", clone)

print("Instructions:")
print(" - Click once on 'sheet' to print coordinates")
print(" - Click and drag on 'sheet' to select a rectangle and open zoom")
print(" - Click inside 'zoom' to get original image coordinates")
print(" - Press 'r' to reset zoom and close zoom window")
print(" - Press ESC to quit")

while True:
    key = cv2.waitKey(1) & 0xFF

    if key == 27:  # ESC
        break
    elif key == ord('r'):
        # Reset zoom
        zoom_img = None
        try:
            cv2.destroyWindow("zoom")
        except cv2.error:
            pass

cv2.destroyAllWindows()
