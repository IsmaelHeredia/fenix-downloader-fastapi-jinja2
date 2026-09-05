from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from yt_dlp.networking.impersonate import ImpersonateTarget

if TYPE_CHECKING:
    from app.services.downloader.manager import VideoManager


def resolve_cookies_file() -> str | None:
    candidates: list[Path] = []
    env = (os.environ.get("YTDLP_COOKIES_FILE") or "").strip()
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path.cwd() / "data" / "cookies.txt")
    candidates.append(Path.home() / ".config" / "fenix-downloader" / "cookies.txt")
    for p in candidates:
        try:
            if p.is_file() and p.stat().st_size > 0:
                return str(p.resolve())
        except OSError:
            continue
    return None


def apply_auth_opts(
    manager: "VideoManager",
    opts: dict[str, Any],
    job_id: str | None = None,
    use_cookies: bool = False,
) -> dict[str, Any]:
    runtime = (
        manager.js_runtime
        if manager.js_runtime in ("deno", "node", "quickjs")
        else "deno"
    )
    opts["js_runtimes"] = {runtime: {}}

    if manager.impersonate:
        try:
            opts["impersonate"] = ImpersonateTarget.from_str(
                str(manager.impersonate).lower()
            )
        except Exception as e:
            if job_id:
                manager._log(job_id, f"[aviso] impersonate ignorado: {e}")

    if use_cookies:
        path = manager.cookies_file or resolve_cookies_file()
        if path:
            manager.cookies_file = path
            opts["cookiefile"] = path
            if job_id:
                manager._log(job_id, f"🍪 Cookies activas → {path}")
        elif manager.cookies_from_browser:
            opts["cookiesfrombrowser"] = (manager.cookies_from_browser,)
            if job_id:
                manager._log(
                    job_id,
                    f"🍪 Cookies desde navegador → {manager.cookies_from_browser}",
                )
        else:
            if job_id:
                manager._log(
                    job_id,
                    "🍪 Pediste cookies pero no hay archivo. Continuando sin cookies.",
                )
    else:
        if job_id:
            manager._log(job_id, "🍪 Cookies desactivadas para este job")
    return opts