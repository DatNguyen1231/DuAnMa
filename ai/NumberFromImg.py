import os

# Phải set trước khi import PaddleOCR
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_enable_pir_in_executor", "0")
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")

import re
import cv2
import numpy as np
from paddleocr import PaddleOCR


# Load model 1 lần duy nhất
ocr = PaddleOCR(
    lang="en",
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False
)


class NumberFromImg:

    @staticmethod
    def preprocess_image(img, scale=2):
        """
        Làm ảnh dễ đọc hơn:
        - Phóng to ảnh
        - Chuyển xám
        - Tăng nét nhẹ
        """
        if img is None:
            raise ValueError("Ảnh truyền vào bị None")

        # Phóng to ảnh để OCR dễ đọc số nhỏ
        if scale and scale > 1:
            img = cv2.resize(
                img,
                None,
                fx=scale,
                fy=scale,
                interpolation=cv2.INTER_CUBIC
            )

        # Tăng nét nhẹ
        kernel = np.array([
            [0, -1, 0],
            [-1, 5, -1],
            [0, -1, 0]
        ])

        img = cv2.filter2D(img, -1, kernel)

        return img

    @staticmethod
    def get_first_available_box_list(res):
        """
        PaddleOCR mỗi version có thể trả box khác nhau:
        - rec_boxes
        - rec_polys
        - dt_polys

        Không dùng `or` trực tiếp với numpy array vì dễ lỗi.
        """
        for key in ["rec_boxes", "rec_polys", "dt_polys"]:
            boxes = res.get(key)

            if boxes is None:
                continue

            try:
                if len(boxes) > 0:
                    return boxes
            except Exception:
                continue

        return []

    @staticmethod
    def get_box_center(box):
        """
        Lấy tâm box OCR.
        Hỗ trợ 2 dạng:
        1. [x1, y1, x2, y2]
        2. [[x,y], [x,y], [x,y], [x,y]]
        """
        if box is None:
            return 0, 0

        # Nếu là numpy array thì đổi về list
        if hasattr(box, "tolist"):
            box = box.tolist()

        # Dạng [x1, y1, x2, y2]
        if (
            isinstance(box, list)
            and len(box) == 4
            and isinstance(box[0], (int, float))
        ):
            x1, y1, x2, y2 = box
            x = (x1 + x2) / 2
            y = (y1 + y2) / 2
            return x, y

        # Dạng [[x,y], [x,y], [x,y], [x,y]]
        try:
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]

            x = sum(xs) / len(xs)
            y = sum(ys) / len(ys)

            return x, y
        except Exception:
            return 0, 0

    @staticmethod
    def group_sort_top_to_bottom(items, y_threshold=12):
        """
        Sort theo kiểu đọc bảng:
        - Gom các item gần cùng tọa độ y thành 1 hàng
        - Trong mỗi hàng sort từ trái sang phải
        - Các hàng sort từ trên xuống dưới
        """
        if not items:
            return []

        # Sort sơ bộ theo y
        items = sorted(items, key=lambda item: item["y"])

        rows = []

        for item in items:
            added = False

            for row in rows:
                row_y = row["avg_y"]

                if abs(item["y"] - row_y) <= y_threshold:
                    row["items"].append(item)

                    # cập nhật lại y trung bình của hàng
                    row["avg_y"] = sum(i["y"] for i in row["items"]) / len(row["items"])

                    added = True
                    break

            if not added:
                rows.append({
                    "avg_y": item["y"],
                    "items": [item]
                })

        # Sort hàng từ trên xuống
        rows.sort(key=lambda row: row["avg_y"])

        sorted_items = []

        for row in rows:
            # Trong cùng hàng sort trái sang phải
            row["items"].sort(key=lambda item: item["x"])
            sorted_items.extend(row["items"])

        return sorted_items

    @staticmethod
    def remove_duplicate_items(items):
        """
        Bỏ trùng nếu OCR trả lặp cùng số gần cùng vị trí.
        """
        result = []
        seen = set()

        for item in items:
            key = (
                item["number"],
                round(item["x"] / 10),
                round(item["y"] / 10)
            )

            if key in seen:
                continue

            seen.add(key)
            result.append(item)

        return result

    @staticmethod
    def detect_numbers_from_image(
        img,
        min_confidence=0.0,
        min_length=1,
        use_preprocess=True,
        return_position=False
    ):
        """
        Nhận diện số từ ảnh.

        Tham số:
        - img: ảnh OpenCV
        - min_confidence: lọc kết quả confidence thấp, ví dụ 0.7
        - min_length: lọc số quá ngắn, ví dụ 5 nếu chỉ muốn số >= 5 chữ số
        - use_preprocess: True để phóng to + tăng nét
        - return_position: True để trả thêm x/y debug
        """

        if img is None:
            raise ValueError("Ảnh truyền vào bị None")

        if use_preprocess:
            img = NumberFromImg.preprocess_image(img, scale=2)

        result = ocr.predict(img)

        items = []

        for page in result:
            data = page.json if hasattr(page, "json") else page

            if not isinstance(data, dict):
                continue

            res = data.get("res", data)

            texts = res.get("rec_texts", [])
            scores = res.get("rec_scores", [])
            boxes = NumberFromImg.get_first_available_box_list(res)

            for i, (text, score) in enumerate(zip(texts, scores)):
                number = re.sub(r"\D", "", str(text))

                if not number:
                    continue

                score = float(score)

                if score < min_confidence:
                    continue

                if len(number) < min_length:
                    continue

                x = 0
                y = 0

                if i < len(boxes):
                    x, y = NumberFromImg.get_box_center(boxes[i])

                items.append({
                    "number": number,
                    "confidence": round(score, 3),
                    "x": round(float(x), 2),
                    "y": round(float(y), 2)
                })

        # Bỏ trùng
        items = NumberFromImg.remove_duplicate_items(items)

        # Sort theo hàng: trên xuống, cùng hàng trái sang phải
        items = NumberFromImg.group_sort_top_to_bottom(items, y_threshold=18)

        arr = []

        for item in items:
            row = {
                "number": item["number"],
                "confidence": item["confidence"]
            }

            if return_position:
                row["x"] = item["x"]
                row["y"] = item["y"]

            arr.append(row)

        return arr