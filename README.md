# Fenix Downloader

Una aplicación web moderna y ligera para descargar y convertir contenido de YouTube, orientada a un uso local y sencillo. Permite gestionar canciones en MP3, videos en MP4, listas de reproducción completas, búsqueda directa por nombre y conversión de archivos locales, con progreso en tiempo real y control total de cancelación.

## Stack Tecnológico

| Capa | Tecnologías |
|------|-------------|
| **Backend** | FastAPI + Jinja2 |
| **Frontend** | HTMX + Tailwind CSS + JavaScript |
| **Extracción y media** | yt-dlp + FFmpeg |

---

## Funcionalidades Principales

### Descarga desde YouTube
* **Links sueltos:** Soporte para uno o varios URLs simultáneos (canciones o videos).
* **Playlists:** Lectura y descarga secuencial de listas completas (audio o video).
* **Exportar playlist:** Genera un archivo `.txt` con todos los links de una playlist, sin necesidad de descargar el contenido.
* **Búsqueda integrada:** Búsqueda directa por nombre de canción (obteniendo el primer resultado relevante).
* **Calidad de video:** Selección entre 720p, 1080p (recomendado) o máxima calidad (evitando formatos AV1 pesados cuando aplica).
* **Audio en español:** Preferencia automática de doblaje si YouTube lo ofrece.
* **Subtítulos optimizados:** Español (oficial o automático) con *fallback* a inglés.
* **Cookies opcionales:** Soporte para formato Netscape (`data/cookies.txt` o variables de entorno) para evitar restricciones de edad, rate limits o bloqueos por región.

### Conversión Local
* **MP4 / Video / Audio a MP3:** Conversión flexible indicando la ruta del archivo en disco, con nombre y carpeta de salida personalizados, acompañado de una barra de progreso impulsada por FFmpeg.

### Experiencia de Uso
* **Interfaz dinámica (HTMX):** Sin recargas de página completas; incluye consolas de logs y barras de progreso independientes por cada *job*.
* **Cancelación cooperativa:** Un único botón inteligente para iniciar y detener la descarga o conversión en curso.
* **Tema Claro / Oscuro:** Diseño elegante con acentos verdes estilo *Gruvbox*, patrones de fondo sutiles y formularios totalmente adaptados.
* **Toasts y alertas sonoras:** Notificaciones visuales y de audio al finalizar una tarea (éxito, error, parcial o cancelada), incluso con la pestaña en segundo plano.
* **Omitir duplicados:** Si el archivo final (MP3/MP4) ya existe en el disco, la descarga se omite automáticamente.

---

## Capturas de Pantalla

![screenshot](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhd4K8zFv8rsY1WK5UQx_fOrYHwPnyCAwfMpafH8vDQKo565_PnZ88i6jIimokxC_9b1_QI8_ARDNYeddK4GTS8Z8twN4D-22_qkN9EKgCxO7hEEXIJVg6ZlTHXsIPHFvh2sqZprlxClN6XgoV1y6aVZXafuMplaa7sSi_AhqPzyZregKp8SZPlPpITpl0/s1476/1.png)

![screenshot](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEjtYdAOtD4nb7OOAeWWVrg3FudtPVuUaZvQ-l6FCalUPn0wxzuro4Vi2Ghx9_krPNYDlNDNgOgq0cLLm2Vhvgy4nucE0Z4mUKgs6zA8TUP33WVGbk7QhDAIEbR-OWr9vZEH4CyH4j9ApXc5mTZ1zS3z_SkNfMjDj6bSi_oltfaOn5c6CGIsqtWsk-MWvfs/s1386/2.png)

![screenshot](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhza0tKfBszf93VO6kM1CsEfvyzRPl9gXW3aoWZL8cuboNzIZTBeLWGazzjd9wVeadh2GSeWJ0sRH7qEbFA_v3qCsLEBdUWcvPRfo5ETlyVOos0r4H8DXY5c1P2fUIUStGxW60mUdetAioHd2pbyMfGD5JKrqTfMS1qms6_IKrQmXwH-KFJCX1ondECsAg/s1496/3.png)

![screenshot](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEhCT3LK-dQrAROrxLNb1EH5nbLDy_uGVJBiCFWNVjg3JVgNz3FpHxd1rBI20gJpU21doKFCnUD3IfyeI_K-D3xrmcdXdzAnbyvbGY7or3wTsVZzXTyvzpwAiwvjipgrOh_jqZTz-I9FVIXZnBkmottRNJ7-6qXAtDwzAZjP20jH0oDnU_htqyiPtY2ihAg/s1383/4.png)

![screenshot](https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEj8EMKr4RjL9IkU6-ZuuhvOj5HokkXVvyY1A2Q9ZLdBdPVrlC-gHZd802QnbgleMzYxLDFHxGSB76Hg0KU6MOT9r-H6Rmk72pF2YysaKBdc5FBAKMbiV9NtBvxHsxMAOkdSiQFadpq3A_YqqNhFcEWCZ3xfGSUW1K9dO2PvKrlCIuk98ySlkP3ohkLUxD4/s1358/5.png)

---

## Requisitos del Sistema

* **Python:** `3.10+` (se recomienda `3.11+`)
* **yt-dlp:** Con soporte para extensiones (`yt-dlp-ejs`)
* **Runtime de JavaScript (para YouTube moderno):** Deno 2.3 o superior (o Node 22 o superior)
* **Opcional:** `curl_cffi` para simulación de cliente (*impersonation* y reducción de errores 403)
* **FFmpeg y FFprobe:** Disponibles en el PATH del sistema

---

## Instalación y Configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/IsmaelHeredia/fenix-downloader-fastapi-jinja2.git
cd fenix-downloader-fastapi-jinja2
```

### 2. Crear entorno virtual e instalar dependencias

```bash
python -m venv .venv
# En Linux/macOS:
source .venv/bin/activate
# En Windows (CMD/PowerShell):
# .venv\Scripts\activate

pip install -U pip
pip install -r requirements.txt
pip install -U "yt-dlp[default]" yt-dlp-ejs "curl_cffi>=0.10"
```

### 3. Instalar Deno (Recomendado para la extracción de YouTube)

```bash
curl -fsSL https://deno.land/install.sh | sh
```

(Reiniciá tu terminal y comprobá la instalación con `deno --version`).

### 4. Ejecutar en modo desarrollo

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Abrí en tu navegador: http://127.0.0.1:8000