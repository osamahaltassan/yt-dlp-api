# YouTube Downloader API

A REST API for downloading YouTube videos and audio using yt-dlp. Supports video/audio downloads, live streams, format selection, and time-based cutting.

## Quick Start

```bash
docker run -d \
  --name yt-dlp-api \
  -p 5000:5000 \
  -v /path/to/data:/data \
  --restart unless-stopped \
  ghcr.io/osamahaltassan/yt-dlp-api:latest
```

The API will be available at `http://localhost:5000`.

On first run, an admin API key is automatically generated. Retrieve it from:
```bash
cat /path/to/data/jsons/api_keys.json
```

## Configuration

Configuration can be customized by mounting a `config.py` file:

```bash
docker run -d \
  --name yt-dlp-api \
  -p 5000:5000 \
  -v /path/to/data:/data \
  -v /path/to/config.py:/opt/app/config.py \
  --restart unless-stopped \
  ghcr.io/osamahaltassan/yt-dlp-api:latest
```

### Default Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `DOWNLOAD_DIR` | `/data/downloads` | Downloaded files location |
| `TASKS_FILE` | `/data/jsons/tasks.json` | Task state storage |
| `KEYS_FILE` | `/data/jsons/api_keys.json` | API keys storage |
| `CLEANUP_TIME_MINUTES` | `10` | Time before completed tasks are removed |
| `REQUEST_LIMIT` | `60` | Max requests per cleanup window |
| `MAX_WORKERS` | `4` | Concurrent download workers |
| `DEFAULT_QUOTA_GB` | `5` | Default memory quota per API key |
| `AVAILABLE_BYTES` | `20GB` | Total server memory limit |

## Authentication

All requests require an API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: your_api_key" http://localhost:5000/get_keys
```

## API Endpoints

### Download Video

**POST** `/get_video`

```json
{
    "url": "https://youtu.be/VIDEO_ID",
    "video_format": "bestvideo[height<=1080]",
    "audio_format": "bestaudio[abr<=129]",
    "output_format": "mp4",
    "start_time": "00:00:30",
    "end_time": "00:01:00",
    "force_keyframes": false
}
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `url` | Yes | - | YouTube URL |
| `video_format` | No | `bestvideo` | yt-dlp format selector |
| `audio_format` | No | `bestaudio` | yt-dlp format selector (use `null` for video only) |
| `output_format` | No | `mp4` | Container format (mp4, mkv, webm) |
| `start_time` | No | - | Start time (HH:MM:SS or seconds) |
| `end_time` | No | - | End time (HH:MM:SS or seconds) |
| `force_keyframes` | No | `false` | Precise cutting (slower) |

**Permission:** `get_video`

---

### Download Audio

**POST** `/get_audio`

```json
{
    "url": "https://youtu.be/VIDEO_ID",
    "audio_format": "bestaudio[abr<=129]",
    "output_format": "mp3",
    "start_time": "00:00:30",
    "end_time": "00:01:00"
}
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `url` | Yes | - | YouTube URL |
| `audio_format` | No | `bestaudio` | yt-dlp format selector |
| `output_format` | No | original | Audio format (mp3, m4a, opus) |
| `start_time` | No | - | Start time |
| `end_time` | No | - | End time |

**Permission:** `get_audio`

---

### Download Live Video

**POST** `/get_live_video`

```json
{
    "url": "https://youtu.be/LIVE_ID",
    "start": 0,
    "duration": 300,
    "video_format": "bestvideo[height<=1080]",
    "audio_format": "bestaudio",
    "output_format": "mp4"
}
```

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `url` | Yes | - | Live stream URL |
| `duration` | Yes | - | Recording length (seconds) |
| `start` | No | `0` | Seconds ago to start from |
| `video_format` | No | `bestvideo` | yt-dlp format selector |
| `audio_format` | No | `bestaudio` | yt-dlp format selector |
| `output_format` | No | `mp4` | Container format |

**Permission:** `get_live_video`

---

### Download Live Audio

**POST** `/get_live_audio`

```json
{
    "url": "https://youtu.be/LIVE_ID",
    "start": 0,
    "duration": 300,
    "audio_format": "bestaudio",
    "output_format": "mp3"
}
```

**Permission:** `get_live_audio`

---

### Get Video Info

**POST** `/get_info`

```json
{
    "url": "https://youtu.be/VIDEO_ID"
}
```

**Permission:** `get_info`

---

### Check Task Status

**GET** `/status/<task_id>`

Returns task status and file path when completed.

---

### Get File

**GET** `/files/<task_id>/<filename>`

Query parameters:
- `raw=true` - Force download
- `qualities` - Return available formats (for info.json)

---

### API Key Management

| Endpoint | Method | Permission | Description |
|----------|--------|------------|-------------|
| `/create_key` | POST | `create_key` | Create new API key |
| `/delete_key/<name>` | DELETE | `delete_key` | Delete API key |
| `/get_key/<name>` | GET | `get_key` | Get API key by name |
| `/get_keys` | GET | `get_keys` | List all API keys |
| `/check_permissions` | POST | - | Check if key has permissions |

**Create Key Request:**
```json
{
    "name": "user_key",
    "permissions": ["get_video", "get_audio", "get_info"]
}
```

## Task Workflow

1. Submit download request → Returns `task_id`
2. Poll `/status/<task_id>` until `status: "completed"`
3. Download file from `/files/<task_id>/<filename>`

Tasks and files are automatically cleaned up after `CLEANUP_TIME_MINUTES`.

## Examples

### Download 1080p Video

```bash
curl -X POST http://localhost:5000/get_video \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/VIDEO_ID", "video_format": "bestvideo[height<=1080]"}'
```

### Download Audio as MP3

```bash
curl -X POST http://localhost:5000/get_audio \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/VIDEO_ID", "output_format": "mp3"}'
```

### Download Video Clip (30s to 1m)

```bash
curl -X POST http://localhost:5000/get_video \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/VIDEO_ID", "start_time": "00:00:30", "end_time": "00:01:00"}'
```

### Check Status and Download

```bash
# Check status
curl -H "X-API-Key: your_key" http://localhost:5000/status/TASK_ID

# Download when completed
curl -H "X-API-Key: your_key" http://localhost:5000/files/TASK_ID/video.mp4 -o video.mp4
```

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid/missing API key |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Task/file not found |
| 429 | Too Many Requests - Rate limit exceeded |
| 500 | Internal Server Error |

## Supported Formats

**Video Containers:** mp4, mkv, webm

**Audio Formats:** mp3, m4a, opus, aac

## License

MIT License