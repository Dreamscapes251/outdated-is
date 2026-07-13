import os
import logging


class Webcam:
    _log = logging.getLogger('Webcam')

    @classmethod
    def run(cls, output_dir: str) -> None:
        out = os.path.join(output_dir, 'Webcam')
        os.makedirs(out, exist_ok=True)
        output_path = os.path.join(out, 'webcam.png')

        try:
            import cv2
        except ImportError:
            cls._log.info('cv2 not available, skipping webcam capture')
            return

        cap = None
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened():
                cap.release()
                cap = cv2.VideoCapture(0)

            if not cap.isOpened():
                cls._log.info('No webcam detected')
                return

            # Warm up the camera — first few frames are often black
            for _ in range(5):
                cap.read()

            ret, frame = cap.read()
            if ret and frame is not None:
                cv2.imwrite(output_path, frame)
                cls._log.info(f'Webcam image saved to {output_path}')
            else:
                cls._log.info('Failed to capture webcam frame')
        except Exception as e:
            cls._log.debug(f'Webcam capture error: {e}')
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
