import os
import sys
import time
import json
import threading
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("PipelineTaskService")
logger.setLevel(logging.INFO)

TELEMETRY_FILE = Path("D:/campaigns/pipeline_telemetry.json")

class PipelineTaskService:
    """
    Singleton service managing background rendering, restoration, and visual QA tasks
    for VEO Boardroom (Studio OS Circuit 1).
    Synchronized via thread-lock and file-backed IPC (D:/campaigns/pipeline_telemetry.json).
    """
    def __init__(self):
        self._lock = threading.Lock()
        self.state: Dict[str, Any] = {
            "status": "idle",       # "idle" | "running" | "completed" | "error"
            "task_id": None,
            "task_name": "Ожидание задачи Совета",
            "actor": "Адриан (Главный архитектор & СТО)",
            "current_phase": "Пайплайн готов к приему шотов",
            "phase_index": 0,
            "total_phases": 0,
            "progress": 0,          # 0 - 100
            "fps": 0.0,
            "frames_done": 0,
            "total_frames": 0,
            "started_at": 0.0,
            "elapsed_seconds": 0,
            "logs": [],
            "output_path": None,
            "preview_url": None,
            "media_name": None,
            "summary": None,
            "updated_at": 0.0
        }

    def _save_file(self):
        try:
            self.state["updated_at"] = time.time()
            TELEMETRY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(TELEMETRY_FILE, "w", encoding="utf-8") as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Error saving telemetry file: {e}")

    def get_telemetry(self) -> Dict[str, Any]:
        with self._lock:
            # Check if file was updated by another process recently
            if TELEMETRY_FILE.exists():
                try:
                    with open(TELEMETRY_FILE, "r", encoding="utf-8") as f:
                        file_data = json.load(f)
                    if file_data.get("updated_at", 0) > self.state.get("updated_at", 0):
                        self.state.update(file_data)
                except Exception:
                    pass

            data = dict(self.state)
            if data["status"] == "running" and data.get("started_at", 0) > 0:
                data["elapsed_seconds"] = int(time.time() - data["started_at"])
            return data

    def start_task(self, task_id: str, task_name: str, total_phases: int = 4, media_name: Optional[str] = None):
        with self._lock:
            self.state = {
                "status": "running",
                "task_id": task_id,
                "task_name": task_name,
                "actor": "Адриан (Главный архитектор & СТО)",
                "current_phase": "Инициализация оптического кернела...",
                "phase_index": 1,
                "total_phases": total_phases,
                "progress": 5,
                "fps": 24.0,
                "frames_done": 0,
                "total_frames": 0,
                "started_at": time.time(),
                "elapsed_seconds": 0,
                "logs": [f"[{time.strftime('%H:%M:%S')}] Задача зарегистрирована: {task_name}"],
                "output_path": None,
                "preview_url": None,
                "media_name": media_name,
                "summary": None,
                "updated_at": time.time()
            }
            self._save_file()
        logger.info(f"[PipelineTaskService] Started task: {task_id} - {task_name}")

    def update_phase(self, phase_name: str, phase_index: Optional[int] = None, progress: Optional[int] = None, log_msg: Optional[str] = None):
        with self._lock:
            if self.state["status"] != "running":
                self.state["status"] = "running"
            self.state["current_phase"] = phase_name
            if phase_index is not None:
                self.state["phase_index"] = phase_index
            if progress is not None:
                self.state["progress"] = min(100, max(0, progress))
            if log_msg:
                t_str = time.strftime('%H:%M:%S')
                self.state["logs"].append(f"[{t_str}] {log_msg}")
                if len(self.state["logs"]) > 30:
                    self.state["logs"] = self.state["logs"][-30:]
            self._save_file()
        logger.info(f"[PipelineTaskService] Phase update: {phase_name} ({progress}%)")

    def update_frame_progress(self, frames_done: int, total_frames: int, fps: float = 24.0):
        with self._lock:
            if self.state["status"] != "running":
                return
            self.state["frames_done"] = frames_done
            self.state["total_frames"] = total_frames
            self.state["fps"] = round(fps, 1)
            self._save_file()

    def complete_task(self, output_path: str, preview_url: Optional[str] = None, summary: Optional[str] = None):
        with self._lock:
            self.state["status"] = "completed"
            self.state["progress"] = 100
            self.state["current_phase"] = "✓ Мастеринг завершен успешно"
            self.state["output_path"] = output_path
            self.state["preview_url"] = preview_url
            self.state["summary"] = summary or "Мастер 4K готов к утверждению Советом"
            t_str = time.strftime('%H:%M:%S')
            self.state["logs"].append(f"[{t_str}] Рендер завершен: {Path(output_path).name}")
            self._save_file()
        logger.info(f"[PipelineTaskService] Task completed: {output_path}")

    def fail_task(self, error_message: str):
        with self._lock:
            self.state["status"] = "error"
            self.state["current_phase"] = f"Ошибка: {error_message}"
            t_str = time.strftime('%H:%M:%S')
            self.state["logs"].append(f"[{t_str}] Ошибка: {error_message}")
            self._save_file()
        logger.error(f"[PipelineTaskService] Task failed: {error_message}")

    def reset(self):
        with self._lock:
            self.state = {
                "status": "idle",
                "task_id": None,
                "task_name": "Ожидание задачи Совета",
                "actor": "Адриан (Главный архитектор & СТО)",
                "current_phase": "Пайплайн готов к приему шотов",
                "phase_index": 0,
                "total_phases": 0,
                "progress": 0,
                "fps": 0.0,
                "frames_done": 0,
                "total_frames": 0,
                "started_at": 0.0,
                "elapsed_seconds": 0,
                "logs": [],
                "output_path": None,
                "preview_url": None,
                "media_name": None,
                "summary": None,
                "updated_at": time.time()
            }
            self._save_file()

pipeline_task_service = PipelineTaskService()
