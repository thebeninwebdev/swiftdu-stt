# SwiftDU STT

FastAPI speech-to-text service for SwiftDU, powered by `faster-whisper`.

## API

```text
GET /
GET /health
POST /transcribe
```

`GET /health` is unauthenticated and can be used by uptime monitors such as UptimeRobot.

`POST /transcribe` accepts `multipart/form-data` with an audio `file` field and returns:

```json
{ "text": "transcribed text" }
```

Supported file types: `webm`, `mp3`, `wav`, `m4a`, `ogg`.

Maximum file size: `10MB`.

## Environment

```text
FRONTEND_ORIGIN=https://your-swiftdu-vercel-domain.vercel.app
STT_API_KEY=replace-with-a-long-random-secret
PORT=8000
```

`FRONTEND_ORIGIN` is required for browser calls from the SwiftDU frontend. The service does not allow all origins.

## Local Run

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Docker

```bash
docker build -t swiftdu-stt .
docker run --env-file .env.example -p 8000:8000 swiftdu-stt
```

## Render

Create a Render Web Service using Docker with this folder as the root.

Render will provide `$PORT`; the Docker command binds uvicorn to `0.0.0.0` and `${PORT:-8000}`.

Set these environment variables on Render:

```text
FRONTEND_ORIGIN=
STT_API_KEY=
```
"# swiftdu-stt" 
