import tkinter as tk
from tkinter import ttk
import threading
import subprocess
import json
import os
import sys
import re
import urllib.request
import urllib.parse
import http.cookiejar
import io
import html
from pathlib import Path

VERSION = "2.4"  

try:
    from PIL import Image, ImageTk
    PILLOW = True
except ImportError:
    PILLOW = False

CARPETA = str(Path.home() / "Downloads" / "VidGet")
os.makedirs(CARPETA, exist_ok=True)
FLAG = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

BG       = "#0d0d11"
SURFACE  = "#16161e"
SURFACE2 = "#1e1e28"
BORDER   = "#2a2a3a"
ACCENT   = "#c8f545"
TEXT     = "#e8e8f0"
MUTED    = "#55556a"
ERROR    = "#ff5c72"
WARN     = "#ffb347"
SUCCESS  = "#c8f545"

F      = ("Segoe UI", 10)
F_SM   = ("Segoe UI", 9)
F_XS   = ("Segoe UI", 8)
F_BOLD = ("Segoe UI", 10, "bold")
F_LG   = ("Segoe UI", 22, "bold")


def mk_frame(parent, **kw):
    kw.setdefault("bg", BG)
    return tk.Frame(parent, **kw)

def mk_label(parent, text="", fg=TEXT, font=F, **kw):
    kw.setdefault("bg", BG)
    return tk.Label(parent, text=text, fg=fg, font=font, **kw)

def mk_btn(parent, text, cmd, bg=SURFACE2, fg=TEXT, font=F, **kw):
    return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                     font=font, relief="flat", cursor="hand2",
                     activebackground=BORDER, activeforeground=TEXT, bd=0, **kw)

def mk_sep(parent, padx=16, pady=8):
    f = tk.Frame(parent, bg=BORDER, height=1)
    f.pack(fill="x", padx=padx, pady=pady)
    return f

# ── Global ref para cookies ───────────────────────────────────────────────────
_url_panel_ref = None
def _get_app_cookies():
    if _url_panel_ref is not None:
        return _url_panel_ref.get_cookies_flags()
    return []

def interpretar_error(txt):
    t = (txt or "").lower()
    if "private" in t:                    return "El contenido es privado."
    if "copyright" in t:                  return "Bloqueado por derechos de autor."
    if "not available" in t:              return "El contenido no está disponible o fue eliminado."
    if "login" in t or "sign in" in t or "auth" in t:
        return "Requiere iniciar sesión.\nEl programa intentara con diferentes metodos automaticamente."
    if "geo" in t:                        return "Bloqueado en tu país."
    if "rate" in t and "limit" in t:      return "Demasiadas descargas. Espera unos minutos."
    if "unsupported url" in t:            return "Link no compatible con esta plataforma."
    if "network" in t or "timed out" in t: return "Error de conexión. Verifica tu internet."
    if "ffmpeg" in t:                     return "Falta ffmpeg.\nInstálalo con:  winget install ffmpeg"
    if "403" in t or "400" in t:
        return "Acceso denegado.\nEl programa intentara con diferentes metodos automaticamente."
    return "No se pudo descargar. El programa intenta todos los metodos disponibles automaticamente."

# ── Sitios que usan gallery-dl (mejor para imágenes) ─────────────────────────
SITIOS_GALLERY_DL = [
    "twitter.com", "x.com", "t.co",
    "instagram.com", "instagr.am",
    "pixiv.net", "artstation.com",
    "deviantart.com", "flickr.com",
    "reddit.com", "imgur.com",
    "pinterest.com", "tumblr.com",
    "danbooru.donmai.us", "gelbooru.com",
]

def es_sitio_imagen(url):
    u = url.lower()
    return any(s in u for s in SITIOS_GALLERY_DL)

def es_url_twitter(url):
    return "twitter.com" in url or "x.com" in url or "t.co" in url

def herramienta_disponible(nombre):
    try:
        r = subprocess.run([nombre, "--version"],
                           capture_output=True, timeout=5, creationflags=FLAG)
        return r.returncode == 0
    except FileNotFoundError:
        return False

def gallery_dl_disponible():
    return herramienta_disponible("gallery-dl")

def you_get_disponible():
    return herramienta_disponible("you-get")

def descargar_con_you_get(url, carpeta):
    """Fallback extra con you-get para sitios no soportados por los otros."""
    try:
        antes = set(str(p) for p in Path(carpeta).glob("**/*") if p.is_file())
        cmd = ["you-get", "--output-dir", carpeta, url]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, creationflags=FLAG)
        despues = set(str(p) for p in Path(carpeta).glob("**/*") if p.is_file())
        nuevos = sorted(despues - antes, key=os.path.getmtime)
        if nuevos:
            return nuevos, None
        return None, r.stderr or "Sin archivos descargados"
    except FileNotFoundError:
        return None, "you-get no instalado"
    except Exception as e:
        return None, str(e)

EXTS_IMG  = {".jpg",".jpeg",".png",".webp",".gif",".mp4",".bmp",".tiff",".avif"}
NAVEGADORES = ["chrome","brave","firefox","edge","opera","chromium","safari","vivaldi"]

def _archivos_en_carpeta(carpeta):
    return set(
        str(p) for p in Path(carpeta).rglob("*")
        if p.is_file() and p.suffix.lower() in EXTS_IMG
    )

def _navegadores_disponibles():
    """Detecta que navegadores estan instalados probando extraer sus cookies."""
    disponibles = []
    for nav in NAVEGADORES:
        try:
            r = subprocess.run(
                ["gallery-dl", "--cookies-from-browser", nav,
                 "--simulate", "https://www.instagram.com/"],
                capture_output=True, timeout=4, creationflags=FLAG
            )
            # Si no da error de "browser not found" lo consideramos disponible
            out = (r.stdout or b"") + (r.stderr or b"")
            out_str = out.decode("utf-8", errors="ignore").lower() if isinstance(out, bytes) else out.lower()
            if "browser" not in out_str or "not found" not in out_str:
                disponibles.append(nav)
        except:
            pass
    return disponibles if disponibles else NAVEGADORES  # si no detecta nada, prueba todos igual

def _detectar_sitio(url):
    """Clasifica el sitio para usar las opciones correctas."""
    u = url.lower()
    if any(x in u for x in ("twitter.com","x.com","t.co")):        return "twitter"
    if any(x in u for x in ("instagram.com","instagr.am")):         return "instagram"
    if "reddit.com" in u or "redd.it" in u:                         return "reddit"
    if "pixiv.net" in u:                                             return "pixiv"
    if "deviantart.com" in u:                                        return "deviantart"
    if "flickr.com" in u:                                            return "flickr"
    if "pinterest.com" in u:                                         return "pinterest"
    if "tumblr.com" in u:                                            return "tumblr"
    if "imgur.com" in u:                                             return "imgur"
    if "artstation.com" in u:                                        return "artstation"
    if any(x in u for x in ("danbooru","gelbooru","rule34","safebooru")): return "booru"
    return "generico"

def _opciones_sitio(sitio):
    """Retorna opciones extra de gallery-dl segun el sitio."""
    opts = {
        "twitter":     ["--option","extractor.twitter.size=orig",
                        "--option","extractor.twitter.retweets=false"],
        "instagram":   ["--option","extractor.instagram.videos=true",
                        "--option","extractor.instagram.stories=false"],
        "reddit":      ["--option","extractor.reddit.videos=true",
                        "--option","extractor.reddit.recursion=0"],
        "pixiv":       ["--option","extractor.pixiv.ugoira=true"],
        "imgur":       ["--option","extractor.imgur.mp4=true"],
    }
    return opts.get(sitio, [])

def _run_gallery_dl(url, carpeta, browser=None, sitio="generico", progreso=None):
    """
    Corre gallery-dl una vez con o sin cookies de un navegador especifico.
    Retorna lista de archivos nuevos o [] si fallo.
    """
    antes = _archivos_en_carpeta(carpeta)
    cmd = ["gallery-dl", "--directory", carpeta]
    if browser:
        cmd += ["--cookies-from-browser", browser]
    cmd += _opciones_sitio(sitio)
    cmd.append(url)

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, creationflags=FLAG)
        for linea in proc.stdout:
            l = linea.strip()
            if l and progreso:
                progreso(l)
        proc.wait()
    except Exception:
        return [], ""

    despues = _archivos_en_carpeta(carpeta)
    nuevos  = sorted(despues - antes, key=os.path.getmtime)
    # Capturar stderr tambien por si hay info util
    return nuevos, ""

def _run_ytdlp(url, carpeta, browser=None, progreso=None):
    """Corre yt-dlp con o sin cookies. Retorna True si descargo algo."""
    antes = _archivos_en_carpeta(carpeta)
    ck = ["--cookies-from-browser", browser] if browser else []
    salida = os.path.join(carpeta, "%(title)s.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "--newline", "-o", salida] + ck + [url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=60, creationflags=FLAG)
    except Exception:
        return False
    despues = _archivos_en_carpeta(carpeta)
    return len(despues - antes) > 0

def _run_you_get(url, carpeta, progreso=None):
    """Corre you-get. Retorna lista de nuevos archivos."""
    antes = _archivos_en_carpeta(carpeta)
    try:
        subprocess.run(["you-get", "--output-dir", carpeta, url],
                       capture_output=True, timeout=60, creationflags=FLAG)
    except Exception:
        return []
    despues = _archivos_en_carpeta(carpeta)
    return sorted(despues - antes, key=os.path.getmtime)

def _run_descarga_directa(url, carpeta):
    """Descarga directa via HTTP para Twitter (pbs.twimg.com)."""
    try:
        import urllib.request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "es-MX,es;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read().decode("utf-8", errors="ignore")
        pattern = "https://pbs.twimg.com/media/[A-Za-z0-9_-]+"
        found = re.findall(pattern, body)


        if not found:
            return None
        img_url = found[0].split("?")[0] + "?format=jpg&name=orig"
        fname = re.search(r"/media/([A-Za-z0-9_\-]+)", img_url)
        nombre = (fname.group(1) if fname else "img") + ".jpg"
        destino = os.path.join(carpeta, nombre)
        req2 = urllib.request.Request(img_url, headers=headers)
        with urllib.request.urlopen(req2, timeout=15) as r:
            data = r.read()
        if len(data) > 1000:
            with open(destino, "wb") as f:
                f.write(data)
            return destino
    except Exception:
        pass
    return None

def descargar_imagen_agresivo(url, carpeta, browser_preferido=None, progreso=None):
    """
    Intenta TODAS las combinaciones posibles hasta descargar la imagen.
    Retorna (archivo, metodo_que_funciono) o (None, None).
    """
    sitio = _detectar_sitio(url)

    def log(msg):
        if progreso:
            progreso(msg)

    # Construir lista de navegadores a probar
    # Primero el que eligio el usuario, luego todos los demas
    navs_a_probar = []
    if browser_preferido and browser_preferido not in ("", "ninguno"):
        navs_a_probar.append(browser_preferido)
    for nav in NAVEGADORES:
        if nav not in navs_a_probar:
            navs_a_probar.append(nav)

    # ── Paso 0: scraping universal (mas rapido, sin herramientas externas) ──────
    log("Buscando imagen en el HTML de la pagina...")
    archivo0, _ = _scrape_universal(url, carpeta)
    if archivo0 and os.path.exists(archivo0):
        return archivo0, "scraping directo"

    # Paso 0: scraping universal del HTML (sin herramientas, el mas rapido)
    log("Buscando imagen en el HTML...")
    archivo0, _ = _scrape_universal(url, carpeta)
    if archivo0 and os.path.exists(archivo0):
        return archivo0, "scraping directo"

    # Paso 0: scraping universal del HTML (sin herramientas, el mas rapido)
    log("Buscando imagen en el HTML...")
    archivo0, _ = _scrape_universal(url, carpeta)
    if archivo0 and os.path.exists(archivo0):
        return archivo0, "scraping directo"

    # Ronda 1: gallery-dl con cada navegador
    for nav in navs_a_probar:
        log(f"gallery-dl + {nav}...")
        archivos, _ = _run_gallery_dl(url, carpeta, browser=nav, sitio=sitio, progreso=None)
        if archivos:
            return archivos[0], f"gallery-dl + {nav}"

    # ── RONDA 2: gallery-dl sin cookies (contenido publico) ──────────────────
    log("gallery-dl sin cookies...")
    archivos, _ = _run_gallery_dl(url, carpeta, browser=None, sitio=sitio, progreso=None)
    if archivos:
        return archivos[0], "gallery-dl (publico)"

    # ── RONDA 3: yt-dlp con cada navegador ───────────────────────────────────
    for nav in navs_a_probar:
        log(f"yt-dlp + {nav}...")
        if _run_ytdlp(url, carpeta, browser=nav, progreso=None):
            nuevos = sorted(_archivos_en_carpeta(carpeta), key=os.path.getmtime)
            if nuevos:
                return nuevos[-1], f"yt-dlp + {nav}"

    # ── RONDA 4: yt-dlp sin cookies ──────────────────────────────────────────
    log("yt-dlp sin cookies...")
    if _run_ytdlp(url, carpeta, browser=None):
        nuevos = sorted(_archivos_en_carpeta(carpeta), key=os.path.getmtime)
        if nuevos:
            return nuevos[-1], "yt-dlp (publico)"

    # ── RONDA 5: you-get ─────────────────────────────────────────────────────
    log("you-get...")
    archivos_you = _run_you_get(url, carpeta, progreso=None)
    if archivos_you:
        return archivos_you[0], "you-get"

    # ── RONDA 6: descarga directa HTTP (Twitter) ──────────────────────────────
    if sitio == "twitter":
        log("descarga directa del tweet...")
        archivo = _run_descarga_directa(url, carpeta)
        if archivo:
            return archivo, "descarga directa"

    return None, None



# URLs que son logos/iconos a ignorar
_BLACKLIST_IMG = [
    "abs.twimg.com",          # iconos de Twitter
    "profile_images",         # fotos de perfil Twitter
    "default_profile",        # avatar default Twitter
    "favicon",
    "/icons/",
    "apple-touch-icon",
    "logo_white",
    "twitter_logo",
    "googlelogo",
    "site_logo",
    "brand_logo",
]

def _es_imagen_valida(url, sitio="generico"):
    u = url.lower()
    if any(b in u for b in _BLACKLIST_IMG):
        return False
    return True

def _extraer_urls_imagen(body, sitio="generico"):
    """Extrae URLs priorizando contenido real sobre logos/iconos."""
    import html as _html
    urls_cdn    = []   # MAXIMA prioridad: CDN de contenido real
    urls_meta   = []   # MEDIA: og:image (puede ser logo)
    urls_gen    = []   # BAJA: cualquier imagen en la pagina
    seen = set()

    def _add(lst, u):
        u = _html.unescape(u.strip()).replace("\u0026", "&")
        if u.startswith("http") and u not in seen and _es_imagen_valida(u, sitio):
            seen.add(u)
            lst.append(u)

    PRE = "https://"

    # ── 1. CDNs de contenido real (maxima prioridad) ──────────────────────────
    for pat in [
        PRE + "pbs[.]twimg[.]com/media/[A-Za-z0-9_-]+",
        PRE + "[a-z0-9.-]+cdninstagram[.]com/[^ \t<>]+",
        PRE + "[a-z0-9.-]+fbcdn[.]net/[^ \t<>]+",
        PRE + "i[.]redd[.]it/[A-Za-z0-9_-]+[.][a-z]+",
        PRE + "preview[.]redd[.]it/[^ \t<>]+",
        PRE + "i[.]imgur[.]com/[A-Za-z0-9]+[.][a-z]+",
        PRE + "i[.]pinimg[.]com/[^ \t<>]+",
        PRE + "[0-9]+[.]media[.]tumblr[.]com/[^ \t<>]+",
    ]:
        for m in re.finditer(pat, body, re.IGNORECASE):
            _add(urls_cdn, m.group(0))

    # JSON keys con imagen real
    for key in ['"display_url"', '"image_url"', '"media_url"', '"download_url"']:
        for m in re.finditer(key + r':"(https://[^"]+)"', body, re.IGNORECASE):
            u = m.group(1)
            if any(x in u.lower() for x in [".jpg",".png",".webp",".gif","cdninstagram","fbcdn","twimg","redd.it","imgur"]):
                _add(urls_cdn, u)

    # ── 2. og:image y meta tags (pueden ser logos para Twitter) ──────────────
    # Para Twitter, og:image suele ser el logo de X - lo ponemos al final
    metas = [
        ('property="og:image" content="', '"'),
        ('property="og:image:secure_url" content="', '"'),
        ('name="twitter:image" content="', '"'),
        ('"thumbnailUrl":"', '"'),
        ('"contentUrl":"', '"'),
    ]
    target = urls_gen if sitio == "twitter" else urls_meta
    for start_tag, end_tag in metas:
        idx = 0
        while True:
            i = body.lower().find(start_tag.lower(), idx)
            if i == -1: break
            i += len(start_tag)
            j = body.find(end_tag, i)
            if j == -1: break
            _add(target, body[i:j])
            idx = j

    # ── 3. Fallback: cualquier imagen directa ─────────────────────────────────
    for m in re.finditer("https?://[^ \t<>]+[.](?:jpg|jpeg|png|webp|gif)", body, re.IGNORECASE):
        _add(urls_gen, m.group(0))

    # Orden: CDN real > meta tags > fallback
    return urls_cdn + urls_meta + urls_gen

def _descargar_url_imagen(img_url, carpeta, headers):
    """Descarga una URL de imagen a la carpeta."""
    import urllib.request
    try:
        # Ajustes de calidad por CDN
        if "pbs.twimg.com/media" in img_url:
            img_url = img_url.split("?")[0] + "?format=jpg&name=orig"
        if "preview.redd.it" in img_url:
            img_url = img_url.replace("preview.redd.it", "i.redd.it").split("?")[0]
        if "pinimg.com" in img_url:
            img_url = re.sub(r"/[0-9]+x/", "/originals/", img_url)
        for thumb in ["s150x150", "s320x320", "s640x640"]:
            img_url = img_url.replace(thumb + "/", "")

        req = urllib.request.Request(img_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read()
            ct = r.headers.get("Content-Type", "")

        if len(data) < 1000:
            return None

        ext = ".jpg"
        if "png" in ct:        ext = ".png"
        elif "webp" in ct:     ext = ".webp"
        elif "gif" in ct:      ext = ".gif"
        elif img_url.lower().endswith(".png"):  ext = ".png"
        elif img_url.lower().endswith(".webp"): ext = ".webp"
        elif img_url.lower().endswith(".gif"):  ext = ".gif"

        slug = re.sub(r"[^A-Za-z0-9_-]", "_",
                      img_url.split("/")[-1].split("?")[0])[:60] or "imagen"
        destino = os.path.join(carpeta, slug + ext)
        with open(destino, "wb") as f:
            f.write(data)
        return destino
    except Exception:
        return None


def _scrape_universal(url, carpeta):
    """
    Descarga imagen de CUALQUIER pagina extrayendo URLs del HTML.
    No requiere herramientas externas. Es el metodo mas rapido.
    """
    import urllib.request
    H = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
        "Referer": url,
    }
    try:
        req = urllib.request.Request(url, headers=H)
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return None, str(e)

    sitio_det = _detectar_sitio(url)
    img_urls = _extraer_urls_imagen(body, sitio=sitio_det)
    if not img_urls:
        return None, "No se encontraron imagenes en la pagina"

    for img_url in img_urls:
        archivo = _descargar_url_imagen(img_url, carpeta, H)
        if archivo:
            return archivo, None

    return None, f"Se encontraron {len(img_urls)} URLs pero ninguna descargo correctamente"


def segundos_a_hms(seg):
    seg = int(seg)
    h, rem = divmod(seg, 3600)
    m, s   = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def detectar_tipo(info):
    """Devuelve 'video', 'audio', 'gif' o 'imagen' según la info de yt-dlp."""
    ext      = (info.get("ext") or "").lower()
    vcodec   = (info.get("vcodec") or "").lower()
    acodec   = (info.get("acodec") or "").lower()
    dur      = info.get("duration", 0) or 0
    category = (info.get("categories") or [""])[0].lower() if info.get("categories") else ""

    if ext == "gif":                          return "gif"
    if ext in ("jpg","jpeg","png","webp","bmp","tiff"): return "imagen"
    if vcodec == "none" and acodec != "none": return "audio"
    if dur > 0 or vcodec not in ("none",""):  return "video"
    return "imagen"


# ═════════════════════════════════════════════════════════════════════════════
#  Progress Panel
# ═════════════════════════════════════════════════════════════════════════════

# =============================================================================
#  Sistema de actualizaciones automaticas
#  Revisa GitHub Releases para ver si hay version nueva
# =============================================================================

# Cambia esto por tu usuario y repo de GitHub cuando lo crees
GITHUB_USER  = "UwUMADDOX"
GITHUB_REPO  = "VidGet"
GITHUB_API   = "https://api.github.com/repos/" + GITHUB_USER + "/" + GITHUB_REPO + "/releases/latest"

def _version_tuple(v):
    try:
        return tuple(int(x) for x in str(v).strip("v").split("."))
    except Exception:
        return (0,)

def verificar_actualizacion():
    """Retorna (hay_update, version_nueva, url_exe) o (False, None, None)."""
    if GITHUB_USER == "TU_USUARIO_GITHUB":
        return False, None, None
    try:
        import urllib.request, json as _j
        req = urllib.request.Request(
            GITHUB_API,
            headers={"User-Agent": "VidGet-Updater/1.0",
                     "Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = _j.loads(r.read().decode())
        version_remota = data.get("tag_name", "0").lstrip("v")
        if _version_tuple(version_remota) > _version_tuple(VERSION):
            assets = data.get("assets", [])
            url = next((a["browser_download_url"] for a in assets
                        if a["name"].lower().endswith(".exe")),
                       "https://github.com/" + GITHUB_USER + "/" + GITHUB_REPO + "/releases/latest/download/VidGet.exe")
            return True, version_remota, url
    except Exception:
        pass
    return False, None, None

def descargar_actualizacion(url, progreso_cb=None):
    """Descarga nuevo .exe a archivo temporal. Retorna ruta o None."""
    try:
        import urllib.request, tempfile
        tmp = tempfile.mktemp(suffix=".exe", prefix="VidGet_upd_")
        def hook(c, bs, ts):
            if ts > 0 and progreso_cb:
                progreso_cb(min(100, int(c * bs * 100 / ts)))
        urllib.request.urlretrieve(url, tmp, hook)
        return tmp
    except Exception:
        return None

def aplicar_actualizacion(nuevo_exe):
    """Reemplaza el .exe actual y reinicia."""
    if not getattr(sys, "frozen", False): return
    exe_actual = sys.executable
    import tempfile
    bat = "@echo off\ntimeout /t 2 /nobreak > nul\nmove /y \"" + nuevo_exe + "\" \"" + exe_actual + "\"\nstart \"" + "\" \"" + exe_actual + "\"\ndel \"%~f0\"\n"
    bp = tempfile.mktemp(suffix=".bat")
    with open(bp, "w") as f:
        f.write(bat)
    import subprocess as _sp
    _sp.Popen(["cmd","/c",bp], creationflags=_sp.CREATE_NO_WINDOW | _sp.DETACHED_PROCESS)
    sys.exit(0)

class ProgressPanel(tk.Frame):
    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG); super().__init__(parent, **kw)
        self._build()

    def _build(self):
        self.lbl_estado = mk_label(self, "", fg=MUTED, font=F_SM)
        self.lbl_estado.pack(anchor="w")
        style = ttk.Style(); style.theme_use("default")
        style.configure("VG.Horizontal.TProgressbar",
                        troughcolor=SURFACE2, background=ACCENT, thickness=6, borderwidth=0)
        self.barra = ttk.Progressbar(self, style="VG.Horizontal.TProgressbar", mode="determinate")
        self.barra.pack(fill="x", pady=(5,3))
        meta = mk_frame(self); meta.pack(fill="x")
        self.lbl_vel  = mk_label(meta, "", fg=MUTED, font=F_SM); self.lbl_vel.pack(side="left")
        self.lbl_eta  = mk_label(meta, "", fg=MUTED, font=F_SM); self.lbl_eta.pack(side="left", padx=(14,0))
        self.lbl_size = mk_label(meta, "", fg=MUTED, font=F_SM); self.lbl_size.pack(side="left", padx=(14,0))
        self.lbl_resultado = mk_label(self, "", fg=SUCCESS, font=F_SM, wraplength=500, justify="left")
        self.lbl_resultado.pack(anchor="w", pady=(6,0))

    def reset(self):
        self.barra["value"] = 0
        for w in [self.lbl_vel, self.lbl_eta, self.lbl_size, self.lbl_estado, self.lbl_resultado]:
            w.config(text="")

    def set_estado(self, txt, color=MUTED):    self.lbl_estado.config(text=txt, fg=color)
    def set_resultado(self, txt, color=SUCCESS): self.lbl_resultado.config(text=txt, fg=color)

    def update_dl(self, pct, vel=None, eta=None, size=None):
        self.barra["value"] = pct
        self.set_estado(f"Descargando...  {int(pct)}%", MUTED)
        if vel:  self.lbl_vel.config(text=f"⚡ {vel}")
        if eta and eta != "Unknown": self.lbl_eta.config(text=f"⏱ {eta}")
        if size: self.lbl_size.config(text=f"📦 {size}")


# ═════════════════════════════════════════════════════════════════════════════
#  Download runner
# ═════════════════════════════════════════════════════════════════════════════
def run_download(cmd, progress_panel, on_done, on_error):
    err_lines = []
    try:
        proceso = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, creationflags=FLAG)
        for l in proceso.stdout:
            l = l.strip()
            if "[download]" in l and "%" in l:
                pct  = re.search(r'(\d+\.?\d*)%', l)
                vel  = re.search(r'at\s+([\d.]+\w+/s)', l)
                eta  = re.search(r'ETA\s+(\S+)', l)
                size = re.search(r'of\s+([\d.]+\s*\w+)', l)
                progress_panel.after(0, lambda p=float(pct.group(1)) if pct else 0,
                                     v=vel.group(1) if vel else None,
                                     e=eta.group(1) if eta else None,
                                     s=size.group(1) if size else None:
                                     progress_panel.update_dl(p, v, e, s))
            elif "error" in l.lower(): err_lines.append(l)
        stderr_txt = proceso.stderr.read() or ""
        proceso.wait()
        if proceso.returncode == 0: progress_panel.after(0, on_done)
        else:
            msg = interpretar_error("\n".join(err_lines) + "\n" + stderr_txt)
            progress_panel.after(0, lambda m=msg: on_error(m))
    except FileNotFoundError:
        progress_panel.after(0, lambda: on_error("yt-dlp no instalado. Ejecuta INSTALAR.bat."))
    except Exception as e:
        progress_panel.after(0, lambda err=str(e): on_error(err))


# ═════════════════════════════════════════════════════════════════════════════
#  Panel avanzado: Video/Audio
# ═════════════════════════════════════════════════════════════════════════════
class PanelVideoAudio(tk.Frame):
    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG); super().__init__(parent, **kw)
        self._build()

    def _build(self):
        pad = {"padx": 12}
        mk_label(self, "Calidad:", fg=MUTED, font=F_XS).pack(anchor="w", pady=(10,4), **pad)
        self.calidad = tk.StringVar(value="best")
        row = mk_frame(self); row.pack(fill="x", **pad)
        for txt, val in [("Mejor", "best"), ("1080p","1080"), ("720p","720"), ("480p","480")]:
            tk.Radiobutton(row, text=txt, variable=self.calidad, value=val, bg=BG, fg=TEXT,
                           selectcolor=BG, activebackground=BG, font=F_SM,
                           cursor="hand2").pack(side="left", padx=(0,10))
        mk_label(self, "Tipo:", fg=MUTED, font=F_XS).pack(anchor="w", pady=(8,4), **pad)
        self.tipo = tk.StringVar(value="video")
        row2 = mk_frame(self); row2.pack(fill="x", **pad)
        for txt, val in [("Video (MP4)","video"), ("Solo audio (MP3)","audio")]:
            tk.Radiobutton(row2, text=txt, variable=self.tipo, value=val, bg=BG, fg=TEXT,
                           selectcolor=BG, activebackground=BG, font=F_SM,
                           cursor="hand2").pack(side="left", padx=(0,12))

    def set_tipo(self, tipo):
        if tipo == "audio": self.tipo.set("audio")
        else: self.tipo.set("video")

    def build_cmd(self, url):
        ck = _get_app_cookies()
        salida = os.path.join(CARPETA, "%(title)s.%(ext)s")
        if self.tipo.get() == "audio":
            return ["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "0",
                    "--no-playlist", "--newline", "-o", salida] + ck + [url]
        fmts = {"best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best",
                "720":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
                "480":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best"}
        return ["yt-dlp", "-f", fmts.get(self.calidad.get(), fmts["best"]),
                "--merge-output-format", "mp4", "--no-playlist",
                "--newline", "-o", salida] + ck + [url]


# ═════════════════════════════════════════════════════════════════════════════
#  Panel avanzado: GIF
# ═════════════════════════════════════════════════════════════════════════════
class PanelGIF(tk.Frame):
    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG); super().__init__(parent, **kw)
        self._es_gif_directo = False; self._duracion = 0
        self._build()

    def _build(self):
        pad = {"padx": 12}
        self.lbl_aviso = mk_label(self, "", fg=MUTED, font=F_SM, wraplength=440, justify="left")
        self.lbl_aviso.pack(anchor="w", pady=(8,4), **pad)

        self.panel_recorte = mk_frame(self)
        mk_label(self.panel_recorte, "Recorte:", fg=MUTED, font=F_XS).pack(anchor="w", pady=(0,4), **pad)
        row = mk_frame(self.panel_recorte); row.pack(fill="x", **pad)
        mk_label(row, "Inicio:", fg=TEXT, font=F_SM).pack(side="left")
        self.inicio_var = tk.StringVar(value="0")
        tk.Entry(row, textvariable=self.inicio_var, width=6, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=F, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT).pack(side="left", ipady=5, ipadx=5, padx=(4,12))
        mk_label(row, "Fin:", fg=TEXT, font=F_SM).pack(side="left")
        self.fin_var = tk.StringVar(value="10")
        tk.Entry(row, textvariable=self.fin_var, width=6, bg=SURFACE, fg=TEXT,
                 insertbackground=TEXT, relief="flat", font=F, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT).pack(side="left", ipady=5, ipadx=5, padx=(4,0))
        self.lbl_dur = mk_label(self.panel_recorte, "", fg=MUTED, font=F_XS)
        self.lbl_dur.pack(anchor="w", **pad, pady=(3,0))
        mk_label(self.panel_recorte, "Resolución:", fg=MUTED, font=F_XS).pack(anchor="w", pady=(6,4), **pad)
        self.res = tk.StringVar(value="480")
        row_r = mk_frame(self.panel_recorte); row_r.pack(fill="x", **pad)
        for txt, val in [("480p","480"), ("360p","360"), ("240p","240")]:
            tk.Radiobutton(row_r, text=txt, variable=self.res, value=val, bg=BG, fg=TEXT,
                           selectcolor=BG, activebackground=BG, font=F_SM,
                           cursor="hand2").pack(side="left", padx=(0,12))
        self.panel_recorte.pack(fill="x")

    def on_info(self, info):
        ext = info.get("ext",""); dur = info.get("duration",0) or 0
        self._duracion = dur; self._es_gif_directo = (ext == "gif")
        if self._es_gif_directo:
            self.panel_recorte.pack_forget()
            self.lbl_aviso.config(text="✅  GIF directo, se descarga sin conversión.", fg=SUCCESS)
        else:
            self.lbl_aviso.config(text="Define el fragmento a convertir en GIF.", fg=MUTED)
            self.panel_recorte.pack(fill="x", after=self.lbl_aviso)
            if dur:
                self.fin_var.set(str(min(10, int(dur))))
                self.lbl_dur.config(text=f"Duración total: {segundos_a_hms(dur)}")

    def on_clear(self):
        self._es_gif_directo = False; self._duracion = 0
        self.lbl_aviso.config(text=""); self.lbl_dur.config(text="")
        self.panel_recorte.pack(fill="x", after=self.lbl_aviso)

    def build_cmd(self, url):
        ck = _get_app_cookies()
        salida = os.path.join(CARPETA, "%(title)s.%(ext)s")
        if self._es_gif_directo:
            return ["yt-dlp", "--no-playlist", "--newline", "-o", salida] + ck + [url], None
        try:
            inicio = float(self.inicio_var.get()); fin = float(self.fin_var.get())
        except ValueError:
            return None, "Inicio y Fin deben ser números."
        if fin <= inicio: return None, "Fin debe ser mayor que inicio."
        if fin - inicio > 120: return None, "Máximo 2 minutos por GIF."
        res_val = self.res.get()
        salida_gif = os.path.join(CARPETA, "%(title)s.gif")
        cmd = ["yt-dlp", "--download-sections", f"*{inicio}-{fin}", "--no-playlist",
               "--newline", "--recode-video", "gif", "--postprocessor-args",
               f"ffmpeg:-vf scale={res_val}:-1:flags=lanczos,fps=12",
               "-o", salida_gif] + ck + [url]
        return cmd, None


# ═════════════════════════════════════════════════════════════════════════════
#  Panel avanzado: Imagen
# ═════════════════════════════════════════════════════════════════════════════
class PanelImagen(tk.Frame):
    """
    Panel avanzado de imagen con 4 modos:
    - Descargar: resolución personalizada
    - Recortar:  márgenes en px
    - Comprimir: calidad JPEG
    - Convertir: cambio de formato + convertidor de archivos locales
    """
    def __init__(self, parent, get_url_fn, progress, **kw):
        kw.setdefault("bg", BG); super().__init__(parent, **kw)
        self.get_url  = get_url_fn
        self.progress = progress
        self._es_video   = False
        self._duracion   = 0
        self._frame_img  = None
        self._build()

    def _build(self):
        pad = {"padx": 14}

        # Aviso dinámico (video vs imagen)
        self.lbl_aviso = mk_label(self, "", fg=MUTED, font=F_SM,
                                  wraplength=490, justify="left")
        self.lbl_aviso.pack(anchor="w", pady=(10,4), **pad)

        # Panel slider fotograma (solo para videos)
        self.panel_slider = mk_frame(self)
        sl_row = mk_frame(self.panel_slider)
        sl_row.pack(fill="x", **pad)
        self.slider_var = tk.DoubleVar(value=0)
        self.slider = ttk.Scale(sl_row, from_=0, to=100,
                                variable=self.slider_var, orient="horizontal",
                                command=lambda v: self.lbl_seg.config(
                                    text=segundos_a_hms(float(v))))
        self.slider.pack(side="left", fill="x", expand=True)
        self.lbl_seg = mk_label(sl_row, "0s", fg=TEXT, font=F_SM)
        self.lbl_seg.pack(side="left", padx=(8,0))
        # Mini preview fotograma
        self.prev_box2 = mk_frame(self.panel_slider, bg=SURFACE, height=90)
        self.prev_box2.pack(fill="x", **pad, pady=(6,0))
        self.prev_box2.pack_propagate(False)
        self.lbl_ph2 = mk_label(self.prev_box2,
            "Mueve el slider para ver el fotograma",
            fg=MUTED, font=F_XS, bg=SURFACE)
        self.lbl_ph2.pack(expand=True)
        self.lbl_fi = tk.Label(self.prev_box2, bg=SURFACE)
        mk_btn(self.panel_slider, "🔍  Ver fotograma",
               self._preview_frame, padx=10, pady=5).pack(
               anchor="w", **pad, pady=(6,0))

        # ── Sub-pestañas ──────────────────────────────────────────────────────
        style = ttk.Style()
        style.configure("Img2.TNotebook", background=BG,
                        borderwidth=0, tabmargins=[0,4,0,0])
        style.configure("Img2.TNotebook.Tab",
                        background="#111118", foreground=MUTED,
                        font=("Segoe UI", 9, "bold"),
                        padding=[16, 8], borderwidth=0)
        style.map("Img2.TNotebook.Tab",
                  background=[("selected", SURFACE2), ("active", "#1e1e2a")],
                  foreground=[("selected", ACCENT), ("active", TEXT)])

        self.sub_nb = ttk.Notebook(self, style="Img2.TNotebook")
        self.sub_nb.pack(fill="both", expand=True, padx=14, pady=(8,4))

        self._build_tab_dl()
        self._build_tab_recortar()
        self._build_tab_comprimir()
        self._build_tab_convertir()



    # ── Tab: Descargar ────────────────────────────────────────────────────────
    def _build_tab_dl(self):
        f = mk_frame(self.sub_nb, bg=SURFACE)
        self.sub_nb.add(f, text="⬇  Descargar")

        mk_label(f, "Resolución de salida:", fg=MUTED, font=F_XS, bg=SURFACE).pack(
            anchor="w", padx=12, pady=(10,4))
        self.dl_res = tk.StringVar(value="original")
        row = mk_frame(f, bg=SURFACE); row.pack(fill="x", padx=12)
        for txt, val in [("Original","original"),("1920px","1920"),
                         ("1280px","1280"),("800px","800"),("400px","400")]:
            tk.Radiobutton(row, text=txt, variable=self.dl_res, value=val,
                           bg=SURFACE, fg=TEXT, selectcolor=SURFACE,
                           activebackground=SURFACE, font=F_SM,
                           cursor="hand2").pack(side="left", padx=(0,8))

        row2 = mk_frame(f, bg=SURFACE); row2.pack(fill="x", padx=12, pady=(8,4))
        mk_label(row2, "Ancho personalizado:", fg=MUTED, font=F_XS, bg=SURFACE).pack(side="left")
        self.dl_custom = tk.StringVar()
        self.dl_custom.trace_add("write",
            lambda *_: self.dl_res.set("custom") if self.dl_custom.get() else None)
        tk.Entry(row2, textvariable=self.dl_custom, width=6,
                 bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat",
                 font=F, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT).pack(
                 side="left", ipady=5, ipadx=5, padx=(6,4))
        mk_label(row2, "px", fg=MUTED, font=F_XS, bg=SURFACE).pack(side="left")

        mk_label(f, "Formato de salida:", fg=MUTED, font=F_XS, bg=SURFACE).pack(
            anchor="w", padx=12, pady=(8,4))
        self.dl_fmt = tk.StringVar(value="original")
        row3 = mk_frame(f, bg=SURFACE); row3.pack(fill="x", padx=12, pady=(0,10))
        for txt, val in [("Original","original"),("JPG","JPG"),("PNG","PNG"),("WEBP","WEBP")]:
            tk.Radiobutton(row3, text=txt, variable=self.dl_fmt, value=val,
                           bg=SURFACE, fg=TEXT, selectcolor=SURFACE,
                           activebackground=SURFACE, font=F_SM,
                           cursor="hand2").pack(side="left", padx=(0,8))

    # ── Tab: Recortar ─────────────────────────────────────────────────────────
    def _build_tab_recortar(self):
        f = mk_frame(self.sub_nb, bg=SURFACE)
        self.sub_nb.add(f, text="✂  Recortar")
        if not PILLOW:
            mk_label(f, "Requiere Pillow.", fg=WARN, font=F_SM, bg=SURFACE).pack(padx=12, pady=16)
            return
        mk_label(f, "Píxeles a recortar por lado:", fg=MUTED,
                 font=F_XS, bg=SURFACE).pack(anchor="w", padx=12, pady=(10,6))
        grid = mk_frame(f, bg=SURFACE); grid.pack(padx=12, anchor="w")
        self.crop = {}
        for i, lado in enumerate(["Arriba","Abajo","Izquierda","Derecha"]):
            mk_label(grid, lado+":", fg=TEXT, font=F_SM, bg=SURFACE).grid(
                row=i//2, column=(i%2)*2, sticky="w", padx=(0,4), pady=4)
            v = tk.StringVar(value="0")
            tk.Entry(grid, textvariable=v, width=6,
                     bg=BG, fg=TEXT, insertbackground=TEXT, relief="flat",
                     font=F, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=ACCENT).grid(
                     row=i//2, column=(i%2)*2+1, padx=(0,16), pady=4, ipady=5)
            self.crop[lado] = v
        mk_label(f, "Guarda como PNG nuevo.", fg=MUTED, font=F_XS, bg=SURFACE).pack(
            anchor="w", padx=12, pady=(6,0))

    # ── Tab: Comprimir ────────────────────────────────────────────────────────
    def _build_tab_comprimir(self):
        f = mk_frame(self.sub_nb, bg=SURFACE)
        self.sub_nb.add(f, text="🗜  Comprimir")
        if not PILLOW:
            mk_label(f, "Requiere Pillow.", fg=WARN, font=F_SM, bg=SURFACE).pack(padx=12, pady=16)
            return
        mk_label(f, "Calidad JPEG (10 = máxima compresión / 100 = sin pérdida):",
                 fg=MUTED, font=F_XS, bg=SURFACE).pack(anchor="w", padx=12, pady=(10,4))
        self.calidad_img = tk.IntVar(value=85)
        sl_row = mk_frame(f, bg=SURFACE); sl_row.pack(fill="x", padx=12)
        sl = ttk.Scale(sl_row, from_=10, to=100, variable=self.calidad_img,
                       orient="horizontal",
                       command=lambda v: self.lbl_q.config(text=f"{int(float(v))}%"))
        sl.pack(side="left", fill="x", expand=True)
        self.lbl_q = mk_label(sl_row, "85%", fg=ACCENT, font=F_BOLD, bg=SURFACE)
        self.lbl_q.pack(side="left", padx=(10,0))
        mk_label(f, "Guarda como JPG optimizado.", fg=MUTED, font=F_XS, bg=SURFACE).pack(
            anchor="w", padx=12, pady=(6,0))

    # ── Tab: Convertir ────────────────────────────────────────────────────────
    def _build_tab_convertir(self):
        f = mk_frame(self.sub_nb, bg=SURFACE)
        self.sub_nb.add(f, text="🔄  Convertir")
        if not PILLOW:
            mk_label(f, "Requiere Pillow.", fg=WARN, font=F_SM, bg=SURFACE).pack(padx=12, pady=16)
            return

        # Formato destino
        mk_label(f, "Convertir a:", fg=MUTED, font=F_XS, bg=SURFACE).pack(
            anchor="w", padx=12, pady=(10,4))
        self.formato_conv = tk.StringVar(value="PNG")
        row = mk_frame(f, bg=SURFACE); row.pack(fill="x", padx=12)
        for fmt in ["PNG","JPG","WEBP","BMP","TIFF","ICO"]:
            tk.Radiobutton(row, text=fmt, variable=self.formato_conv, value=fmt,
                           bg=SURFACE, fg=TEXT, selectcolor=SURFACE,
                           activebackground=SURFACE, font=F_SM,
                           cursor="hand2").pack(side="left", padx=(0,8))

        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", padx=12, pady=10)

        # Convertidor de archivos locales ya descargados
        tk.Frame(f, bg=BORDER, height=1).pack(fill="x", padx=12, pady=(6,10))
        mk_label(f, "── Convertir archivos ya descargados ──",
                 fg=MUTED, font=("Segoe UI", 8, "bold"), bg=SURFACE).pack(anchor="w", padx=12, pady=(0,4))
        mk_label(f, "Selecciona imágenes de tu carpeta VidGet y conviértelas al formato de arriba.",
                 fg=MUTED, font=F_XS, bg=SURFACE, wraplength=420, justify="left").pack(anchor="w", padx=12, pady=(0,6))

        self.lbl_archivos_sel = mk_label(f, "Ningún archivo seleccionado",
                                          fg=MUTED, font=F_XS, bg=SURFACE)
        self.lbl_archivos_sel.pack(anchor="w", padx=12)

        btns = mk_frame(f, bg=SURFACE); btns.pack(fill="x", padx=12, pady=(6,4))
        tk.Button(btns, text="📂  Seleccionar imágenes",
                  command=self._seleccionar_archivos_locales,
                  bg=SURFACE2, fg=TEXT, font=("Segoe UI", 10),
                  relief="flat", cursor="hand2",
                  activebackground=BORDER,
                  pady=9, padx=14).pack(side="left")
        tk.Button(btns, text="📁  Abrir carpeta VidGet",
                  command=self._abrir_carpeta_vidget,
                  bg=SURFACE2, fg=MUTED, font=("Segoe UI", 10),
                  relief="flat", cursor="hand2",
                  activebackground=BORDER,
                  pady=9, padx=14).pack(side="left", padx=(10,0))

        self._archivos_locales = []

        # Botón de conversión grande y claro
        tk.Button(f, text="🔄  Convertir archivos seleccionados",
                  command=self._convertir_archivos_locales,
                  bg="#1a2a00", fg=ACCENT,
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2",
                  activebackground="#2a3f00",
                  activeforeground=ACCENT,
                  pady=10).pack(fill="x", padx=12, pady=(6,10))

        # Barra de progreso local para conversión
        self.conv_progress_lbl = mk_label(f, "", fg=MUTED, font=F_XS, bg=SURFACE)
        self.conv_progress_lbl.pack(anchor="w", padx=12, pady=(0,6))

    def _seleccionar_archivos_locales(self):
        from tkinter import filedialog
        archivos = filedialog.askopenfilenames(
            title="Selecciona imágenes",
            initialdir=CARPETA,
            filetypes=[
                ("Imágenes", "*.jpg *.jpeg *.png *.webp *.gif *.bmp *.tiff *.avif"),
                ("Todos", "*.*")
            ]
        )
        if archivos:
            self._archivos_locales = list(archivos)
            n = len(archivos)
            nombres = ", ".join(os.path.basename(a) for a in archivos[:3])
            if n > 3: nombres += f" (+{n-3} más)"
            self.lbl_archivos_sel.config(
                text=f"{n} archivo(s): {nombres}", fg=SUCCESS)

    def _abrir_carpeta_vidget(self):
        if sys.platform == "win32": os.startfile(CARPETA)
        elif sys.platform == "darwin": subprocess.Popen(["open", CARPETA])
        else: subprocess.Popen(["xdg-open", CARPETA])

    def _convertir_archivos_locales(self):
        if not self._archivos_locales:
            self.conv_progress_lbl.config(
                text="⚠  Selecciona archivos primero.", fg=WARN)
            return
        if not PILLOW:
            self.conv_progress_lbl.config(text="❌  Pillow no instalado.", fg=ERROR)
            return
        threading.Thread(target=self._conv_thread, daemon=True).start()

    def _conv_thread(self):
        fmt     = self.formato_conv.get()
        ext_map = {"PNG":".png","JPG":".jpg","WEBP":".webp",
                   "BMP":".bmp","TIFF":".tiff","ICO":".ico"}
        ext     = ext_map.get(fmt, ".png")
        total   = len(self._archivos_locales)
        ok = fail = 0

        for i, path in enumerate(self._archivos_locales, 1):
            self.after(0, lambda i=i, t=total, f=fmt:
                self.conv_progress_lbl.config(
                    text=f"Convirtiendo {i}/{t} → {f}...", fg=MUTED))
            try:
                img      = Image.open(path)
                save_fmt = "JPEG" if fmt == "JPG" else fmt
                if fmt in ("JPG","BMP"): img = img.convert("RGB")
                elif fmt == "ICO":       img = img.resize((256,256), Image.LANCZOS)
                elif fmt == "PNG":       img = img.convert("RGBA")
                base    = os.path.splitext(os.path.basename(path))[0]
                destino = os.path.join(CARPETA, base + "_" + fmt.lower() + ext)
                kw = {"quality": self.calidad_img.get()} if fmt == "JPG" else {}
                img.save(destino, save_fmt, **kw)
                ok += 1
            except Exception:
                fail += 1

        msg = f"✅  {ok}/{total} convertidos a {fmt}"
        if fail: msg += f"  ({fail} fallaron)"
        color = SUCCESS if not fail else WARN
        self.after(0, lambda: self.conv_progress_lbl.config(text=msg, fg=color))
        self.after(0, lambda: self.lbl_archivos_sel.config(
            text="Ningún archivo seleccionado", fg=MUTED))
        self._archivos_locales = []

    # ── Info desde link ───────────────────────────────────────────────────────
    def on_info(self, info):
        ext = info.get("ext",""); dur = info.get("duration",0) or 0
        self._duracion = dur
        es_img = ext in ("jpg","jpeg","png","webp","bmp","tiff")
        if es_img:
            self._es_video = False
            self.lbl_aviso.config(text="✅  Imagen directa.", fg=SUCCESS)
            self.panel_slider.pack_forget()
        elif dur > 0:
            self._es_video = True
            self.lbl_aviso.config(
                text=f"🎬  Video ({segundos_a_hms(dur)}). Usa el slider para elegir el fotograma.",
                fg=TEXT)
            self.slider.config(to=dur); self.slider_var.set(0)
            self.lbl_seg.config(text="0s"); self._reset_frame_prev()
            self.panel_slider.pack(fill="x", padx=14, pady=(0,6), before=self.sub_nb)
        else:
            self._es_video = False
            self.lbl_aviso.config(text="⚠  Se descargará como imagen.", fg=WARN)
            self.panel_slider.pack_forget()

    def on_clear(self):
        self._es_video = False; self._duracion = 0
        self.lbl_aviso.config(text=""); self.panel_slider.pack_forget()
        self._reset_frame_prev()

    def _reset_frame_prev(self):
        self.lbl_fi.pack_forget(); self.lbl_ph2.pack(expand=True)

    def _preview_frame(self):
        url = self.get_url()
        if not url: return
        seg = int(self.slider_var.get())
        self.lbl_ph2.config(text="Extrayendo fotograma...")
        self.lbl_fi.pack_forget()
        threading.Thread(target=self._extraer_frame_prev,
                         args=(url, seg), daemon=True).start()

    def _extraer_frame_prev(self, url, seg):
        if not PILLOW:
            self.after(0, lambda: self.lbl_ph2.config(text="Instala Pillow.")); return
        try:
            tmp = os.path.join(CARPETA, "_frame_preview.jpg")
            info_r = subprocess.run(
                ["yt-dlp","-g","--no-playlist",url] + _get_app_cookies(),
                capture_output=True, text=True, timeout=15, creationflags=FLAG)
            stream = info_r.stdout.strip().split("\n")[0]
            if stream:
                subprocess.run(["ffmpeg","-y","-ss",str(seg),"-i",stream,
                                "-frames:v","1","-q:v","2",tmp],
                               capture_output=True, timeout=20, creationflags=FLAG)
            if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
                img = Image.open(tmp)
                img.thumbnail((160,80), Image.LANCZOS)
                self._frame_img = ImageTk.PhotoImage(img)
                self.after(0, lambda: [self.lbl_ph2.pack_forget(),
                                       self.lbl_fi.config(image=self._frame_img),
                                       self.lbl_fi.pack(expand=True, pady=4)])
            else:
                self.after(0, lambda: self.lbl_ph2.config(text="No se pudo. ¿ffmpeg instalado?"))
        except Exception as e:
            self.after(0, lambda: self.lbl_ph2.config(text=f"Error: {e}"))

    def get_tab_idx(self):
        return self.sub_nb.index(self.sub_nb.select())



    def build_cmd_simple(self, url):
        ck = _get_app_cookies()
        salida = os.path.join(CARPETA, "%(title)s.%(ext)s")
        return ["yt-dlp","--no-playlist","--newline","-o",salida] + ck + [url]

    def postprocesar(self, archivo, on_done, on_error):
        """Aplica la operación del tab activo sobre el archivo descargado."""
        tab = self.get_tab_idx()

        if not PILLOW:
            on_done(archivo); return

        if tab == 0:   # Descargar: redimensionar + cambio de formato
            threading.Thread(target=self._op_descargar,
                             args=(archivo, on_done, on_error), daemon=True).start()
        elif tab == 1: # Recortar
            threading.Thread(target=self._op_recortar,
                             args=(archivo, on_done, on_error), daemon=True).start()
        elif tab == 2: # Comprimir
            threading.Thread(target=self._op_comprimir,
                             args=(archivo, on_done, on_error), daemon=True).start()
        elif tab == 3: # Convertir
            threading.Thread(target=self._op_convertir,
                             args=(archivo, on_done, on_error), daemon=True).start()

    def _nuevo_nombre(self, path, sufijo, ext):
        base = os.path.splitext(os.path.basename(path))[0]
        return os.path.join(CARPETA, base + sufijo + ext)

    def _op_descargar(self, archivo, on_done, on_error):
        try:
            img = Image.open(archivo)
            # Redimensionar si se pidió
            custom  = self.dl_custom.get().strip()
            res_val = self.dl_res.get()
            ancho   = (int(custom) if custom and custom.isdigit()
                       else (None if res_val == "original" else int(res_val)))
            if ancho and ancho != img.width:
                ratio = ancho / img.width
                img   = img.resize((ancho, int(img.height*ratio)), Image.LANCZOS)

            # Cambiar formato si se pidió
            fmt = self.dl_fmt.get()
            if fmt == "original":
                # Guardar en el mismo formato
                ext     = os.path.splitext(archivo)[1] or ".jpg"
                destino = self._nuevo_nombre(archivo, "_dl", ext)
                img.save(destino)
            else:
                ext_map = {"JPG":".jpg","PNG":".png","WEBP":".webp"}
                ext     = ext_map.get(fmt, ".jpg")
                destino = self._nuevo_nombre(archivo, "_dl", ext)
                save_fmt = "JPEG" if fmt == "JPG" else fmt
                if fmt in ("JPG",): img = img.convert("RGB")
                img.save(destino, save_fmt,
                         quality=self.calidad_img.get() if fmt=="JPG" else None)
            on_done(destino)
        except Exception as e:
            on_error(str(e))

    def _op_recortar(self, archivo, on_done, on_error):
        try:
            img = Image.open(archivo).convert("RGBA")
            top    = int(self.crop["Arriba"].get()    or 0)
            bottom = int(self.crop["Abajo"].get()     or 0)
            left   = int(self.crop["Izquierda"].get() or 0)
            right  = int(self.crop["Derecha"].get()   or 0)
            w, h   = img.size
            box    = (left, top,
                      w - right  if right  else w,
                      h - bottom if bottom else h)
            img = img.crop(box)
            s   = self._nuevo_nombre(archivo, "_recortada", ".png")
            img.save(s, "PNG")
            on_done(s)
        except Exception as e:
            on_error(str(e))

    def _op_comprimir(self, archivo, on_done, on_error):
        try:
            q   = int(self.calidad_img.get())
            img = Image.open(archivo).convert("RGB")
            s   = self._nuevo_nombre(archivo, f"_q{q}", ".jpg")
            img.save(s, "JPEG", quality=q, optimize=True)
            on_done(s)
        except Exception as e:
            on_error(str(e))

    def _op_convertir(self, archivo, on_done, on_error):
        try:
            fmt     = self.formato_conv.get()
            ext_map = {"PNG":".png","JPG":".jpg","WEBP":".webp",
                       "BMP":".bmp","TIFF":".tiff","ICO":".ico"}
            ext     = ext_map.get(fmt, ".png")
            s       = self._nuevo_nombre(archivo, f"_a_{fmt.lower()}", ext)
            save_fmt = "JPEG" if fmt == "JPG" else fmt
            img     = Image.open(archivo)
            if fmt in ("JPG","BMP"): img = img.convert("RGB")
            elif fmt == "ICO":       img = img.resize((256,256), Image.LANCZOS)
            else:                    img = img.convert("RGBA")
            kw = {}
            if fmt == "JPG": kw["quality"] = self.calidad_img.get()
            img.save(s, save_fmt, **kw)
            on_done(s)
        except Exception as e:
            on_error(str(e))


class VidGet(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"VidGet v{VERSION}"); self.minsize(560, 480); self.geometry("600x620")
        self.configure(bg=BG)
        # Intentar cargar icono
        try:
            ico_path = os.path.join(os.path.dirname(os.path.abspath(
                sys.executable if getattr(sys,"frozen",False) else __file__
            )), "vidget.ico")
            if os.path.exists(ico_path):
                self.iconbitmap(default=ico_path)
        except Exception:
            pass
        self._info        = None
        self._tipo        = None
        self._busy        = False
        self._modo_avanzado = tk.BooleanVar(value=False)
        self._build()
        self.bind("<Configure>", self._on_resize)
        # Verificar actualizacion en background (no bloquea el inicio)
        threading.Thread(target=self._check_update_bg, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    # ─────────────────────────────────────────────────────────────────────────
    def _build(self):
        main = mk_frame(self); main.pack(fill="both", expand=True)

        # Header
        hdr = mk_frame(main); hdr.pack(fill="x", padx=20, pady=(16,0))
        mk_label(hdr, "VidGet", fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(side="left")
        mk_btn(hdr, "📁", self._abrir_carpeta, bg=SURFACE2, fg=MUTED,
               font=F_SM, padx=10, pady=5).pack(side="right")

        # Botón de actualización (oculto hasta que se detecte una)
        self.btn_update = tk.Button(hdr, text="",
                                    command=self._mostrar_update_dialog,
                                    bg="#1a2600", fg=ACCENT,
                                    font=("Segoe UI", 8, "bold"),
                                    relief="flat", cursor="hand2",
                                    activebackground="#2a3f00",
                                    activeforeground=ACCENT,
                                    padx=10, pady=5)
        # No se muestra hasta que haya update
        self._update_info = None
        tk.Checkbutton(hdr, text="Modo avanzado", variable=self._modo_avanzado,
                       command=self._toggle_avanzado,
                       bg=BG, fg=MUTED, selectcolor=BG, activebackground=BG,
                       activeforeground=TEXT, font=F_XS, cursor="hand2").pack(side="right", padx=(0,10))

        mk_label(main, "Descarga cualquier cosa", fg=TEXT, font=F_LG, bg=BG).pack(
            anchor="w", padx=20, pady=(4,0))
        mk_label(main, "YouTube · Instagram · TikTok · Twitter/X · Facebook · Reddit · +1000 sitios",
                 fg=MUTED, font=F_XS, bg=BG).pack(anchor="w", padx=20, pady=(2,12))

        mk_sep(main, padx=20, pady=6)

        # ── URL row ───────────────────────────────────────────────────────────
        mk_label(main, "PEGA EL LINK", fg=MUTED, font=F_XS, bg=BG).pack(anchor="w", padx=20, pady=(0,4))

        url_row = mk_frame(main); url_row.pack(fill="x", padx=20)
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self._on_url_change)
        self.url_entry = tk.Entry(url_row, textvariable=self.url_var, bg=SURFACE, fg=TEXT,
                                  insertbackground=TEXT, relief="flat", font=F,
                                  highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT)
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=10, ipadx=10)
        self.url_entry.bind("<Return>", lambda e: self._descargar())
        mk_btn(url_row, "📋", self._pegar, padx=13, pady=10).pack(side="left", padx=(6,0))
        mk_btn(url_row, "✕", self._limpiar, fg=MUTED, padx=12, pady=10).pack(side="left", padx=(4,0))

        # Cookies: manejadas automaticamente por el motor de descarga
        # Se prueban todos los navegadores sin intervención del usuario
        self.usar_cookies = tk.BooleanVar(value=True)   # siempre activo internamente
        self.browser_var  = tk.StringVar(value="")      # autodetectado

        # Validación + preview
        self.lbl_valid = mk_label(main, "", fg=MUTED, font=F_XS, bg=BG)
        self.lbl_valid.pack(anchor="w", padx=20, pady=(6,0))

        # Preview box con galería de miniaturas
        self.prev_box = mk_frame(main, bg=SURFACE, height=160)
        self.prev_box.pack(fill="x", padx=20, pady=(6,0))
        self.prev_box.pack_propagate(False)

        self.lbl_ph = mk_label(self.prev_box,
            "La vista previa aparecerá aquí al pegar un link",
            fg=MUTED, font=F_SM, bg=SURFACE)
        self.lbl_ph.pack(expand=True)

        # Canvas scrollable para galería de imágenes
        self.prev_canvas = tk.Canvas(self.prev_box, bg=SURFACE, height=155,
                                     highlightthickness=0)
        self.prev_scrollbar = ttk.Scrollbar(self.prev_box, orient="horizontal",
                                             command=self.prev_canvas.xview)
        self.prev_canvas.configure(xscrollcommand=self.prev_scrollbar.set)
        self.prev_inner = tk.Frame(self.prev_canvas, bg=SURFACE)
        self.prev_canvas_window = self.prev_canvas.create_window(
            (0,0), window=self.prev_inner, anchor="nw")
        self.prev_inner.bind("<Configure>",
            lambda e: self.prev_canvas.configure(
                scrollregion=self.prev_canvas.bbox("all")))
        # Scroll con rueda del mouse
        self.prev_canvas.bind("<MouseWheel>",
            lambda e: self.prev_canvas.xview_scroll(-1*(e.delta//120), "units"))

        # Labels de info debajo de la galería
        self.lbl_prev_titulo = mk_label(self.prev_box, "", fg=TEXT, font=F_BOLD,
                                        bg=SURFACE, wraplength=360, justify="left")
        self.lbl_prev_meta   = mk_label(self.prev_box, "", fg=MUTED, font=F_SM, bg=SURFACE)
        self.lbl_tipo_badge  = mk_label(self.prev_box, "", fg=BG,
                                        font=("Segoe UI", 8, "bold"), bg=ACCENT)

        self._thumb_imgs      = []   # referencias para evitar GC
        self._thumb_urls      = []   # URLs de imágenes encontradas
        self._selected_thumb  = tk.IntVar(value=0)

        mk_sep(main, padx=20, pady=8)

        # ── Modo avanzado (oculto por defecto) ───────────────────────────────
        self.avanzado_frame = mk_frame(main)
        # Notebook de pestañas avanzadas
        style = ttk.Style()
        style.configure("VG.TNotebook", background=BG, borderwidth=0, tabmargins=[0,4,0,0])
        style.configure("VG.TNotebook.Tab",
                        background="#1a1a24",
                        foreground=MUTED,
                        font=("Segoe UI", 9, "bold"),
                        padding=[16, 8],
                        borderwidth=0)
        style.map("VG.TNotebook.Tab",
                  background=[("selected", SURFACE2), ("active", "#222230")],
                  foreground=[("selected", ACCENT), ("active", TEXT)])

        nb_wrap = mk_frame(self.avanzado_frame, bg=BORDER, highlightthickness=0)
        nb_wrap.pack(fill="both", expand=True, padx=20)
        nb_wrap.columnconfigure(0, weight=1)
        nb_inner = mk_frame(nb_wrap, bg=BG)
        nb_inner.pack(fill="both", expand=True, padx=1, pady=(0,1))
        self.notebook = ttk.Notebook(nb_inner, style="VG.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        # Progress (siempre visible)
        self.progress = ProgressPanel(main)
        self.progress.pack(fill="x", padx=20, pady=(6,0))

        # Paneles avanzados
        self.panel_va     = PanelVideoAudio(self.notebook)
        self.panel_gif    = PanelGIF(self.notebook)
        self.panel_imagen = PanelImagen(self.notebook, self.url_var.get, self.progress)

        self.notebook.add(self.panel_va,     text="🎬  Video / Audio")
        self.notebook.add(self.panel_gif,    text="🎞  GIF")
        self.notebook.add(self.panel_imagen, text="🖼  Imagen")
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        mk_sep(main, padx=20, pady=6)

        # ── Botón principal ───────────────────────────────────────────────────
        self.btn = tk.Button(main, text="↓   Descargar", command=self._descargar,
                             bg=ACCENT, fg="#0d0d11", font=("Segoe UI", 13, "bold"),
                             relief="flat", cursor="hand2", activebackground="#d4ff5a",
                             activeforeground="#0d0d11", pady=12, state="disabled")
        self.btn.pack(fill="x", padx=20, pady=(0,8))

        # Abrir carpeta al terminar (simple, abajo del botón)
        self.abrir_auto = tk.BooleanVar(value=False)
        tk.Checkbutton(main, text="Abrir carpeta al terminar",
                       variable=self.abrir_auto, bg=BG, fg=MUTED, selectcolor=BG,
                       activebackground=BG, font=F_XS, cursor="hand2").pack(anchor="w", padx=20, pady=(0,10))

        global _url_panel_ref
        _url_panel_ref = self  # self actúa como url_panel para cookies

    # ── URL helpers ───────────────────────────────────────────────────────────
    def get_cookies_flags(self):
        return []  # El motor de descarga prueba todos los navegadores automaticamente

    def _on_cookies_toggle(self): pass  # manejado automaticamente

    def _pegar(self):
        try: self.url_var.set(self.clipboard_get().strip())
        except: pass

    def _limpiar(self):
        self.url_var.set(""); self._info = None; self._tipo = None
        self._reset_prev(); self.lbl_valid.config(text="")
        self.btn.config(state="disabled", text="↓   Descargar")
        self.progress.reset()
        self.panel_gif.on_clear(); self.panel_imagen.on_clear()

    def _on_url_change(self, *_):
        url = self.url_var.get().strip()
        if not url:
            self._limpiar(); return
        if not url.startswith("http"):
            self.lbl_valid.config(text="⚠  No parece un link válido.", fg=WARN)
            self._reset_prev(); return
        self.lbl_valid.config(text="🔍  Detectando contenido...", fg=MUTED)
        self.btn.config(state="disabled")
        threading.Thread(target=self._fetch_info, args=(url,), daemon=True).start()

    _fetch_tid = 0
    def _fetch_info(self, url):
        VidGet._fetch_tid += 1; tid = VidGet._fetch_tid
        try:
            ck = self.get_cookies_flags()
            res = subprocess.run(["yt-dlp", "--dump-json", "--no-playlist", url] + ck,
                                 capture_output=True, text=True, timeout=20, creationflags=FLAG)
            if tid != VidGet._fetch_tid: return

            if res.returncode == 0:
                # yt-dlp funciono — flujo normal
                info = json.loads(res.stdout)
                self._info = info
                self._tipo = detectar_tipo(info)
                self.after(0, lambda: self._apply_info(info))
                return

            # yt-dlp fallo — si es sitio de imagenes, NO bloquear al usuario
            if es_sitio_imagen(url):
                # Crear info falsa para que el flujo continue con gallery-dl
                self._info  = {"title": url, "ext": "jpg", "duration": 0}
                self._tipo  = "imagen"
                info_fake   = self._info.copy()
                self.after(0, lambda: [
                    self.lbl_valid.config(
                        text="🖼  Contenido detectado. Listo para descargar.",
                        fg=ACCENT),
                    self.btn.config(state="normal"),
                    self._show_prev_simple(url)
                ])
                self.after(0, lambda: self.notebook.select(2))  # pestaña imagen
                return

            # Para otros sitios, mostrar error
            msg = interpretar_error((res.stderr or "") + (res.stdout or ""))
            self.after(0, lambda: [self.lbl_valid.config(text=f"❌  {msg}", fg=ERROR),
                                   self._reset_prev()])
        except FileNotFoundError:
            if tid == VidGet._fetch_tid:
                self.after(0, lambda: self.lbl_valid.config(
                    text="❌  yt-dlp no instalado. Ejecuta INSTALAR.bat.", fg=ERROR))
        except Exception:
            if tid == VidGet._fetch_tid:
                self.after(0, lambda: self.lbl_valid.config(
                    text="⚠  No se pudo verificar el link.", fg=WARN))

    def _apply_info(self, info):
        tipo = self._tipo
        iconos = {"video":"🎬","audio":"🎵","gif":"🎞","imagen":"🖼"}
        nombres = {"video":"VIDEO","audio":"AUDIO","gif":"GIF","imagen":"IMAGEN"}
        # Validación
        self.lbl_valid.config(
            text=f"✅  {nombres.get(tipo,'?')} detectado  {iconos.get(tipo,'')}  — listo para descargar",
            fg=SUCCESS)
        self.btn.config(state="normal")

        # Preview
        titulo   = info.get("title","")
        thumb    = info.get("thumbnail","")
        duracion = info.get("duration_string","")
        uploader = info.get("uploader","")
        meta = ("⏱ "+duracion if duracion else "") + ("   👤 "+uploader if uploader else "")
        self.lbl_prev_titulo.config(text=titulo)
        self.lbl_prev_meta.config(text=meta)
        self.lbl_tipo_badge.config(text=f"  {nombres.get(tipo,'?')}  ")

        # Auto-seleccionar pestaña avanzada correcta
        tab_map = {"video":0,"audio":0,"gif":1,"imagen":2}
        self.notebook.select(tab_map.get(tipo, 0))

        # Notificar a paneles avanzados
        self.panel_va.set_tipo(tipo)
        self.panel_gif.on_info(info)
        self.panel_imagen.on_info(info)

        # Cargar thumbnail y galería de imágenes
        self._show_prev_img()
        if PILLOW and thumb:
            threading.Thread(target=self._load_thumb, args=(thumb,), daemon=True).start()
        # Cargar galería de imágenes del HTML en paralelo
        threading.Thread(target=self._cargar_thumbs_html,
                         args=(self.url_var.get().strip(),), daemon=True).start()

    def _load_thumb(self, url):
        """Carga el thumbnail principal (og:image) para el badge de info."""
        # El thumbnail principal se muestra en el primer slot de la galería
        try:
            req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as r: data = r.read()
            if len(data) < 500: return
            img = Image.open(io.BytesIO(data))
            img.thumbnail((120,120), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.after(0, lambda p=photo: self._agregar_thumb_ui(p, 0, url))
        except: pass

    def _reset_prev(self):
        for w in self.prev_box.winfo_children(): w.pack_forget()
        self.lbl_ph.pack(expand=True)
        self._thumb_imgs = []
        self._thumb_urls = []
        for w in self.prev_inner.winfo_children():
            w.destroy()

    def _show_prev_img(self):
        self._reset_prev()
        self.lbl_prev_img.config(image=self._thumb_img)
        self.lbl_prev_img.pack(side="left", padx=(10,8), pady=8)
        tf = tk.Frame(self.prev_box, bg=SURFACE); tf.pack(side="left", anchor="w", pady=8, fill="both", expand=True)
        self.lbl_tipo_badge.pack_forget()
        tk.Label(tf, text=self.lbl_tipo_badge.cget("text"), fg=BG, font=("Segoe UI",8,"bold"),
                 bg=ACCENT, padx=6, pady=2).pack(anchor="w", pady=(0,4))
        tk.Label(tf, text=self.lbl_prev_titulo.cget("text"), bg=SURFACE, fg=TEXT,
                 font=F_BOLD, wraplength=330, justify="left").pack(anchor="w")
        tk.Label(tf, text=self.lbl_prev_meta.cget("text"), bg=SURFACE, fg=MUTED, font=F_SM).pack(anchor="w", pady=(2,0))

    def _show_prev_txt(self):
        self._reset_prev()
        self.lbl_tipo_badge.pack(anchor="w", padx=12, pady=(10,4))
        self.lbl_prev_titulo.pack(anchor="w", padx=12, pady=(0,2))
        self.lbl_prev_meta.pack(anchor="w", padx=12)

    def _show_prev_simple(self, url):
        """Preview minimo + intenta cargar miniaturas del HTML."""
        self._reset_prev()
        dominio = url.split("/")[2] if "/" in url else url
        self.lbl_tipo_badge.config(text="  IMAGEN  ")
        self.lbl_prev_titulo.config(text=dominio)
        self.lbl_prev_meta.config(text=url[:70] + ("..." if len(url) > 70 else ""))
        self.lbl_tipo_badge.pack(anchor="w", padx=12, pady=(6,2))
        self.lbl_prev_titulo.pack(anchor="w", padx=12)
        self.lbl_prev_meta.pack(anchor="w", padx=12, pady=(0,4))
        self.prev_canvas.pack(fill="x", padx=4, expand=True)
        self.prev_scrollbar.pack(fill="x", padx=4)
        # Intentar cargar miniaturas del HTML
        threading.Thread(target=self._cargar_thumbs_html,
                         args=(url,), daemon=True).start()

    def _cargar_thumbs_html(self, url):
        """Extrae URLs de imágenes del HTML y muestra miniaturas."""
        if not PILLOW: return
        try:
            import urllib.request, html as _html
            H = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,*/*;q=0.9",
                "Accept-Language": "es-MX,es;q=0.9",
            }
            req = urllib.request.Request(url, headers=H)
            with urllib.request.urlopen(req, timeout=12) as r:
                body = r.read().decode("utf-8", errors="ignore")
            sitio = _detectar_sitio(url)
            img_urls = _extraer_urls_imagen(body, sitio=sitio)
            # Limitar a las primeras 10
            img_urls = img_urls[:10]
            self._thumb_urls = img_urls
            for i, img_url in enumerate(img_urls):
                threading.Thread(target=self._cargar_thumb_uno,
                                 args=(img_url, i), daemon=True).start()
        except Exception:
            pass

    def _cargar_thumb_uno(self, img_url, idx):
        """Descarga y muestra una miniatura individual."""
        if not PILLOW: return
        try:
            import urllib.request
            H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
            # Ajustar a thumbnail para preview (no descargar calidad completa)
            thumb_url = img_url
            if "pbs.twimg.com/media" in img_url:
                thumb_url = img_url.split("?")[0] + "?format=jpg&name=small"
            elif "cdninstagram" in img_url or "fbcdn" in img_url:
                thumb_url = img_url
            req = urllib.request.Request(thumb_url, headers=H)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
            if len(data) < 500: return
            img = Image.open(io.BytesIO(data))
            # Thumb de 120x120
            img.thumbnail((120, 120), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self.after(0, lambda p=photo, i=idx, u=img_url:
                       self._agregar_thumb_ui(p, i, u))
        except Exception:
            pass

    def _agregar_thumb_ui(self, photo, idx, url):
        """Agrega una miniatura al canvas de preview."""
        self._thumb_imgs.append(photo)  # evitar GC
        col = len([w for w in self.prev_inner.winfo_children() if isinstance(w, tk.Frame)])

        cell = tk.Frame(self.prev_inner, bg=SURFACE2, padx=2, pady=2)
        cell.grid(row=0, column=col, padx=3, pady=3)

        # Número de imagen
        mk_label(cell, f"#{idx+1}", fg=MUTED, font=F_XS, bg=SURFACE2).pack()

        # Imagen clickeable
        lbl = tk.Label(cell, image=photo, bg=SURFACE2, cursor="hand2",
                       relief="flat", bd=2)
        lbl.pack()

        # Al hacer click, marcar como seleccionada
        def seleccionar(u=url, l=lbl, c=cell):
            self._selected_thumb.set(idx)
            # Highlight
            for w in self.prev_inner.winfo_children():
                w.config(bg=SURFACE2)
                for ww in w.winfo_children():
                    ww.config(bg=SURFACE2)
            c.config(bg=BORDER)
            l.config(bg=BORDER)

        lbl.bind("<Button-1>", lambda e, f=seleccionar: f())

        # Numero debajo
        mk_label(cell, f"img {idx+1}", fg=MUTED, font=("Segoe UI",7), bg=SURFACE2).pack()

    # ── Modo avanzado toggle ──────────────────────────────────────────────────
    def _toggle_avanzado(self):
        if self._modo_avanzado.get():
            self.avanzado_frame.pack(fill="both", expand=True, before=self.progress)
            self.geometry("600x820"); self.minsize(560,780)
        else:
            self.avanzado_frame.pack_forget()
            self.geometry("600x620"); self.minsize(560,480)

    def _on_tab_changed(self, _):
        pass  # La pestaña se auto-selecciona, pero el user puede cambiarla manualmente

    # ── Descarga ──────────────────────────────────────────────────────────────
    def _descargar(self):
        if self._busy: return
        url = self.url_var.get().strip()
        if not url or not self._info:
            self.progress.set_resultado("⚠  Pega un link válido primero.", WARN); return

        tipo = self._tipo
        avanzado = self._modo_avanzado.get()

        self._busy = True
        self.btn.config(state="disabled", text="Descargando...", bg=BORDER, fg=MUTED)
        self.progress.reset(); self.progress.set_estado("Conectando...", MUTED)

        if avanzado:
            # Usar configuración de la pestaña activa
            tab = self.notebook.index(self.notebook.select())
            if tab == 0:
                cmd = self.panel_va.build_cmd(url)
                threading.Thread(target=run_download,
                                 args=(cmd, self.progress, self._exito, self._error_dl),
                                 daemon=True).start()
            elif tab == 1:
                cmd, err = self.panel_gif.build_cmd(url)
                if err:
                    self.progress.set_resultado(f"⚠  {err}", WARN)
                    self._reset_btn(); return
                threading.Thread(target=run_download,
                                 args=(cmd, self.progress, self._exito, self._error_dl),
                                 daemon=True).start()
            elif tab == 2:
                if self.panel_imagen._es_video:
                    seg = int(self.panel_imagen.slider_var.get())
                    threading.Thread(target=self._descargar_fotograma,
                                     args=(url, seg), daemon=True).start()
                elif es_sitio_imagen(url) and not self.panel_imagen._es_video:
                    threading.Thread(target=self._descargar_twitter_img_simple,
                                     args=(url,), daemon=True).start()
                else:
                    cmd = self.panel_imagen.build_cmd_simple(url)
                    threading.Thread(target=self._descargar_imagen_pp,
                                     args=(cmd, url), daemon=True).start()
        else:
            # Modo simple: descarga directa según tipo detectado
            ck = self.get_cookies_flags()
            salida = os.path.join(CARPETA, "%(title)s.%(ext)s")
            if tipo == "audio":
                cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "0",
                       "--no-playlist", "--newline", "-o", salida] + ck + [url]
            elif tipo == "gif":
                cmd = ["yt-dlp", "--no-playlist", "--newline", "-o", salida] + ck + [url]
            elif tipo == "imagen":
                # Para sitios de imágenes usar gallery-dl
                if es_sitio_imagen(url):
                    threading.Thread(target=self._descargar_twitter_img_simple,
                                     args=(url,), daemon=True).start()
                    return
                cmd = ["yt-dlp", "--no-playlist", "--newline", "-o", salida] + ck + [url]
            else:  # video
                cmd = ["yt-dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                       "--merge-output-format", "mp4", "--no-playlist",
                       "--newline", "-o", salida] + ck + [url]
            threading.Thread(target=run_download,
                             args=(cmd, self.progress, self._exito, self._error_dl),
                             daemon=True).start()

    def _descargar_fotograma(self, url, seg):
        try:
            salida_jpg = os.path.join(CARPETA, f"fotograma_{seg}.jpg")
            info_r = subprocess.run(["yt-dlp", "-g", "--no-playlist", url] + self.get_cookies_flags(),
                                    capture_output=True, text=True, timeout=15, creationflags=FLAG)
            stream_url = info_r.stdout.strip().split("\n")[0]
            if not stream_url: raise Exception("No se pudo obtener el stream.")
            subprocess.run(["ffmpeg", "-y", "-ss", str(seg), "-i", stream_url,
                            "-frames:v", "1", "-q:v", "1", salida_jpg],
                           capture_output=True, timeout=30, creationflags=FLAG)
            if os.path.exists(salida_jpg) and os.path.getsize(salida_jpg) > 0:
                self.after(0, lambda: self.panel_imagen.postprocesar(salida_jpg, self._exito, self._error_dl))
            else:
                self.after(0, lambda: self._error_dl("No se pudo extraer. ¿ffmpeg instalado?\nwinget install ffmpeg"))
        except Exception as e:
            self.after(0, lambda err=str(e): self._error_dl(err))

    def _descargar_imagen_pp(self, cmd, url):
        err_lines = []
        try:
            proceso = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, creationflags=FLAG)
            ultimo = None
            for l in proceso.stdout:
                l = l.strip()
                m = re.search(r'\[download\] Destination: (.+)', l)
                if m: ultimo = m.group(1)
                if "[download]" in l and "%" in l:
                    pct = re.search(r'(\d+\.?\d*)%', l)
                    if pct:
                        p = float(pct.group(1))
                        self.progress.after(0, lambda v=p: self.progress.update_dl(v))
            stderr_txt = proceso.stderr.read() or ""
            proceso.wait()
            if proceso.returncode != 0:
                # Si es sitio de imágenes, intentar con gallery-dl
                if es_sitio_imagen(url):
                    self.progress.after(0, lambda: self.progress.set_estado(
                        "Intentando con gallery-dl...", MUTED))
                    browser = None  # El motor prueba todos los navegadores automaticamente
                    arquivo_r, _ = descargar_imagen_agresivo(url, CARPETA, browser_preferido=browser)
                    if arquivo_r and os.path.exists(arquivo_r):
                        self.after(0, lambda f=arquivo_r: self.panel_imagen.postprocesar(
                            f, self._exito, self._error_dl))
                        return
                    self.after(0, lambda e=err: self._error_dl(
                        f"{e}\n\nÚltima opción: abre el tweet en tu navegador,\n"
                        "clic derecho en la imagen → 'Guardar imagen como'."))
                    return
                msg = interpretar_error(stderr_txt)
                self.after(0, lambda m=msg: self._error_dl(m)); return
            if ultimo and os.path.exists(ultimo):
                self.after(0, lambda f=ultimo: self.panel_imagen.postprocesar(f, self._exito, self._error_dl))
            else:
                self.after(0, self._exito)
        except Exception as e:
            self.after(0, lambda err=str(e): self._error_dl(err))

    def _descargar_twitter_img_simple(self, url):
        """
        Motor de descarga de imagenes: prueba TODO automaticamente.
        """
        browser = None  # El motor prueba todos los navegadores automaticamente
        pasos   = []

        def progreso(msg):
            if msg and not msg.startswith("#") and len(msg) > 3:
                short = msg[:80] + ("..." if len(msg) > 80 else "")
                pasos.append(short)
                self.progress.after(0, lambda m=short: self.progress.set_estado(
                    f"Intentando... {m}", MUTED))

        archivo, metodo = descargar_imagen_agresivo(
            url, CARPETA,
            browser_preferido=browser,
            progreso=progreso
        )

        if archivo and os.path.exists(archivo):
            self.after(0, lambda f=archivo: self._exito(f))
        else:
            sitio = _detectar_sitio(url)
            ayudas = {
                "instagram": "Abre Instagram en tu navegador, inicia sesion, y vuelve a intentar.",
                "twitter":   "Abre x.com en tu navegador, inicia sesion, y vuelve a intentar.",
                "reddit":    "El post puede ser privado o eliminado.",
                "generico":  "El contenido puede requerir inicio de sesion en el sitio.",
            }
            ayuda = ayudas.get(sitio, ayudas["generico"])
            self.after(0, lambda a=ayuda: self._error_dl(
                f"No se pudo descargar con ninguna herramienta.\n\n{a}"))


    def _exito(self, archivo=None):
        self._busy = False; self.progress.barra["value"] = 100
        self.progress.set_estado("✅  Completado", SUCCESS)
        self.progress.set_resultado("✅  ¡Listo! Guardado en ~/Downloads/VidGet", SUCCESS)
        self._reset_btn()
        if self.abrir_auto.get(): self._abrir_carpeta()

    def _error_dl(self, msg):
        self._busy = False
        self.progress.set_estado("❌  Error", ERROR)
        self.progress.set_resultado(f"❌  {msg}", ERROR)
        self._reset_btn()

    def _reset_btn(self):
        self.btn.config(state="normal", text="↓   Descargar", bg=ACCENT, fg="#0d0d11")

    def _toggle_avanzado(self):
        if self._modo_avanzado.get():
            self.avanzado_frame.pack(fill="both", expand=True, before=self.progress)
            self.geometry("600x860"); self.minsize(560,800)
        else:
            self.avanzado_frame.pack_forget()
            self.geometry("600x620"); self.minsize(560,480)

    def _cerrar(self):
        """Cierra el programa completamente, sin dejar procesos huerfanos."""
        try:
            self.destroy()
        except:
            pass
        # Forzar salida del proceso principal y todos los hilos daemon
        import os
        os._exit(0)


    # ── Actualizaciones ───────────────────────────────────────────────────────
    def _check_update_bg(self):
        """Verifica en background si hay actualizacion disponible."""
        if GITHUB_USER == "TU_USUARIO_GITHUB":
            return
        hay, version, url = verificar_actualizacion()
        if hay:
            self._update_info = (version, url)
            self.after(0, self._mostrar_badge_update)

    def _mostrar_badge_update(self):
        """Muestra boton de update en el header."""
        if not self._update_info: return
        version, _ = self._update_info
        self.btn_update.config(text=f"  Nueva version {version}")
        self.btn_update.pack(side="right", padx=(0,8))

    def _mostrar_update_dialog(self):
        """Ventana de actualizacion integrada."""
        if not self._update_info: return
        version, url = self._update_info

        dialog = tk.Toplevel(self)
        dialog.title("Actualizacion disponible")
        dialog.geometry("420x260")
        dialog.resizable(False, False)
        dialog.configure(bg=BG)
        dialog.grab_set()
        dialog.transient(self)

        mk_label(dialog, f"  Version {version} disponible",
                 fg=ACCENT, font=("Segoe UI", 14, "bold"), bg=BG).pack(pady=(24,6))
        mk_label(dialog, f"Tu version actual: v{VERSION}",
                 fg=MUTED, font=F_SM, bg=BG).pack()
        mk_label(dialog,
                 "Se descargara e instalara automaticamente.\nEl programa se reiniciara al terminar.",
                 fg=TEXT, font=F_SM, bg=BG, justify="center").pack(pady=(10,0))

        prog_frame = mk_frame(dialog)
        prog_frame.pack(fill="x", padx=24, pady=(16,0))

        style = ttk.Style()
        style.configure("Upd.Horizontal.TProgressbar",
                        troughcolor=SURFACE2, background=ACCENT,
                        thickness=6, borderwidth=0)
        barra = ttk.Progressbar(prog_frame, style="Upd.Horizontal.TProgressbar",
                                mode="determinate", length=370)
        barra.pack(fill="x")
        lbl_est = mk_label(prog_frame, "", fg=MUTED, font=F_XS, bg=BG)
        lbl_est.pack(anchor="w", pady=(4,0))

        btns = mk_frame(dialog)
        btns.pack(pady=(14,0))

        def iniciar():
            btn_si.config(state="disabled", text="Descargando...")
            btn_no.config(state="disabled")
            lbl_est.config(text="Descargando actualizacion...")

            def progreso(pct):
                dialog.after(0, lambda p=pct: [
                    barra.__setitem__("value", p),
                    lbl_est.config(text=f"Descargando... {p}%")
                ])

            def hilo():
                nuevo = descargar_actualizacion(url, progreso)
                if nuevo:
                    dialog.after(0, lambda: lbl_est.config(
                        text="Instalando... El programa se reiniciara."))
                    dialog.after(800, lambda: aplicar_actualizacion(nuevo))
                else:
                    dialog.after(0, lambda: [
                        lbl_est.config(text="Error al descargar.", fg=ERROR),
                        btn_si.config(state="normal", text="Reintentar"),
                        btn_no.config(state="normal"),
                    ])

            threading.Thread(target=hilo, daemon=True).start()

        btn_si = tk.Button(btns, text="  Actualizar ahora",
                           command=iniciar,
                           bg=ACCENT, fg="#0d0d11",
                           font=("Segoe UI", 11, "bold"),
                           relief="flat", cursor="hand2",
                           activebackground="#d4ff5a",
                           padx=16, pady=8)
        btn_si.pack(side="left", padx=(0,8))

        btn_no = tk.Button(btns, text="Ahora no",
                           command=dialog.destroy,
                           bg=SURFACE2, fg=MUTED,
                           font=F_SM, relief="flat",
                           cursor="hand2", padx=16, pady=8)
        btn_no.pack(side="left")

    def _on_resize(self, _):
        w = self.winfo_width() - 48
        if w > 100: self.progress.lbl_resultado.config(wraplength=w)

    def _abrir_carpeta(self):
        if sys.platform == "win32": os.startfile(CARPETA)
        elif sys.platform == "darwin": subprocess.Popen(["open", CARPETA])
        else: subprocess.Popen(["xdg-open", CARPETA])


if __name__ == "__main__":
    VidGet().mainloop()
