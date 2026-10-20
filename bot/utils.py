from typing import List
from aiogram.types import Message

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

async def send_long_message(message: Message, text: str, parse_mode: str = "HTML", reply_markup = None):
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


def extract_keyframes_from_video(video_path: str, duration: float = 10.0, max_frames: int = 6) -> List[tuple]:
    """
    Извлекает до max_frames ключевых кадров из видеофайла с помощью ffmpeg.
    Возвращает список кортежей (timestamp_sec, base64_jpeg).
    """
    import subprocess
    import os
    import tempfile
    import base64

    if duration <= 0:
        duration = 10.0

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

