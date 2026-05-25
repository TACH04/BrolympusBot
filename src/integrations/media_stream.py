import cv2
import threading
import logging
import time
import numpy as np

logger = logging.getLogger(__name__)

class StreamCapture:
    """
    Headless RTMP stream capture module.
    Maintains a single background thread that constantly reads frames from the stream
    to drain the buffer, ensuring that get_latest_frame() always returns the most recent live frame.
    """
    def __init__(self, url: str):
        self.url = url
        self._latest_frame = None
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        # We don't open the capture immediately; we do it in the thread to handle reconnects
        
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info(f"StreamCapture started for {self.url}")

    def _read_loop(self):
        cap = None
        retry_delay = 1
        
        while self._running:
            try:
                if cap is None or not cap.isOpened():
                    logger.debug(f"Attempting to open stream: {self.url}")
                    # FFMPEG backend helps with RTMP/SRT stability
                    cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
                    if not cap.isOpened():
                        logger.debug(f"Failed to open stream, retrying in {retry_delay}s...")
                        time.sleep(retry_delay)
                        retry_delay = min(retry_delay * 2, 5)
                        continue
                    else:
                        logger.info(f"Successfully connected to stream: {self.url}")
                        retry_delay = 1 # reset on success
                
                # Grab frame (drains buffer)
                ret, frame = cap.read()
                if ret and frame is not None:
                    with self._lock:
                        self._latest_frame = frame
                else:
                    logger.warning("Stream ended or error reading frame, reconnecting...")
                    cap.release()
                    cap = None
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Error in stream capture loop: {e}")
                if cap:
                    cap.release()
                    cap = None
                time.sleep(1)
                
        if cap:
            cap.release()
            
    def get_latest_frame(self) -> np.ndarray:
        """Returns the most recent frame, or None if stream isn't connected/no frames yet."""
        with self._lock:
            if self._latest_frame is None:
                return None
            return self._latest_frame.copy()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        logger.info(f"StreamCapture stopped for {self.url}")

def resize_for_vlm(frame: np.ndarray, width: int = 640) -> bytes:
    """Resizes the frame maintaining aspect ratio and encodes to JPEG bytes."""
    if frame is None:
        return b""
    
    h, w = frame.shape[:2]
    # Calculate new height to maintain aspect ratio
    height = int((width / w) * h)
    
    resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    # Encode as JPEG (quality 80 is usually fine for VLM)
    ret, buf = cv2.imencode('.jpg', resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    
    if ret:
        return buf.tobytes()
    return b""
