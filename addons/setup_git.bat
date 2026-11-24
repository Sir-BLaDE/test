@echo off
setlocal enabledelayedexpansion

echo ============================================================
echo 🚀 NUVIO ADDON GIT SETUP - PREPARANDO PARA GITHUB
echo ============================================================
echo.

REM Verificar si está en repo git
powershell -Command "Test-Path 'C:\Dev\Default Project\.git'" >nul 2>&1
if %errorlevel% neq 0 (
    echo ⚠️ El directorio NO es un repo Git. Creando uno ahora...
    cd /d "%~dp0"
    git init
    
    # Crear .gitignore básico
    echo >>.gitignore
    echo nuvio_search_es_priority.pyc >>.gitignore
    echo __pycache__ >>.gitignore
    echo *.pyc >>.gitignore
    echo env >>.gitignore
    echo >.gitignore
    
    echo ✅ Repo Git creado
) else (
    cd /d "%~dp0"
    echo ✅ Ya existe un repo Git en esta ubicación
)

echo.
echo =============================================
echo ARCHIVOS LISTOS PARA GITHUB
echo =============================================
echo.
powershell -Command "Get-ChildItem -Force | Sort-Object LastWriteTime -Descending | Select-Object Name, @{N='Fecha';E={$_.LastWriteTime}}"

echo.
echo 📦 Archivos del addon:
powershell -Command "(Get-ChildItem '*.py','*.json','*.md').Name -join '\n'"

echo.
echo =============================================
echo PASOS PARA PUBLICAR EN GITHUB (3 CLICKS):
echo =============================================
echo.
echo 1️⃣  Crea repositorio en GitHub.com:
echo      https://github.com/new
echo      - Nombre repo: nuvio-search-es-priority (o el que prefieras)
echo      - Descripción: Nuvio addon para búsqueda prioritaria castellano español
echo      - Licencia: MIT License
echo      - Marca como public ✅
echo.
echo 2️⃣  Clone al repositorio localmente:
echo.
echo      git clone https://github.com/TU_USUARIO/nuvio-search-es-priority.git
echo.
echo 3️⃣  Push con estos comandos (ejecutar en PowerShell):
echo.
echo      cd nuvio-search-es-priority
echo      # Si tienes credenciales configuradas, funciona directo:
echo      
echo      git remote add origin https://TU_USUARIO@github.com/TU_USUARIO/nuvio-search-es-priority.git
echo      
echo      git push -u origin main
echo.
echo 💡 O USAR GITHUB DESKTOP (aún más fácil):
echo    - Descarga GitHub Desktop desde github.com/desktop-app/download
echo    - Importa repositorio
echo    - Botón "Sync to GitHub" en interfaz gráfica
echo.

echo ============================================================
echo ✅ LISTO PARA SUBIR A GITHUB!
echo.
echo URL final de instalación:
echo https://github.com/TU_USUARIO/nuvio-search-es-priority/releases/download/v1.0.0/nuvio-search-es-priority.zip
echo.
echo 📁 Archivos en repositorio raíz:
powershell -Command "(Get-ChildItem -File | Sort-Object Name).Name"

echo ============================================================
echo ✅ FIN DEL SCRIPT - AHORA HAZ EL PUSH A GITHUB COMO SE EXPLICA ARRIBA!
echo ============================================================
