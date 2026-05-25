import os
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from faster_whisper import WhisperModel

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

SERVICE_NAME = "swiftdu-stt"
MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".webm", ".mp3", ".wav", ".m4a", ".ogg"}
ALLOWED_CONTENT_TYPES = {
    "audio/webm",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/m4a",
    "audio/ogg",
    "application/ogg",
}

app = FastAPI(title="SwiftDU Speech to Text", version="1.0.0")

frontend_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
allowed_origins = [frontend_origin] if frontend_origin else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["x-api-key", "content-type"],
)

model: WhisperModel | None = None


@app.on_event("startup")
def load_model() -> None:
    global model
    model = WhisperModel("base", device="cpu", compute_type="int8")


def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected_api_key = os.getenv("STT_API_KEY", "").strip()

    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="STT_API_KEY is not configured.",
        )

    if not x_api_key or x_api_key != expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )


def validate_upload(file: UploadFile) -> str:
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(extension.lstrip(".") for extension in ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio file type. Accepted types: {allowed}.",
        )

    content_type = (file.content_type or "").lower().split(";", 1)[0].strip()

    if content_type and content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio content type: {file.content_type}.",
        )

    return suffix


async def save_upload_to_temp_file(file: UploadFile, suffix: str) -> str:
    size = 0

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = temp_file.name

        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                temp_file.close()
                os.unlink(temp_path)
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Audio file is too large. Maximum size is 10MB.",
                )

            temp_file.write(chunk)

    if size == 0:
        os.unlink(temp_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Audio file is empty.",
        )

    return temp_path


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME}


@app.head("/")
def health_check_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "model": "ready" if model is not None else "loading",
    }


@app.head("/health")
def health_head() -> Response:
    return Response(status_code=status.HTTP_200_OK)


@app.post("/transcribe", dependencies=[Depends(require_api_key)])
async def transcribe(file: UploadFile = File(...)) -> dict[str, str]:
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Speech model is still loading. Please try again shortly.",
        )

    suffix = validate_upload(file)
    temp_path = await save_upload_to_temp_file(file, suffix)

    try:
        segments, _info = model.transcribe(temp_path, language="en")
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return {"text": text}
    finally:
        await file.close()
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass
