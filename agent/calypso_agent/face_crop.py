"""Isolated CPU face adapter. JPEG on stdin, one face JPEG or empty stdout.

OpenCV and PyAV bundle different FFmpeg native libraries on macOS. Keeping
OpenCV out of the LiveKit process avoids duplicate Objective-C classes.
"""

from io import BytesIO
import sys

import cv2
import numpy as np
from PIL import Image


def crop(data):
    detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if detector.empty():
        raise RuntimeError("Face detector could not be loaded")
    image = Image.open(BytesIO(data)).convert("RGB")
    image.thumbnail((640, 640))
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) != 1:
        return b""
    x, y, w, h = map(int, faces[0])
    out = BytesIO()
    image.crop((x, y, x + w, y + h)).save(out, "JPEG", quality=90)
    return out.getvalue()


if __name__ == "__main__":
    sys.stdout.buffer.write(crop(sys.stdin.buffer.read()))
