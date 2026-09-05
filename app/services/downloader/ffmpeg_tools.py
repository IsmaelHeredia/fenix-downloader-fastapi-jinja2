from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from app.events import job_manager
from app.services.downloader.exceptions import DownloadCancelled

if TYPE_CHECKING:
    from app.services.downloader.manager import VideoManager

_LANG3 = {
    "es": "spa",
    "en": "eng",
    "pt": "por",
    "fr": "fra",
    "de": "deu",
    "it": "ita",
    "ja": "jpn",
    "ko": "kor",
    "zh": "zho",
    "ru": "rus",
    "ar": "ara",
}


def _lang3(code: str | None) -> str:
    if not code:
        return "und"
    base = code.split("-")[0].lower()
    return _LANG3.get(base, "und")


class FFmpegMixin:

    def _ffprobe_duration(self: "VideoManager", path: str) -> float:
        try:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ]
            out = (
                subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
                .decode()
                .strip()
            )
            return float(out) if out else 0.0
        except Exception:
            return 0.0

    def _run_ffmpeg_with_progress(
        self: "VideoManager",
        job_id: str,
        command: list[str],
        duration: float,
        status_msg: str = "🔄 Convirtiendo...",
    ) -> bool:
        self._check_cancelled(job_id)
        self._status(job_id, status_msg)
        last_percent = -1.0
        try:
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1,
            )
            time_re = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
            for line in proc.stderr:
                if job_manager.is_cancelled(job_id):
                    proc.kill()
                    try:
                        proc.wait(timeout=5)
                    except Exception:
                        pass
                    raise DownloadCancelled("Cancelado por el usuario")
                m = time_re.search(line)
                if m and duration > 0:
                    h, mi, s = m.groups()
                    current = int(h) * 3600 + int(mi) * 60 + float(s)
                    percent = min(99.5, (current / duration) * 100)
                    if abs(percent - last_percent) >= 0.8:
                        last_percent = percent
                        job_manager.emit(
                            job_id,
                            {
                                "type": "download_progress",
                                "percent": percent,
                                "eta": "",
                                "speed": "",
                            },
                        )
            proc.wait()
            if proc.returncode != 0:
                err = ""
                try:
                    if proc.stderr:
                        err = proc.stderr.read()
                except Exception:
                    pass
                self._log(job_id, f"Error de ffmpeg: {err}")
                return False
            job_manager.emit(
                job_id,
                {
                    "type": "download_progress",
                    "percent": 100.0,
                    "eta": "",
                    "speed": "",
                },
            )
            return True
        except DownloadCancelled:
            raise
        except Exception as e:
            self._log(job_id, f"Error ejecutando ffmpeg: {e}")
            return False

    def convert_to_mp4(
        self: "VideoManager", job_id: str, input_path: str, output_path: str
    ) -> bool:
        self._check_cancelled(job_id)
        if input_path.lower().endswith(".mp4"):
            if os.path.abspath(input_path) != os.path.abspath(output_path):
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(input_path, output_path)
            return True
        self._status(job_id, "🔄 Convirtiendo a MP4...")
        self._log(job_id, f"Convirtiendo {os.path.basename(input_path)} a MP4 ...")
        duration = self._ffprobe_duration(input_path)
        command = [
            "ffmpeg",
            "-i",
            input_path,
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "22",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            "-y",
            output_path,
        ]
        ok = self._run_ffmpeg_with_progress(
            job_id, command, duration, "🔄 Convirtiendo a MP4..."
        )
        if ok:
            self._safe_remove(input_path)
        return ok

    def embed_subtitle(
        self: "VideoManager",
        job_id: str,
        video_path: str,
        subtitle_path: str,
        output_path: str,
        lang_code: str | None = None,
    ) -> bool:
        self._check_cancelled(job_id)
        self._status(job_id, "📝 Insertando subtítulos...")
        duration = self._ffprobe_duration(video_path)
        command = [
            "ffmpeg",
            "-i",
            video_path,
            "-i",
            subtitle_path,
            "-map",
            "0",
            "-map",
            "1",
            "-c:v",
            "copy",
            "-c:a",
            "copy",
            "-c:s",
            "mov_text",
            "-metadata:s:s:0",
            f"language={_lang3(lang_code)}",
            "-y",
            output_path,
        ]
        return self._run_ffmpeg_with_progress(
            job_id, command, duration, "📝 Insertando subtítulos..."
        )

    def convert_to_mp3(
        self: "VideoManager",
        job_id: str,
        video_path: str,
        output_name: str = None,
        output_folder: str = None,
    ):
        self._check_cancelled(job_id)
        if not os.path.isfile(video_path):
            self._log(job_id, "Archivo no encontrado para convertir")
            return None
        self._status(job_id, "🔄 Convirtiendo a MP3...")
        self._log(job_id, "Convirtiendo a MP3 ...")
        base_name = output_name or Path(video_path).stem
        output_dir = self.get_output_path(is_video=False, output_folder=output_folder)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(output_dir, f"{base_name}.mp3")
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            self._log(job_id, f"✅ Ya existe (omitido): {output_path}")
            if "temp_" in os.path.basename(video_path):
                self._safe_remove(video_path)
            return output_path
        duration = self._ffprobe_duration(video_path)
        command = [
            "ffmpeg",
            "-i",
            video_path,
            "-vn",
            "-acodec",
            "libmp3lame",
            "-ab",
            "192k",
            "-ar",
            "44100",
            "-y",
            output_path,
        ]
        ok = self._run_ffmpeg_with_progress(
            job_id, command, duration, "🔄 Convirtiendo a MP3..."
        )
        if not ok:
            self._safe_remove(output_path)
            return None
        self._safe_remove(video_path)
        self._log(job_id, f"✅ Guardado: {output_path}")
        return output_path

    def convert_local_mp4_to_mp3(
        self: "VideoManager",
        job_id: str,
        mp4_path: str,
        output_name: str = None,
        output_folder: str = None,
    ) -> str | None:
        self._check_cancelled(job_id)
        mp4_path = mp4_path.strip().strip('"').strip("'")
        if not os.path.isfile(mp4_path):
            self._log(job_id, f"Archivo no encontrado: {mp4_path}")
            return None
        if not mp4_path.lower().endswith(
            (".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4a", ".wav", ".flac", ".ogg")
        ):
            self._log(
                job_id,
                "Formato no soportado. Usá un archivo de video/audio válido.",
            )
            return None
        title = self.clear_title(output_name or Path(mp4_path).stem)
        self._item_progress(job_id, 1, 1, title)
        self._log(job_id, f"Origen: {mp4_path}")
        output_dir = self.get_output_path(is_video=False, output_folder=output_folder)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = os.path.join(output_dir, f"{title}.mp3")
        if os.path.isfile(output_path) and os.path.getsize(output_path) > 0:
            self._log(job_id, f"✅ Ya existe (omitido): {output_path}")
            self._status(job_id, "✅ Ya convertido (omitido)")
            return output_path
        self._status(job_id, "🔄 Convirtiendo a MP3...")
        self._log(job_id, "Convirtiendo a MP3 ...")
        duration = self._ffprobe_duration(mp4_path)
        command = [
            "ffmpeg",
            "-i",
            mp4_path,
            "-vn",
            "-acodec",
            "libmp3lame",
            "-ab",
            "192k",
            "-ar",
            "44100",
            "-y",
            output_path,
        ]
        try:
            ok = self._run_ffmpeg_with_progress(
                job_id, command, duration, "🔄 Convirtiendo a MP3..."
            )
        except DownloadCancelled:
            self._safe_remove(output_path)
            self._handle_cancel(job_id)
            return None
        if not ok:
            self._safe_remove(output_path)
            return None
        self._log(job_id, f"✅ Guardado: {output_path}")
        return output_path