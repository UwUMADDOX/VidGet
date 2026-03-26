# VidGet
Descargador de videos, audio e imágenes. YouTube, Instagram, TikTok, Twitter/X y +1000 sitios.

# ===================================================================
#  VIDGET - HISTORIAL DE VERSIONES
#  Repositorio: github.com/UwUMADDOX/VidGet
#  Ultima actualizacion: 2026-03-25
# ===================================================================

### 🛠️ Sistema de Versiones
| Versión | Tipo de Cambio | Ejemplo |
| :--- | :--- | :--- |
| **X.XX** | Fix pequeño, detalle, texto | `v3.01`, `v3.02` |
| **X.X** | Feature nueva dentro de lo existente | `v3.1`, `v3.2` |
| **X.0** | Reescritura o cambio radical | `v4.0` |

---

## 🚀 VERSIÓN ACTUAL (v3.x)

### **v3.2 [2026-03-25] - FEATURE: UI Profesional y Configuración**
* **Rediseño Visual (TTK Moderno):**
  * Eliminado el diseño "Windows XP" de las pestañas avanzadas.
  * Uso de `theme_use("clam")` centralizado en `_setup_ttk_styles()`.
  * Layout personalizado sin bordes 3D y eliminación de configuraciones inline redundantes.
* **Estabilidad de Ventana:**
  * Dimensiones mínimas fijas: `680x720` (Modo Simple) y `680x920` (Modo Avanzado).
  * Herramientas de control siempre visibles.
* **Gestión de Miniaturas (Thumbnails):**
  * Tamaño uniforme: `130x90`.
  * Modos seleccionables: **Uniforme** (centradas con fondo oscuro) o **Proporcional** (aspecto original).
* **Panel de Configuración (Botón "Config"):**
  * Opciones de vista previa y apertura automática de carpeta al finalizar descarga.
  * Información de versión y acceso directo al repositorio.
  * Persistencia de ajustes en `~/.vidget_config.json`.

### **v3.11 [2026-03-22] - FIX: Estética del Sistema**
* Corrección de barra de título oscura (DWM), icono de ventana e implementación de `iconphoto`.

### **v3.1 [2026-03-21] - FEATURE: Validación**
* Implementación de validación de imágenes y restricción `MIN_CONTENT_SIZE`.

### **v3.0 - v3.02 [2026-03-21] - REESCRITURA MAYOR**
* **v3.0:** Reestructuración completa del núcleo del programa.
* **v3.02:** Añadidos placeholders, estados de carga (loading) y fallback para `gallery-dl`.
* **v3.01:** Fixes en modo avanzado, gestión de listas negras y validación PIL.

---

## 📜 VERSIONES ANTERIORES (v1.x - v2.x)

<details>
<summary>Ver historial detallado</summary>

* **v2.0 - v2.5:** Reescritura con sistema de pestañas, ventana redimensionable y gestión de fotogramas.
* **v1.2:** Gestión de errores específicos, validación de enlaces y soporte para GIF.
* **v1.1:** Migración a Tkinter real (eliminación de dependencia de navegador).
* **v1.0:** Prototipo inicial en Flask + navegador (Descartado).
</details>

---

## ⏳ PENDIENTES (Roadmap)

- [ ] Preview real para Instagram (requiere sesión).
- [ ] Selección de galería conectada al motor de descarga.
- [ ] Cola de múltiples links.
- [ ] Tema claro (modo día).
- [ ] Desarrollo continuo de nuevas funciones.
