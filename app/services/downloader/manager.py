from __future__ import annotations

import os
import re
import time
import unicodedata
from pathlib import Path

from yt_dlp import YoutubeDL

from app.events import job_manager
from app.services.duck_duck_go import DuckDuckGoSearch
from app.services.downloader.auth import apply_auth_opts, resolve_cookies_file
from app.services.downloader.exceptions import DownloadCancelled
from app.services.downloader.ffmpeg_tools import FFmpegMixin
from app.services.downloader.subtitles import apply_subtitles_opts, strip_subtitle_opts
from app.services.downloader.ydl_logger import YDLLogger

_AUTH_ERROR_MARKERS = (
    "sign in",
    "not a bot",
    "confirm your age",
    "confirm you're not a bot",
    "login required",
    "private video",
    "age-restricted",
    "Sign in to confirm",
)

_SUB_SUFFIXES = (".srt", ".vtt", ".ass", ".ssa")


class VideoManager(FFmpegMixin):
    def __init__(self) -> None:
        home = Path.home()
        self.music_folder = home / "Music"
        self.videos_folder = home / "Videos"
        if not self.music_folder.exists() and (home / "Música").exists():
            self.music_folder = home / "Música"
        if not self.videos_folder.exists() and (home / "Vídeos").exists():
            self.videos_folder = home / "Vídeos"

        self.directory = self.music_folder / "Video_downloads"
        self.directory_videos = self.videos_folder / "Video_downloads"
        self.directory.mkdir(parents=True, exist_ok=True)
        self.directory_videos.mkdir(parents=True, exist_ok=True)

        self.timeout_wait = 3
        self.ddg = DuckDuckGoSearch()

        self.cookies_file = resolve_cookies_file()
        self.cookies_from_browser = (
            os.environ.get("YTDLP_COOKIES_FROM_BROWSER") or ""
        ).strip() or None
        self.js_runtime = (os.environ.get("YTDLP_JS_RUNTIME") or "deno").strip().lower()
        imp = (os.environ.get("YTDLP_IMPERSONATE") or "chrome").strip()
        self.impersonate = None if imp in ("0", "false", "no", "off", "") else imp

        self._cleanup_orphaned_temps()

    def _check_cancelled(self, job_id: str) -> None:
        if job_manager.is_cancelled(job_id):
            raise DownloadCancelled("Cancelado por el usuario")

    def _handle_cancel(self, job_id: str, temp_base: str | None = None) -> None:
        self._log(job_id, "⏹ Descarga cancelada")
        self._status(job_id, "⏹ Cancelado")
        if temp_base:
            for p in self._find_temp_related(temp_base):
                self._safe_remove(p)

    def _is_auth_error(self, msg: str) -> bool:
        if not msg:
            return False
        return any(m in msg.lower() for m in _AUTH_ERROR_MARKERS)

    def _emit_auth_required(self, job_id: str, msg: str) -> None:
        job_manager.emit(
            job_id,
            {
                "type": "auth_required",
                "message": f"⚠️ YouTube requiere autenticación: {msg}",
            },
        )

    def _log(self, job_id: str, message: str) -> None:
        job_manager.emit(job_id, {"type": "log", "message": message})

    def _status(self, job_id: str, message: str) -> None:
        job_manager.emit(job_id, {"type": "status", "message": message})

    def _item_progress(
        self, job_id: str, current: int, total: int, title: str = ""
    ) -> None:
        job_manager.emit(
            job_id,
            {
                "type": "item_progress",
                "current": current,
                "total": total,
                "title": title,
            },
        )

    def _job_result(
        self,
        job_id: str,
        success: int,
        total: int,
        failed_links: list[str] | None = None,
    ) -> None:
        job_manager.emit(
            job_id,
            {
                "type": "job_result",
                "success": success,
                "total": total,
                "failed": max(0, total - success),
                "failed_links": failed_links or [],
                "cancelled": job_manager.is_cancelled(job_id),
            },
        )

    def _safe_remove(self, path: str | Path | None) -> None:
        if not path:
            return
        try:
            p = Path(path)
            if p.is_file():
                p.unlink()
        except OSError:
            pass

    def _cleanup_orphaned_temps(self, max_age_seconds: float = 3600) -> None:
        try:
            now = time.time()
            for f in self.directory_videos.iterdir():
                if not f.is_file():
                    continue
                name = f.name
                if not (
                    name.startswith("temp_")
                    or name.endswith(".embed.mp4")
                    or ".embed." in name
                ):
                    if not name.startswith("temp_"):
                        continue
                try:
                    age = now - f.stat().st_mtime
                    if age >= max_age_seconds:
                        f.unlink()
                except OSError:
                    pass
        except OSError:
            pass

    def _find_temp_related(self, temp_base: str) -> list[str]:
        name = os.path.basename(temp_base)
        stem = Path(name).stem
        prefix = stem
        found: list[str] = []
        try:
            for f in os.listdir(self.directory_videos):
                if (
                    f == name
                    or f == prefix
                    or f.startswith(prefix + ".")
                    or f.startswith(prefix + "-")
                ):
                    found.append(os.path.join(self.directory_videos, f))
        except OSError:
            pass
        return found

    def _cleanup_temp_subs(self, temp_base: str, keep: set[str] | None = None) -> None:
        keep = keep or set()
        keep_abs = {os.path.abspath(k) for k in keep}
        for p in self._find_temp_related(temp_base):
            ap = os.path.abspath(p)
            if ap in keep_abs:
                continue
            low = p.lower()
            if any(low.endswith(s) or s + "." in low for s in _SUB_SUFFIXES):
                self._safe_remove(p)
            elif low.endswith(".part") or low.endswith(".ytdl"):
                self._safe_remove(p)

    def clear_title(self, video_title: str) -> str:
        video_title = unicodedata.normalize("NFKC", video_title)
        video_title = re.sub(r'[\\/*?:"<>|]', "", video_title)
        video_title = "".join(
            c
            for c in video_title
            if c.isprintable() and unicodedata.category(c) not in ["Cs"]
        )
        return video_title.strip()

    def _generate_temp_filename(self, extension=".mp4") -> str:
        return os.path.join(
            self.directory_videos,
            f"temp_{int(time.time())}_{os.getpid()}{extension}",
        )

    def get_output_path(self, is_video: bool, output_folder: str = None) -> Path:
        base_path = self.directory_videos if is_video else self.directory
        return base_path / output_folder if output_folder else base_path

    def _item_name(self, output_name: str, idx: int, total: int) -> str:
        if not output_name:
            return None
        if total == 1:
            return output_name
        return f"{output_name} ({idx})"

    def _format_speed(self, speed_bytes):
        if not speed_bytes or speed_bytes <= 0:
            return ""
        if speed_bytes >= 1024 * 1024:
            return f"{speed_bytes / (1024 * 1024):.2f} MiB/s"
        if speed_bytes >= 1024:
            return f"{speed_bytes / 1024:.2f} KiB/s"
        return f"{speed_bytes:.2f} B/s"

    def _format_eta(self, eta_seconds):
        if not eta_seconds or eta_seconds < 0:
            return ""
        hours, remainder = divmod(int(eta_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _parse_percent(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = re.sub(r"[^\d.]", "", value)
            try:
                return float(cleaned)
            except ValueError:
                return 0.0
        return 0.0

    def _download_progress_hook(self, job_id: str):
        last_percent = 0

        def hook(d: dict):
            nonlocal last_percent
            if job_manager.is_cancelled(job_id):
                raise DownloadCancelled("Cancelado por el usuario")
            try:
                if d["status"] == "downloading":
                    self._status(job_id, "📥 Descargando...")
                    percent = self._parse_percent(d.get("_percent", 0))
                    if abs(percent - last_percent) >= 0.5:
                        last_percent = percent
                        speed = self._format_speed(d.get("speed", 0))
                        eta = self._format_eta(d.get("eta", 0))
                        job_manager.emit(
                            job_id,
                            {
                                "type": "download_progress",
                                "percent": percent,
                                "eta": eta,
                                "speed": speed,
                            },
                        )
                elif d["status"] == "finished":
                    job_manager.emit(
                        job_id,
                        {
                            "type": "download_progress",
                            "percent": 100.0,
                            "eta": "",
                            "speed": "",
                        },
                    )
            except DownloadCancelled:
                raise
            except Exception as e:
                job_manager.emit(
                    job_id, {"type": "log", "message": f"[hook error] {e}"}
                )

        return hook

    def _format_for_quality(self, quality: str, prefer_spanish_audio: bool) -> str:
        if prefer_spanish_audio:
            audio = "ba[language*=es]/ba"
        else:
            audio = "ba"
        if quality == "720":
            video = "bv*[height<=720]"
        elif quality == "max":
            video = "bv*[vcodec!~='av01'][height<=2160]/bv*[height<=2160]"
        else:
            video = "bv*[height<=1080]"
        return (
            f"{video}[ext=mp4]+{audio}/"
            f"{video}+{audio}/"
            f"b[height<=1080]/b"
        )

    def _build_ydl_opts(
        self,
        job_id: str,
        prefer_spanish_audio: bool = False,
        spanish_subs: bool = False,
        quality: str = "1080",
        use_cookies: bool = False,
    ) -> dict:
        fmt = self._format_for_quality(quality, prefer_spanish_audio)
        opts = {
            "format": fmt,
            "ignoreerrors": True,
            "cachedir": False,
            "quiet": True,
            "no_warnings": False,
            "progress_hooks": [self._download_progress_hook(job_id)],
            "logger": YDLLogger(job_id, self),
            "extract_flat": False,
            "merge_output_format": "mp4",
        }
        apply_auth_opts(self, opts, job_id=job_id, use_cookies=use_cookies)
        return opts

    def download_video(
        self,
        job_id: str,
        video_url: str,
        is_video: bool,
        output_name: str = None,
        output_folder: str = None,
        current: int = 1,
        total: int = 1,
        prefer_spanish_audio: bool = False,
        spanish_subs: bool = False,
        quality: str = "1080",
        use_cookies: bool = False,
    ):
        self._check_cancelled(job_id)
        video_url = video_url.strip()
        self._status(job_id, "🔍 Obteniendo información...")
        self._log(job_id, f"Procesando: {video_url}")
        self._log(job_id, f"Calidad: {quality}")

        ydl_opts = self._build_ydl_opts(
            job_id,
            prefer_spanish_audio,
            spanish_subs,
            quality,
            use_cookies=use_cookies,
        )

        temp_base = None
        downloaded_file = None

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
        except DownloadCancelled:
            self._handle_cancel(job_id)
            return None
        except Exception as e:
            error_msg = str(e).strip() or repr(e) or type(e).__name__
            self._log(job_id, f"Error obteniendo info: {error_msg}")
            self._log(job_id, f"[detalle] {type(e).__name__}: {repr(e)}")
            if self._is_auth_error(error_msg):
                self._emit_auth_required(job_id, error_msg)
            return None

        if info is None:
            self._log(job_id, "No se pudo obtener información del video")
            return None

        self._check_cancelled(job_id)

        video_title = self.clear_title(info.get("title", "untitled"))
        self._log(job_id, f"Título: {video_title}")
        self._item_progress(job_id, current, total, video_title)

        if prefer_spanish_audio:
            has_es = any(
                (f.get("language") or "").lower().startswith("es")
                for f in (info.get("formats") or [])
                if f.get("acodec") and f.get("acodec") != "none"
            )
            if has_es:
                self._log(job_id, "🎙 Pista de audio en español detectada → se usará")
            else:
                self._log(job_id, "ℹ️ No hay doblaje en español → audio original")

        want_subs = bool(spanish_subs)
        if want_subs:
            ydl_opts = apply_subtitles_opts(self, ydl_opts, info, job_id)

        final_name = output_name or video_title

        if not is_video:
            mp3_dir = self.get_output_path(False, output_folder)
            mp3_dir.mkdir(parents=True, exist_ok=True)
            final_mp3 = mp3_dir / f"{final_name}.mp3"
            if final_mp3.is_file() and final_mp3.stat().st_size > 0:
                self._log(job_id, f"✅ Ya existe (omitido): {final_mp3}")
                self._status(job_id, "✅ Ya descargado (omitido)")
                return str(final_mp3)
        else:
            video_dir = self.get_output_path(True, output_folder)
            video_dir.mkdir(parents=True, exist_ok=True)
            final_mp4 = video_dir / f"{final_name}.mp4"
            if final_mp4.is_file() and final_mp4.stat().st_size > 0:
                self._log(job_id, f"✅ Ya existe (omitido): {final_mp4}")
                self._status(job_id, "✅ Ya descargado (omitido)")
                return str(final_mp4)

        temp_base = self._generate_temp_filename()
        ydl_opts["outtmpl"] = temp_base

        self._status(job_id, "📥 Descargando...")
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])
        except DownloadCancelled:
            self._handle_cancel(job_id, temp_base)
            return None
        except Exception as e:
            if job_manager.is_cancelled(job_id) or "Cancelado" in str(e):
                self._handle_cancel(job_id, temp_base)
                return None
            error_msg = str(e).strip() or repr(e) or type(e).__name__
            low = error_msg.lower()
            if want_subs and (
                "subtitle" in low or "429" in low or "too many requests" in low
            ):
                self._log(
                    job_id,
                    "[aviso] Falló con subtítulos → reintento sin subtítulos",
                )
                ydl_opts = strip_subtitle_opts(dict(ydl_opts))
                ydl_opts["outtmpl"] = temp_base
                try:
                    self._check_cancelled(job_id)
                    with YoutubeDL(ydl_opts) as ydl:
                        ydl.download([video_url])
                except DownloadCancelled:
                    self._handle_cancel(job_id, temp_base)
                    return None
                except Exception as e2:
                    error_msg = str(e2).strip() or repr(e2) or type(e2).__name__
                    self._log(job_id, f"Error descargando: {error_msg}")
                    if self._is_auth_error(error_msg):
                        self._emit_auth_required(job_id, error_msg)
                    for p in self._find_temp_related(temp_base):
                        self._safe_remove(p)
                    return None
            else:
                self._log(job_id, f"Error descargando: {error_msg}")
                if self._is_auth_error(error_msg):
                    self._emit_auth_required(job_id, error_msg)
                for p in self._find_temp_related(temp_base):
                    self._safe_remove(p)
                return None

        if job_manager.is_cancelled(job_id):
            self._handle_cancel(job_id, temp_base)
            return None

        for f in self._find_temp_related(temp_base):
            if not os.path.isfile(f):
                continue
            low = f.lower()
            if low.endswith((".srt", ".vtt", ".ass", ".ssa", ".part", ".ytdl")):
                continue
            if any(
                low.endswith(ext)
                for ext in (".mp4", ".webm", ".mkv", ".m4a", ".opus")
            ):
                downloaded_file = f
                break
            if downloaded_file is None:
                downloaded_file = f

        if not downloaded_file:
            self._log(job_id, "Archivo descargado no encontrado")
            for p in self._find_temp_related(temp_base):
                self._safe_remove(p)
            return None

        output_dir = self.get_output_path(is_video=True, output_folder=output_folder)
        output_dir.mkdir(parents=True, exist_ok=True)
        final_output = os.path.join(output_dir, f"{final_name}.mp4")

        try:
            self._check_cancelled(job_id)
            if not downloaded_file.lower().endswith(".mp4"):
                if not self.convert_to_mp4(job_id, downloaded_file, final_output):
                    self._log(job_id, "Falló la conversión a MP4")
                    for p in self._find_temp_related(temp_base):
                        self._safe_remove(p)
                    return None
            else:
                if os.path.abspath(downloaded_file) != os.path.abspath(final_output):
                    if os.path.exists(final_output):
                        os.remove(final_output)
                    os.rename(downloaded_file, final_output)
                downloaded_file = None

            try:
                stem = Path(temp_base).stem
                sub_path = None
                sub_lang = None
                for p in list(self.directory_videos.glob(f"{stem}*")):
                    if not p.is_file():
                        continue
                    if p.suffix.lower() in (".srt", ".vtt", ".ass", ".ssa"):
                        if sub_path is None:
                            sub_path = str(p)
                            sub_lang = (ydl_opts.get("subtitleslangs") or [None])[0]
                    else:
                        if os.path.abspath(str(p)) != os.path.abspath(final_output):
                            self._safe_remove(p)

                if sub_path and os.path.isfile(final_output):
                    self._check_cancelled(job_id)
                    embed_tmp = final_output + ".embed.mp4"
                    embedded_ok = False
                    try:
                        embedded_ok = self.embed_subtitle(
                            job_id, final_output, sub_path, embed_tmp, sub_lang
                        )
                    except DownloadCancelled:
                        self._safe_remove(embed_tmp)
                        raise

                    if embedded_ok and os.path.isfile(embed_tmp):
                        os.replace(embed_tmp, final_output)
                        self._log(job_id, "📝 Subtítulos insertados en el video")
                        self._safe_remove(sub_path)
                    else:
                        self._safe_remove(embed_tmp)
                        dest = Path(output_dir) / f"{final_name}{Path(sub_path).suffix}"
                        try:
                            if dest.exists():
                                dest.unlink()
                            Path(sub_path).rename(dest)
                            self._log(
                                job_id,
                                "⚠️ No se pudieron insertar los subtítulos en el "
                                f"video, quedaron aparte: {dest}",
                            )
                        except OSError:
                            self._safe_remove(sub_path)

                self._cleanup_temp_subs(temp_base, keep={final_output})
            except OSError:
                pass

            for p in self._find_temp_related(temp_base):
                if os.path.abspath(p) != os.path.abspath(final_output):
                    self._safe_remove(p)

            self._safe_remove(final_output + ".embed.mp4")

            self._log(job_id, f"✅ Guardado: {final_output}")
            return str(final_output)
        except DownloadCancelled:
            self._handle_cancel(job_id, temp_base)
            return None
        except Exception as e:
            self._log(job_id, f"Error post-descarga: {e}")
            for p in self._find_temp_related(temp_base):
                self._safe_remove(p)
            return None

    def download_multiple(
        self,
        job_id: str,
        links: list[str],
        is_song: bool,
        output_name: str = None,
        output_folder: str = None,
        prefer_spanish_audio: bool = False,
        spanish_subs: bool = False,
        quality: str = "1080",
        use_cookies: bool = False,
    ) -> tuple[int, list[str]]:
        total = len(links)
        success = 0
        failed: list[str] = []
        for idx, link in enumerate(links, start=1):
            if job_manager.is_cancelled(job_id):
                self._log(
                    job_id, f"⏹ Cancelado — restantes omitidos ({total - idx + 1})"
                )
                failed.extend(links[idx - 1 :])
                break
            self._item_progress(job_id, idx, total, link)
            item_name = self._item_name(output_name, idx, total)
            try:
                video_path = self.download_video(
                    job_id,
                    link,
                    is_video=not is_song,
                    output_name=item_name,
                    output_folder=output_folder,
                    current=idx,
                    total=total,
                    prefer_spanish_audio=prefer_spanish_audio,
                    spanish_subs=spanish_subs,
                    quality=quality,
                    use_cookies=use_cookies,
                )
            except DownloadCancelled:
                self._handle_cancel(job_id)
                failed.extend(links[idx - 1 :])
                break
            ok = False
            if is_song and video_path:
                try:
                    mp3 = self.convert_to_mp3(
                        job_id,
                        video_path,
                        output_name=item_name,
                        output_folder=output_folder,
                    )
                    ok = bool(mp3)
                except DownloadCancelled:
                    self._handle_cancel(job_id)
                    failed.extend(links[idx - 1 :])
                    break
            elif video_path:
                ok = True
            if ok:
                success += 1
            else:
                if not job_manager.is_cancelled(job_id):
                    failed.append(link)
            if idx < total and not job_manager.is_cancelled(job_id):
                time.sleep(self.timeout_wait)
        self._job_result(job_id, success, total, failed)
        return success, failed

    def search_and_download(
        self,
        job_id: str,
        names: list[str],
        output_name: str = None,
        output_folder: str = None,
        prefer_spanish_audio: bool = False,
        spanish_subs: bool = False,
        quality: str = "1080",
        use_cookies: bool = False,
    ) -> tuple[int, list[str]]:
        total = len(names)
        success = 0
        failed: list[str] = []
        for idx, name in enumerate(names, start=1):
            if job_manager.is_cancelled(job_id):
                self._log(job_id, "⏹ Cancelado — restantes omitidos")
                failed.extend(n for n in names[idx - 1 :] if n.strip())
                break
            name = name.strip()
            if not name:
                continue
            self._item_progress(job_id, idx, total, name)
            self._log(job_id, f"🔍 Buscando: {name}")
            query = f"site:https://www.youtube.com {name}"
            link = self.ddg.send_first_result(query)
            if not link:
                self._log(job_id, f"No se encontró resultado para: {name}")
                failed.append(name)
                continue
            item_name = self._item_name(output_name, idx, total) or name
            try:
                video_path = self.download_video(
                    job_id,
                    link,
                    is_video=False,
                    output_name=item_name,
                    output_folder=output_folder,
                    current=idx,
                    total=total,
                    prefer_spanish_audio=prefer_spanish_audio,
                    spanish_subs=spanish_subs,
                    quality=quality,
                    use_cookies=use_cookies,
                )
            except DownloadCancelled:
                self._handle_cancel(job_id)
                failed.extend(n for n in names[idx - 1 :] if n.strip())
                break
            if video_path:
                try:
                    mp3 = self.convert_to_mp3(
                        job_id,
                        video_path,
                        output_name=item_name,
                        output_folder=output_folder,
                    )
                    if mp3:
                        success += 1
                    else:
                        failed.append(link)
                except DownloadCancelled:
                    self._handle_cancel(job_id)
                    failed.extend(n for n in names[idx - 1 :] if n.strip())
                    break
            else:
                if not job_manager.is_cancelled(job_id):
                    failed.append(link)
            if idx < total and not job_manager.is_cancelled(job_id):
                time.sleep(self.timeout_wait)
        self._job_result(job_id, success, total, failed)
        return success, failed

    def _extract_playlist_entries(
        self, playlist_link: str, use_cookies: bool = False
    ) -> list[str]:
        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "ignoreerrors": True,
            "cachedir": False,
        }
        apply_auth_opts(self, ydl_opts, job_id=None, use_cookies=use_cookies)
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(playlist_link, download=False)
        if not info:
            return []
        links = []
        for entry in info.get("entries", []):
            if not entry:
                continue
            video_id = entry.get("id")
            if video_id:
                links.append(f"https://www.youtube.com/watch?v={video_id}")
            elif entry.get("url"):
                links.append(entry["url"])
        return links

    def get_playlist_links(
        self, job_id: str, playlist_link: str, use_cookies: bool = False
    ) -> list[str]:
        try:
            return self._extract_playlist_entries(
                playlist_link, use_cookies=use_cookies
            )
        except Exception as e:
            self._log(job_id, f"Error leyendo playlist: {e}")
            return []

    def export_playlist_links(self, playlist_link: str) -> list[str]:
        try:
            return self._extract_playlist_entries(playlist_link, use_cookies=False)
        except Exception:
            return []

    def export_playlist_job(
        self,
        job_id: str,
        playlist_link: str,
        filename: str = "playlist",
        use_cookies: bool = False,
    ) -> tuple[int, list[str]]:
        self._check_cancelled(job_id)
        self._status(job_id, "📋 Leyendo playlist...")
        self._log(job_id, f"Exportando links: {playlist_link}")

        try:
            links = self.get_playlist_links(
                job_id, playlist_link, use_cookies=use_cookies
            )
        except DownloadCancelled:
            self._handle_cancel(job_id)
            self._job_result(job_id, 0, 0, [])
            return 0, []

        if job_manager.is_cancelled(job_id):
            self._handle_cancel(job_id)
            self._job_result(job_id, 0, 0, [])
            return 0, []

        total = len(links)
        safe = (filename or "playlist").strip() or "playlist"
        if not safe.lower().endswith(".txt"):
            safe += ".txt"

        if total == 0:
            self._log(job_id, "No se encontraron videos en la playlist")
            job_manager.emit(
                job_id,
                {"type": "export_result", "links": [], "filename": safe},
            )
            self._job_result(job_id, 0, 0, [])
            return 0, []

        self._check_cancelled(job_id)
        self._log(job_id, f"{total} links listos para exportar")
        self._item_progress(job_id, total, total, f"{total} videos")

        job_manager.emit(
            job_id,
            {"type": "export_result", "links": links, "filename": safe},
        )
        self._status(job_id, "✅ Lista lista")
        self._job_result(job_id, total, total, [])
        return total, []

    def download_playlist(
        self,
        job_id: str,
        playlist_link: str,
        is_song: bool,
        output_folder: str = None,
        prefer_spanish_audio: bool = False,
        spanish_subs: bool = False,
        quality: str = "1080",
        use_cookies: bool = False,
    ) -> tuple[int, list[str]]:
        self._check_cancelled(job_id)
        self._status(job_id, "📋 Leyendo playlist...")
        self._log(job_id, "Leyendo playlist ...")
        links = self.get_playlist_links(
            job_id, playlist_link, use_cookies=use_cookies
        )
        total = len(links)
        if total == 0:
            self._log(job_id, "No se encontraron videos en la playlist")
            self._job_result(job_id, 0, 0, [])
            return 0, []
        self._log(job_id, f"{total} elementos encontrados en la playlist")
        success = 0
        failed: list[str] = []
        for idx, link in enumerate(links, start=1):
            if job_manager.is_cancelled(job_id):
                self._log(
                    job_id, f"⏹ Cancelado — restantes omitidos ({total - idx + 1})"
                )
                failed.extend(links[idx - 1 :])
                break
            self._item_progress(job_id, idx, total, link)
            try:
                video_path = self.download_video(
                    job_id,
                    link,
                    is_video=not is_song,
                    output_folder=output_folder,
                    current=idx,
                    total=total,
                    prefer_spanish_audio=prefer_spanish_audio,
                    spanish_subs=spanish_subs,
                    quality=quality,
                    use_cookies=use_cookies,
                )
            except DownloadCancelled:
                self._handle_cancel(job_id)
                failed.extend(links[idx - 1 :])
                break
            ok = False
            if is_song and video_path:
                try:
                    mp3 = self.convert_to_mp3(
                        job_id, video_path, output_folder=output_folder
                    )
                    ok = bool(mp3)
                except DownloadCancelled:
                    self._handle_cancel(job_id)
                    failed.extend(links[idx - 1 :])
                    break
            elif video_path:
                ok = True
            if ok:
                success += 1
            else:
                if not job_manager.is_cancelled(job_id):
                    failed.append(link)
            if idx < total and not job_manager.is_cancelled(job_id):
                time.sleep(self.timeout_wait)
        self._job_result(job_id, success, total, failed)
        return success, failed