from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.downloader.manager import VideoManager


class YDLLogger:
    def __init__(self, job_id: str, manager: "VideoManager") -> None:
        self.job_id = job_id
        self.manager = manager

    def debug(self, msg):
        pass

    def info(self, msg):
        if not msg:
            return
        if "No supported JavaScript runtime" in msg or "js runtime" in msg.lower():
            self.manager._log(self.job_id, f"[aviso] {msg}")

    def warning(self, msg):
        if not msg:
            return
        low = msg.lower()
        if (
            "unable to download video subtitles" in low
            or ("subtitle" in low and "429" in low)
            or ("http error 429" in low and "subtitle" in low)
        ):
            self.manager._log(
                self.job_id,
                f"[aviso] Subtítulos omitidos (rate limit / 429): {msg}",
            )
            return
        if "No supported JavaScript runtime" in msg:
            self.manager._log(self.job_id, f"[aviso] {msg}")
            self.manager._log(
                self.job_id,
                "[aviso] Instalá Deno (https://deno.land) y: pip install -U yt-dlp-ejs",
            )
        elif "impersonate" in low or "impersonation" in low:
            self.manager._log(self.job_id, f"[aviso] {msg}")
            self.manager._log(
                self.job_id,
                '[aviso] Para impersonate: pip install -U "curl_cffi>=0.10"',
            )
        else:
            self.manager._log(self.job_id, f"[!] {msg}")

    def error(self, msg):
        if not msg:
            return
        low = msg.lower()
        if (
            "unable to download video subtitles" in low
            or ("subtitle" in low and "429" in low)
            or ("http error 429" in low and "subtit" in low)
        ):
            self.manager._log(
                self.job_id,
                f"[aviso] Subtítulos omitidos (429): {msg}",
            )
            return
        if self.manager._is_auth_error(msg):
            self.manager._emit_auth_required(self.job_id, msg)
        else:
            self.manager._log(self.job_id, f"[error] {msg}")