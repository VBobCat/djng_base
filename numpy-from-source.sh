#!/usr/bin/env bash
set -euo pipefail

# 1. Detecta o executável Python (Global no container ou VENV no servidor)
if [ -n "${VIRTUAL_ENV:-}" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python"
elif [ -f ".venv/bin/python" ]; then
    PYTHON_BIN="$(pwd)/.venv/bin/python"
else
    PYTHON_BIN=$(which python3)
fi

# 2. Função para rodar comandos como root apenas se necessário (ignora sudo se não existir)
run_root() {
    if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
        sudo "$@"
    else
        "$@"
    fi
}

# 3. Verificação de CPU
CPU_FLAGS="$(grep -m1 '^flags' /proc/cpuinfo)"
NEED_REBUILD=0
for f in ssse3 sse4_1 sse4_2 popcnt; do
    echo "$CPU_FLAGS" | grep -qw "$f" || NEED_REBUILD=1
done

if [ "$NEED_REBUILD" -eq 0 ]; then
    echo "CPU compatível com x86_64_v2 — mantendo NumPy via wheel."
    exit 0
fi

echo "CPU NÃO compatível — recompilando NumPy para baseline legado."

# 4. Instalação de dependências de compilação
run_root apt-get update
run_root apt-get install -qy build-essential gfortran pkg-config libopenblas-dev liblapack-dev ninja-build

# 5. Processo de compilação
NUMPY_VERSION="$($PYTHON_BIN -m pip show numpy | awk '/Version:/ {print $2}')"
if [ -z "$NUMPY_VERSION" ]; then echo "NumPy não encontrado"; exit 1; fi

$PYTHON_BIN -m pip uninstall -y numpy
$PYTHON_BIN -m pip install --no-cache-dir meson meson-python ninja Cython pybind11

# A mágica da compatibilidade: desativando instruções avançadas
$PYTHON_BIN -m pip install -v \
    --no-binary=:all: \
    --no-build-isolation \
    --config-settings=setup-args=-Dcpu-baseline=none \
    --config-settings=setup-args=-Dcpu-dispatch=none \
    "numpy==$NUMPY_VERSION"

# Limpeza para reduzir o tamanho da imagem (apenas se estivermos no Docker)
if [ -f /.dockerenv ]; then
    run_root apt-get purge -qy build-essential gfortran pkg-config ninja-build
    run_root apt-get autoremove -qy
    run_root rm -rf /var/lib/apt/lists/*
fi
$PYTHON_BIN -m pip uninstall -y meson meson-python ninja Cython pybind11
