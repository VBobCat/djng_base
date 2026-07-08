@ECHO OFF

REM Abre contexto local para variáveis de ambiente entre SETLOCAL e ENDLOCAL
SETLOCAL

REM salva diretório atual e muda para o diretório em que este arquivo está
SET "ORIG_DIR=%CD%"
cd /D "%~dp0/backend"

REM instala dependências de desenvolvimento (pip setuptools pipdeptree) e do projeto
ECHO:
ECHO Install/update devtools (pip setuptools pipdeptree)...
ECHO ======================================================
python -m pip install --no-cache-dir --upgrade --upgrade-strategy eager pip setuptools pipdeptree isort ssort
ECHO:
ECHO Install/update requirements (-r requirements.txt)...
ECHO ====================================================
python -m pip install --no-cache-dir --upgrade --upgrade-strategy eager -r requirements.txt
ECHO:
ECHO Check broken dependencies...
ECHO ============================
pip check
ECHO:
ECHO List remaining outdated packages (may be pinned by other packages)...
ECHO =====================================================================
pip list -o

REM Retorna ao diretório original
CD /D "%ORIG_DIR%"

(ENDLOCAL
 EXIT /B 0)
