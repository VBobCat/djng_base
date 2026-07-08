import os
import threading
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable

import duckdb
import psutil
import sqlglot
from django.conf import settings

_install_lock = threading.Lock()
_extensions_installed = False


def get_macros():
    macros_path = Path(__file__).parent.joinpath('duckdb_macros.sql')
    for macro_ast in sqlglot.parse(macros_path.read_text(), read='duckdb', error_level=sqlglot.ErrorLevel.IGNORE):
        if macro_ast is not None:
            yield macro_ast.sql(dialect='duckdb', pretty=True, comments=False)


def read_parquet_file_metadata(ddb: duckdb.DuckDBPyConnection, file: str | Path):
    # noinspection SqlResolve
    return ddb.sql('SELECT * FROM parquet_file_metadata($1)', params=[Path(file).as_posix()])


def read_parquet_info(ddb: duckdb.DuckDBPyConnection, file: str | Path):
    # noinspection SqlResolve
    return ddb.sql(
        r'''
        WITH meta AS (SELECT path_in_schema,
                             ANY_VALUE(type)                                                        AS type,
                             ANY_VALUE(compression)                                                 AS compression,
                             SUM(num_values)                                                        AS num_values,
                             SUM(stats_null_count)                                                  AS stats_null_count,
                             (SUM(stats_null_count) / NULLIF(SUM(num_values), 0))                   AS stats_null_ratio,
                             MIN(stats_min)                                                         AS min_global,
                             MAX(stats_max)                                                         AS max_global,
                             SUM(total_compressed_size)                                             AS total_compressed_size,
                             SUM(total_uncompressed_size)                                           AS total_uncompressed_size,
                             (SUM(total_compressed_size) / NULLIF(SUM(total_uncompressed_size), 0)) AS compression_ratio
                      FROM parquet_metadata($1)
                      GROUP BY path_in_schema
                      ORDER BY path_in_schema),
             esquema AS (SELECT * FROM parquet_schema($1))
        SELECT m.*,
               e.* EXCLUDE("type")
        FROM meta m
                 LEFT JOIN esquema e ON e.name = m.path_in_schema
        ORDER BY e.column_id;
        ''', params=[Path(file).as_posix()],
    )


def read_parquet_metadata(ddb: duckdb.DuckDBPyConnection, file: str | Path):
    # noinspection SqlResolve
    return ddb.sql('SELECT * FROM parquet_metadata($1)', params=[Path(file).as_posix()])


def read_parquet_kv_metadata(ddb: duckdb.DuckDBPyConnection, file: str | Path):
    # noinspection SqlResolve
    return ddb.sql('SELECT * FROM parquet_kv_metadata($1)', params=[Path(file).as_posix()])


def read_parquet_schema(ddb: duckdb.DuckDBPyConnection, file: str | Path):
    # noinspection SqlResolve
    return ddb.sql('SELECT * FROM parquet_schema($1)', params=[Path(file).as_posix()])


@contextmanager
def get_duckdb(database: str | Path = ':memory:', *, vacuum: bool = False):
    """
    Um gerenciador de contexto que fornece uma conexão DuckDB configurada para alto desempenho.

    A conexão é otimizada com base nos recursos de hardware da máquina (CPUs, memória)
    para acelerar o processamento de consultas.

    Args:
        database (str | Path): O caminho para o arquivo do banco de dados DuckDB.
                               O padrão é ':memory:' para um banco de dados em memória.
        vacuum (bool): Se True, executa um comando VACUUM ao fechar a conexão
                       para otimizar o arquivo de banco de dados (se não for em memória).

    Yields:
        duckdb.DuckDBPyConnection: Uma conexão DuckDB configurada.
    """
    global _extensions_installed
    temp_dir_root = Path.home() / '.duckdb_tmp'
    temp_dir_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=temp_dir_root, ignore_cleanup_errors=True) as temp_dir:
        temp_dir = Path(temp_dir).as_posix().replace("'", "''")
        cpus = psutil.cpu_count(logical=False) or os.cpu_count() or 1
        threads = int(cpus * 2 / 3) if cpus > 2 else 1
        memory = psutil.virtual_memory().total / (1024 ** 3)
        memory_limit = int(memory * ((1 / 3) if memory < 4 else (2 / 3)))
        default_db = settings.DATABASES['default']
        ddb = duckdb.connect(database.as_posix() if isinstance(database, Path) else database)
        try:
            if not _extensions_installed:
                with _install_lock:
                    if not _extensions_installed:  # Double-check recomendado para multi-threading
                        ddb.execute('INSTALL excel; INSTALL postgres;')
                        _extensions_installed = True
            ddb.execute('LOAD excel; LOAD postgres;')
            ddb.execute(f"SET temp_directory = '{temp_dir}';")
            ddb.execute(f'SET threads={threads};')
            ddb.execute(f"SET memory_limit='{memory_limit}GB';")
            ddb.execute('SET preserve_insertion_order=false;')
            if 'postgresql' in default_db.get('ENGINE', ''):
                pg_cs = 'dbname={NAME} user={USER} password={PASSWORD} host={HOST} port={PORT}'.format(**default_db)
                ddb.execute(f"ATTACH '{pg_cs}' AS atena (TYPE POSTGRES, READ_ONLY, SCHEMA 'public');")
            for macro in get_macros():
                ddb.execute(macro)
            yield ddb
        finally:
            try:
                if vacuum and database != ':memory:':
                    ddb.execute('VACUUM;')
            finally:
                ddb.close()


def read_parquet_files_to_duckdb(duckdb_path: str | Path, parquet_files: Iterable[str | Path]):
    duckdb_path = Path(duckdb_path).resolve()
    parquet_files = sorted((Path(p).resolve() for p in parquet_files), key=lambda p: p.stem[15:])
    for parquet_file in parquet_files:
        table_name = parquet_file.stem[15:]
        tmp_table_name = f'TMP_{parquet_file.stem}'
        try:
            with duckdb.connect(duckdb_path) as con:
                con.execute(f"CREATE TABLE {tmp_table_name} AS SELECT * FROM read_parquet('{parquet_file}');")
                con.execute(f"ALTER TABLE {tmp_table_name} ADD CONSTRAINT {table_name}_PK PRIMARY KEY (ID);")
                con.execute(f"DROP TABLE IF EXISTS {table_name};")
                con.execute(f"ALTER TABLE {tmp_table_name} RENAME TO {table_name};")
        except duckdb.Error as e:
            print(e)


def analisar_unicidade(caminho_parquet, coluna_chave):
    with get_duckdb() as con:

        try:
            # 1. Obtém metadados das colunas
            colunas_info = con.execute(f"DESCRIBE SELECT * FROM '{caminho_parquet}'").fetchall()
            todas_colunas = [col[0] for col in colunas_info]

            if coluna_chave not in todas_colunas:
                print(f"Erro: Coluna '{coluna_chave}' não encontrada.")
                return

            colunas_teste = [c for c in todas_colunas if c != coluna_chave]

            # 2. Monta a query com contador de divergências
            # Para cada coluna, verificamos se o count distinct > 1. Se sim, somamos 1 ao total.
            select_counts = ",\n        ".join([f"COUNT(DISTINCT \"{c}\") AS \"{c}\"" for c in colunas_teste])

            # Cria a soma lógica: (col1 > 1)::int + (col2 > 1)::int ...
            soma_divergencias = " + ".join([f"(COUNT(DISTINCT \"{c}\") > 1)::INT" for c in colunas_teste])

            query = f"""
                SELECT 
                    "{coluna_chave}",
                    ({soma_divergencias}) AS TOTAL_DIVERGENCIAS,
                    {select_counts}
                FROM '{caminho_parquet}'
                GROUP BY "{coluna_chave}"
                HAVING TOTAL_DIVERGENCIAS > 0
                ORDER BY TOTAL_DIVERGENCIAS DESC, "{coluna_chave}"
                """

            print(f"--- Analisando e Ordenando Divergências para: {coluna_chave} ---")
            df_resultado = con.execute(query).df()

            if df_resultado.empty:
                print("Sucesso: A coluna é única para todos os registros!")
            else:
                print(f"Encontrados {len(df_resultado)} IDs com problemas:")

                # Identifica quais colunas de dados (ignorando a chave e o total) têm erro
                df_counts = df_resultado.drop(columns=[coluna_chave, 'TOTAL_DIVERGENCIAS'])
                colunas_com_erro = df_counts.columns[(df_counts > 1).any()].tolist()

                # Exibe o resultado formatado
                colunas_para_exibir = [coluna_chave, 'TOTAL_DIVERGENCIAS'] + colunas_com_erro
                # print("\nTop IDs com maior número de campos divergentes:")
                print(df_resultado[colunas_para_exibir].to_string(index=False))

        except Exception as e:
            print(f"Erro ao processar o arquivo: {e}")


def query_export(source: Path | str, target: Path | str, query: str | None = None):
    with get_duckdb() as ddb:
        view = 'QSOURCE'
        ddb.read_parquet(Path(source).as_posix()).to_view('QSOURCE')
        if query:
            sql = sqlglot.parse_one(query).from_('QSOURCE').sql(dialect='duckdb', pretty=True)
            ddb.sql(sql).to_view('QQUERY')
            view = 'QQUERY'
        target = Path(target)
        target_str = Path(target).as_posix().replace("'", "''")
        if target.suffix == '.xlsx':
            ddb.sql(f"COPY {view} TO '{target_str}' WITH (FORMAT xlsx, HEADER true)")
        else:
            ddb.sql(f"COPY {view} TO '{target_str}' WITH (FORMAT parquet, COMPRESSION zstd)")
