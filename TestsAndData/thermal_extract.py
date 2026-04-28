"""
Thermal Image Temperature Extraction Tool  (White-Hot Grayscale)
================================================================
Opens a grayscale white-hot thermal image and lets you:
  1. Draw a rectangle over the region of interest (ROI).
  2. Enter min / max temperature values.
  3. Export a CSV where each cell holds the estimated temperature.

Mapping: pixel brightness 0 (black) = t_min, 255 (white) = t_max.

Dependencies:  pip install opencv-python numpy
"""

import cv2
import numpy as np
import csv
import sys
import os

# ── state holders for mouse callbacks ────────────────────────────────────────

drawing = False
ix, iy = -1, -1
rect_coords = []          # [(x1,y1), (x2,y2)]


def mouse_callback(event, x, y, flags, param):
    global drawing, ix, iy, rect_coords

    img_display = param["img_display"]
    img_clean = param["img_clean"]

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        tmp = img_clean.copy()
        cv2.rectangle(tmp, (ix, iy), (x, y), (0, 255, 0), 2)
        img_display[:] = tmp
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        rect_coords.clear()
        rect_coords.append((ix, iy))
        rect_coords.append((x, y))
        tmp = img_clean.copy()
        cv2.rectangle(tmp, (ix, iy), (x, y), (0, 255, 0), 2)
        img_display[:] = tmp


# ── helpers ──────────────────────────────────────────────────────────────────

def map_roi_to_temperatures(gray, roi, t_min, t_max):
    """Map grayscale ROI pixels to temperatures (white-hot: 255=t_max, 0=t_min)."""
    x1, y1 = roi[0]
    x2, y2 = roi[1]
    r_top, r_bot = min(y1, y2), max(y1, y2)
    c_left, c_right = min(x1, x2), max(x1, x2)

    roi_gray = gray[r_top:r_bot, c_left:c_right].astype(np.float64)
    temps = t_min + (roi_gray / 255.0) * (t_max - t_min)
    return np.round(temps, 1)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        # default to the image in the same folder
        script_dir = os.path.dirname(os.path.abspath(__file__))

        candidates = [f for f in os.listdir(script_dir)
                       if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff'))]

        if not candidates:
            print("Usage: python thermal_extract.py <image_path>")
            sys.exit(1)
        img_path = os.path.join(script_dir, candidates[0])
        print(f"No image argument given — using: {img_path}")
    else:
        img_path = sys.argv[1]
    img_path = os.path.join(script_dir, IMAGE)
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(f"Error: cannot open image '{img_path}'")
        sys.exit(1)

    # Convert to 3-channel gray so we can draw colored overlays
    img_bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    win = "Thermal Extraction Tool"
    img_display = img_bgr.copy()
    param = {"img_display": img_display, "img_clean": img_bgr.copy()}

    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win, min(img.shape[1], 1200), min(img.shape[0], 900))
    cv2.setMouseCallback(win, mouse_callback, param)

    # ── Step 1: draw ROI rectangle ───────────────────────────────────────
    print("\n=== STEP 1 ===")
    print("Draw a RECTANGLE around the region of interest.")
    print("Click-drag to draw. Press ENTER when satisfied, or 'r' to redraw.\n")

    while True:
        cv2.imshow(win, img_display)
        key = cv2.waitKey(20) & 0xFF
        if key == 13:  # Enter
            if len(rect_coords) == 2:
                break
            else:
                print("Please draw a rectangle first.")
        elif key == ord('r'):
            rect_coords.clear()
            img_display[:] = img_bgr.copy()
        elif key == 27:  # Esc
            cv2.destroyAllWindows()
            sys.exit(0)

    print(f"ROI rectangle: {rect_coords[0]} -> {rect_coords[1]}")
    cv2.destroyAllWindows()

    # ── Step 2: user inputs ──────────────────────────────────────────────
    print("\n=== STEP 2 ===")
    t_min_str = input("Enter the MIN temperature value (black = cold): ")
    t_max_str = input("Enter the MAX temperature value (white = hot):  ")
    t_min = float(t_min_str)
    t_max = float(t_max_str)

    # ── Step 3: map ROI to temperatures ─────────────────────────────────
    print("\nProcessing …")
    temps = map_roi_to_temperatures(img, rect_coords, t_min, t_max)

    # ── Step 4: export CSV ───────────────────────────────────────────────
    out_csv = os.path.splitext(img_path)[0] + "_temperatures.csv"
    with open(out_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([f"# Image: {os.path.basename(img_path)}"])
        writer.writerow([f"# ROI: {rect_coords[0]} -> {rect_coords[1]}"])
        writer.writerow([f"# Temp range: {t_min} - {t_max}"])
        writer.writerow([f"# Scale: white-hot grayscale"])
        writer.writerow([])
        for row in temps:
            writer.writerow(row.tolist())

    print(f"\nDone!  CSV saved to: {out_csv}")
    print(f"  Grid size : {temps.shape[1]} x {temps.shape[0]} (cols x rows)")
    print(f"  Temp range: {np.nanmin(temps):.2f} – {np.nanmax(temps):.2f}")


if __name__ == "__main__":
    IMAGE = "DC_0042.jpg"
    main()
