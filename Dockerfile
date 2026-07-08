# ESTÁGIO 1: FRONTEND ANGULAR
FROM node:24-trixie-slim AS frontend-build

# Instala e atualiza pacotes do SO e dependências
RUN apt-get update && \
    apt-get upgrade -qy && \
    apt-get install -qy ca-certificates curl gnupg locales tzdata &&  \
    rm -rf /var/lib/apt/lists/*

# Localização e horário
RUN localedef -i pt_BR -f UTF-8 pt_BR.UTF-8
ENV LANG=pt_BR.UTF-8
ENV LANGUAGE=pt_BR.UTF-8
ENV LC_ALL=pt_BR.UTF-8
ENV TZ="America/Sao_Paulo"

# Configuração do ambiente do container
ENV NG_CLI_ANALYTICS=ci
WORKDIR /opt/stack/frontend

# Cópia e instalação das dependencias
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install -g npm@latest && npm ci

# Cópia e build da aplicação Angular
COPY frontend/ ./
RUN npm run build


# ESTÁGIO 2 (FINAL): BACKEND DJANGO
FROM python:3.14-trixie AS backend-build

# Instala e atualiza pacotes do SO e dependências básicas
RUN apt-get update && \
    apt-get upgrade -qy && \
    apt-get install -qy locales tzdata libnsl2 libpq-dev unzip curl && \
    rm -rf /var/lib/apt/lists/*

# Localização e horário
RUN localedef -i pt_BR -f UTF-8 pt_BR.UTF-8
ENV LANG=pt_BR.UTF-8
ENV LANGUAGE=pt_BR.UTF-8
ENV LC_ALL=pt_BR.UTF-8
ENV TZ="America/Sao_Paulo"

# --- USUÁRIO DA APLICAÇÃO ---
ARG HOST_APP_UID=1001
ARG HOST_APP_GID=1002
RUN groupadd --gid ${HOST_APP_GID} appuser && \
    useradd --uid ${HOST_APP_UID} --gid ${HOST_APP_GID} --create-home \
            --home-dir /home/appuser --shell /bin/bash --comment "Application User" appuser

# --- CONFIGURAÇÃO DO ORACLE INSTANT CLIENT ---
ARG ORACLE_IC_MAJOR=23
ARG ORACLE_IC_VERSION=23.26.1.0.0
ARG ORACLE_IC_DIR=2326100
WORKDIR /opt/oracle
RUN curl -fsSLo libaio1.deb \
    https://deb.debian.org/debian/pool/main/liba/libaio/libaio1_0.3.113-4_amd64.deb && \
    dpkg -i libaio1.deb && rm libaio1.deb && \
    curl -fsSLo instantclient-basic.zip \
    https://download.oracle.com/otn_software/linux/instantclient/${ORACLE_IC_DIR}/instantclient-basic-linux.x64-${ORACLE_IC_VERSION}.zip && \
    unzip instantclient-basic.zip && rm instantclient-basic.zip && \
    ln -s instantclient_${ORACLE_IC_MAJOR}_* instantclient
ENV LD_LIBRARY_PATH=/opt/oracle/instantclient

# --- AMBIENTE VIRTUAL E PYTHON ---
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /opt/stack/backend

# Infra básica de build (agora instalando dentro da venv pelo PATH)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel gunicorn colorama

# Instala dependências do projeto
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --upgrade --upgrade-strategy eager -r requirements.txt

# --- COMPILAÇÃO CONDICIONAL DO NUMPY ---
# Este script verifica a CPU; se for antiga (sem x86_64_v2), recompila o NumPy
COPY numpy-from-source.sh ./
RUN chmod +x numpy-from-source.sh && ./numpy-from-source.sh

# Teste de Sanidade: Falha o build se o NumPy der "Illegal Instruction"
RUN python -c "import numpy; print(f'Sucesso: NumPy {numpy.__version__} validado para esta CPU.')"

# --- FINALIZAÇÃO DO CÓDIGO ---
COPY backend/ ./
RUN chmod +x entrypoint.sh

# Copia arquivos do frontend, remove referências de source maps ausentes e coleta estáticos
COPY --from=frontend-build /opt/stack/frontend/dist /opt/stack/frontend/dist
RUN find /opt/stack/frontend/dist -type f -name "*.js" -exec sed -i 's|//# sourceMappingURL=.*||g' {} +
RUN python manage.py collectstatic -c --noinput

# Salva data do build
RUN date +%Y.%m%d.%H%M >/opt/stack/backend/build-version.txt

# O entrypoint deve ativar a venv ou usar o path absoluto
ENTRYPOINT ["./entrypoint.sh"]