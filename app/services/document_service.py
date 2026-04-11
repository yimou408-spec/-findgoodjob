from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.exceptions import FileProcessingError, FileValidationError

MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/bmp",
    "image/tiff",
    "application/octet-stream",
}


@dataclass
class ParsedDocument:
    filename: str
    content_type: str
    extracted_text: str


async def extract_text_from_upload(file: UploadFile) -> ParsedDocument:
    filename = Path(file.filename or "").name
    if not filename:
        raise FileValidationError("请上传有效文件", error_code="missing_filename")

    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise FileValidationError("仅支持 PDF 或常见图片格式", error_code="unsupported_file_type")

    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise FileValidationError("文件 MIME 类型不受支持", error_code="unsupported_mime_type")

    data = await file.read()
    if not data:
        raise FileValidationError("上传文件为空", error_code="empty_file")
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise FileValidationError("文件大小不能超过 10MB", error_code="file_too_large", status_code=413)

    if extension == ".pdf":
        extracted_text = _extract_pdf_text(data)
        normalized_content_type = "application/pdf"
    else:
        extracted_text = _extract_image_text(data)
        normalized_content_type = content_type if content_type != "application/octet-stream" else "image/*"

    cleaned_text = extracted_text.strip()
    if not cleaned_text:
        raise FileProcessingError("未能从文件中提取到有效文本")

    return ParsedDocument(
        filename=filename,
        content_type=normalized_content_type,
        extracted_text=cleaned_text,
    )


def _extract_pdf_text(data: bytes) -> str:
    if not data.startswith(b"%PDF"):
        raise FileValidationError("上传文件不是有效 PDF", error_code="invalid_pdf")

    try:
        import fitz
    except ImportError as exc:
        raise FileProcessingError("服务端缺少 PyMuPDF，暂时无法解析 PDF") from exc

    try:
        document = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise FileValidationError("PDF 文件已损坏或无法读取", error_code="invalid_pdf") from exc

    try:
        page_texts = [(page.get_text("text") or "").strip() for page in document]
        combined = "\n".join(text for text in page_texts if text).strip()
        if combined:
            return combined

        ocr_texts = []
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            image_bytes = pixmap.tobytes("png")
            text = _extract_image_text(image_bytes)
            if text.strip():
                ocr_texts.append(text.strip())
        return "\n".join(ocr_texts)
    finally:
        document.close()


def _extract_image_text(data: bytes) -> str:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise FileProcessingError("服务端缺少 Pillow，暂时无法解析图片") from exc

    try:
        import pytesseract
    except ImportError as exc:
        raise FileProcessingError("服务端缺少 pytesseract，暂时无法进行 OCR") from exc

    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image).convert("L")
    except Exception as exc:
        raise FileValidationError("上传文件不是有效图片", error_code="invalid_image") from exc

    try:
        return pytesseract.image_to_string(image)
    except pytesseract.TesseractNotFoundError as exc:
        raise FileProcessingError("服务端未安装 Tesseract OCR，可先上传 PDF 或联系管理员安装") from exc
    except Exception as exc:
        raise FileProcessingError("OCR 识别失败，请尝试更清晰的图片或 PDF") from exc
