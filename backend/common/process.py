import os
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Callable, Any, TypeVar, ParamSpec
import django
import psutil
from django.core.cache import cache

# Tipagem moderna para manter o suporte do editor (Python 3.14)
P = ParamSpec("P")
R = TypeVar("R")


# noinspection PyBroadException
def low_priority_process_initializer():
    try:
        os.nice(10)  # Prioridade de CPU
    except Exception:
        pass
    try:
        psutil.Process().ionice(psutil.IOPRIO_CLASS_BE, value=7)  # Prioridade de Disco (I/O)
    except Exception:
        pass
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "atena.settings")
    try:
        django.setup()
    except Exception:
        pass


def run_in_low_priority_process(func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
    """
    Executa a função em um processo isolado com baixa prioridade.
    Utiliza um semáforo no cache do Django para garantir que apenas
    um processo pesado rode por vez em toda a infraestrutura.
    """
    lock_id = "lock_global_low_priority_process"
    timeout_espera = 3600  # Tempo máximo esperando na fila (1 hora)
    timeout_lock = 4800  # Tempo máximo de vida do lock (2 horas) - Previne deadlocks
    intervalo_polling = 2  # De quanto em quanto tempo checa o cache
    inicio_espera = time.time()
    while True: # 1. Spin-lock para adquirir o semáforo
        # cache.add é ATÔMICO na maioria dos backends (Redis, Memcached).
        # Retorna True APENAS se a chave foi criada com sucesso agora.
        if cache.add(lock_id, "locked", timeout=timeout_lock):
            break  # Conseguimos o lock!
        if time.time() - inicio_espera > timeout_espera:
            raise TimeoutError("Timeout esgotado aguardando o semáforo do ETL liberar.")
        time.sleep(intervalo_polling)
    try: # 2. Execução protegida
        with ProcessPoolExecutor(max_workers=1, initializer=low_priority_process_initializer) as executor:
            future = executor.submit(func, *args, **kwargs)
            return future.result()
    except AssertionError as ae:
        if 'daemonic processes are not allowed to have children' in str(ae):
            return func(*args, **kwargs)
        else:
            raise
    finally:
        # 3. Liberação garantida do semáforo, mesmo se ocorrer exceção
        cache.delete(lock_id)