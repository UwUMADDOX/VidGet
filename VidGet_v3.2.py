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
import base64
import ctypes
import tempfile
from pathlib import Path

VERSION = "3.2"

try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    PILLOW = True
except ImportError:
    PILLOW = False

CARPETA = str(Path.home() / "Downloads" / "VidGet")
os.makedirs(CARPETA, exist_ok=True)
FLAG = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _aplicar_dark_titlebar(ventana):
    """Aplica barra de titulo oscura en Windows 10/11 via DWM API."""
    if sys.platform != "win32":
        return
    try:
        ventana.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(ventana.winfo_id())
        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 11) o 19 (Windows 10 build 18985+)
        DWMWA = 20
        valor = ctypes.c_int(1)
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA, ctypes.byref(valor), ctypes.sizeof(valor))
        if result != 0:
            # Fallback para Windows 10
            DWMWA = 19
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, DWMWA, ctypes.byref(valor), ctypes.sizeof(valor))
    except Exception:
        pass


def _obtener_base_dir():
    """Retorna el directorio base del ejecutable o script."""
    return os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, "frozen", False) else __file__
    ))


def _generar_ico_runtime():
    """Genera vidget.ico desde los PNG del logo. Retorna path o None."""
    if not PILLOW:
        return None
    base_dir = _obtener_base_dir()
    ico_path = os.path.join(base_dir, "vidget.ico")
    # Si ya existe, retornarlo
    if os.path.exists(ico_path):
        return ico_path
    # Buscar PNG fuente
    for nombre in ["vidget_logo_512.png", "vidget_logo_1024.png"]:
        png_path = os.path.join(base_dir, nombre)
        if os.path.exists(png_path):
            try:
                img = Image.open(png_path)
                img = img.resize((256, 256), Image.LANCZOS)
                img.save(ico_path, format="ICO",
                         sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
                return ico_path
            except Exception:
                pass
    # Generar desde cero con PIL
    try:
        img = _generar_logo_pil(256)
        if img:
            img.save(ico_path, format="ICO",
                     sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
            return ico_path
    except Exception:
        pass
    return None


def _cargar_icono_ventana(ventana):
    """Carga el icono en la ventana: iconbitmap + iconphoto para quitar la pluma."""
    if not PILLOW:
        return
    base_dir = _obtener_base_dir()

    # 1. Intentar con .ico (para la barra de titulo)
    ico_path = _generar_ico_runtime()
    if ico_path:
        try:
            ventana.iconbitmap(default=ico_path)
        except Exception:
            pass

    # 2. iconphoto (reemplaza la pluma en la barra de titulo Y en la taskbar)
    for nombre in ["vidget_logo_512.png", "vidget_logo_1024.png"]:
        ruta = os.path.join(base_dir, nombre)
        if os.path.exists(ruta):
            try:
                img = Image.open(ruta)
                # Crear multiples tamanos para que Windows elija el mejor
                sizes = []
                for s in [16, 32, 48, 64, 128, 256]:
                    resized = img.copy()
                    resized.thumbnail((s, s), Image.LANCZOS)
                    sizes.append(ImageTk.PhotoImage(resized))
                ventana._icon_photos = sizes  # Evitar GC
                ventana.iconphoto(True, *sizes)
                return
            except Exception:
                pass

    # 3. Fallback: generar icono con PIL
    try:
        img = _generar_logo_pil(64)
        if img:
            photo = ImageTk.PhotoImage(img)
            ventana._icon_photo_fallback = photo
            ventana.iconphoto(True, photo)
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════
#  PALETA DE COLORES
# ═══════════════════════════════════════════════════════════════════════════
BG        = "#0d0d11"
SURFACE   = "#131319"
SURFACE2  = "#1a1a24"
SURFACE3  = "#22222e"
BORDER    = "#2a2a3a"
BORDER_LT = "#363648"
ACCENT    = "#c8f545"
ACCENT2   = "#a8d435"
TEXT      = "#e8e8f0"
TEXT2     = "#c0c0d0"
MUTED     = "#55556a"
MUTED2    = "#44445a"
ERROR     = "#ff5c72"
WARN      = "#ffb347"
SUCCESS   = "#c8f545"

# ═══════════════════════════════════════════════════════════════════════════
#  FUENTES
# ═══════════════════════════════════════════════════════════════════════════
F        = ("Segoe UI", 10)
F_SM     = ("Segoe UI", 9)
F_XS     = ("Segoe UI", 8)
F_BOLD   = ("Segoe UI", 10, "bold")
F_LG     = ("Segoe UI", 20, "bold")
F_TITLE  = ("Segoe UI", 13, "bold")
F_TAB    = ("Segoe UI Semibold", 10)
F_HEADER = ("Segoe UI", 11, "bold")

# ═══════════════════════════════════════════════════════════════════════════
#  CONSTANTES DE UI
# ═══════════════════════════════════════════════════════════════════════════
THUMB_W       = 130   # Ancho uniforme de cada miniatura
THUMB_H       = 90    # Alto uniforme de cada miniatura
WIN_MIN_W     = 680   # Ancho minimo ventana
WIN_SIMPLE_H  = 720   # Alto modo simple
WIN_ADV_H     = 920   # Alto modo avanzado

# ═══════════════════════════════════════════════════════════════════════════
#  CONFIGURACION DE USUARIO (persistente en JSON)
# ═══════════════════════════════════════════════════════════════════════════
_CONFIG_PATH = os.path.join(str(Path.home()), ".vidget_config.json")

_DEFAULT_CONFIG = {
    "thumb_mode": "uniform",       # "uniform" (todas iguales) | "proportional" (mantener aspecto)
    "open_folder_on_done": False,  # Abrir carpeta al terminar
    "last_browser": "",            # Ultimo navegador usado
}

def _cargar_config():
    try:
        with open(_CONFIG_PATH, "r") as f:
            cfg = json.loads(f.read())
        # Merge con defaults para nuevas keys
        for k, v in _DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    except Exception:
        return dict(_DEFAULT_CONFIG)

def _guardar_config(cfg):
    try:
        with open(_CONFIG_PATH, "w") as f:
            f.write(json.dumps(cfg, indent=2))
    except Exception:
        pass

CONFIG = _cargar_config()


def _setup_ttk_styles():
    """Configura todos los estilos ttk para eliminar el look Windows XP."""
    style = ttk.Style()
    style.theme_use("clam")  # 'clam' es el theme mas limpio para personalizar

    # --- Notebook principal (Video/Audio, GIF, Imagen) ---
    style.configure("VG.TNotebook", background=BG, borderwidth=0,
                    tabmargins=[0, 0, 0, 0])
    style.configure("VG.TNotebook.Tab",
                    background=SURFACE2, foreground=MUTED,
                    font=F_TAB, padding=[20, 9],
                    borderwidth=0, focuscolor=BG)
    style.map("VG.TNotebook.Tab",
              background=[("selected", SURFACE3), ("active", SURFACE2)],
              foreground=[("selected", ACCENT), ("active", TEXT)])
    style.layout("VG.TNotebook.Tab", [
        ("Notebook.tab", {"sticky": "nswe", "children": [
            ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                ("Notebook.label", {"side": "top", "sticky": ""})
            ]})
        ]})
    ])

    # --- Sub-notebook de Imagen (Descargar, Recortar, Comprimir, Convertir) ---
    style.configure("Img3.TNotebook", background=SURFACE,
                    borderwidth=0, tabmargins=[0, 0, 0, 0])
    style.configure("Img3.TNotebook.Tab",
                    background="#111118", foreground="#555570",
                    font=("Segoe UI Semibold", 9),
                    padding=[14, 7], borderwidth=0, focuscolor=SURFACE)
    style.map("Img3.TNotebook.Tab",
              background=[("selected", SURFACE3), ("active", "#16161e")],
              foreground=[("selected", ACCENT), ("active", TEXT)])
    style.layout("Img3.TNotebook.Tab", [
        ("Notebook.tab", {"sticky": "nswe", "children": [
            ("Notebook.padding", {"side": "top", "sticky": "nswe", "children": [
                ("Notebook.label", {"side": "top", "sticky": ""})
            ]})
        ]})
    ])

    # --- Progress bars ---
    style.configure("VG.Horizontal.TProgressbar",
                    troughcolor=SURFACE2, background=ACCENT,
                    thickness=6, borderwidth=0)
    style.configure("Upd.Horizontal.TProgressbar",
                    troughcolor=SURFACE2, background=ACCENT,
                    thickness=6, borderwidth=0)

    # --- Scales (sliders) ---
    style.configure("TScale", background=BG, troughcolor=SURFACE2,
                    borderwidth=0, focuscolor=BG)

    # --- Scrollbars ---
    style.configure("TScrollbar", background=SURFACE2,
                    troughcolor=BG, borderwidth=0, arrowsize=0)

# ═══════════════════════════════════════════════════════════════════════════
#  LOGO EMBEBIDO (flecha de descarga verde sobre fondo oscuro)
# ═══════════════════════════════════════════════════════════════════════════
LOGO_B64 = None  # Se carga desde archivo si existe

def _generar_logo_pil(size=32):
    """Genera el logo VidGet con PIL si no existe archivo."""
    if not PILLOW:
        return None
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # Fondo redondeado oscuro
    r = size // 6
    d.rounded_rectangle([0, 0, size-1, size-1], radius=r, fill="#16161e")
    # Flecha de descarga verde
    cx, cy = size//2, size//2
    s = size // 3  # tamaño de la flecha
    # Barra vertical
    bw = max(2, size//10)
    d.rectangle([cx-bw, cy-s, cx+bw, cy+bw], fill=ACCENT)
    # Punta de flecha
    pts = [(cx-s, cy-bw), (cx, cy+s//2+bw), (cx+s, cy-bw)]
    d.polygon(pts, fill=ACCENT)
    # Linea base
    d.rectangle([cx-s, cy+s//2+bw+2, cx+s, cy+s//2+bw+2+max(1,size//16)], fill=ACCENT)
    return img


def _cargar_logo(root, size=32):
    """Intenta cargar el logo desde archivo, si no genera uno."""
    if not PILLOW:
        return None
    base_dir = _obtener_base_dir()
    for nombre in ["vidget_logo_512.png", "vidget_logo_1024.png", "vidget_logo.png", "vidget.ico"]:
        ruta = os.path.join(base_dir, nombre)
        if os.path.exists(ruta):
            try:
                img = Image.open(ruta)
                img.thumbnail((size, size), Image.LANCZOS)
                return ImageTk.PhotoImage(img)
            except Exception:
                pass
    # Generar logo si no hay archivo
    img = _generar_logo_pil(size)
    if img:
        return ImageTk.PhotoImage(img)
    return None


# ═══════════════════════════════════════════════════════════════════════════
#  WIDGETS HELPER
# ═══════════════════════════════════════════════════════════════════════════
def mk_frame(parent, bg_color=BG, **kw):
    return tk.Frame(parent, bg=bg_color, **kw)

def mk_label(parent, text="", fg=TEXT, font=F, bg_color=BG, **kw):
    return tk.Label(parent, text=text, fg=fg, font=font, bg=bg_color, **kw)

def mk_btn(parent, text, cmd, bg_color=SURFACE2, fg=TEXT, font=F, **kw):
    return tk.Button(parent, text=text, command=cmd, bg=bg_color, fg=fg,
                     font=font, relief="flat", cursor="hand2",
                     activebackground=BORDER, activeforeground=TEXT, bd=0, **kw)

def mk_entry(parent, var, **kw):
    kw.setdefault("width", 6)
    return tk.Entry(parent, textvariable=var, bg=SURFACE, fg=TEXT,
                    insertbackground=TEXT, relief="flat", font=F,
                    highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=ACCENT, **kw)

def mk_sep(parent, padx=16, pady=8):
    f = tk.Frame(parent, bg=BORDER, height=1)
    f.pack(fill="x", padx=padx, pady=pady)
    return f

def mk_radio(parent, text, var, val, bg_color=BG, **kw):
    return tk.Radiobutton(parent, text=text, variable=var, value=val,
                          bg=bg_color, fg=TEXT, selectcolor=bg_color,
                          activebackground=bg_color, activeforeground=TEXT,
                          font=F_SM, cursor="hand2", **kw)

def mk_check(parent, text, var, bg_color=BG, **kw):
    return tk.Checkbutton(parent, text=text, variable=var,
                          bg=bg_color, fg=MUTED, selectcolor=bg_color,
                          activebackground=bg_color, activeforeground=TEXT,
                          font=F_XS, cursor="hand2", **kw)


# ═══════════════════════════════════════════════════════════════════════════
#  FUNCIONES GLOBALES — MOTOR DE DESCARGA
# ═══════════════════════════════════════════════════════════════════════════
def interpretar_error(txt):
    t = (txt or "").lower()
    if "private" in t:                    return "El contenido es privado."
    if "copyright" in t:                  return "Bloqueado por derechos de autor."
    if "not available" in t:              return "El contenido no esta disponible o fue eliminado."
    if "login" in t or "sign in" in t or "auth" in t:
        return "Requiere iniciar sesion. Se intentara con diferentes metodos."
    if "geo" in t:                        return "Bloqueado en tu pais."
    if "rate" in t and "limit" in t:      return "Demasiadas descargas. Espera unos minutos."
    if "unsupported url" in t:            return "Link no compatible."
    if "network" in t or "timed out" in t: return "Error de conexion. Verifica tu internet."
    if "ffmpeg" in t:                     return "Falta ffmpeg. Ejecuta INSTALAR.bat para instalarlo."
    if "403" in t or "400" in t:
        return "Acceso denegado. Se intentara con otros metodos."
    return "No se pudo descargar. Se intentan todos los metodos disponibles."

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
    except (FileNotFoundError, Exception):
        return False

def gallery_dl_disponible():
    return herramienta_disponible("gallery-dl")

def you_get_disponible():
    return herramienta_disponible("you-get")

EXTS_IMG  = {".jpg",".jpeg",".png",".webp",".gif",".mp4",".bmp",".tiff",".avif"}
NAVEGADORES = ["chrome","brave","firefox","edge","opera","chromium","safari","vivaldi"]

def _archivos_en_carpeta(carpeta):
    return set(
        str(p) for p in Path(carpeta).rglob("*")
        if p.is_file() and p.suffix.lower() in EXTS_IMG
    )

def _detectar_sitio(url):
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
    if "tiktok.com" in u:                                            return "tiktok"
    if "youtube.com" in u or "youtu.be" in u:                       return "youtube"
    if "facebook.com" in u or "fb.watch" in u:                      return "facebook"
    return "generico"

def _opciones_sitio(sitio):
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
    return nuevos, ""

def _run_ytdlp(url, carpeta, browser=None, progreso=None):
    antes = _archivos_en_carpeta(carpeta)
    ck = ["--cookies-from-browser", browser] if browser else []
    salida = os.path.join(carpeta, "%(title)s.%(ext)s")
    cmd = ["yt-dlp", "--no-playlist", "--newline", "-o", salida] + ck + [url]
    try:
        subprocess.run(cmd, capture_output=True, text=True,
                       timeout=60, creationflags=FLAG)
    except Exception:
        return False
    despues = _archivos_en_carpeta(carpeta)
    return len(despues - antes) > 0

def _run_you_get(url, carpeta, progreso=None):
    antes = _archivos_en_carpeta(carpeta)
    try:
        subprocess.run(["you-get", "--output-dir", carpeta, url],
                       capture_output=True, timeout=60, creationflags=FLAG)
    except Exception:
        return []
    despues = _archivos_en_carpeta(carpeta)
    return sorted(despues - antes, key=os.path.getmtime)

def _run_descarga_directa(url, carpeta):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/122.0.0.0 Safari/537.36",
            "Accept-Language": "es-MX,es;q=0.9",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            body = r.read().decode("utf-8", errors="ignore")
        pattern = r"https://pbs\.twimg\.com/media/[A-Za-z0-9_-]+"
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


# ═══════════════════════════════════════════════════════════════════════════
#  MOTOR DE DESCARGA AGRESIVO (cascada)
# ═══════════════════════════════════════════════════════════════════════════
MIN_CONTENT_SIZE = 200  # Imagenes menores a 200x200 son iconos/logos

def _validar_imagen_real(path, min_size=MIN_CONTENT_SIZE):
    """Verifica que un archivo descargado sea contenido real, no un icono.
    Retorna (es_valida, ancho, alto, formato)."""
    if not path or not os.path.exists(path):
        return False, 0, 0, ""
    if not PILLOW:
        # Sin PIL, aceptar si pesa mas de 10KB
        return os.path.getsize(path) > 10000, 0, 0, ""
    try:
        img = Image.open(path)
        w, h = img.size
        fmt = (img.format or "").upper()
        if w < min_size and h < min_size:
            return False, w, h, fmt  # Es un icono
        return True, w, h, fmt
    except Exception:
        return False, 0, 0, ""

def descargar_imagen_agresivo(url, carpeta, browser_preferido=None, progreso=None):
    """Prueba TODOS los metodos en cascada hasta descargar la imagen REAL.
    Valida cada resultado para no aceptar iconos/logos."""
    sitio = _detectar_sitio(url)
    iconos_encontrados = []  # Guardar iconos por si el usuario los quiere

    def log(msg):
        if progreso:
            progreso(msg)

    def validar(path, metodo):
        """Valida un archivo descargado. Si es icono, lo mueve aparte."""
        if not path or not os.path.exists(path):
            return None
        es_real, w, h, fmt = _validar_imagen_real(path)
        if es_real:
            return path
        # Es un icono - moverlo a subcarpeta
        log(f"Descartado: {w}x{h} (icono de pagina)")
        iconos_encontrados.append(path)
        return None

    navs_a_probar = []
    if browser_preferido and browser_preferido not in ("", "ninguno"):
        navs_a_probar.append(browser_preferido)
    for nav in NAVEGADORES:
        if nav not in navs_a_probar:
            navs_a_probar.append(nav)

    # Paso 0: scraping universal
    log("Buscando imagen en el HTML...")
    archivo0, _ = _scrape_universal(url, carpeta)
    resultado = validar(archivo0, "scraping")
    if resultado:
        return resultado, "scraping directo"

    # Ronda 1: gallery-dl con cada navegador
    for nav in navs_a_probar:
        log(f"gallery-dl + {nav}...")
        archivos, _ = _run_gallery_dl(url, carpeta, browser=nav, sitio=sitio)
        for arch in archivos:
            resultado = validar(arch, f"gallery-dl + {nav}")
            if resultado:
                return resultado, f"gallery-dl + {nav}"

    # Ronda 2: gallery-dl sin cookies
    log("gallery-dl sin cookies...")
    archivos, _ = _run_gallery_dl(url, carpeta, browser=None, sitio=sitio)
    for arch in archivos:
        resultado = validar(arch, "gallery-dl")
        if resultado:
            return resultado, "gallery-dl (publico)"

    # Ronda 3: yt-dlp con cada navegador
    for nav in navs_a_probar:
        log(f"yt-dlp + {nav}...")
        if _run_ytdlp(url, carpeta, browser=nav):
            nuevos = sorted(_archivos_en_carpeta(carpeta), key=os.path.getmtime)
            for arch in reversed(nuevos):
                resultado = validar(arch, f"yt-dlp + {nav}")
                if resultado:
                    return resultado, f"yt-dlp + {nav}"

    # Ronda 4: yt-dlp sin cookies
    log("yt-dlp sin cookies...")
    if _run_ytdlp(url, carpeta, browser=None):
        nuevos = sorted(_archivos_en_carpeta(carpeta), key=os.path.getmtime)
        for arch in reversed(nuevos):
            resultado = validar(arch, "yt-dlp")
            if resultado:
                return resultado, "yt-dlp (publico)"

    # Ronda 5: you-get
    log("you-get...")
    archivos_you = _run_you_get(url, carpeta)
    for arch in archivos_you:
        resultado = validar(arch, "you-get")
        if resultado:
            return resultado, "you-get"

    # Ronda 6: descarga directa (Twitter)
    if sitio == "twitter":
        log("descarga directa del tweet...")
        archivo = _run_descarga_directa(url, carpeta)
        resultado = validar(archivo, "directo")
        if resultado:
            return resultado, "descarga directa"

    return None, None


# ═══════════════════════════════════════════════════════════════════════════
#  EXTRACCION DE IMAGENES DEL HTML
# ═══════════════════════════════════════════════════════════════════════════
_BLACKLIST_IMG = [
    "abs.twimg.com", "profile_images", "default_profile",
    "favicon", "/icons/", "apple-touch-icon", "logo_white",
    "twitter_logo", "googlelogo", "site_logo", "brand_logo",
    "emoji", "avatar", "badge", "sprite", "placeholder",
    "/static/", "cdn.shopify.com/s/files",
    "widgets.twimg", "ton.twimg.com",
    "logo.", "/logo", "_logo", "site-logo", "header-logo",
    "footer", "btn_", "button_", "arrow_",
    "loading", "spinner", "pixel.gif", "spacer",
    "tracking", "analytics", "beacon",
    ".svg", "gravatar.com", "wp-content/plugins",
    "googleadservices", "doubleclick", "facebook.com/tr",
    "connect.facebook.net", "platform.twitter.com",
]

def _es_imagen_valida(url, sitio="generico"):
    u = url.lower()
    if any(b in u for b in _BLACKLIST_IMG):
        return False
    if re.search(r'[_-](?:16|24|32|48|64|72|96)(?:x\d+)?\.', u):
        return False
    # Rechazar URLs muy cortas (tracking pixels)
    path = u.split("?")[0]
    if len(path) < 25:
        return False
    return True

def _extraer_urls_imagen(body, sitio="generico"):
    """Extrae URLs priorizando contenido real sobre logos/iconos."""
    urls_cdn  = []
    urls_meta = []
    urls_gen  = []
    seen = set()

    def _add(lst, u):
        u = html.unescape(u.strip()).replace("\u0026", "&")
        if u.startswith("http") and u not in seen and _es_imagen_valida(u, sitio):
            seen.add(u)
            lst.append(u)

    PRE = "https://"

    # 1. CDNs de contenido real
    for pat in [
        PRE + r"pbs[.]twimg[.]com/media/[A-Za-z0-9_-]+",
        PRE + r"[a-z0-9.-]+cdninstagram[.]com/[^ \t<>]+",
        PRE + r"[a-z0-9.-]+fbcdn[.]net/[^ \t<>]+",
        PRE + r"i[.]redd[.]it/[A-Za-z0-9_-]+[.][a-z]+",
        PRE + r"preview[.]redd[.]it/[^ \t<>]+",
        PRE + r"i[.]imgur[.]com/[A-Za-z0-9]+[.][a-z]+",
        PRE + r"i[.]pinimg[.]com/[^ \t<>]+",
        PRE + r"[0-9]+[.]media[.]tumblr[.]com/[^ \t<>]+",
    ]:
        for m in re.finditer(pat, body, re.IGNORECASE):
            _add(urls_cdn, m.group(0))

    # JSON keys
    for key in ['"display_url"', '"image_url"', '"media_url"', '"download_url"']:
        for m in re.finditer(key + r':"(https://[^"]+)"', body, re.IGNORECASE):
            u = m.group(1)
            if any(x in u.lower() for x in [".jpg",".png",".webp",".gif","cdninstagram","fbcdn","twimg","redd.it","imgur"]):
                _add(urls_cdn, u)

    # 2. og:image / meta tags
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

    # 3. Fallback
    for m in re.finditer(r"https?://[^ \t<>]+[.](?:jpg|jpeg|png|webp|gif)", body, re.IGNORECASE):
        _add(urls_gen, m.group(0))

    return urls_cdn + urls_meta + urls_gen

def _descargar_url_imagen(img_url, carpeta, headers):
    try:
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

        # Verificar que sea imagen real con PIL (no logo/icono pequeno)
        if PILLOW:
            try:
                img_check = Image.open(io.BytesIO(data))
                w, h = img_check.size
                # Rechazar imagenes menores a 200x200 (son iconos/logos)
                if w < MIN_CONTENT_SIZE and h < MIN_CONTENT_SIZE:
                    return None
            except Exception:
                pass  # Si PIL falla, continuar de todas formas

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
    H = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/122.0.0.0 Safari/537.36",
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
        return None, "No se encontraron imagenes"
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
    ext      = (info.get("ext") or "").lower()
    vcodec   = (info.get("vcodec") or "").lower()
    acodec   = (info.get("acodec") or "").lower()
    dur      = info.get("duration", 0) or 0
    if ext == "gif":                                      return "gif"
    if ext in ("jpg","jpeg","png","webp","bmp","tiff"):   return "imagen"
    if vcodec == "none" and acodec != "none":             return "audio"
    if dur > 0 or vcodec not in ("none",""):              return "video"
    return "imagen"

def _obtener_dimensiones_imagen(url_img):
    """Descarga parcialmente una imagen para obtener sus dimensiones."""
    if not PILLOW:
        return None, None
    try:
        H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
        if "pbs.twimg.com/media" in url_img:
            url_img = url_img.split("?")[0] + "?format=jpg&name=small"
        req = urllib.request.Request(url_img, headers=H)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = r.read()
        if len(data) < 500:
            return None, None
        img = Image.open(io.BytesIO(data))
        return img.size  # (width, height)
    except Exception:
        return None, None


# ═══════════════════════════════════════════════════════════════════════════
#  SISTEMA DE ACTUALIZACIONES
# ═══════════════════════════════════════════════════════════════════════════
GITHUB_USER  = "UwUMADDOX"
GITHUB_REPO  = "VidGet"
GITHUB_API   = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"

def _version_tuple(v):
    try:
        return tuple(int(x) for x in str(v).strip("v").split("."))
    except Exception:
        return (0,)

def verificar_actualizacion():
    try:
        req = urllib.request.Request(
            GITHUB_API,
            headers={"User-Agent": "VidGet-Updater/1.0",
                     "Accept": "application/vnd.github.v3+json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read().decode())
        version_remota = data.get("tag_name", "0").lstrip("v")
        if _version_tuple(version_remota) > _version_tuple(VERSION):
            assets = data.get("assets", [])
            url = next(
                (a["browser_download_url"] for a in assets
                 if a["name"].lower().endswith(".exe")),
                f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/releases/latest/download/VidGet.exe"
            )
            return True, version_remota, url
    except Exception:
        pass
    return False, None, None

def descargar_actualizacion(url, progreso_cb=None):
    try:
        import tempfile
        tmp = tempfile.mktemp(suffix=".exe", prefix="VidGet_upd_")
        def hook(c, bs, ts):
            if ts > 0 and progreso_cb:
                progreso_cb(min(100, int(c * bs * 100 / ts)))
        urllib.request.urlretrieve(url, tmp, hook)
        return tmp
    except Exception:
        return None

def aplicar_actualizacion(nuevo_exe):
    if not getattr(sys, "frozen", False): return
    exe_actual = sys.executable
    import tempfile
    bat = (f'@echo off\ntimeout /t 2 /nobreak > nul\n'
           f'move /y "{nuevo_exe}" "{exe_actual}"\n'
           f'start "" "{exe_actual}"\n'
           f'del "%~f0"\n')
    bp = tempfile.mktemp(suffix=".bat")
    with open(bp, "w") as f:
        f.write(bat)
    subprocess.Popen(["cmd","/c",bp],
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
    sys.exit(0)


# ═══════════════════════════════════════════════════════════════════════════
#  Download runner (para yt-dlp)
# ═══════════════════════════════════════════════════════════════════════════
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
            elif "error" in l.lower():
                err_lines.append(l)
        stderr_txt = proceso.stderr.read() or ""
        proceso.wait()
        if proceso.returncode == 0:
            progress_panel.after(0, on_done)
        else:
            msg = interpretar_error("\n".join(err_lines) + "\n" + stderr_txt)
            progress_panel.after(0, lambda m=msg: on_error(m))
    except FileNotFoundError:
        progress_panel.after(0, lambda: on_error("yt-dlp no instalado. Ejecuta INSTALAR.bat."))
    except Exception as e:
        progress_panel.after(0, lambda err=str(e): on_error(err))


# ═══════════════════════════════════════════════════════════════════════════
#  PROGRESS PANEL
# ═══════════════════════════════════════════════════════════════════════════
class ProgressPanel(tk.Frame):
    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG)
        super().__init__(parent, **kw)
        self._build()

    def _build(self):
        self.lbl_estado = mk_label(self, "", fg=MUTED, font=F_SM)
        self.lbl_estado.pack(anchor="w")
        self.barra = ttk.Progressbar(self, style="VG.Horizontal.TProgressbar",
                                      mode="determinate")
        self.barra.pack(fill="x", pady=(5,3))
        meta = mk_frame(self)
        meta.pack(fill="x")
        self.lbl_vel  = mk_label(meta, "", fg=MUTED, font=F_XS)
        self.lbl_vel.pack(side="left")
        self.lbl_eta  = mk_label(meta, "", fg=MUTED, font=F_XS)
        self.lbl_eta.pack(side="left", padx=(14,0))
        self.lbl_size = mk_label(meta, "", fg=MUTED, font=F_XS)
        self.lbl_size.pack(side="left", padx=(14,0))
        self.lbl_resultado = mk_label(self, "", fg=SUCCESS, font=F_SM,
                                       wraplength=500, justify="left")
        self.lbl_resultado.pack(anchor="w", pady=(6,0))

    def reset(self):
        self.barra["value"] = 0
        for w in [self.lbl_vel, self.lbl_eta, self.lbl_size,
                  self.lbl_estado, self.lbl_resultado]:
            w.config(text="")

    def set_estado(self, txt, color=MUTED):
        self.lbl_estado.config(text=txt, fg=color)

    def set_resultado(self, txt, color=SUCCESS):
        self.lbl_resultado.config(text=txt, fg=color)

    def update_dl(self, pct, vel=None, eta=None, size=None):
        self.barra["value"] = pct
        self.set_estado(f"Descargando...  {int(pct)}%", MUTED)
        if vel:  self.lbl_vel.config(text=f"  {vel}")
        if eta and eta != "Unknown": self.lbl_eta.config(text=f"  {eta}")
        if size: self.lbl_size.config(text=f"  {size}")


# ═══════════════════════════════════════════════════════════════════════════
#  PANEL VIDEO / AUDIO
# ═══════════════════════════════════════════════════════════════════════════
class PanelVideoAudio(tk.Frame):
    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG)
        super().__init__(parent, **kw)
        self._build()

    def _build(self):
        pad = {"padx": 14}
        mk_label(self, "Calidad de video:", fg=MUTED, font=F_XS).pack(
            anchor="w", pady=(12,6), **pad)
        self.calidad = tk.StringVar(value="best")
        row = mk_frame(self)
        row.pack(fill="x", **pad)
        for txt, val in [("Mejor", "best"), ("1080p","1080"),
                         ("720p","720"), ("480p","480")]:
            mk_radio(row, txt, self.calidad, val).pack(side="left", padx=(0,10))

        mk_sep(self, padx=14, pady=10)

        mk_label(self, "Tipo de descarga:", fg=MUTED, font=F_XS).pack(
            anchor="w", pady=(0,6), **pad)
        self.tipo = tk.StringVar(value="video")
        row2 = mk_frame(self)
        row2.pack(fill="x", **pad)
        mk_radio(row2, "Video (MP4)", self.tipo, "video").pack(
            side="left", padx=(0,12))
        mk_radio(row2, "Solo audio (MP3)", self.tipo, "audio").pack(
            side="left", padx=(0,12))

    def set_tipo(self, tipo):
        self.tipo.set("audio" if tipo == "audio" else "video")

    def build_cmd(self, url):
        salida = os.path.join(CARPETA, "%(title)s.%(ext)s")
        if self.tipo.get() == "audio":
            return ["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "0",
                    "--no-playlist", "--newline", "-o", salida, url]
        fmts = {
            "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080]/best",
            "720":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best",
            "480":  "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480]/best",
        }
        return ["yt-dlp", "-f", fmts.get(self.calidad.get(), fmts["best"]),
                "--merge-output-format", "mp4", "--no-playlist",
                "--newline", "-o", salida, url]


# ═══════════════════════════════════════════════════════════════════════════
#  PANEL GIF
# ═══════════════════════════════════════════════════════════════════════════
class PanelGIF(tk.Frame):
    def __init__(self, parent, **kw):
        kw.setdefault("bg", BG)
        super().__init__(parent, **kw)
        self._es_gif_directo = False
        self._duracion = 0
        self._build()

    def _build(self):
        pad = {"padx": 14}
        self.lbl_aviso = mk_label(self, "", fg=MUTED, font=F_SM,
                                   wraplength=440, justify="left")
        self.lbl_aviso.pack(anchor="w", pady=(10,6), **pad)

        self.panel_recorte = mk_frame(self)
        mk_label(self.panel_recorte, "Recorte de tiempo:", fg=MUTED,
                 font=F_XS).pack(anchor="w", pady=(0,6), **pad)
        row = mk_frame(self.panel_recorte)
        row.pack(fill="x", **pad)
        mk_label(row, "Inicio (seg):", fg=TEXT, font=F_SM).pack(side="left")
        self.inicio_var = tk.StringVar(value="0")
        mk_entry(row, self.inicio_var).pack(
            side="left", ipady=5, ipadx=5, padx=(6,14))
        mk_label(row, "Fin (seg):", fg=TEXT, font=F_SM).pack(side="left")
        self.fin_var = tk.StringVar(value="10")
        mk_entry(row, self.fin_var).pack(
            side="left", ipady=5, ipadx=5, padx=(6,0))

        self.lbl_dur = mk_label(self.panel_recorte, "", fg=MUTED, font=F_XS)
        self.lbl_dur.pack(anchor="w", **pad, pady=(4,0))

        mk_sep(self.panel_recorte, padx=14, pady=8)

        mk_label(self.panel_recorte, "Resolucion del GIF:", fg=MUTED,
                 font=F_XS).pack(anchor="w", pady=(0,6), **pad)
        self.res = tk.StringVar(value="480")
        row_r = mk_frame(self.panel_recorte)
        row_r.pack(fill="x", **pad)
        for txt, val in [("480p","480"), ("360p","360"), ("240p","240")]:
            mk_radio(row_r, txt, self.res, val).pack(side="left", padx=(0,12))

        self.panel_recorte.pack(fill="x")

    def on_info(self, info):
        ext = info.get("ext","")
        dur = info.get("duration",0) or 0
        self._duracion = dur
        self._es_gif_directo = (ext == "gif")
        if self._es_gif_directo:
            self.panel_recorte.pack_forget()
            self.lbl_aviso.config(text="GIF directo, se descarga sin conversion.", fg=SUCCESS)
        else:
            self.lbl_aviso.config(text="Define el fragmento a convertir en GIF.", fg=MUTED)
            self.panel_recorte.pack(fill="x", after=self.lbl_aviso)
            if dur:
                self.fin_var.set(str(min(10, int(dur))))
                self.lbl_dur.config(text=f"Duracion total: {segundos_a_hms(dur)}")

    def on_clear(self):
        self._es_gif_directo = False
        self._duracion = 0
        self.lbl_aviso.config(text="")
        self.lbl_dur.config(text="")
        self.panel_recorte.pack(fill="x", after=self.lbl_aviso)

    def build_cmd(self, url):
        salida = os.path.join(CARPETA, "%(title)s.%(ext)s")
        if self._es_gif_directo:
            return ["yt-dlp", "--no-playlist", "--newline", "-o", salida, url], None
        try:
            inicio = float(self.inicio_var.get())
            fin = float(self.fin_var.get())
        except ValueError:
            return None, "Inicio y Fin deben ser numeros."
        if fin <= inicio:
            return None, "Fin debe ser mayor que inicio."
        if fin - inicio > 120:
            return None, "Maximo 2 minutos por GIF."
        res_val = self.res.get()
        salida_gif = os.path.join(CARPETA, "%(title)s.gif")
        cmd = ["yt-dlp", "--download-sections", f"*{inicio}-{fin}", "--no-playlist",
               "--newline", "--recode-video", "gif", "--postprocessor-args",
               f"ffmpeg:-vf scale={res_val}:-1:flags=lanczos,fps=12",
               "-o", salida_gif, url]
        return cmd, None


# ═══════════════════════════════════════════════════════════════════════════
#  PANEL IMAGEN (avanzado)
# ═══════════════════════════════════════════════════════════════════════════
class PanelImagen(tk.Frame):
    def __init__(self, parent, get_url_fn, progress, **kw):
        kw.setdefault("bg", BG)
        super().__init__(parent, **kw)
        self.get_url  = get_url_fn
        self.progress = progress
        self._es_video   = False
        self._duracion   = 0
        self._frame_img  = None
        self._build()

    def _build(self):
        pad = {"padx": 14}
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

        self.prev_box2 = mk_frame(self.panel_slider, bg_color=SURFACE, height=90)
        self.prev_box2.pack(fill="x", **pad, pady=(6,0))
        self.prev_box2.pack_propagate(False)
        self.lbl_ph2 = mk_label(self.prev_box2,
            "Mueve el slider para ver el fotograma",
            fg=MUTED, font=F_XS, bg_color=SURFACE)
        self.lbl_ph2.pack(expand=True)
        self.lbl_fi = tk.Label(self.prev_box2, bg=SURFACE)
        mk_btn(self.panel_slider, "  Ver fotograma",
               self._preview_frame, padx=10, pady=5).pack(
               anchor="w", **pad, pady=(6,0))

        # Sub-pestanas de imagen (estilos ya configurados globalmente)
        self.sub_nb = ttk.Notebook(self, style="Img3.TNotebook")
        self.sub_nb.pack(fill="both", expand=True, padx=14, pady=(8,4))

        self._build_tab_dl()
        self._build_tab_recortar()
        self._build_tab_comprimir()
        self._build_tab_convertir()

    def _build_tab_dl(self):
        f = mk_frame(self.sub_nb, bg_color=SURFACE)
        self.sub_nb.add(f, text="  Descargar")

        mk_label(f, "Resolucion de salida:", fg=MUTED, font=F_XS,
                 bg_color=SURFACE).pack(anchor="w", padx=12, pady=(12,6))
        self.dl_res = tk.StringVar(value="original")
        row = mk_frame(f, bg_color=SURFACE)
        row.pack(fill="x", padx=12)
        for txt, val in [("Original","original"),("1920px","1920"),
                         ("1280px","1280"),("800px","800"),("400px","400")]:
            mk_radio(row, txt, self.dl_res, val, bg_color=SURFACE).pack(
                side="left", padx=(0,8))

        row2 = mk_frame(f, bg_color=SURFACE)
        row2.pack(fill="x", padx=12, pady=(10,6))
        mk_label(row2, "Ancho x Alto personalizado:", fg=MUTED, font=F_XS,
                 bg_color=SURFACE).pack(side="left")
        self.dl_custom = tk.StringVar()
        self.dl_custom.trace_add("write",
            lambda *_: self.dl_res.set("custom") if self.dl_custom.get() else None)
        mk_entry(row2, self.dl_custom).pack(
            side="left", ipady=5, ipadx=5, padx=(6,4))
        mk_label(row2, "px", fg=MUTED, font=F_XS, bg_color=SURFACE).pack(side="left")

        mk_sep(f, padx=12, pady=8)

        mk_label(f, "Formato de salida:", fg=MUTED, font=F_XS,
                 bg_color=SURFACE).pack(anchor="w", padx=12, pady=(0,6))
        self.dl_fmt = tk.StringVar(value="original")
        row3 = mk_frame(f, bg_color=SURFACE)
        row3.pack(fill="x", padx=12, pady=(0,10))
        for txt, val in [("Original","original"),("JPG","JPG"),
                         ("PNG","PNG"),("WEBP","WEBP")]:
            mk_radio(row3, txt, self.dl_fmt, val, bg_color=SURFACE).pack(
                side="left", padx=(0,8))

    def _build_tab_recortar(self):
        f = mk_frame(self.sub_nb, bg_color=SURFACE)
        self.sub_nb.add(f, text="  Recortar")
        if not PILLOW:
            mk_label(f, "Requiere Pillow.", fg=WARN, font=F_SM,
                     bg_color=SURFACE).pack(padx=12, pady=16)
            return
        mk_label(f, "Pixeles a recortar por lado:", fg=MUTED,
                 font=F_XS, bg_color=SURFACE).pack(anchor="w", padx=12, pady=(12,8))
        grid = mk_frame(f, bg_color=SURFACE)
        grid.pack(padx=12, anchor="w")
        self.crop = {}
        for i, lado in enumerate(["Arriba","Abajo","Izquierda","Derecha"]):
            mk_label(grid, lado+":", fg=TEXT, font=F_SM, bg_color=SURFACE).grid(
                row=i//2, column=(i%2)*2, sticky="w", padx=(0,4), pady=5)
            v = tk.StringVar(value="0")
            mk_entry(grid, v).grid(
                row=i//2, column=(i%2)*2+1, padx=(0,16), pady=5, ipady=5)
            self.crop[lado] = v
        mk_label(f, "Se guarda como PNG.", fg=MUTED, font=F_XS,
                 bg_color=SURFACE).pack(anchor="w", padx=12, pady=(8,0))

    def _build_tab_comprimir(self):
        f = mk_frame(self.sub_nb, bg_color=SURFACE)
        self.sub_nb.add(f, text="  Comprimir")
        if not PILLOW:
            mk_label(f, "Requiere Pillow.", fg=WARN, font=F_SM,
                     bg_color=SURFACE).pack(padx=12, pady=16)
            return
        mk_label(f, "Calidad JPEG (10 = max compresion / 100 = sin perdida):",
                 fg=MUTED, font=F_XS, bg_color=SURFACE).pack(
                     anchor="w", padx=12, pady=(12,6))
        self.calidad_img = tk.IntVar(value=85)
        sl_row = mk_frame(f, bg_color=SURFACE)
        sl_row.pack(fill="x", padx=12)
        sl = ttk.Scale(sl_row, from_=10, to=100, variable=self.calidad_img,
                       orient="horizontal",
                       command=lambda v: self.lbl_q.config(text=f"{int(float(v))}%"))
        sl.pack(side="left", fill="x", expand=True)
        self.lbl_q = mk_label(sl_row, "85%", fg=ACCENT, font=F_BOLD, bg_color=SURFACE)
        self.lbl_q.pack(side="left", padx=(10,0))
        mk_label(f, "Se guarda como JPG optimizado.", fg=MUTED, font=F_XS,
                 bg_color=SURFACE).pack(anchor="w", padx=12, pady=(8,0))

    def _build_tab_convertir(self):
        f = mk_frame(self.sub_nb, bg_color=SURFACE)
        self.sub_nb.add(f, text="  Convertir")
        if not PILLOW:
            mk_label(f, "Requiere Pillow.", fg=WARN, font=F_SM,
                     bg_color=SURFACE).pack(padx=12, pady=16)
            return
        mk_label(f, "Convertir a:", fg=MUTED, font=F_XS,
                 bg_color=SURFACE).pack(anchor="w", padx=12, pady=(12,6))
        self.formato_conv = tk.StringVar(value="PNG")
        row = mk_frame(f, bg_color=SURFACE)
        row.pack(fill="x", padx=12)
        for fmt in ["PNG","JPG","WEBP","BMP","TIFF","ICO"]:
            mk_radio(row, fmt, self.formato_conv, fmt, bg_color=SURFACE).pack(
                side="left", padx=(0,8))

        mk_sep(f, padx=12, pady=10)

        mk_label(f, "Convertir archivos ya descargados",
                 fg=TEXT2, font=("Segoe UI", 9, "bold"), bg_color=SURFACE).pack(
                     anchor="w", padx=12, pady=(0,4))
        mk_label(f, "Selecciona imagenes de tu carpeta VidGet.",
                 fg=MUTED, font=F_XS, bg_color=SURFACE, wraplength=420,
                 justify="left").pack(anchor="w", padx=12, pady=(0,8))

        self.lbl_archivos_sel = mk_label(f, "Ningun archivo seleccionado",
                                          fg=MUTED, font=F_XS, bg_color=SURFACE)
        self.lbl_archivos_sel.pack(anchor="w", padx=12)

        btns = mk_frame(f, bg_color=SURFACE)
        btns.pack(fill="x", padx=12, pady=(8,4))
        mk_btn(btns, "  Seleccionar imagenes", self._seleccionar_archivos_locales,
               padx=14, pady=8).pack(side="left")
        mk_btn(btns, "  Abrir carpeta VidGet", self._abrir_carpeta_vidget,
               fg=MUTED, padx=14, pady=8).pack(side="left", padx=(10,0))

        self._archivos_locales = []

        mk_btn(f, "  Convertir archivos seleccionados",
               self._convertir_archivos_locales,
               bg_color="#1a2a00", fg=ACCENT, font=("Segoe UI", 10, "bold"),
               padx=10, pady=10).pack(fill="x", padx=12, pady=(8,10))

        self.conv_progress_lbl = mk_label(f, "", fg=MUTED, font=F_XS,
                                           bg_color=SURFACE)
        self.conv_progress_lbl.pack(anchor="w", padx=12, pady=(0,6))

    def _seleccionar_archivos_locales(self):
        from tkinter import filedialog
        archivos = filedialog.askopenfilenames(
            title="Selecciona imagenes",
            initialdir=CARPETA,
            filetypes=[("Imagenes", "*.jpg *.jpeg *.png *.webp *.gif *.bmp *.tiff *.avif"),
                       ("Todos", "*.*")])
        if archivos:
            self._archivos_locales = list(archivos)
            n = len(archivos)
            nombres = ", ".join(os.path.basename(a) for a in archivos[:3])
            if n > 3: nombres += f" (+{n-3} mas)"
            self.lbl_archivos_sel.config(text=f"{n} archivo(s): {nombres}", fg=SUCCESS)

    def _abrir_carpeta_vidget(self):
        if sys.platform == "win32": os.startfile(CARPETA)
        elif sys.platform == "darwin": subprocess.Popen(["open", CARPETA])
        else: subprocess.Popen(["xdg-open", CARPETA])

    def _convertir_archivos_locales(self):
        if not self._archivos_locales:
            self.conv_progress_lbl.config(text="Selecciona archivos primero.", fg=WARN)
            return
        if not PILLOW:
            self.conv_progress_lbl.config(text="Pillow no instalado.", fg=ERROR)
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
                    text=f"Convirtiendo {i}/{t} a {f}...", fg=MUTED))
            try:
                img      = Image.open(path)
                save_fmt = "JPEG" if fmt == "JPG" else fmt
                if fmt in ("JPG","BMP"):  img = img.convert("RGB")
                elif fmt == "ICO":        img = img.resize((256,256), Image.LANCZOS)
                elif fmt == "PNG":        img = img.convert("RGBA")
                base    = os.path.splitext(os.path.basename(path))[0]
                destino = os.path.join(CARPETA, base + "_" + fmt.lower() + ext)
                kw = {"quality": self.calidad_img.get()} if fmt == "JPG" else {}
                img.save(destino, save_fmt, **kw)
                ok += 1
            except Exception:
                fail += 1
        msg = f"{ok}/{total} convertidos a {fmt}"
        if fail: msg += f"  ({fail} fallaron)"
        color = SUCCESS if not fail else WARN
        self.after(0, lambda: self.conv_progress_lbl.config(text=msg, fg=color))
        self.after(0, lambda: self.lbl_archivos_sel.config(
            text="Ningun archivo seleccionado", fg=MUTED))
        self._archivos_locales = []

    def on_info(self, info):
        ext = info.get("ext","")
        dur = info.get("duration",0) or 0
        self._duracion = dur
        es_img = ext in ("jpg","jpeg","png","webp","bmp","tiff")
        if es_img:
            self._es_video = False
            self.lbl_aviso.config(text="Imagen detectada.", fg=SUCCESS)
            self.panel_slider.pack_forget()
        elif dur > 0:
            self._es_video = True
            self.lbl_aviso.config(
                text=f"Video ({segundos_a_hms(dur)}). Usa el slider para elegir fotograma.",
                fg=TEXT)
            self.slider.config(to=dur)
            self.slider_var.set(0)
            self.lbl_seg.config(text="0s")
            self._reset_frame_prev()
            self.panel_slider.pack(fill="x", padx=14, pady=(0,6), before=self.sub_nb)
        else:
            self._es_video = False
            self.lbl_aviso.config(text="Se descargara como imagen.", fg=WARN)
            self.panel_slider.pack_forget()

    def on_clear(self):
        self._es_video = False
        self._duracion = 0
        self.lbl_aviso.config(text="")
        self.panel_slider.pack_forget()
        self._reset_frame_prev()

    def _reset_frame_prev(self):
        self.lbl_fi.pack_forget()
        self.lbl_ph2.pack(expand=True)

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
            self.after(0, lambda: self.lbl_ph2.config(text="Instala Pillow."))
            return
        try:
            tmp = os.path.join(CARPETA, "_frame_preview.jpg")
            info_r = subprocess.run(
                ["yt-dlp","-g","--no-playlist",url],
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
                self.after(0, lambda: self.lbl_ph2.config(
                    text="No se pudo extraer. Instala ffmpeg."))
        except Exception as e:
            self.after(0, lambda: self.lbl_ph2.config(text=f"Error: {e}"))

    def get_tab_idx(self):
        return self.sub_nb.index(self.sub_nb.select())

    def build_cmd_simple(self, url):
        salida = os.path.join(CARPETA, "%(title)s.%(ext)s")
        return ["yt-dlp","--no-playlist","--newline","-o",salida,url]

    def postprocesar(self, archivo, on_done, on_error):
        tab = self.get_tab_idx()
        if not PILLOW:
            on_done(archivo)
            return
        ops = {0: self._op_descargar, 1: self._op_recortar,
               2: self._op_comprimir, 3: self._op_convertir}
        op = ops.get(tab, lambda a,d,e: d(a))
        threading.Thread(target=op, args=(archivo, on_done, on_error),
                         daemon=True).start()

    def _nuevo_nombre(self, path, sufijo, ext):
        base = os.path.splitext(os.path.basename(path))[0]
        return os.path.join(CARPETA, base + sufijo + ext)

    def _op_descargar(self, archivo, on_done, on_error):
        try:
            img = Image.open(archivo)
            custom  = self.dl_custom.get().strip()
            res_val = self.dl_res.get()
            ancho   = (int(custom) if custom and custom.isdigit()
                       else (None if res_val == "original" else int(res_val)))
            if ancho and ancho != img.width:
                ratio = ancho / img.width
                img   = img.resize((ancho, int(img.height*ratio)), Image.LANCZOS)
            fmt = self.dl_fmt.get()
            if fmt == "original":
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
            box    = (left, top, w - right if right else w, h - bottom if bottom else h)
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
            kw = {"quality": self.calidad_img.get()} if fmt == "JPG" else {}
            img.save(s, save_fmt, **kw)
            on_done(s)
        except Exception as e:
            on_error(str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  VENTANA PRINCIPAL — VidGet
# ═══════════════════════════════════════════════════════════════════════════
class VidGet(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"VidGet v{VERSION}")
        self.minsize(WIN_MIN_W, WIN_SIMPLE_H)
        self.geometry(f"{WIN_MIN_W}x{WIN_SIMPLE_H}")
        self.configure(bg=BG)

        # Estilos ttk globales (elimina look Windows XP)
        _setup_ttk_styles()

        # Aplicar barra de titulo oscura (quita el borde blanco)
        _aplicar_dark_titlebar(self)

        # Cargar icono (quita la pluma de tkinter)
        _cargar_icono_ventana(self)

        self._info           = None
        self._tipo           = None
        self._busy           = False
        self._modo_avanzado  = tk.BooleanVar(value=False)
        self._thumb_imgs     = []
        self._thumb_urls     = []
        self._thumb_selected = {}   # idx -> BooleanVar
        self._thumb_dims     = {}   # idx -> (w, h)
        self._logo_img       = None
        self._prev_photo     = None

        self._build()
        self.bind("<Configure>", self._on_resize)
        self._centrar_ventana()
        threading.Thread(target=self._check_update_bg, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _build(self):
        main = mk_frame(self)
        main.pack(fill="both", expand=True)

        # ── HEADER ─────────────────────────────────────────────────────────
        hdr = mk_frame(main)
        hdr.pack(fill="x", padx=24, pady=(18,0))

        # Logo
        hdr_left = mk_frame(hdr)
        hdr_left.pack(side="left")
        self._logo_img = _cargar_logo(self, size=30)
        if self._logo_img:
            tk.Label(hdr_left, image=self._logo_img, bg=BG).pack(side="left", padx=(0,8))
        mk_label(hdr_left, "VidGet", fg=ACCENT, font=F_HEADER).pack(side="left")
        mk_label(hdr_left, f"v{VERSION}", fg=MUTED2, font=F_XS).pack(
            side="left", padx=(6,0), pady=(3,0))

        # Header right
        hdr_right = mk_frame(hdr)
        hdr_right.pack(side="right")

        self.btn_update = tk.Button(hdr_right, text="",
                                     command=self._mostrar_update_dialog,
                                     bg="#1a2600", fg=ACCENT,
                                     font=("Segoe UI", 8, "bold"),
                                     relief="flat", cursor="hand2",
                                     activebackground="#2a3f00",
                                     padx=10, pady=4)
        self._update_info = None

        mk_btn(hdr_right, "  Carpeta", self._abrir_carpeta,
               fg=MUTED, font=F_XS, padx=10, pady=5).pack(side="right")
        mk_btn(hdr_right, "  Config", self._mostrar_config,
               fg=MUTED, font=F_XS, padx=10, pady=5).pack(side="right", padx=(0,4))
        mk_check(hdr_right, "Avanzado", self._modo_avanzado,
                 bg_color=BG, command=self._toggle_avanzado).pack(side="right", padx=(0,10))

        # ── TITULO ─────────────────────────────────────────────────────────
        mk_label(main, "Video  ·  Audio  ·  Imagen  ·  GIF",
                 fg=TEXT, font=F_LG).pack(anchor="w", padx=24, pady=(12,0))
        mk_label(main,
                 "YouTube  ·  Instagram  ·  TikTok  ·  Twitter/X  ·  Reddit  ·  +1000 sitios",
                 fg=MUTED, font=F_XS).pack(anchor="w", padx=24, pady=(2,10))

        mk_sep(main, padx=24, pady=4)

        # ── URL INPUT ──────────────────────────────────────────────────────
        url_section = mk_frame(main)
        url_section.pack(fill="x", padx=24, pady=(6,0))

        mk_label(url_section, "PEGA EL LINK AQUI", fg=ACCENT,
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0,6))

        url_row = mk_frame(url_section)
        url_row.pack(fill="x")

        # URL entry con borde accent
        url_container = tk.Frame(url_row, bg=ACCENT, padx=1, pady=1)
        url_container.pack(side="left", fill="x", expand=True)
        self.url_var = tk.StringVar()
        self.url_var.trace_add("write", self._on_url_change)
        self.url_entry = tk.Entry(url_container, textvariable=self.url_var,
                                  bg=SURFACE, fg=TEXT, insertbackground=ACCENT,
                                  relief="flat", font=("Segoe UI", 11),
                                  highlightthickness=0)
        self.url_entry.pack(fill="x", ipady=10, ipadx=10)
        self.url_entry.bind("<Return>", lambda e: self._descargar())

        btn_frame = mk_frame(url_row)
        btn_frame.pack(side="left", padx=(6,0))
        mk_btn(btn_frame, " Pegar", self._pegar, bg_color=SURFACE2,
               font=F_SM, padx=12, pady=10).pack(side="left")
        mk_btn(btn_frame, " X ", self._limpiar, fg=MUTED, font=F_SM,
               padx=10, pady=10).pack(side="left", padx=(4,0))

        # Status label
        self.lbl_valid = mk_label(url_section, "", fg=MUTED, font=F_SM)
        self.lbl_valid.pack(anchor="w", pady=(6,0))

        # ── PREVIEW / GALERIA ──────────────────────────────────────────────
        self.prev_container = mk_frame(main)
        self.prev_container.pack(fill="x", padx=24, pady=(6,0))

        self.prev_box = mk_frame(self.prev_container, bg_color=SURFACE)
        self.prev_box.pack(fill="x")
        self.prev_box.configure(height=120)
        self.prev_box.pack_propagate(False)

        self.lbl_ph = mk_label(self.prev_box,
            "Vista previa al pegar un link",
            fg=MUTED2, font=F_SM, bg_color=SURFACE)
        self.lbl_ph.pack(expand=True)

        # Canvas scrollable para galeria
        self.prev_canvas = tk.Canvas(self.prev_box, bg=SURFACE, height=110,
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
        self.prev_canvas.bind("<MouseWheel>",
            lambda e: self.prev_canvas.xview_scroll(-1*(e.delta//120), "units"))

        # Info labels
        self.lbl_prev_titulo = mk_label(self.prev_box, "", fg=TEXT, font=F_BOLD,
                                         bg_color=SURFACE, wraplength=400, justify="left")
        self.lbl_prev_meta   = mk_label(self.prev_box, "", fg=MUTED, font=F_SM,
                                         bg_color=SURFACE)
        self.lbl_tipo_badge  = mk_label(self.prev_box, "", fg=BG,
                                         font=("Segoe UI", 8, "bold"), bg_color=ACCENT)

        # Gallery info bar
        self.gallery_bar = mk_frame(self.prev_container, bg_color=SURFACE2)
        self.lbl_gallery_info = mk_label(self.gallery_bar, "", fg=MUTED, font=F_XS,
                                          bg_color=SURFACE2)
        self.lbl_gallery_info.pack(side="left", padx=10, pady=4)
        self.btn_select_all = mk_btn(self.gallery_bar, "Todas", self._select_all_thumbs,
                                     font=F_XS, fg=ACCENT, padx=8, pady=2)
        self.btn_deselect_all = mk_btn(self.gallery_bar, "Ninguna", self._deselect_all_thumbs,
                                       font=F_XS, fg=MUTED, padx=8, pady=2)

        mk_sep(main, padx=24, pady=6)

        # ── MODO AVANZADO ──────────────────────────────────────────────────
        self.avanzado_frame = mk_frame(main)

        nb_wrap = mk_frame(self.avanzado_frame, bg_color=BORDER)
        nb_wrap.pack(fill="both", expand=True, padx=24)
        nb_inner = mk_frame(nb_wrap)
        nb_inner.pack(fill="both", expand=True, padx=1, pady=(0,1))
        self.notebook = ttk.Notebook(nb_inner, style="VG.TNotebook")
        self.notebook.pack(fill="both", expand=True)

        # Progress
        self.progress = ProgressPanel(main)
        self.progress.pack(fill="x", padx=24, pady=(6,0))

        # Paneles avanzados
        self.panel_va     = PanelVideoAudio(self.notebook)
        self.panel_gif    = PanelGIF(self.notebook)
        self.panel_imagen = PanelImagen(self.notebook, self.url_var.get, self.progress)

        self.notebook.add(self.panel_va,     text="  Video / Audio  ")
        self.notebook.add(self.panel_gif,    text="  GIF  ")
        self.notebook.add(self.panel_imagen, text="  Imagen  ")

        mk_sep(main, padx=24, pady=6)

        # ── BOTON PRINCIPAL ────────────────────────────────────────────────
        self.btn = tk.Button(main, text="Descargar", command=self._descargar,
                             bg=ACCENT, fg="#0d0d11", font=("Segoe UI", 13, "bold"),
                             relief="flat", cursor="hand2", activebackground="#d4ff5a",
                             activeforeground="#0d0d11", pady=12, state="disabled")
        self.btn.pack(fill="x", padx=24, pady=(0,6))

        # Opciones finales
        bottom_row = mk_frame(main)
        bottom_row.pack(fill="x", padx=24, pady=(0,12))
        self.abrir_auto = tk.BooleanVar(value=False)
        mk_check(bottom_row, "Abrir carpeta al terminar", self.abrir_auto).pack(
            side="left")
        mk_label(bottom_row, f"Descargas en ~/Downloads/VidGet",
                 fg=MUTED2, font=("Segoe UI", 7)).pack(side="right")

    # ── URL helpers ─────────────────────────────────────────────────────
    def _pegar(self):
        try:
            self.url_var.set(self.clipboard_get().strip())
        except Exception:
            pass

    def _limpiar(self):
        self.url_var.set("")
        self._info = None
        self._tipo = None
        self._reset_prev()
        self.lbl_valid.config(text="")
        self.btn.config(state="disabled", text="Descargar")
        self.progress.reset()
        self.panel_gif.on_clear()
        self.panel_imagen.on_clear()

    def _on_url_change(self, *_):
        url = self.url_var.get().strip()
        if not url:
            self._limpiar()
            return
        if not url.startswith("http"):
            self.lbl_valid.config(text="No parece un link valido.", fg=WARN)
            self._reset_prev()
            return
        self.lbl_valid.config(text="Detectando contenido...", fg=MUTED)
        self.btn.config(state="disabled")
        threading.Thread(target=self._fetch_info, args=(url,), daemon=True).start()

    _fetch_tid = 0
    def _fetch_info(self, url):
        VidGet._fetch_tid += 1
        tid = VidGet._fetch_tid
        try:
            res = subprocess.run(
                ["yt-dlp", "--dump-json", "--no-playlist", url],
                capture_output=True, text=True, timeout=20, creationflags=FLAG)
            if tid != VidGet._fetch_tid:
                return
            if res.returncode == 0:
                info = json.loads(res.stdout)
                self._info = info
                self._tipo = detectar_tipo(info)
                self.after(0, lambda: self._apply_info(info))
                return
            # yt-dlp fallo — para sitios de imagenes, seguir adelante
            if es_sitio_imagen(url):
                self._info = {"title": url, "ext": "jpg", "duration": 0}
                self._tipo = "imagen"
                self.after(0, lambda: [
                    self.lbl_valid.config(
                        text="Contenido detectado. Listo para descargar.", fg=ACCENT),
                    self.btn.config(state="normal"),
                    self._show_prev_simple(url),
                    self.notebook.select(2)
                ])
                return
            msg = interpretar_error((res.stderr or "") + (res.stdout or ""))
            self.after(0, lambda: [
                self.lbl_valid.config(text=msg, fg=ERROR),
                self._reset_prev()
            ])
        except FileNotFoundError:
            if tid == VidGet._fetch_tid:
                self.after(0, lambda: self.lbl_valid.config(
                    text="yt-dlp no instalado. Ejecuta INSTALAR.bat.", fg=ERROR))
        except Exception:
            if tid == VidGet._fetch_tid:
                self.after(0, lambda: self.lbl_valid.config(
                    text="No se pudo verificar el link.", fg=WARN))

    def _apply_info(self, info):
        tipo = self._tipo
        nombres = {"video":"VIDEO","audio":"AUDIO","gif":"GIF","imagen":"IMAGEN"}
        # Status
        self.lbl_valid.config(
            text=f"{nombres.get(tipo,'?')} detectado — listo para descargar",
            fg=SUCCESS)
        self.btn.config(state="normal")

        # Preview info
        titulo   = info.get("title","")
        thumb    = info.get("thumbnail","")
        duracion = info.get("duration_string","")
        uploader = info.get("uploader","")
        w_vid    = info.get("width", 0) or 0
        h_vid    = info.get("height", 0) or 0

        meta_parts = []
        if duracion:  meta_parts.append(f"{duracion}")
        if uploader:  meta_parts.append(uploader)
        if w_vid and h_vid: meta_parts.append(f"{w_vid}x{h_vid}")
        meta = "  ·  ".join(meta_parts)

        self.lbl_prev_titulo.config(text=titulo)
        self.lbl_prev_meta.config(text=meta)
        self.lbl_tipo_badge.config(text=f"  {nombres.get(tipo,'?')}  ")

        # Auto-seleccionar pestana avanzada
        tab_map = {"video":0,"audio":0,"gif":1,"imagen":2}
        self.notebook.select(tab_map.get(tipo, 0))

        # Notificar paneles
        self.panel_va.set_tipo(tipo)
        self.panel_gif.on_info(info)
        self.panel_imagen.on_info(info)

        # Mostrar preview
        self._show_prev_info()

        url_actual = self.url_var.get().strip()
        if PILLOW and thumb:
            threading.Thread(target=self._load_thumb_real,
                             args=(thumb, url_actual), daemon=True).start()
        threading.Thread(target=self._cargar_thumbs_html,
                         args=(url_actual,), daemon=True).start()

    def _load_thumb_real(self, thumb_url, page_url):
        if not PILLOW:
            return
        H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}

        def _intentar_cargar(url_img, slot=0):
            try:
                if "pbs.twimg.com/media" in url_img:
                    url_img = url_img.split("?")[0] + "?format=jpg&name=medium"
                req = urllib.request.Request(url_img, headers=H)
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = r.read()
                    ct   = r.headers.get("Content-Type","")
                if len(data) < 500:
                    return False
                img = Image.open(io.BytesIO(data))
                w_real, h_real = img.size
                # Rechazar imagenes pequenas (logos/iconos)
                if w_real < MIN_CONTENT_SIZE and h_real < MIN_CONTENT_SIZE:
                    return False
                fmt = img.format or ""
                if not fmt:
                    if "webp" in ct: fmt = "WEBP"
                    elif "png" in ct: fmt = "PNG"
                    elif "gif" in ct: fmt = "GIF"
                    else: fmt = "JPG"
                is_webp = (fmt.upper() == "WEBP" or "webp" in ct
                           or url_img.lower().split("?")[0].endswith(".webp"))
                img.thumbnail((200, 120), Image.LANCZOS)
                if CONFIG.get("thumb_mode", "uniform") == "uniform":
                    canvas = Image.new("RGBA", (THUMB_W, THUMB_H), (26, 26, 36, 255))
                    paste_x = (THUMB_W - img.width) // 2
                    paste_y = (THUMB_H - img.height) // 2
                    if img.mode == "RGBA":
                        canvas.paste(img, (paste_x, paste_y), img)
                    else:
                        canvas.paste(img, (paste_x, paste_y))
                    photo = ImageTk.PhotoImage(canvas)
                else:
                    photo = ImageTk.PhotoImage(img)
                self.after(0, lambda p=photo, u=url_img, w=w_real, h=h_real,
                           f=fmt.upper(), wb=is_webp:
                           self._agregar_thumb_ui(p, slot, u, w, h, f, wb))
                return True
            except Exception:
                return False

        if _intentar_cargar(thumb_url):
            return
        try:
            req = urllib.request.Request(page_url, headers=H)
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read().decode("utf-8", errors="ignore")
            sitio = _detectar_sitio(page_url)
            urls = _extraer_urls_imagen(body, sitio=sitio)
            for u in urls[:5]:
                if _intentar_cargar(u):
                    return
        except Exception:
            pass

    def _alerta_webp(self):
        current = self.lbl_valid.cget("text")
        if "WEBP" in current:
            return
        self.lbl_valid.config(
            text="Formato WEBP detectado — Usa Avanzado > Imagen > Convertir para cambiar formato",
            fg=WARN)

    def _reset_prev(self):
        for w in self.prev_box.winfo_children():
            w.pack_forget()
        self.lbl_ph.pack(expand=True)
        self._thumb_imgs = []
        self._thumb_urls = []
        self._thumb_selected = {}
        self._thumb_dims = {}
        for w in self.prev_inner.winfo_children():
            w.destroy()
        self.gallery_bar.pack_forget()
        self.prev_box.configure(height=120)

    def _show_prev_info(self):
        """Muestra preview con badge + titulo + meta."""
        self._reset_prev()
        self.lbl_ph.pack_forget()  # Ocultar placeholder
        info_frame = mk_frame(self.prev_box, bg_color=SURFACE)
        info_frame.pack(fill="both", expand=True, padx=12, pady=10)
        # Badge
        badge = tk.Label(info_frame, text=self.lbl_tipo_badge.cget("text"),
                         fg=BG, bg=ACCENT, font=("Segoe UI",8,"bold"),
                         padx=6, pady=2)
        badge.pack(anchor="w", pady=(0,4))
        # Titulo
        tk.Label(info_frame, text=self.lbl_prev_titulo.cget("text"),
                 bg=SURFACE, fg=TEXT, font=F_BOLD,
                 wraplength=500, justify="left", anchor="w").pack(anchor="w")
        # Meta
        meta_txt = self.lbl_prev_meta.cget("text")
        if meta_txt:
            tk.Label(info_frame, text=meta_txt, bg=SURFACE, fg=MUTED,
                     font=F_SM).pack(anchor="w", pady=(2,0))

    def _show_prev_simple(self, url):
        """Preview para sitios de imagen (sin yt-dlp info)."""
        self._reset_prev()
        self.lbl_ph.pack_forget()  # Ocultar placeholder
        dominio = url.split("/")[2] if "/" in url else url
        info_frame = mk_frame(self.prev_box, bg_color=SURFACE)
        info_frame.pack(fill="both", expand=True, padx=12, pady=10)
        tk.Label(info_frame, text="  IMAGEN  ", fg=BG, bg=ACCENT,
                 font=("Segoe UI",8,"bold"), padx=6, pady=2).pack(anchor="w", pady=(0,4))
        tk.Label(info_frame, text=dominio, bg=SURFACE, fg=TEXT,
                 font=F_BOLD).pack(anchor="w")
        # Loading indicator
        self._prev_loading_lbl = tk.Label(info_frame, text="Cargando vista previa...",
                                           bg=SURFACE, fg=MUTED, font=F_XS)
        self._prev_loading_lbl.pack(anchor="w", pady=(4,0))

        # Expandir para galeria
        self.prev_box.configure(height=180)
        self.prev_canvas.pack(fill="x", padx=4, expand=True)
        self.prev_scrollbar.pack(fill="x", padx=4)
        threading.Thread(target=self._cargar_thumbs_html,
                         args=(url,), daemon=True).start()

    def _cargar_thumbs_html(self, url):
        if not PILLOW:
            return
        img_urls = []

        # Metodo 1: scraping directo del HTML
        try:
            H = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0",
                "Accept": "text/html,*/*;q=0.9",
                "Accept-Language": "es-MX,es;q=0.9",
            }
            req = urllib.request.Request(url, headers=H)
            with urllib.request.urlopen(req, timeout=12) as r:
                body = r.read().decode("utf-8", errors="ignore")
            sitio = _detectar_sitio(url)
            img_urls = _extraer_urls_imagen(body, sitio=sitio)
        except Exception:
            pass

        # Metodo 2: gallery-dl --get-urls (mas confiable para Instagram, Twitter, etc.)
        if (not img_urls or len(img_urls) < 1) and es_sitio_imagen(url):
            self.after(0, lambda: self._update_loading_lbl(
                "Buscando imagenes con gallery-dl..."))
            try:
                # Probar con cookies de cada navegador
                for nav in NAVEGADORES[:4]:
                    cmd = ["gallery-dl", "--get-urls",
                           "--cookies-from-browser", nav, url]
                    r = subprocess.run(cmd, capture_output=True, text=True,
                                       timeout=20, creationflags=FLAG)
                    if r.returncode == 0 and r.stdout.strip():
                        for line in r.stdout.strip().split("\n"):
                            line = line.strip()
                            if line.startswith("http") and _es_imagen_valida(line):
                                img_urls.append(line)
                        if img_urls:
                            break
                # Sin cookies
                if not img_urls:
                    cmd = ["gallery-dl", "--get-urls", url]
                    r = subprocess.run(cmd, capture_output=True, text=True,
                                       timeout=20, creationflags=FLAG)
                    if r.returncode == 0 and r.stdout.strip():
                        for line in r.stdout.strip().split("\n"):
                            line = line.strip()
                            if line.startswith("http") and _es_imagen_valida(line):
                                img_urls.append(line)
            except (FileNotFoundError, Exception):
                pass

        img_urls = img_urls[:12]
        self._thumb_urls = img_urls

        if not img_urls:
            self.after(0, lambda: self._update_loading_lbl(
                "No se encontraron imagenes. Puedes descargar directamente."))
            return

        # Ocultar loading, mostrar galeria
        self.after(0, lambda: self._update_loading_lbl(""))

        if len(img_urls) >= 1:
            self.after(0, lambda n=len(img_urls): [
                self.prev_box.configure(height=200),
                self.prev_canvas.pack(fill="x", padx=4, expand=True),
                self.prev_scrollbar.pack(fill="x", padx=4),
                self.gallery_bar.pack(fill="x") if n > 1 else None,
                self._update_gallery_bar() if n > 1 else None
            ])

        for i, img_url in enumerate(img_urls):
            threading.Thread(target=self._cargar_thumb_uno,
                             args=(img_url, i), daemon=True).start()

    def _update_loading_lbl(self, text):
        """Actualiza el label de carga en el preview."""
        try:
            if hasattr(self, '_prev_loading_lbl') and self._prev_loading_lbl.winfo_exists():
                if text:
                    self._prev_loading_lbl.config(text=text)
                else:
                    self._prev_loading_lbl.pack_forget()
        except Exception:
            pass

    def _cargar_thumb_uno(self, img_url, idx):
        if not PILLOW:
            return
        try:
            H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0"}
            thumb_url = img_url
            if "pbs.twimg.com/media" in img_url:
                thumb_url = img_url.split("?")[0] + "?format=jpg&name=small"
            req = urllib.request.Request(thumb_url, headers=H)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read()
                ct = r.headers.get("Content-Type", "")
            if len(data) < 500:
                return
            img = Image.open(io.BytesIO(data))
            w_real, h_real = img.size
            # Rechazar imagenes pequenas (logos/iconos)
            if w_real < MIN_CONTENT_SIZE and h_real < MIN_CONTENT_SIZE:
                return
            # Detectar formato
            fmt = img.format or ""
            if not fmt:
                if "webp" in ct: fmt = "WEBP"
                elif "png" in ct: fmt = "PNG"
                elif "gif" in ct: fmt = "GIF"
                else: fmt = "JPG"
            img.thumbnail((110, 100), Image.LANCZOS)
            # Modo uniforme: crear canvas de tamaño fijo y centrar la imagen
            if CONFIG.get("thumb_mode", "uniform") == "uniform":
                canvas = Image.new("RGBA", (THUMB_W, THUMB_H), (26, 26, 36, 255))
                paste_x = (THUMB_W - img.width) // 2
                paste_y = (THUMB_H - img.height) // 2
                if img.mode == "RGBA":
                    canvas.paste(img, (paste_x, paste_y), img)
                else:
                    canvas.paste(img, (paste_x, paste_y))
                photo = ImageTk.PhotoImage(canvas)
            else:
                photo = ImageTk.PhotoImage(img)
            is_webp = (fmt.upper() == "WEBP" or "webp" in ct
                       or img_url.lower().split("?")[0].endswith(".webp"))
            self.after(0, lambda p=photo, i=idx, u=img_url, w=w_real, h=h_real,
                       f=fmt.upper(), wb=is_webp:
                       self._agregar_thumb_ui(p, i, u, w, h, f, wb))
        except Exception:
            pass

    def _agregar_thumb_ui(self, photo, idx, url, w=0, h=0, fmt="", is_webp=False):
        self._thumb_imgs.append(photo)
        self._thumb_dims[idx] = (w, h)
        if idx not in self._thumb_selected:
            self._thumb_selected[idx] = tk.BooleanVar(value=True)

        col = len([w for w in self.prev_inner.winfo_children()
                   if isinstance(w, tk.Frame)])

        cell = tk.Frame(self.prev_inner, bg=SURFACE2, padx=2, pady=2)
        cell.grid(row=0, column=col, padx=3, pady=3)

        # Checkbox de seleccion
        chk = tk.Checkbutton(cell, variable=self._thumb_selected[idx],
                             bg=SURFACE2, selectcolor=SURFACE2,
                             activebackground=SURFACE2,
                             command=self._update_gallery_bar)
        chk.pack(anchor="w")

        # Imagen
        lbl = tk.Label(cell, image=photo, bg=SURFACE2, cursor="hand2",
                       relief="flat", bd=1)
        lbl.pack()

        # Dimensiones + formato
        dim_text = ""
        if w and h:
            dim_text = f"{w}x{h}"
            if fmt:
                dim_text += f" {fmt}"
        # Color naranja si es WEBP
        dim_fg = WARN if is_webp else MUTED
        mk_label(cell, dim_text, fg=dim_fg, font=("Segoe UI",7), bg_color=SURFACE2).pack()
        # Aviso WEBP
        if is_webp:
            self._alerta_webp()

        # Click para toggle seleccion
        def toggle(var=self._thumb_selected[idx]):
            var.set(not var.get())
            self._update_gallery_bar()
        lbl.bind("<Button-1>", lambda e: toggle())

        self._update_gallery_bar()

    def _update_gallery_bar(self):
        total = len(self._thumb_selected)
        selected = sum(1 for v in self._thumb_selected.values() if v.get())
        if total > 1:
            self.lbl_gallery_info.config(
                text=f"{selected}/{total} imagenes seleccionadas")
            self.btn_select_all.pack(side="right", padx=(0,6), pady=3)
            self.btn_deselect_all.pack(side="right", padx=(0,4), pady=3)
        else:
            self.lbl_gallery_info.config(text="")
            self.btn_select_all.pack_forget()
            self.btn_deselect_all.pack_forget()

    def _select_all_thumbs(self):
        for v in self._thumb_selected.values():
            v.set(True)
        self._update_gallery_bar()

    def _deselect_all_thumbs(self):
        for v in self._thumb_selected.values():
            v.set(False)
        self._update_gallery_bar()

    # ── Modo avanzado toggle ──────────────────────────────────────────────
    def _toggle_avanzado(self):
        if self._modo_avanzado.get():
            self.avanzado_frame.pack(fill="both", expand=True, before=self.progress)
            self.geometry(f"{WIN_MIN_W}x{WIN_ADV_H}")
            self.minsize(WIN_MIN_W, WIN_ADV_H)
        else:
            self.avanzado_frame.pack_forget()
            self.geometry(f"{WIN_MIN_W}x{WIN_SIMPLE_H}")
            self.minsize(WIN_MIN_W, WIN_SIMPLE_H)

    # ── Descarga ──────────────────────────────────────────────────────────
    def _descargar(self):
        if self._busy:
            return
        url = self.url_var.get().strip()
        if not url or not self._info:
            self.progress.set_resultado("Pega un link valido primero.", WARN)
            return

        tipo = self._tipo
        avanzado = self._modo_avanzado.get()

        self._busy = True
        self.btn.config(state="disabled", text="Descargando...", bg=BORDER, fg=MUTED)
        self.progress.reset()
        self.progress.set_estado("Conectando...", MUTED)

        if avanzado:
            tab = self.notebook.index(self.notebook.select())
            if tab == 0:
                cmd = self.panel_va.build_cmd(url)
                threading.Thread(target=run_download,
                                 args=(cmd, self.progress, self._exito, self._error_dl),
                                 daemon=True).start()
            elif tab == 1:
                cmd, err = self.panel_gif.build_cmd(url)
                if err:
                    self.progress.set_resultado(err, WARN)
                    self._reset_btn()
                    return
                threading.Thread(target=run_download,
                                 args=(cmd, self.progress, self._exito, self._error_dl),
                                 daemon=True).start()
            elif tab == 2:
                if self.panel_imagen._es_video:
                    seg = int(self.panel_imagen.slider_var.get())
                    threading.Thread(target=self._descargar_fotograma,
                                     args=(url, seg), daemon=True).start()
                elif es_sitio_imagen(url):
                    threading.Thread(target=self._descargar_imagen_motor,
                                     args=(url,), daemon=True).start()
                else:
                    cmd = self.panel_imagen.build_cmd_simple(url)
                    threading.Thread(target=self._descargar_imagen_pp,
                                     args=(cmd, url), daemon=True).start()
        else:
            # Modo simple
            salida = os.path.join(CARPETA, "%(title)s.%(ext)s")
            if tipo == "audio":
                cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "--audio-quality", "0",
                       "--no-playlist", "--newline", "-o", salida, url]
            elif tipo == "gif":
                cmd = ["yt-dlp", "--no-playlist", "--newline", "-o", salida, url]
            elif tipo == "imagen":
                if es_sitio_imagen(url):
                    threading.Thread(target=self._descargar_imagen_motor,
                                     args=(url,), daemon=True).start()
                    return
                cmd = ["yt-dlp", "--no-playlist", "--newline", "-o", salida, url]
            else:
                cmd = ["yt-dlp", "-f",
                       "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                       "--merge-output-format", "mp4", "--no-playlist",
                       "--newline", "-o", salida, url]
            threading.Thread(target=run_download,
                             args=(cmd, self.progress, self._exito, self._error_dl),
                             daemon=True).start()

    def _descargar_fotograma(self, url, seg):
        try:
            salida_jpg = os.path.join(CARPETA, f"fotograma_{seg}.jpg")
            info_r = subprocess.run(["yt-dlp", "-g", "--no-playlist", url],
                                    capture_output=True, text=True,
                                    timeout=15, creationflags=FLAG)
            stream_url = info_r.stdout.strip().split("\n")[0]
            if not stream_url:
                raise Exception("No se pudo obtener el stream.")
            subprocess.run(["ffmpeg", "-y", "-ss", str(seg), "-i", stream_url,
                            "-frames:v", "1", "-q:v", "1", salida_jpg],
                           capture_output=True, timeout=30, creationflags=FLAG)
            if os.path.exists(salida_jpg) and os.path.getsize(salida_jpg) > 0:
                self.after(0, lambda: self.panel_imagen.postprocesar(
                    salida_jpg, self._exito, self._error_dl))
            else:
                self.after(0, lambda: self._error_dl(
                    "No se pudo extraer. Instala ffmpeg."))
        except Exception as e:
            self.after(0, lambda err=str(e): self._error_dl(err))

    def _descargar_imagen_pp(self, cmd, url):
        try:
            proceso = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE,
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
                if es_sitio_imagen(url):
                    self.progress.after(0, lambda: self.progress.set_estado(
                        "Intentando con gallery-dl...", MUTED))
                    archivo_r, _ = descargar_imagen_agresivo(url, CARPETA)
                    if archivo_r and os.path.exists(archivo_r):
                        self.after(0, lambda f=archivo_r: self.panel_imagen.postprocesar(
                            f, self._exito, self._error_dl))
                        return
                    self.after(0, lambda: self._error_dl(
                        "No se pudo descargar. Intenta abrir el link en tu navegador "
                        "y guardar la imagen manualmente."))
                    return
                msg = interpretar_error(stderr_txt)
                self.after(0, lambda m=msg: self._error_dl(m))
                return

            if ultimo and os.path.exists(ultimo):
                self.after(0, lambda f=ultimo: self.panel_imagen.postprocesar(
                    f, self._exito, self._error_dl))
            else:
                self.after(0, self._exito)
        except Exception as e:
            self.after(0, lambda err=str(e): self._error_dl(err))

    def _descargar_imagen_motor(self, url):
        """Motor agresivo de descarga de imagenes."""
        def progreso(msg):
            if msg and len(msg) > 3:
                short = msg[:80] + ("..." if len(msg) > 80 else "")
                self.progress.after(0, lambda m=short:
                    self.progress.set_estado(f"Intentando... {m}", MUTED))

        archivo, metodo = descargar_imagen_agresivo(
            url, CARPETA, progreso=progreso)

        if archivo and os.path.exists(archivo):
            # Mostrar dimensiones del archivo descargado
            dims_text = ""
            if PILLOW:
                try:
                    img = Image.open(archivo)
                    w, h = img.size
                    ext = os.path.splitext(archivo)[1].upper().lstrip(".")
                    dims_text = f"  ({w}x{h} {ext})"
                except Exception:
                    pass
            self.after(0, lambda f=archivo, d=dims_text: self._exito(f, d))
        else:
            sitio = _detectar_sitio(url)
            ayudas = {
                "instagram": "Abre Instagram en tu navegador, inicia sesion, y vuelve a intentar.",
                "twitter":   "Abre x.com en tu navegador, inicia sesion, y vuelve a intentar.",
                "reddit":    "El post puede ser privado o eliminado.",
                "generico":  "El contenido puede requerir inicio de sesion.",
            }
            ayuda = ayudas.get(sitio, ayudas["generico"])
            self.after(0, lambda a=ayuda: self._error_dl(
                f"No se pudo descargar con ninguna herramienta.\n\n{a}"))

    def _exito(self, archivo=None, extra=""):
        self._busy = False
        self.progress.barra["value"] = 100
        self.progress.set_estado("Completado", SUCCESS)
        msg = "Guardado en ~/Downloads/VidGet"
        if extra:
            msg += extra
        self.progress.set_resultado(msg, SUCCESS)
        self._reset_btn()
        if self.abrir_auto.get():
            self._abrir_carpeta()

    def _error_dl(self, msg):
        self._busy = False
        self.progress.set_estado("Error", ERROR)
        self.progress.set_resultado(msg, ERROR)
        self._reset_btn()

    def _reset_btn(self):
        self.btn.config(state="normal", text="Descargar",
                        bg=ACCENT, fg="#0d0d11")

    def _centrar_ventana(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _cerrar(self):
        try:
            self.destroy()
        except Exception:
            pass
        os._exit(0)

    # ── Configuracion ─────────────────────────────────────────────────
    def _mostrar_config(self):
        dialog = tk.Toplevel(self)
        dialog.title("Configuracion - VidGet")
        dialog.geometry("460x400")
        dialog.resizable(False, False)
        dialog.configure(bg=BG)
        dialog.grab_set()
        dialog.transient(self)
        _aplicar_dark_titlebar(dialog)

        mk_label(dialog, "Configuracion", fg=ACCENT,
                 font=("Segoe UI", 14, "bold")).pack(pady=(20,12))

        # ── Seccion: Preview de imagenes ──
        sec1 = mk_frame(dialog, bg_color=SURFACE)
        sec1.pack(fill="x", padx=20, pady=(0,10))
        mk_label(sec1, "  Vista previa de imagenes", fg=TEXT,
                 font=F_BOLD, bg_color=SURFACE).pack(anchor="w", pady=(10,6))

        thumb_var = tk.StringVar(value=CONFIG.get("thumb_mode", "uniform"))

        r1 = mk_frame(sec1, bg_color=SURFACE)
        r1.pack(fill="x", padx=16, pady=(0,4))
        mk_radio(r1, "Tamano uniforme (todas iguales, centradas)",
                 thumb_var, "uniform", bg_color=SURFACE).pack(anchor="w")

        r2 = mk_frame(sec1, bg_color=SURFACE)
        r2.pack(fill="x", padx=16, pady=(0,10))
        mk_radio(r2, "Tamano proporcional (aspecto real de la imagen)",
                 thumb_var, "proportional", bg_color=SURFACE).pack(anchor="w")

        # ── Seccion: Descarga ──
        sec2 = mk_frame(dialog, bg_color=SURFACE)
        sec2.pack(fill="x", padx=20, pady=(0,10))
        mk_label(sec2, "  Descarga", fg=TEXT,
                 font=F_BOLD, bg_color=SURFACE).pack(anchor="w", pady=(10,6))

        open_var = tk.BooleanVar(value=CONFIG.get("open_folder_on_done", False))
        mk_check(sec2, "Abrir carpeta al terminar descarga",
                 open_var, bg_color=SURFACE).pack(anchor="w", padx=16, pady=(0,10))

        # ── Seccion: Info ──
        sec3 = mk_frame(dialog, bg_color=SURFACE)
        sec3.pack(fill="x", padx=20, pady=(0,10))
        mk_label(sec3, "  Informacion", fg=TEXT,
                 font=F_BOLD, bg_color=SURFACE).pack(anchor="w", pady=(10,6))
        mk_label(sec3, f"  Version: v{VERSION}", fg=MUTED, font=F_SM,
                 bg_color=SURFACE).pack(anchor="w")
        mk_label(sec3, f"  Carpeta: {CARPETA}", fg=MUTED, font=F_XS,
                 bg_color=SURFACE).pack(anchor="w", pady=(2,4))
        mk_label(sec3, "  GitHub: github.com/UwUMADDOX/VidGet", fg=MUTED,
                 font=F_XS, bg_color=SURFACE).pack(anchor="w", pady=(0,10))

        # ── Botones ──
        btn_row = mk_frame(dialog)
        btn_row.pack(pady=(12,0))

        def guardar():
            CONFIG["thumb_mode"] = thumb_var.get()
            CONFIG["open_folder_on_done"] = open_var.get()
            _guardar_config(CONFIG)
            self.abrir_auto.set(open_var.get())
            dialog.destroy()

        tk.Button(btn_row, text="  Guardar  ", command=guardar,
                  bg=ACCENT, fg="#0d0d11", font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2", activebackground="#d4ff5a",
                  padx=16, pady=8).pack(side="left", padx=(0,8))
        tk.Button(btn_row, text="Cancelar", command=dialog.destroy,
                  bg=SURFACE2, fg=MUTED, font=F_SM, relief="flat",
                  cursor="hand2", padx=16, pady=8).pack(side="left")

    # ── Actualizaciones ───────────────────────────────────────────────────
    def _check_update_bg(self):
        hay, version, url = verificar_actualizacion()
        if hay:
            self._update_info = (version, url)
            self.after(0, self._mostrar_badge_update)

    def _mostrar_badge_update(self):
        if not self._update_info:
            return
        version, _ = self._update_info
        self.btn_update.config(text=f"  v{version} disponible  ")
        self.btn_update.pack(side="right", padx=(0,8))

    def _mostrar_update_dialog(self):
        if not self._update_info:
            return
        version, url = self._update_info

        dialog = tk.Toplevel(self)
        dialog.title("Actualizacion disponible")
        dialog.geometry("420x260")
        dialog.resizable(False, False)
        dialog.configure(bg=BG)
        dialog.grab_set()
        dialog.transient(self)
        _aplicar_dark_titlebar(dialog)

        mk_label(dialog, f"Version {version} disponible",
                 fg=ACCENT, font=("Segoe UI", 14, "bold")).pack(pady=(24,6))
        mk_label(dialog, f"Tu version actual: v{VERSION}",
                 fg=MUTED, font=F_SM).pack()
        mk_label(dialog,
                 "Se descargara e instalara automaticamente.\nEl programa se reiniciara al terminar.",
                 fg=TEXT, font=F_SM, justify="center").pack(pady=(10,0))

        prog_frame = mk_frame(dialog)
        prog_frame.pack(fill="x", padx=24, pady=(16,0))

        barra = ttk.Progressbar(prog_frame, style="Upd.Horizontal.TProgressbar",
                                mode="determinate", length=370)
        barra.pack(fill="x")
        lbl_est = mk_label(prog_frame, "", fg=MUTED, font=F_XS)
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
                    lbl_est.config(text=f"Descargando... {p}%")])
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
                        btn_no.config(state="normal")])
            threading.Thread(target=hilo, daemon=True).start()

        btn_si = tk.Button(btns, text="  Actualizar ahora  ", command=iniciar,
                           bg=ACCENT, fg="#0d0d11", font=("Segoe UI", 11, "bold"),
                           relief="flat", cursor="hand2", activebackground="#d4ff5a",
                           padx=16, pady=8)
        btn_si.pack(side="left", padx=(0,8))

        btn_no = tk.Button(btns, text="Ahora no", command=dialog.destroy,
                           bg=SURFACE2, fg=MUTED, font=F_SM, relief="flat",
                           cursor="hand2", padx=16, pady=8)
        btn_no.pack(side="left")

    def _on_resize(self, _):
        w = self.winfo_width() - 56
        if w > 100:
            self.progress.lbl_resultado.config(wraplength=w)

    def _abrir_carpeta(self):
        if sys.platform == "win32": os.startfile(CARPETA)
        elif sys.platform == "darwin": subprocess.Popen(["open", CARPETA])
        else: subprocess.Popen(["xdg-open", CARPETA])


if __name__ == "__main__":
    VidGet().mainloop()
