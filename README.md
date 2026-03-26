# VidGet
Descargador de videos, audio e imágenes. YouTube, Instagram, TikTok, Twitter/X y +1000 sitios.

# ===================================================================
#  VIDGET - HISTORIAL DE VERSIONES
#  Repositorio: github.com/UwUMADDOX/VidGet
#  Ultima actualizacion: 2026-03-25
# ===================================================================
#
#  SISTEMA DE VERSIONES:
#    X.XX   -> Fix pequeno, detalle, texto         ej: v3.01, v3.02
#    X.X    -> Feature nueva dentro de lo existente ej: v3.1, v3.2
#    X.0    -> Reescritura o cambio radical         ej: v4.0
#
# ===================================================================


== VERSIONES ANTERIORES (v1.x - v2.x) ==

v1.0    Flask + navegador (descartado)
v1.1    Tkinter real, sin navegador
v1.2    Errores especificos, validacion, GIF
v2.0    Reescritura: pestanas, ventana redimensionable, fotograma
v2.1-v2.5  (ver historial completo en sesiones anteriores)


== VERSION ACTUAL (v3.x) ==

v3.0    [2026-03-21] REESCRITURA MAYOR
v3.01   [2026-03-21] FIX - Avanzado, blacklist, validacion PIL
v3.02   [2026-03-21] FIX - Placeholder, loading, gallery-dl fallback
v3.1    [2026-03-21] FEATURE - Validacion de imagenes, MIN_CONTENT_SIZE
v3.11   [2026-03-22] FIX - DWM dark titlebar, icono ventana, iconphoto

v3.2    [2026-03-25] FEATURE - UI profesional y configuracion
        - ELIMINADO diseno Windows XP de las pestanas avanzadas
          * theme_use("clam") reemplaza "default"
          * Todos los estilos ttk en _setup_ttk_styles() centralizado
          * style.layout personalizado sin bordes 3D
          * 5 configuraciones inline duplicadas eliminadas
        - Ventana con tamano estable:
          * Minimo 680x720 modo simple, 680x920 modo avanzado
          * Herramientas siempre visibles
          * Se agranda pero nunca mas chica que lo necesario
        - Thumbnails uniformes:
          * THUMB_W=130, THUMB_H=90
          * Modo "uniforme": todas iguales, centradas con fondo oscuro
          * Modo "proporcional": aspecto real
          * Configurable desde Config
        - Panel de Configuracion (boton "Config"):
          * Vista previa: uniforme vs proporcional
          * Descarga: abrir carpeta al terminar
          * Info: version, carpeta, GitHub
          * Persistente en ~/.vidget_config.json


== PENDIENTES ==

- [ ] Preview real para Instagram (requiere sesion)
- [ ] Seleccion de galeria conectada al motor de descarga
- [ ] Cola de multiples links
- [ ] Tema claro (modo dia)
- [ ] y mucho mas :D
