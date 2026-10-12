import cv2
import numpy as np
class RedImg:

    @staticmethod
    def read_image_from_upload(contents: bytes):
        img_array = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img