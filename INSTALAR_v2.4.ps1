# ============================================================
#  VidGet v2.4 - Instalador completo
#  Instala: Python, pip, yt-dlp, gallery-dl, you-get,
#           Pillow, ffmpeg, pyinstaller
#  Crea: VidGet.exe + acceso directo en el escritorio
# ============================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "VidGet v2.4 - Instalador"
$ErrorActionPreference = "Continue"

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR

function Escribir-Titulo {
    param([string]$texto)
    Write-Host ""
    Write-Host "  $texto" -ForegroundColor Cyan
    Write-Host ("  " + "=" * ($texto.Length)) -ForegroundColor DarkCyan
}

function Escribir-OK   { Write-Host "  [OK] $args" -ForegroundColor Green }
function Escribir-Info { Write-Host "  [..] $args" -ForegroundColor Yellow }
function Escribir-Error{ Write-Host "  [!!] $args" -ForegroundColor Red }
function Escribir-Paso { param([int]$n,[int]$total,[string]$txt)
    Write-Host ""
    Write-Host "  [$n/$total] $txt" -ForegroundColor White
}

Clear-Host
Write-Host ""
Write-Host "  ======================================================" -ForegroundColor DarkGreen
Write-Host "   VidGet v2.4 - Instalador automatico" -ForegroundColor Green
Write-Host "   Esto puede tardar 5-10 minutos. No cierres la ventana." -ForegroundColor Gray
Write-Host "  ======================================================" -ForegroundColor DarkGreen
Write-Host ""

$TOTAL_PASOS = 9

# -- PASO 1: Verificar / instalar Python --------------------------------------
Escribir-Paso 1 $TOTAL_PASOS "Verificando Python..."

$python = $null
foreach ($cmd in @("python","py","python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $python = $cmd
            Escribir-OK "Python encontrado: $ver"
            break
        }
    } catch {}
}

if (-not $python) {
    Escribir-Info "Python no encontrado. Instalando via winget..."
    try {
        winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements --override "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1" 2>&1 | Out-Null

        # Refrescar PATH en esta sesion
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

        Start-Sleep -Seconds 3
        foreach ($cmd in @("python","py","python3")) {
            try {
                $ver = & $cmd --version 2>&1
                if ($ver -match "Python 3") { $python = $cmd; break }
            } catch {}
        }
    } catch {
        Escribir-Error "winget no disponible. Intentando descarga directa..."
    }

    # Si winget fallo, descargar instalador de python.org
    if (-not $python) {
        Escribir-Info "Descargando instalador de Python desde python.org..."
        $pyInstaller = "$env:TEMP\python_installer.exe"
        try {
            Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe" `
                              -OutFile $pyInstaller -UseBasicParsing
            Start-Process -FilePath $pyInstaller `
                          -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1" `
                          -Wait
            $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
            Start-Sleep -Seconds 3
            foreach ($cmd in @("python","py","python3")) {
                try {
                    $ver = & $cmd --version 2>&1
                    if ($ver -match "Python 3") { $python = $cmd; break }
                } catch {}
            }
        } catch {
            Escribir-Error "No se pudo instalar Python automaticamente."
            Write-Host ""
            Write-Host "  Instala Python manualmente:" -ForegroundColor Yellow
            Write-Host "  1. Ve a https://python.org/downloads" -ForegroundColor White
            Write-Host "  2. Descarga e instala" -ForegroundColor White
            Write-Host "  3. IMPORTANTE: marca 'Add Python to PATH'" -ForegroundColor White
            Write-Host "  4. Cierra y vuelve a ejecutar este instalador" -ForegroundColor White
            Write-Host ""
            Read-Host "Presiona Enter para salir"
            exit 1
        }
    }

    if (-not $python) {
        Escribir-Error "Python instalado pero no detectado. Cierra y vuelve a ejecutar."
        Read-Host "Presiona Enter para salir"
        exit 1
    }
    Escribir-OK "Python instalado correctamente: $python"
}

# -- PASO 2: Actualizar pip ----------------------------------------------------
Escribir-Paso 2 $TOTAL_PASOS "Actualizando pip..."
& $python -m pip install --upgrade pip --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "pip actualizado"

# -- PASO 3: Instalar yt-dlp ---------------------------------------------------
Escribir-Paso 3 $TOTAL_PASOS "Instalando yt-dlp (descarga de videos)..."
& $python -m pip install yt-dlp --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "yt-dlp instalado"

# -- PASO 4: Instalar gallery-dl -----------------------------------------------
Escribir-Paso 4 $TOTAL_PASOS "Instalando gallery-dl (descarga de imagenes: Twitter, Instagram, Reddit...)..."
& $python -m pip install gallery-dl --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "gallery-dl instalado"

# -- PASO 5: Instalar you-get --------------------------------------------------
Escribir-Paso 5 $TOTAL_PASOS "Instalando you-get (herramienta alternativa de descarga)..."
& $python -m pip install you-get --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "you-get instalado"

# -- PASO 6: Instalar Pillow ---------------------------------------------------
Escribir-Paso 6 $TOTAL_PASOS "Instalando Pillow (vistas previas e imagenes)..."
& $python -m pip install Pillow --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "Pillow instalado"

# -- PASO 7: Instalar ffmpeg ---------------------------------------------------
Escribir-Paso 7 $TOTAL_PASOS "Instalando ffmpeg (necesario para GIFs y combinar video+audio)..."

$ffmpeg_ok = $false
try {
    $ffver = & ffmpeg -version 2>&1 | Select-Object -First 1
    if ($ffver -match "ffmpeg") {
        Escribir-OK "ffmpeg ya estaba instalado: $ffver"
        $ffmpeg_ok = $true
    }
} catch {}

if (-not $ffmpeg_ok) {
    # Intentar via winget
    try {
        winget install --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
        Start-Sleep -Seconds 2
        $ffver = & ffmpeg -version 2>&1 | Select-Object -First 1
        if ($ffver -match "ffmpeg") {
            Escribir-OK "ffmpeg instalado via winget"
            $ffmpeg_ok = $true
        }
    } catch {}

    # Si winget fallo, descargar binario directamente
    if (-not $ffmpeg_ok) {
        Escribir-Info "Descargando ffmpeg directamente..."
        try {
            $ffZip = "$env:TEMP\ffmpeg.zip"
            $ffDir = "$env:LOCALAPPDATA\ffmpeg"
            Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" `
                              -OutFile $ffZip -UseBasicParsing
            Expand-Archive -Path $ffZip -DestinationPath "$env:TEMP\ffmpeg_extract" -Force
            $ffBin = Get-ChildItem "$env:TEMP\ffmpeg_extract" -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
            if ($ffBin) {
                New-Item -ItemType Directory -Force -Path "$ffDir\bin" | Out-Null
                Copy-Item $ffBin.FullName "$ffDir\bin\ffmpeg.exe" -Force
                Copy-Item ($ffBin.FullName -replace "ffmpeg.exe","ffprobe.exe") "$ffDir\bin\ffprobe.exe" -Force -ErrorAction SilentlyContinue

                # Agregar al PATH del usuario permanentemente
                $userPath = [System.Environment]::GetEnvironmentVariable("Path","User")
                if ($userPath -notlike "*$ffDir\bin*") {
                    [System.Environment]::SetEnvironmentVariable("Path", "$userPath;$ffDir\bin", "User")
                    $env:Path += ";$ffDir\bin"
                }
                Escribir-OK "ffmpeg instalado en $ffDir\bin"
                $ffmpeg_ok = $true
            }
        } catch {
            Escribir-Error "No se pudo instalar ffmpeg automaticamente."
            Write-Host "  Instala manualmente: winget install ffmpeg" -ForegroundColor Yellow
        }
    }
}

# -- PASO 8: Crear VidGet.exe --------------------------------------------------
Escribir-Paso 8 $TOTAL_PASOS "Instalando pyinstaller y creando VidGet.exe..."
& $python -m pip install pyinstaller --quiet --disable-pip-version-check 2>&1 | Out-Null

# Buscar el archivo .py de esta version
$pyFile = Get-ChildItem -Path $SCRIPT_DIR -Filter "VidGet_v2.4.py" | Select-Object -First 1
if (-not $pyFile) {
    $pyFile = Get-ChildItem -Path $SCRIPT_DIR -Filter "VidGet_v*.py" | Sort-Object Name -Descending | Select-Object -First 1
}

if (-not $pyFile) {
    Escribir-Error "No se encontro el archivo VidGet_v2.4.py en esta carpeta."
    Read-Host "Presiona Enter para salir"
    exit 1
}

Escribir-Info "Compilando $($pyFile.Name)... (puede tardar 2-3 minutos)"

& $python -m PyInstaller --noconfirm --onefile --noconsole --name "VidGet" `
    --hidden-import PIL `
    --hidden-import PIL.Image `
    --hidden-import PIL.ImageTk `
    $pyFile.FullName 2>&1 | Out-Null

$exePath = Join-Path $SCRIPT_DIR "dist\VidGet.exe"
$exeDest = Join-Path $SCRIPT_DIR "VidGet.exe"

if (Test-Path $exePath) {
    Move-Item $exePath $exeDest -Force
    # Copiar icono junto al exe para que la ventana lo muestre
    $ico_src = Join-Path $SCRIPT_DIR "vidget.ico"
    if (Test-Path $ico_src) {
        Copy-Item $ico_src (Join-Path $SCRIPT_DIR "vidget.ico") -Force -ErrorAction SilentlyContinue
    }
    Remove-Item (Join-Path $SCRIPT_DIR "dist")  -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $SCRIPT_DIR "build") -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $SCRIPT_DIR "VidGet.spec") -Force -ErrorAction SilentlyContinue
    Escribir-OK "VidGet.exe creado"
} else {
    Escribir-Error "No se pudo crear VidGet.exe"
    Write-Host "  Intenta ejecutar este script como Administrador (clic derecho -> Ejecutar con PowerShell como Administrador)" -ForegroundColor Yellow
    Read-Host "Presiona Enter para salir"
    exit 1
}

# -- PASO 9: Crear acceso directo en el escritorio ----------------------------
Escribir-Paso 9 $TOTAL_PASOS "Creando acceso directo en el escritorio..."

try {
    $escritorio = [System.Environment]::GetFolderPath("Desktop")
    $shortcutPath = Join-Path $escritorio "VidGet.lnk"

    $WshShell = New-Object -ComObject WScript.Shell
    $shortcut = $WshShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath    = $exeDest
    $shortcut.WorkingDirectory = $SCRIPT_DIR
    $shortcut.Description   = "VidGet - Descargador de videos, audio e imagenes"
    $shortcut.WindowStyle   = 1
    if (Test-Path $ico_path) { $shortcut.IconLocation = $ico_path }
    $shortcut.Save()

    Escribir-OK "Acceso directo creado en el escritorio"
} catch {
    Escribir-Error "No se pudo crear el acceso directo: $_"
    Write-Host "  Puedes crear el acceso directo manualmente desde $exeDest" -ForegroundColor Yellow
}

# -- Resumen final -------------------------------------------------------------
Write-Host ""
Write-Host "  ======================================================" -ForegroundColor DarkGreen
Write-Host "   Instalacion completada!" -ForegroundColor Green
Write-Host "  ======================================================" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "  Herramientas instaladas:" -ForegroundColor White
Write-Host "   - yt-dlp       Videos de YouTube, TikTok, Facebook y mas" -ForegroundColor Gray
Write-Host "   - gallery-dl   Imagenes de Twitter/X, Instagram, Reddit, Pixiv..." -ForegroundColor Gray
Write-Host "   - you-get      Descargador alternativo como respaldo" -ForegroundColor Gray
Write-Host "   - ffmpeg       Conversion de video, audio y GIFs" -ForegroundColor Gray
Write-Host "   - Pillow       Procesamiento y vista previa de imagenes" -ForegroundColor Gray
Write-Host ""
Write-Host "  Acceso directo creado en tu escritorio" -ForegroundColor Cyan
Write-Host "  Abriendo VidGet..." -ForegroundColor Cyan
Write-Host ""

Start-Sleep -Seconds 2
Start-Process $exeDest
