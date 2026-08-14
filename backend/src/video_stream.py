"""
Threaded Video Stream Module for Burn-Ex.
Decouples frame grabbing from pipeline execution to prevent blocking on camera sensor.
"""

import threading
import time
from typing import Optional, Union
import cv2
import numpy as np


class VideoStream:
    """
    Asynchronous camera stream reader running in a separate background daemon thread.
    """

    def __init__(
        self,
        src: Union[int, str] = 1,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> None:
        self.stream = cv2.VideoCapture(src)
        if isinstance(src, int) and src != 0 and not self.stream.isOpened():
            print(f"[VideoStream] Warning: Camera index {src} failed to open. Falling back to default index 0.")
            self.stream = cv2.VideoCapture(0)
        if width is not None:
            self.stream.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        if height is not None:
            self.stream.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        self.grabbed, self.frame = self.stream.read()
        self.stopped = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self.update, args=(), daemon=True)

    def start(self) -> "VideoStream":
        """Start the background thread to read frames."""
        self.thread.start()
        return self

    def update(self) -> None:
        """Background loop reading frames continuously."""
        while not self.stopped:
            if not self.stream.isOpened():
                time.sleep(0.01)
                continue
            grabbed, frame = self.stream.read()
            with self.lock:
                self.grabbed = grabbed
                if grabbed:
                    self.frame = frame
                else:
                    self.frame = None
            time.sleep(0.002)

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        """Return the most recently grabbed frame."""
        with self.lock:
            if self.frame is not None:
                return self.grabbed, self.frame.copy()
            return self.grabbed, None

    def stop(self) -> None:
        """Stop the background thread and release resources."""
        self.stopped = True
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        self.stream.release()

    def release(self) -> None:
        """Alias for stop() to provide drop-in compatibility with cv2.VideoCapture."""
        self.stop()

    def isOpened(self) -> bool:
        """Check if camera stream is successfully initialized."""
        return self.stream.isOpened()

    def set(self, propId: int, value: float) -> bool:
        """Set a property in the cv2 VideoCapture stream."""
        return self.stream.set(propId, value)

    def get(self, propId: int) -> float:
        """Get a property from the cv2 VideoCapture stream."""
        return self.stream.get(propId)
