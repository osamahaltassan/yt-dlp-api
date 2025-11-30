import os
import json
import random
import string
import yt_dlp
import shutil
from threading import Timer
from flask import Flask, request, jsonify, send_from_directory, send_file
from src.storage import Storage
from src.auth import auth_manager, memory_manager, require_permission, AuthManager
from src.models import Task, TaskStatus, TaskType
from config import storage
from src import yt_handler

app = Flask(__name__)
app.json.sort_keys = False

def generate_task_id(length: int = 16) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def create_task(task_type: TaskType, data: dict) -> dict:
    if not data.get('url'):
        return {'status': 'error', 'message': 'URL is required'}, 400
    
    task_id = generate_task_id()
    api_key = request.headers.get('X-API-Key')
    
    task = Task(
        task_id=task_id,
        key_name=AuthManager.get_key_name(api_key),
        status=TaskStatus.WAITING,
        task_type=task_type,
        url=data['url'],
        video_format=data.get('video_format', 'bestvideo'),
        audio_format=data.get('audio_format', 'bestaudio'),
        start_time=data.get('start_time'),
        end_time=data.get('end_time'),
        force_keyframes=data.get('force_keyframes', False),
        start=data.get('start', 0),
        duration=data.get('duration'),
        output_format=data.get('output_format')
    )
    
    tasks = Storage.load_tasks()
    tasks[task_id] = task.to_dict()
    Storage.save_tasks(tasks)
    
    return jsonify({'status': 'waiting', 'task_id': task_id})

@app.route('/get_video', methods=['POST'])
@require_permission('get_video')
def get_video():
    return create_task(TaskType.GET_VIDEO, request.json)

@app.route('/get_audio', methods=['POST'])
@require_permission('get_audio')
def get_audio():
    return create_task(TaskType.GET_AUDIO, request.json)

@app.route('/get_info', methods=['POST'])
@require_permission('get_info')
def get_info():
    return create_task(TaskType.GET_INFO, request.json)

@app.route('/get_live_video', methods=['POST'])
@require_permission('get_live_video')
def get_live_video():
    return create_task(TaskType.GET_LIVE_VIDEO, request.json)

@app.route('/get_live_audio', methods=['POST'])
@require_permission('get_live_audio')
def get_live_audio():
    return create_task(TaskType.GET_LIVE_AUDIO, request.json)

@app.route('/status/<task_id>', methods=['GET'])
def status(task_id: str):
    tasks = Storage.load_tasks()
    if task_id not in tasks:
        return jsonify({'status': 'error', 'message': 'Task not found'}), 404
    return jsonify(tasks[task_id])

@app.route('/files/<path:filename>', methods=['GET'])
def get_file(filename: str):
    file_path = os.path.abspath(os.path.join(storage.DOWNLOAD_DIR, filename))
    
    if not os.path.isfile(file_path):
        return jsonify({"error": "File not found"}), 404
    
    if not file_path.startswith(os.path.abspath(storage.DOWNLOAD_DIR)):
        return jsonify({"error": "Access denied"}), 403
    
    if filename.endswith('info.json'):
        return handle_info_file(file_path)
    
    return handle_regular_file(filename)

def handle_info_file(file_path: str):
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    params = request.args
    if not params: 
        return jsonify(data)
    
    result = {}
    if 'qualities' in params:
        result['qualities'] = extract_qualities(data)
    for key in params:
        if key != 'qualities' and key in data:
            result[key] = data[key]
    
    if result:
        return jsonify(result)
    return jsonify({"error": "No matching parameters"}), 404

def extract_qualities(data: dict) -> dict:
    qualities = {"audio": {}, "video": {}}
    
    for fmt in data.get('formats', []):
        if fmt.get('format_note') in ['unknown', 'storyboard']:
            continue
        
        # Audio format
        if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none' and fmt.get('abr'):
            qualities["audio"][fmt['format_id']] = {
                "abr": int(fmt['abr']),
                "acodec": fmt['acodec'],
                "audio_channels": int(fmt.get('audio_channels', 0)),
                "language": fmt['language'],
                "filesize": int(fmt.get('filesize') or fmt.get('filesize_approx') or 0)
            }
        
        # Video format
        elif fmt.get('vcodec') != 'none' and fmt.get('height') and fmt.get('fps'):
            qualities["video"][fmt['format_id']] = {
                "height": int(fmt['height']),
                "width": int(fmt['width']),
                "fps": int(fmt['fps']),
                "vcodec": fmt['vcodec'],
                "format_note": fmt.get('format_note', 'unknown'),
                "dynamic_range": fmt.get('dynamic_range', 'unknown'),
                "filesize": int(fmt.get('filesize') or fmt.get('filesize_approx') or 0)
            }
    
    qualities["video"] = dict(sorted(qualities["video"].items(), 
                                   key=lambda x: (x[1]['height'], x[1]['fps'])))
    qualities["audio"] = dict(sorted(qualities["audio"].items(), 
                                   key=lambda x: x[1]['abr']))
    
    return qualities

def handle_regular_file(filename: str):
    raw = request.args.get('raw', 'false').lower() == 'true'
    response = send_from_directory(storage.DOWNLOAD_DIR, filename, as_attachment=raw)
    response.headers['Accept-Ranges'] = 'bytes'
    response.headers['Cache-Control'] = 'public, max-age=3600'
    if raw:
        response.headers['Content-Disposition'] = f'inline; filename="{filename}"'
    return response

@app.route('/create_key', methods=['POST'])
@require_permission('create_key')
def create_key():
    data = request.json
    name = data.get('name')
    permissions = data.get('permissions')
    
    if not name or not permissions:
        return jsonify({'error': 'Name and permissions required'}), 400
    
    key = auth_manager.create_key(name, permissions)
    return jsonify({'message': 'API key created', 'name': name, 'key': key}), 201

@app.route('/delete_key/<name>', methods=['DELETE'])
@require_permission('delete_key')
def delete_key(name: str):
    if auth_manager.delete_key(name):
        return jsonify({'message': 'API key deleted', 'name': name}), 200
    return jsonify({'error': 'Key not found'}), 404

@app.route('/get_key/<name>', methods=['GET'])
@require_permission('get_key')
def get_key(name: str):
    keys = Storage.load_keys()
    if name in keys:
        return jsonify({'name': name, 'key': keys[name]['key']}), 200
    return jsonify({'error': 'Key not found'}), 404

@app.route('/get_keys', methods=['GET'])
@require_permission('get_keys')
def get_keys():
    return jsonify(Storage.load_keys()), 200

@app.route('/check_permissions', methods=['POST'])
def check_permissions():
    api_key = request.headers.get('X-API-Key')
    if not api_key:
        return jsonify({'error': 'No API key provided'}), 401
    
    keys = Storage.load_keys()
    key_name = AuthManager.get_key_name(api_key)
    
    if not key_name or key_name not in keys:
        return jsonify({'error': 'Invalid API key'}), 401
    
    required = request.json.get('permissions', [])
    current = keys[key_name]['permissions']
    
    if set(required).issubset(current):
        return jsonify({'message': 'Permissions granted'}), 200
    return jsonify({'message': 'Insufficient permissions'}), 403

def schedule_cleanup(path: str, delay_seconds: int = 300):
    """Delete path after delay"""
    def do_cleanup():
        shutil.rmtree(path, ignore_errors=True)
    Timer(delay_seconds, do_cleanup).start()


@app.route('/download', methods=['POST'])
@require_permission('get_video')
def download_sync():
    """Synchronous download - blocks until complete, returns file directly"""
    data = request.json or {}
    
    if not data.get('url'):
        return jsonify({'error': 'URL is required'}), 400
    
    api_key = request.headers.get('X-API-Key')
    task_id = generate_task_id()
    download_path = os.path.join(storage.DOWNLOAD_DIR, task_id)
    
    try:
        # Estimate size and check quota
        is_video = data.get('type', 'video') == 'video'
        video_format = data.get('video_format', 'bestvideo[height<=1080]') if is_video else None
        audio_format = data.get('audio_format', 'bestaudio')
        
        total_size = yt_handler.downloader.estimate_size(
            data['url'],
            video_format,
            audio_format if is_video else data.get('audio_format', 'bestaudio')
        )
        
        if total_size > 0:
            memory_manager.check_and_update_quota(api_key, total_size, task_id)
        
        # Download to temp directory
        os.makedirs(download_path, exist_ok=True)
        
        # Build yt-dlp options
        output_format = data.get('output_format', 'mp4' if is_video else 'mp3')
        
        if is_video:
            if audio_format and str(audio_format).lower() not in ['none', 'null']:
                format_option = f"{video_format}+{audio_format}/best"
            else:
                format_option = f"{video_format}/bestvideo"
            output_name = 'video.%(ext)s'
        else:
            format_option = f"{audio_format}/bestaudio"
            output_name = 'audio.%(ext)s'
        
        ydl_opts = {
            'format': format_option,
            'outtmpl': os.path.join(download_path, output_name),
            'extractor_args': {'youtube': {'player_client': ['default', '-tv_simply']}},
            'quiet': True,
            'no_warnings': True,
        }
        
        if output_format:
            if is_video:
                ydl_opts['merge_output_format'] = output_format
            else:
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': output_format,
                }]
        
        # Handle time range
        if data.get('start_time') or data.get('end_time'):
            from yt_dlp.utils import download_range_func
            start = yt_handler.downloader._time_to_seconds(data.get('start_time', 0))
            end = yt_handler.downloader._time_to_seconds(data.get('end_time', 36000))
            ydl_opts['download_ranges'] = download_range_func(None, [(start, end)])
            ydl_opts['force_keyframes_at_cuts'] = data.get('force_keyframes', False)
        
        # Download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([data['url']])
        
        # Find the downloaded file
        files = os.listdir(download_path)
        if not files:
            raise Exception("Download failed - no file created")
        
        file_path = os.path.join(download_path, files[0])
        
        # Schedule cleanup after 5 minutes (enough time to stream large files)
        schedule_cleanup(download_path, delay_seconds=3600)
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=files[0]
        )
        
    except Exception as e:
        shutil.rmtree(download_path, ignore_errors=True)
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0')
