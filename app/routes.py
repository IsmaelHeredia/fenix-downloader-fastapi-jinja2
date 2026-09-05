import asyncio
import json
import threading

from fastapi import APIRouter, Request, Form
from fastapi.responses import StreamingResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates

from app.events import job_manager
from app.services.video_manager import VideoManager, DownloadCancelled

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
vm = VideoManager()


def _flag(value: str) -> bool:
    return (value or "").strip().lower() in ("1", "on", "true", "yes")


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.post("/download")
async def download(
    request: Request,
    links: str = Form(...),
    tipo: str = Form(...),
    output_name: str = Form(""),
    output_folder: str = Form(""),
    prefer_spanish_audio: str = Form(""),
    spanish_subs: str = Form(""),
    use_cookies: str = Form(""),
    quality: str = Form("1080"),
):
    link_list = [l.strip() for l in links.splitlines() if l.strip()]
    if not link_list:
        if tipo == "search":
            message = "Escribí al menos un nombre de canción."
        elif tipo == "convert":
            message = "Indicá la ruta del archivo a convertir."
        elif tipo == "export":
            message = "Pegá el link de la playlist."
        else:
            message = "Pegá al menos un link."
        return templates.TemplateResponse(
            "partials/error.html", {"request": request, "message": message}
        )

    prefer_es_audio = _flag(prefer_spanish_audio)
    want_es_subs = _flag(spanish_subs)
    want_cookies = _flag(use_cookies)
    quality = (quality or "1080").strip().lower()
    if quality not in ("max", "1080", "720"):
        quality = "1080"

    print(
        f"Tipo={tipo} quality={quality} "
        f"es_audio={prefer_es_audio} es_subs={want_es_subs} cookies={want_cookies}"
    )
    print(f"Links: {link_list}")

    job_id = job_manager.create_job()
    output_name = output_name or None
    output_folder = output_folder or None

    def run():
        success = 0
        total = len(link_list)
        failed_links: list[str] = []
        try:
            if tipo == "song":
                if len(link_list) == 1:
                    path = vm.download_video(
                        job_id,
                        link_list[0],
                        is_video=False,
                        output_name=output_name,
                        output_folder=output_folder,
                        current=1,
                        total=1,
                        prefer_spanish_audio=prefer_es_audio,
                        spanish_subs=want_es_subs,
                        quality=quality,
                        use_cookies=want_cookies,
                    )
                    if path:
                        mp3 = vm.convert_to_mp3(
                            job_id,
                            path,
                            output_name=output_name,
                            output_folder=output_folder,
                        )
                        if mp3:
                            success = 1
                        else:
                            failed_links.append(link_list[0])
                    else:
                        failed_links.append(link_list[0])
                    vm._job_result(job_id, success, 1, failed_links)
                else:
                    success, failed_links = vm.download_multiple(
                        job_id,
                        link_list,
                        is_song=True,
                        output_name=output_name,
                        output_folder=output_folder,
                        prefer_spanish_audio=prefer_es_audio,
                        spanish_subs=want_es_subs,
                        quality=quality,
                        use_cookies=want_cookies,
                    )

            elif tipo == "video":
                if len(link_list) == 1:
                    path = vm.download_video(
                        job_id,
                        link_list[0],
                        is_video=True,
                        output_name=output_name,
                        output_folder=output_folder,
                        current=1,
                        total=1,
                        prefer_spanish_audio=prefer_es_audio,
                        spanish_subs=want_es_subs,
                        quality=quality,
                        use_cookies=want_cookies,
                    )
                    if path:
                        success = 1
                    else:
                        failed_links.append(link_list[0])
                    vm._job_result(job_id, success, 1, failed_links)
                else:
                    success, failed_links = vm.download_multiple(
                        job_id,
                        link_list,
                        is_song=False,
                        output_name=output_name,
                        output_folder=output_folder,
                        prefer_spanish_audio=prefer_es_audio,
                        spanish_subs=want_es_subs,
                        quality=quality,
                        use_cookies=want_cookies,
                    )

            elif tipo == "search":
                success, failed_links = vm.search_and_download(
                    job_id,
                    link_list,
                    output_name=output_name,
                    output_folder=output_folder,
                    prefer_spanish_audio=prefer_es_audio,
                    spanish_subs=want_es_subs,
                    quality=quality,
                    use_cookies=want_cookies,
                )

            elif tipo == "playlist_songs":
                success, failed_links = vm.download_playlist(
                    job_id,
                    link_list[0],
                    is_song=True,
                    output_folder=output_folder,
                    prefer_spanish_audio=prefer_es_audio,
                    spanish_subs=want_es_subs,
                    quality=quality,
                    use_cookies=want_cookies,
                )

            elif tipo == "playlist_videos":
                success, failed_links = vm.download_playlist(
                    job_id,
                    link_list[0],
                    is_song=False,
                    output_folder=output_folder,
                    prefer_spanish_audio=prefer_es_audio,
                    spanish_subs=want_es_subs,
                    quality=quality,
                    use_cookies=want_cookies,
                )

            elif tipo == "convert":
                path = link_list[0]
                result = vm.convert_local_mp4_to_mp3(
                    job_id,
                    path,
                    output_name=output_name,
                    output_folder=output_folder,
                )
                if result:
                    success = 1
                else:
                    failed_links.append(path)
                vm._job_result(job_id, success, 1, failed_links)

            elif tipo == "export":
                fname = (output_name or "playlist").strip() or "playlist"
                n, failed_links = vm.export_playlist_job(
                    job_id,
                    link_list[0],
                    filename=fname,
                    use_cookies=want_cookies,
                )
                success = n

            else:
                vm._log(job_id, f"Tipo desconocido: {tipo}")
                vm._job_result(job_id, 0, total, link_list)

        except DownloadCancelled:
            vm._log(job_id, "⏹ Job cancelado")
            vm._job_result(job_id, success, total, failed_links or link_list)
        except Exception as e:
            if job_manager.is_cancelled(job_id):
                vm._log(job_id, "⏹ Job cancelado")
            else:
                vm._log(job_id, f"Error: {e}")
            vm._job_result(job_id, success, total, failed_links or link_list)
        finally:
            job_manager.close(job_id)

    threading.Thread(target=run, daemon=True).start()
    return templates.TemplateResponse(
        "partials/console.html", {"request": request, "job_id": job_id}
    )


@router.post("/cancel/{job_id}")
async def cancel_job(job_id: str):
    ok = job_manager.cancel(job_id)
    if not ok:
        return JSONResponse(
            {"ok": False, "message": "Job no encontrado o ya finalizado"},
            status_code=404,
        )
    return JSONResponse(
        {"ok": True, "job_id": job_id, "message": "Cancelación pedida"}
    )


@router.get("/export-playlist")
async def export_playlist(link: str, filename: str = "playlist"):
    links = await asyncio.to_thread(vm.export_playlist_links, link)
    if not links:
        content = "# No se encontraron videos en la playlist, o el link no es válido.\n"
    else:
        content = "\n".join(links) + "\n"
    safe_name = (filename or "playlist").strip() or "playlist"
    if not safe_name.lower().endswith(".txt"):
        safe_name += ".txt"
    return Response(
        content=content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/stream/{job_id}")
async def stream(job_id: str):
    q = job_manager.get_queue(job_id)

    async def event_generator():
        if q is None:
            yield f"data: {json.dumps({'type': 'log', 'message': 'Job no encontrado'})}\n\n"
            return
        while True:
            try:
                event = await asyncio.to_thread(q.get, timeout=1.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") == "done":
                    break
            except Exception:
                continue

    return StreamingResponse(event_generator(), media_type="text/event-stream")