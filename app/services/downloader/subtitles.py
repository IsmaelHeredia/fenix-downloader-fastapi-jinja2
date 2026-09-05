from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.downloader.manager import VideoManager

def _original_auto_lang(auto: dict) -> str | None:
    for k in auto:
        if k.lower().endswith("-orig"):
            return k
    return None


def pick_sub_langs(info: dict) -> tuple[list[str], bool, str]:
    official = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    es_pref = ("es", "es-419", "es-ES", "es-MX", "es-US", "es-AR", "es-CL", "es-CO")
    en_pref = ("en", "en-US", "en-GB", "en-AU")

    def first_match(keys_map: dict, preferred: tuple[str, ...]) -> str | None:
        for lang in preferred:
            if lang in keys_map:
                return lang
        prefix = preferred[0].split("-")[0].lower()
        for k in keys_map:
            if k.lower().startswith(prefix):
                return k
        return None

    lang = first_match(official, es_pref)
    if lang:
        return [lang], False, f"español oficial ({lang})"

    orig_key = _original_auto_lang(auto)
    if orig_key and orig_key.lower().startswith("es"):
        return [orig_key], True, f"español automático original ({orig_key})"

    lang = first_match(official, en_pref)
    if lang:
        return [lang], False, f"inglés oficial ({lang})"

    if orig_key:
        return [orig_key], True, f"automático original, sin traducir ({orig_key})"

    return [], False, ""

def apply_subtitles_opts(
    manager: "VideoManager",
    ydl_opts: dict[str, Any],
    info: dict,
    job_id: str,
) -> dict[str, Any]:
    langs, use_auto, label = pick_sub_langs(info)
    if not langs:
        manager._log(
            job_id,
            "ℹ️ No hay subtítulos seguros en español ni inglés "
            "(se omite para evitar el 429 de traducción automática)",
        )
        ydl_opts.pop("writesubtitles", None)
        ydl_opts.pop("writeautomaticsub", None)
        ydl_opts.pop("subtitleslangs", None)
        ydl_opts.pop("sleep_interval_subtitles", None)
        return ydl_opts

    manager._log(job_id, f"📝 Subtítulos → {label}")
    ydl_opts["subtitleslangs"] = langs[:1]
    ydl_opts["subtitlesformat"] = "srt"
    ydl_opts["sleep_interval_subtitles"] = 8
    ydl_opts["ignoreerrors"] = True

    if use_auto:
        ydl_opts["writesubtitles"] = False
        ydl_opts["writeautomaticsub"] = True
    else:
        ydl_opts["writesubtitles"] = True
        ydl_opts["writeautomaticsub"] = False

    return ydl_opts

def strip_subtitle_opts(ydl_opts: dict[str, Any]) -> dict[str, Any]:
    for k in (
        "writesubtitles",
        "writeautomaticsub",
        "subtitleslangs",
        "subtitlesformat",
        "sleep_interval_subtitles",
    ):
        ydl_opts.pop(k, None)
    return ydl_opts