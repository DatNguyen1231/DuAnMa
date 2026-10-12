from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from paddleocr import PaddleOCR
import cv2
import numpy as np
from pathlib import Path
import re
import traceback

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ocr = PaddleOCR(lang="en")


def read_image_from_upload(contents: bytes):
    img_array = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is None:
        raise ValueError("Không đọc được ảnh. File upload có thể không phải ảnh hợp lệ.")

    return img


def detect_numbers_from_image(img):
    result = ocr.predict(img)

    arr = []

    for page in result:
        data = page.json if hasattr(page, "json") else page

        if not isinstance(data, dict):
            continue

        res = data.get("res", data)

        texts = res.get("rec_texts", [])
        scores = res.get("rec_scores", [])

        for text, score in zip(texts, scores):
            number = re.sub(r"\D", "", str(text))

            if number:
                arr.append({
                    "number": number,
                    "confidence": round(float(score), 3)
                })

    return arr


@app.get("/")
def home():
    return {
        "message": "OCR API đang chạy"
    }


@app.get("/ui")
def ui():
    return FileResponse(BASE_DIR / "index.html")


@app.post("/ocr")
async def ocr_image(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        if not contents:
            raise ValueError("File upload rỗng.")

        img = read_image_from_upload(contents)

        numbers = detect_numbers_from_image(img)

        return {
            "success": True,
            "data": numbers
        }

    except Exception as e:
        print("===== OCR ERROR =====")
        traceback.print_exc()
        print("=====================")

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
