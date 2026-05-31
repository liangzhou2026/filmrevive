import asyncio
import os
from io import BytesIO

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, ImageOps, UnidentifiedImageError


app = FastAPI(title="FilmRevive API", version="0.1.0")

DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://filmrevive.com",
    "https://www.filmrevive.com",
]

cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", ",".join(DEFAULT_CORS_ORIGINS)).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
MAX_UPLOAD_BYTES = 120 * 1024 * 1024
PROCESSING_TIMEOUT_SECONDS = 90


def decode_upload(file_bytes: bytes) -> np.ndarray:
    try:
        pil_image = Image.open(BytesIO(file_bytes))
        pil_image = ImageOps.exif_transpose(pil_image).convert("RGB")
    except UnidentifiedImageError:
        raise HTTPException(status_code=400, detail="无法读取图片，请上传 JPG、PNG、WEBP、BMP 或 TIFF。")

    image_rgb = np.array(pil_image)
    return cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)


def invert_negative(image_bgr: np.ndarray) -> np.ndarray:
    return 255 - image_bgr


def auto_levels(image_bgr: np.ndarray, shadow_percent: float = 0.5, highlight_percent: float = 99.5) -> np.ndarray:
    result = np.empty_like(image_bgr)

    for channel_index in range(3):
        channel = image_bgr[:, :, channel_index]
        low = np.percentile(channel, shadow_percent)
        high = np.percentile(channel, highlight_percent)

        if high <= low:
            result[:, :, channel_index] = channel
            continue

        stretched = (channel.astype(np.float32) - low) * (255.0 / (high - low))
        result[:, :, channel_index] = np.clip(stretched, 0, 255).astype(np.uint8)

    return result


def gray_world_white_balance(image_bgr: np.ndarray) -> np.ndarray:
    image = image_bgr.astype(np.float32)
    channel_means = image.reshape(-1, 3).mean(axis=0)
    gray_mean = channel_means.mean()
    gains = gray_mean / np.maximum(channel_means, 1.0)
    balanced = image * gains
    return np.clip(balanced, 0, 255).astype(np.uint8)


def denoise_image(image_bgr: np.ndarray) -> np.ndarray:
    denoised = cv2.fastNlMeansDenoisingColored(image_bgr, None, 3, 3, 7, 21)
    return cv2.addWeighted(image_bgr, 0.35, denoised, 0.65, 0)


def order_points(points: np.ndarray) -> np.ndarray:
    rect = np.zeros((4, 2), dtype=np.float32)
    sums = points.sum(axis=1)
    diffs = np.diff(points, axis=1)
    rect[0] = points[np.argmin(sums)]
    rect[2] = points[np.argmax(sums)]
    rect[1] = points[np.argmin(diffs)]
    rect[3] = points[np.argmax(diffs)]
    return rect


def find_film_quad(image_bgr: np.ndarray) -> np.ndarray | None:
    height, width = image_bgr.shape[:2]
    if width < 80 or height < 80:
        return None

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120)
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 17))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, close_kernel)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = width * height
    candidates: list[tuple[float, np.ndarray]] = []

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < image_area * 0.25 or area > image_area * 0.98:
            continue

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.025 * perimeter, True)
        if len(approx) == 4:
            quad = approx.reshape(4, 2).astype(np.float32)
        else:
            rect = cv2.minAreaRect(contour)
            quad = cv2.boxPoints(rect).astype(np.float32)

        x, y, w, h = cv2.boundingRect(quad.astype(np.int32))
        if w < width * 0.35 or h < height * 0.35:
            continue
        candidates.append((area, order_points(quad)))

    if candidates:
        return max(candidates, key=lambda item: item[0])[1]

    threshold = max(8, int(float(np.std(gray)) * 0.16))
    rows = np.where(np.std(gray, axis=1) > threshold)[0]
    cols = np.where(np.std(gray, axis=0) > threshold)[0]
    if rows.size == 0 or cols.size == 0:
        return None

    y, y2 = int(rows[0]), int(rows[-1])
    x, x2 = int(cols[0]), int(cols[-1])
    if (x2 - x) * (y2 - y) < image_area * 0.25:
        return None

    margin = max(2, int(min(width, height) * 0.006))
    return np.array(
        [
            [x + margin, y + margin],
            [x2 - margin, y + margin],
            [x2 - margin, y2 - margin],
            [x + margin, y2 - margin],
        ],
        dtype=np.float32,
    )


def crop_and_correct_perspective(image_bgr: np.ndarray) -> np.ndarray:
    quad = find_film_quad(image_bgr)
    if quad is None:
        return image_bgr

    width_a = np.linalg.norm(quad[2] - quad[3])
    width_b = np.linalg.norm(quad[1] - quad[0])
    height_a = np.linalg.norm(quad[1] - quad[2])
    height_b = np.linalg.norm(quad[0] - quad[3])
    max_width = int(max(width_a, width_b))
    max_height = int(max(height_a, height_b))

    image_area = image_bgr.shape[0] * image_bgr.shape[1]
    if max_width * max_height > image_area * 0.98 or max_width < 40 or max_height < 40:
        return image_bgr

    destination = np.array(
        [[0, 0], [max_width - 1, 0], [max_width - 1, max_height - 1], [0, max_height - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(quad, destination)
    return cv2.warpPerspective(image_bgr, matrix, (max_width, max_height), flags=cv2.INTER_CUBIC)


def estimate_orange_mask_color(negative_bgr: np.ndarray) -> np.ndarray:
    height, width = negative_bgr.shape[:2]
    border = max(6, int(min(width, height) * 0.08))
    border_pixels = np.concatenate(
        [
            negative_bgr[:border, :, :].reshape(-1, 3),
            negative_bgr[-border:, :, :].reshape(-1, 3),
            negative_bgr[:, :border, :].reshape(-1, 3),
            negative_bgr[:, -border:, :].reshape(-1, 3),
        ],
        axis=0,
    )

    hsv = cv2.cvtColor(negative_bgr, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    orange_mask = ((hue >= 5) & (hue <= 35) & (saturation > 35) & (value > 80)).reshape(-1)
    orange_pixels = negative_bgr.reshape(-1, 3)[orange_mask]

    samples = border_pixels
    if orange_pixels.size > 300:
        samples = np.concatenate([border_pixels, orange_pixels], axis=0)

    mask_color = np.percentile(samples.astype(np.float32), 80, axis=0)
    return np.maximum(mask_color, 8.0)


def compensate_orange_mask_rgb(negative_bgr: np.ndarray) -> np.ndarray:
    image = negative_bgr.astype(np.float32)
    mask_color = estimate_orange_mask_color(negative_bgr)
    target = float(np.mean(mask_color))
    compensated = image / mask_color.reshape(1, 1, 3) * target
    return np.clip(compensated, 0, 255).astype(np.uint8)


def apply_black_highlight_points(image_bgr: np.ndarray) -> np.ndarray:
    return auto_levels(image_bgr, 0.2, 99.8)


def correct_gray_point(image_bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    luminance = lab[:, :, 0]
    chroma = np.abs(lab[:, :, 1].astype(np.int16) - 128) + np.abs(lab[:, :, 2].astype(np.int16) - 128)
    neutral_mask = (luminance > 45) & (luminance < 225) & (chroma < 22)

    image = image_bgr.astype(np.float32)
    if np.count_nonzero(neutral_mask) > 200:
        means = image[neutral_mask].mean(axis=0)
        target = float(np.mean(means))
        gains = target / np.maximum(means, 1.0)
        image *= gains.reshape(1, 1, 3)

    return np.clip(image, 0, 255).astype(np.uint8)


def correct_skin_tone(image_bgr: np.ndarray) -> np.ndarray:
    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
    y = ycrcb[:, :, 0]
    cr = ycrcb[:, :, 1]
    cb = ycrcb[:, :, 2]
    skin_mask = (y > 50) & (y < 235) & (cr > 132) & (cr < 178) & (cb > 85) & (cb < 135)

    if np.count_nonzero(skin_mask) < 300:
        return image_bgr

    image = image_bgr.astype(np.float32)
    skin_mean = image[skin_mask].mean(axis=0)
    red_blue_balance = skin_mean[2] - skin_mean[0]
    green_balance = skin_mean[1] - ((skin_mean[0] + skin_mean[2]) * 0.5)
    image[:, :, 2] += np.clip(18.0 - red_blue_balance, -6.0, 6.0) * 0.25
    image[:, :, 1] -= np.clip(green_balance, -8.0, 8.0) * 0.25
    return np.clip(image, 0, 255).astype(np.uint8)


def lift_underexposed_frame(image_bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB)
    l_channel = lab[:, :, 0].astype(np.float32)
    mid_luma = float(np.percentile(l_channel, 45))

    if mid_luma >= 92.0:
        return image_bgr

    lift = min(18.0, (92.0 - mid_luma) * 0.42)
    shadow_mask = np.clip((145.0 - l_channel) / 145.0, 0.0, 1.0)
    lab_float = lab.astype(np.float32)
    lab_float[:, :, 0] += shadow_mask * lift
    return cv2.cvtColor(np.clip(lab_float, 0, 255).astype(np.uint8), cv2.COLOR_LAB2BGR)


def natural_portra_skin(image_bgr: np.ndarray) -> np.ndarray:
    ycrcb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2YCrCb)
    y = ycrcb[:, :, 0].astype(np.float32)
    cr = ycrcb[:, :, 1]
    cb = ycrcb[:, :, 2]
    skin_mask = (y > 35) & (y < 240) & (cr > 130) & (cr < 182) & (cb > 78) & (cb < 142)

    if np.count_nonzero(skin_mask) < 250:
        return image_bgr

    mask = skin_mask.astype(np.uint8) * 255
    mask = cv2.medianBlur(mask, 5)
    mask = cv2.GaussianBlur(mask, (0, 0), 5).astype(np.float32) / 255.0

    image = image_bgr.astype(np.float32)
    skin_pixels = image[skin_mask]
    skin_luma = y[skin_mask]
    mean_bgr = skin_pixels.mean(axis=0)
    mean_luma = float(np.mean(skin_luma))

    # Portra 400-inspired portrait bias: soft contrast, warm but not orange,
    # gentle green reduction, and shadow lift only when skin is underexposed.
    target_bgr = np.array([126.0, 154.0, 188.0], dtype=np.float32)
    chroma_shift = np.clip((target_bgr - mean_bgr) * 0.10, -5.0, 5.0)
    image += mask[:, :, None] * chroma_shift.reshape(1, 1, 3)

    if mean_luma < 136.0:
        lift = min(34.0, (136.0 - mean_luma) * 0.48)
        image += mask[:, :, None] * lift

    if mean_luma < 105.0:
        shadow_boost = np.clip((120.0 - y) / 120.0, 0.0, 1.0)
        image += (mask * shadow_boost)[:, :, None] * 12.0

    # Keep skin from becoming too crunchy after auto levels.
    softened = cv2.bilateralFilter(np.clip(image, 0, 255).astype(np.uint8), 5, 24, 24).astype(np.float32)
    image = image * (1.0 - mask[:, :, None] * 0.18) + softened * (mask[:, :, None] * 0.18)

    return np.clip(image, 0, 255).astype(np.uint8)


def airy_natural_portrait_grade(image_bgr: np.ndarray) -> np.ndarray:
    image = image_bgr.astype(np.float32) / 255.0

    # Soft, airy tonality: lifted shadows, protected highlights, lower harsh contrast.
    luminance = (
        image[:, :, 2] * 0.299
        + image[:, :, 1] * 0.587
        + image[:, :, 0] * 0.114
    )
    shadow_mask = np.clip((0.55 - luminance) / 0.55, 0.0, 1.0)
    highlight_mask = np.clip((luminance - 0.72) / 0.28, 0.0, 1.0)
    image += shadow_mask[:, :, None] * 0.035
    image -= highlight_mask[:, :, None] * 0.018
    image = (image - 0.5) * 0.93 + 0.5

    hsv = cv2.cvtColor(np.clip(image * 255.0, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] *= 0.92
    image = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32) / 255.0

    # Gentle open-shade color: slightly cooler shadows, clean warm skin/high mids.
    image[:, :, 0] += shadow_mask * 0.012
    image[:, :, 2] += (1.0 - shadow_mask) * 0.008
    image[:, :, 1] += 0.004

    return np.clip(image * 255.0, 0, 255).astype(np.uint8)


def one_click_remove_color_cast(negative_bgr: np.ndarray) -> np.ndarray:
    corrected = compensate_orange_mask_rgb(negative_bgr)
    positive = invert_negative(corrected)
    positive = apply_black_highlight_points(positive)
    positive = gray_world_white_balance(positive)
    positive = correct_gray_point(positive)
    positive = lift_underexposed_frame(positive)
    positive = correct_skin_tone(positive)
    positive = natural_portra_skin(positive)
    positive = airy_natural_portrait_grade(positive)
    positive = apply_black_highlight_points(positive)
    return positive


def revive_negative(
    image_bgr: np.ndarray,
    denoise: bool = False,
    one_click_color_cast: bool = True,
) -> np.ndarray:
    if one_click_color_cast:
        positive = one_click_remove_color_cast(image_bgr)
    else:
        positive = invert_negative(image_bgr)
        positive = gray_world_white_balance(positive)
        positive = auto_levels(positive, 0.5, 99.5)

    if denoise:
        positive = denoise_image(positive)
    positive = natural_portra_skin(positive)
    positive = airy_natural_portrait_grade(positive)
    return positive


def decode_and_process(
    file_bytes: bytes,
    denoise: bool,
    one_click_color_cast: bool,
) -> np.ndarray:
    image = decode_upload(file_bytes)
    return revive_negative(image, denoise, one_click_color_cast)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/convert")
async def convert_negative(
    file: UploadFile = File(...),
    denoise: bool = Form(False),
    one_click_color_cast: bool = Form(True),
) -> Response:
    filename = file.filename or ""
    extension = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""

    if extension and extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="暂不支持这个文件格式，请上传 JPG、PNG、WEBP、BMP 或 TIFF。")
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传 JPG、PNG、WEBP、BMP 或 TIFF 图片文件。")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="图片文件为空。")
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="文件太大，请上传 120MB 以内的图片。")

    try:
        processed = await asyncio.wait_for(
            asyncio.to_thread(
                decode_and_process,
                file_bytes,
                denoise,
                one_click_color_cast,
            ),
            timeout=PROCESSING_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="处理时间过长，已停止。请先把大文件导出为较小的 TIFF/JPG 后再试。")

    success, encoded = cv2.imencode(".jpg", processed, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    if not success:
        raise HTTPException(status_code=500, detail="图片编码失败。")

    return Response(
        content=BytesIO(encoded.tobytes()).getvalue(),
        media_type="image/jpeg",
        headers={"Content-Disposition": 'inline; filename="filmrevive-positive.jpg"'},
    )
