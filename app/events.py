import queue
import threading
import uuid
from typing import Dict, Optional, Set


class JobManager:
    def __init__(self) -> None:
        self._jobs: Dict[str, "queue.Queue[dict]"] = {}
        self._cancelled: Set[str] = set()
        self._lock = threading.Lock()

    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        with self._lock:
            self._jobs[job_id] = queue.Queue()
            self._cancelled.discard(job_id)
        return job_id

    def get_queue(self, job_id: str) -> Optional["queue.Queue[dict]"]:
        with self._lock:
            return self._jobs.get(job_id)

    def emit(self, job_id: str, event: dict) -> None:
        with self._lock:
            q = self._jobs.get(job_id)
        if q is not None:
            q.put(event)

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            exists = job_id in self._jobs
            if exists:
                self._cancelled.add(job_id)
        if exists:
            self.emit(
                job_id,
                {
                    "type": "status",
                    "message": "⏹ Cancelando...",
                },
            )
            self.emit(
                job_id,
                {
                    "type": "log",
                    "message": "⏹ Cancelación pedida por el usuario",
                },
            )
        return exists

    def is_cancelled(self, job_id: str) -> bool:
        with self._lock:
            return job_id in self._cancelled

    def close(self, job_id: str) -> None:
        self.emit(job_id, {"type": "done"})
        with self._lock:
            self._jobs.pop(job_id, None)
            self._cancelled.discard(job_id)


job_manager = JobManager()