#!/usr/bin/env python
# scripts/measure_template.py
import cv2, json, sys
from pathlib import Path
from datetime import datetime

class TemplateMeasurer:
    def __init__(self, image_path: str):
        self.image_path = image_path
        self.original_image = cv2.imread(image_path)
        if self.original_image is None:
            raise FileNotFoundError(f"Could not load image: {image_path}")
        self.image = self.original_image.copy()
        self.points = []
        self.measurements = {
            "image_path": image_path,
            "image_dimensions": {"width": self.image.shape[1], "height": self.image.shape[0]},
            "recorded_points": [],
            "calculated_values": {}
        }
        self.window_name = "Template Measurer"

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.points.append((x, y))
            idx = len(self.points)
            self.measurements["recorded_points"].append({"index": idx, "x": x, "y": y})
            cv2.circle(self.image, (x, y), 8, (0, 0, 255), -1)
            cv2.putText(self.image, f"{idx}", (x+10, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
            if len(self.points) >= 2:
                p1, p2 = self.points[-2], self.points[-1]
                print(f"Point {idx}: ({x},{y}), Δ from prev: dx={p2[0]-p1[0]}, dy={p2[1]-p1[1]}")
            self._calc_values()

    def _calc_values(self):
        if len(self.points) >= 2:
            p1, p2 = self.points[0], self.points[1]
            self.measurements["calculated_values"]["bubblesGap"] = p2[0] - p1[0]
        if len(self.points) >= 3:
            p1, p3 = self.points[0], self.points[2]
            self.measurements["calculated_values"]["labelsGap"] = p3[1] - p1[1]
        if len(self.points) >= 4:
            p1, p4 = self.points[0], self.points[3]
            self.measurements["calculated_values"]["bubbleDimensions"] = [p4[0]-p1[0], p4[1]-p1[1]]
            self.measurements["calculated_values"]["origin"] = [p1[0], p1[1]]

    def run(self):
        print("Click in order:\n 1) TOP-LEFT of Q1-A\n 2) TOP-LEFT of Q1-B\n 3) TOP-LEFT of Q2-A (next row)\n 4) BOTTOM-RIGHT of Q1-A")
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.window_name, self.mouse_callback)
        while True:
            cv2.imshow(self.window_name, self.image)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'): break
            if key == ord('s'): self._save(); break
            if key == ord('r'): self.image = self.original_image.copy(); self.points = []; self.measurements["recorded_points"]=[]; self.measurements["calculated_values"]={}
        cv2.destroyAllWindows()

    def _save(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = f"measurements_{Path(self.image_path).stem}_{ts}.json"
        with open(out, 'w') as f:
            json.dump(self.measurements, f, indent=2)
        print("Saved:", out); print("Values:", self.measurements["calculated_values"])

if __name__ == "__main__":
    if len(sys.argv) < 2: print("Usage: python scripts/measure_template.py <image_path>"); sys.exit(1)
    TemplateMeasurer(sys.argv[1]).run()