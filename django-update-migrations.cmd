@ECHO OFF

REM Abre contexto local para variáveis de ambiente entre SETLOCAL e ENDLOCAL
SETLOCAL

REM salva diretório atual e muda para o diretório em que este arquivo está
SET "ORIG_DIR=%CD%"
cd /D "%~dp0/backend"

REM cria e executa migrações do banco de dados
python manage.py makemigrations && python manage.py migrate && git add ./*/migrations/*

REM Retorna ao diretório original
CD /D "%ORIG_DIR%"

(ENDLOCAL
 EXIT /B 0)
