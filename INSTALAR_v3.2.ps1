# VidGet v3.2 - Instalador completo
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "VidGet v3.2 - Instalador"
$ErrorActionPreference = "Continue"
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $SCRIPT_DIR
function Escribir-OK   { Write-Host "  [OK] $args" -ForegroundColor Green }
function Escribir-Info { Write-Host "  [..] $args" -ForegroundColor Yellow }
function Escribir-Error{ Write-Host "  [!!] $args" -ForegroundColor Red }
function Escribir-Paso { param([int]$n,[int]$total,[string]$txt); Write-Host ""; Write-Host "  [$n/$total] $txt" -ForegroundColor White }
Clear-Host
Write-Host ""
Write-Host "  ======================================================" -ForegroundColor DarkGreen
Write-Host "   VidGet v3.2 - Instalador automatico" -ForegroundColor Green
Write-Host "   Esto puede tardar 5-10 minutos. No cierres la ventana." -ForegroundColor Gray
Write-Host "  ======================================================" -ForegroundColor DarkGreen
Write-Host ""
$TOTAL_PASOS = 9
Escribir-Paso 1 $TOTAL_PASOS "Verificando Python..."
$python = $null
foreach ($cmd in @("python","py","python3")) { try { $ver = & $cmd --version 2>&1; if ($ver -match "Python 3") { $python = $cmd; Escribir-OK "Python encontrado: $ver"; break } } catch {} }
if (-not $python) {
    Escribir-Info "Python no encontrado. Instalando via winget..."
    try { winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements --override "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1" 2>&1 | Out-Null; $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User"); Start-Sleep -Seconds 3; foreach ($cmd in @("python","py","python3")) { try { $ver = & $cmd --version 2>&1; if ($ver -match "Python 3") { $python = $cmd; break } } catch {} } } catch { Escribir-Error "winget no disponible." }
    if (-not $python) { Escribir-Info "Descargando Python desde python.org..."; $pyInst = "$env:TEMP\python_installer.exe"; try { Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.12.0/python-3.12.0-amd64.exe" -OutFile $pyInst -UseBasicParsing; Start-Process -FilePath $pyInst -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1" -Wait; $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User"); Start-Sleep -Seconds 3; foreach ($cmd in @("python","py","python3")) { try { $ver = & $cmd --version 2>&1; if ($ver -match "Python 3") { $python = $cmd; break } } catch {} } } catch { Escribir-Error "No se pudo instalar Python. Instalalo manualmente desde python.org"; Read-Host "Enter para salir"; exit 1 } }
    if (-not $python) { Escribir-Error "Python no detectado. Cierra y vuelve a ejecutar."; Read-Host "Enter para salir"; exit 1 }
    Escribir-OK "Python instalado: $python"
}
Escribir-Paso 2 $TOTAL_PASOS "Actualizando pip..."
& $python -m pip install --upgrade pip --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "pip actualizado"
Escribir-Paso 3 $TOTAL_PASOS "Instalando yt-dlp..."
& $python -m pip install yt-dlp --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "yt-dlp instalado"
Escribir-Paso 4 $TOTAL_PASOS "Instalando gallery-dl..."
& $python -m pip install gallery-dl --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "gallery-dl instalado"
Escribir-Paso 5 $TOTAL_PASOS "Instalando you-get..."
& $python -m pip install you-get --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "you-get instalado"
Escribir-Paso 6 $TOTAL_PASOS "Instalando Pillow..."
& $python -m pip install Pillow --quiet --disable-pip-version-check 2>&1 | Out-Null
Escribir-OK "Pillow instalado"
Escribir-Paso 7 $TOTAL_PASOS "Instalando ffmpeg..."
$ffmpeg_ok = $false
try { $ffver = & ffmpeg -version 2>&1 | Select-Object -First 1; if ($ffver -match "ffmpeg") { Escribir-OK "ffmpeg ya instalado"; $ffmpeg_ok = $true } } catch {}
if (-not $ffmpeg_ok) { try { winget install --id Gyan.FFmpeg --silent --accept-package-agreements --accept-source-agreements 2>&1 | Out-Null; $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User"); Start-Sleep -Seconds 2; $ffver = & ffmpeg -version 2>&1 | Select-Object -First 1; if ($ffver -match "ffmpeg") { Escribir-OK "ffmpeg instalado via winget"; $ffmpeg_ok = $true } } catch {}
    if (-not $ffmpeg_ok) { Escribir-Info "Descargando ffmpeg..."; try { $ffZip = "$env:TEMP\ffmpeg.zip"; $ffDir = "$env:LOCALAPPDATA\ffmpeg"; Invoke-WebRequest -Uri "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip" -OutFile $ffZip -UseBasicParsing; Expand-Archive -Path $ffZip -DestinationPath "$env:TEMP\ffmpeg_extract" -Force; $ffBin = Get-ChildItem "$env:TEMP\ffmpeg_extract" -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1; if ($ffBin) { New-Item -ItemType Directory -Force -Path "$ffDir\bin" | Out-Null; Copy-Item $ffBin.FullName "$ffDir\bin\ffmpeg.exe" -Force; $userPath = [System.Environment]::GetEnvironmentVariable("Path","User"); if ($userPath -notlike "*$ffDir\bin*") { [System.Environment]::SetEnvironmentVariable("Path", "$userPath;$ffDir\bin", "User"); $env:Path += ";$ffDir\bin" }; Escribir-OK "ffmpeg instalado en $ffDir\bin"; $ffmpeg_ok = $true } } catch { Escribir-Error "No se pudo instalar ffmpeg. Instala manualmente: winget install ffmpeg" } }
}
Escribir-Paso 8 $TOTAL_PASOS "Creando VidGet.exe..."
& $python -m pip install pyinstaller --quiet --disable-pip-version-check 2>&1 | Out-Null
$pyFile = Get-ChildItem -Path $SCRIPT_DIR -Filter "VidGet_v*.py" | Sort-Object Name -Descending | Select-Object -First 1
if (-not $pyFile) { Escribir-Error "No se encontro VidGet_v*.py"; Read-Host "Enter para salir"; exit 1 }
Escribir-Info "Compilando $($pyFile.Name)... (2-3 minutos)"
$logoFile = $null; foreach ($logo in @("vidget_logo_512.png", "vidget_logo_1024.png")) { $lp = Join-Path $SCRIPT_DIR $logo; if (Test-Path $lp) { $logoFile = $lp; break } }
$icoArg = ""
if ($logoFile) { Escribir-Info "Generando icono..."; $icoPath = Join-Path $SCRIPT_DIR "vidget.ico"; $icoScript = "from PIL import Image`nimport sys`nimg = Image.open(sys.argv[1])`nimg = img.resize((256, 256), Image.LANCZOS)`nimg.save(sys.argv[2], format='ICO', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])"; $icoScript | Out-File -Encoding utf8 "$env:TEMP\gen_ico.py"; & $python "$env:TEMP\gen_ico.py" "$logoFile" "$icoPath" 2>&1 | Out-Null; if (Test-Path $icoPath) { $icoArg = "--icon=$icoPath"; Escribir-OK "Icono generado" } }
$addDataArgs = @(); foreach ($logo in @("vidget_logo_512.png", "vidget_logo_1024.png")) { $lp = Join-Path $SCRIPT_DIR $logo; if (Test-Path $lp) { $addDataArgs += "--add-data"; $addDataArgs += "$lp;." } }; $icoAbs = Join-Path $SCRIPT_DIR "vidget.ico"; if (Test-Path $icoAbs) { $addDataArgs += "--add-data"; $addDataArgs += "$icoAbs;." }
$args2 = @("--noconfirm","--onefile","--noconsole","--name","VidGet","--hidden-import","PIL","--hidden-import","PIL.Image","--hidden-import","PIL.ImageTk","--hidden-import","PIL.ImageDraw"); if ($icoArg) { $args2 += $icoArg }; $args2 += $addDataArgs; $args2 += $pyFile.FullName
& $python -m PyInstaller @args2 2>&1 | Out-Null
$exePath = Join-Path $SCRIPT_DIR "dist\VidGet.exe"; $exeDest = Join-Path $SCRIPT_DIR "VidGet.exe"
if (Test-Path $exePath) { Move-Item $exePath $exeDest -Force; $icoSrc = Join-Path $SCRIPT_DIR "vidget.ico"; if (Test-Path $icoSrc) { Copy-Item $icoSrc (Join-Path (Split-Path $exeDest) "vidget.ico") -Force -ErrorAction SilentlyContinue }; foreach ($logo in @("vidget_logo_512.png","vidget_logo_1024.png")) { $lp = Join-Path $SCRIPT_DIR $logo; if (Test-Path $lp) { Copy-Item $lp (Join-Path (Split-Path $exeDest) $logo) -Force -ErrorAction SilentlyContinue } }; Remove-Item (Join-Path $SCRIPT_DIR "dist") -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item (Join-Path $SCRIPT_DIR "build") -Recurse -Force -ErrorAction SilentlyContinue; Remove-Item (Join-Path $SCRIPT_DIR "VidGet.spec") -Force -ErrorAction SilentlyContinue; Escribir-OK "VidGet.exe creado" } else { Escribir-Error "No se pudo crear VidGet.exe"; Read-Host "Enter para salir"; exit 1 }
Escribir-Paso 9 $TOTAL_PASOS "Creando acceso directo..."
try { $escritorio = [System.Environment]::GetFolderPath("Desktop"); $shortcutPath = Join-Path $escritorio "VidGet.lnk"; $WshShell = New-Object -ComObject WScript.Shell; $shortcut = $WshShell.CreateShortcut($shortcutPath); $shortcut.TargetPath = $exeDest; $shortcut.WorkingDirectory = $SCRIPT_DIR; $shortcut.Description = "VidGet - Descargador de videos, audio e imagenes"; $shortcut.WindowStyle = 1; $ico_abs = Join-Path $SCRIPT_DIR "vidget.ico"; if (Test-Path $ico_abs) { $shortcut.IconLocation = "$ico_abs,0" }; $shortcut.Save(); Escribir-OK "Acceso directo creado" } catch { Escribir-Error "No se pudo crear acceso directo: $_" }
Write-Host ""; Write-Host "  ======================================================" -ForegroundColor DarkGreen; Write-Host "   Instalacion completada!" -ForegroundColor Green; Write-Host "  ======================================================" -ForegroundColor DarkGreen; Write-Host ""
Write-Host "  Herramientas: yt-dlp, gallery-dl, you-get, ffmpeg, Pillow" -ForegroundColor Gray; Write-Host "  Abriendo VidGet..." -ForegroundColor Cyan; Write-Host ""
Start-Sleep -Seconds 2; Start-Process $exeDest
