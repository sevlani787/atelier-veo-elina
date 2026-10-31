import base64
import os
import re
import subprocess
import tempfile
from typing import List, Tuple
from urllib.parse import parse_qs, urlparse

from aiogram.types import Message
import httpx


def split_text(text: str, limit: int = 4000) -> List[str]:
    """
    Разбивает текст на части, не превышающие лимит, стараясь не разрывать строки.
    """
    if len(text) <= limit:
        return [text]

    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break

        # Ищем последний перевод строки в пределах лимита
        split_pos = text.rfind('\n', 0, limit)
        if split_pos == -1:
            # Если нет перевода строки, ищем пробел
            split_pos = text.rfind(' ', 0, limit)

        if split_pos == -1:
            # Если нет ни того, ни другого, просто режем по лимиту
            split_pos = limit

        chunks.append(text[:split_pos].strip())
        text = text[split_pos:].strip()

    return chunks


async def send_long_message(message: Message, text: str, parse_mode: str = "HTML", reply_markup=None):
    """
    Отправляет длинное сообщение, разбивая его на части.
    """
    chunks = split_text(text)

    for i, chunk in enumerate(chunks):
        # Добавляем клавиатуру только к последнему сообщению
        markup = reply_markup if i == len(chunks) - 1 else None

        try:
            await message.answer(chunk, parse_mode=parse_mode, reply_markup=markup)
        except Exception as e:
            # Если ошибка в HTML (например, тег разорван), пробуем отправить без разметки
            if "can't parse entities" in str(e).lower():
                await message.answer(chunk, parse_mode=None, reply_markup=markup)
            else:
                raise e


def get_video_duration(video_path: str) -> float:
    """
    Определяет точную длительность видеофайла с помощью ffprobe.
    """
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        val = res.stdout.strip()
        if val:
            return max(1.0, float(val))
    except Exception as e:
        print(f"[FFPROBE] Error getting duration: {e}")
    return 10.0


def extract_keyframes_from_video(video_path: str, duration: float = 0.0, max_frames: int = 6) -> List[Tuple[float, str]]:
    """
    Извлекает до max_frames ключевых кадров из видеофайла с помощью ffmpeg.
    Возвращает список кортежей (timestamp_sec, base64_jpeg).
    """
    if duration <= 0:
        duration = get_video_duration(video_path)

    if duration <= 3.0:
        timestamps = [round(duration / 2, 2)]
    else:
        count = min(max_frames, max(3, int(duration // 3)))
        step = (duration * 0.8) / (count - 1) if count > 1 else 0
        timestamps = [round(duration * 0.1 + i * step, 2) for i in range(count)]

    frames = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for i, ts in enumerate(timestamps):
            out_img = os.path.join(tmpdir, f"frame_{i}.jpg")
            cmd_frame = [
                'ffmpeg', '-y',
                '-ss', str(ts),
                '-i', video_path,
                '-vframes', '1',
                '-vf', 'scale=720:-1',
                '-q:v', '3',
                out_img
            ]
            try:
                subprocess.run(cmd_frame, capture_output=True, check=True)
                if os.path.exists(out_img) and os.path.getsize(out_img) > 0:
                    with open(out_img, 'rb') as f:
                        b64 = base64.b64encode(f.read()).decode('utf-8')
                        frames.append((ts, b64))
            except Exception as e:
                print(f"[FFMPEG] Error extracting frame at {ts}s: {e}")

    return frames


def extract_audio_from_media(media_path: str, max_duration: float = 90.0) -> str | None:
    """
    Извлекает аудиодорожку из видео или аудиофайла и конвертирует в 16kHz mono WAV (base64)
    для прямой подачи в Gemini Multimodal Audio API.
    """
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_wav:
        wav_path = tmp_wav.name
    try:
        cmd = [
            'ffmpeg', '-y', '-i', media_path,
            '-t', str(max_duration),
            '-vn',
            '-ar', '16000',
            '-ac', '1',
            '-sample_fmt', 's16',
            wav_path
        ]
        res = subprocess.run(cmd, capture_output=True)
        if res.returncode == 0 and os.path.exists(wav_path) and os.path.getsize(wav_path) > 500:
            with open(wav_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"[FFMPEG AUDIO] Extraction error: {e}")
    finally:
        if os.path.exists(wav_path):
            try:
                os.unlink(wav_path)
            except Exception:
                pass
    return None


def extract_video_url_from_text(text: str) -> str | None:
    """
    Ищет в тексте ссылку на Google Drive, Dropbox или прямой видеофайл.
    """
    if not text:
        return None
    pattern = r'https?://[^\s<>"]+'
    matches = re.findall(pattern, text)
    for url in matches:
        clean_url = url.rstrip('.,!?;:)')
        parsed = urlparse(clean_url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        # Google Drive
        if "drive.google.com" in domain:
            return clean_url
        # Dropbox
        if "dropbox.com" in domain:
            return clean_url
        # Прямые ссылки на видеофайлы
        if any(path.endswith(ext) for ext in ('.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v')):
            return clean_url

    return None


def transform_cloud_url(url: str) -> str:
    """
    Преобразует публичную веб-ссылку облака в прямую ссылку для потокового скачивания.
    """
    # Dropbox
    if "dropbox.com" in url:
        if "dl=0" in url:
            return url.replace("dl=0", "dl=1")
        if "raw=1" not in url and "dl=1" not in url:
            sep = "&" if "?" in url else "?"
            return f"{url}{sep}dl=1"
        return url

    # Google Drive
    if "drive.google.com" in url:
        match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
        if match:
            file_id = match.group(1)
            return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if 'id' in qs:
            file_id = qs['id'][0]
            return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"

    return url


async def download_cloud_video(url: str, dest_path: str, max_size_mb: int = 2000) -> bool:
    """
    Потоково скачивает видео по ссылке (Google Drive, Dropbox, прямой URL) во временный файл.
    """
    direct_url = transform_cloud_url(url)
    max_bytes = max_size_mb * 1024 * 1024
    downloaded = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=300.0) as client:
            async with client.stream("GET", direct_url, headers=headers) as response:
                if response.status_code != 200:
                    # Проверяем подтверждение для Google Drive при больших размерах
                    if "drive.google.com" in url or "drive.usercontent.google.com" in direct_url:
                        confirm_token = None
                        for key, val in response.cookies.items():
                            if "download_warning" in key:
                                confirm_token = val
                                break
                        if confirm_token:
                            async with client.stream("GET", f"{direct_url}&confirm={confirm_token}", headers=headers) as resp2:
                                if resp2.status_code == 200:
                                    with open(dest_path, "wb") as f:
                                        async for chunk in resp2.aiter_bytes(chunk_size=1024 * 1024):
                                            downloaded += len(chunk)
                                            if downloaded > max_bytes:
                                                return False
                                            f.write(chunk)
                                    return downloaded > 0
                    return False

                with open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            return False
                        f.write(chunk)

        return downloaded > 0
    except Exception as e:
        print(f"[CLOUD_DOWNLOAD] Error downloading from {url}: {e}")
        return False
