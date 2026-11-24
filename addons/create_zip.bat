@echo off
echo ============================================================
echo NUVIO ADDON PACKAGE CREATOR
echo ============================================================
echo.

REM Carrito de trabajo
set "ADDON_PATH=C:\Dev\Default Project\addons"
set "ZIP_PATH=%ADDON_PATH%\nuvio-search-es-priority.zip"

echo 📦 Creando paquete ZIP...
cd /d %ADDON_PATH%

REM Crear ZIP con todos los archivos
powershell -Command "Compress-Archive -Path * -DestinationPath %ZIP_PATH%"

if exist "%ZIP_PATH%">
    echo ✅ ZIP creado con éxito!
    
    REM Mostrar información
    for %%A in ("%ZIP_PATH%") do (
        echo 📦 Tamaño: %%~zA bytes
        echo 📁 Ruta: %%~dpnxa
    )
    
    echo.
    echo =============================================
    echo CONTENIDO DEL ZIP
    echo =============================================
    
    powershell -Command "Get-Content -Path '%ZIP_PATH%' | ForEach-Object { Write-Host '  $_' }"
    
    echo.
    echo 💡 PARA INSTALAR DESDE NUVIO:
    echo.
    echo   1. Sube este ZIP a un host HTTP/HTTPS público:
    echo      - GitHub Releases (recomendado)
    echo      - Cloudflare Pages / Netlify Drop
    echo      - Tu propio servidor web (Apache/Nginx)
    echo.
    echo   2. Una vez subido, la URL sería:
    echo      https://tu-host.com/nuevo-search-package.zip
    echo.
    echo   3. En Nuvio -> Administrar addons -> Instalar desde URL
    echo.
    
else
    echo ❌ Error creando ZIP
fi

echo ============================================================
