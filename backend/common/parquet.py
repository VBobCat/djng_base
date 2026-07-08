import json
import tempfile
from contextlib import contextmanager
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.pandas_compat as pd_compat
import pyarrow.parquet as pq
import regex

from common.duckdb import get_duckdb


@contextmanager
def get_temp_parquet_dir():
    """Cria um diretório temporário para armazenar arquivos Parquet e o remove ao sair do contexto."""
    with tempfile.TemporaryDirectory(
        dir=Path(__file__).parent, prefix='parquet_', ignore_cleanup_errors=True,
    ) as tmpdir:
        tmpdir_path = Path(tmpdir)
        tmpdir_path.joinpath('.gitignore').write_text('*\n')
        yield tmpdir_path


def parquet_to_xlsx(input_path: str | Path, output_path: str | Path | None = None):
    """
    Converte um arquivo Parquet para um arquivo XLSX (Excel).

    Esta função utiliza o DuckDB com a extensão 'excel' para realizar a conversão.
    Ela lida com a limpeza de dados durante o processo, removendo caracteres de
    controle inválidos de campos de texto e convertendo valores NaN (Not a Number)
    de colunas de ponto flutuante para nulos, garantindo a compatibilidade com o Excel.

    Args:
        input_path (str | Path): O caminho para o arquivo Parquet de entrada.
        output_path (str | Path | None): O caminho para o arquivo XLSX de saída.
                                         Se None, o arquivo de saída terá o mesmo nome
                                         do arquivo de entrada, mas com a extensão '.xlsx'.
    """
    input_path = Path(input_path)
    output_path = Path(output_path) if output_path else input_path.with_suffix('.xlsx')
    with get_duckdb() as con:
        con.execute('INSTALL excel; LOAD excel;')
        con.execute(f"CREATE OR REPLACE TABLE temp_raw AS SELECT * FROM read_parquet('{input_path}')")
        columns_info = con.execute('DESCRIBE temp_raw').fetchall()
        select_parts = []
        for col_name, col_type, _, _, _, _ in columns_info:
            safe_name = f'"{col_name}"'
            if col_type == 'VARCHAR':
                select_parts.append(
                    f'NULLIF(regexp_replace({safe_name}, '
                    f"'[\\x00-\\x08\\x0B\\x0C\\x0E-\\x1F]', '', 'g'), '') "
                    f'AS {safe_name}',
                )
            elif col_type in ('FLOAT', 'DOUBLE'):
                select_parts.append(f'(CASE WHEN isnan({safe_name}) THEN NULL ELSE {safe_name} END) AS {safe_name}')
            else:
                select_parts.append(safe_name)
        final_query = f'SELECT {", ".join(select_parts)} FROM temp_raw'
        con.execute(f"COPY ({final_query}) TO '{output_path}' (FORMAT xlsx)")


def _make_timestamp_glob_pattern(name: str):
    """Cria um padrão glob para encontrar arquivos Parquet com timestamp no nome."""
    return f'{"[0-9]" * 14}_{name}'


def _map_columns_to_pandas_format(schema):
    """Mapeia um esquema PyArrow para o formato de metadados de coluna do Pandas."""
    numpy_map = pd_compat.get_numpy_logical_type_map()
    columns = []
    for name in schema.names:
        arrow_type = schema.field(name).type
        logical_type = pd_compat.get_logical_type(arrow_type)
        numpy_type = numpy_map.get(logical_type, 'object')
        columns.append(
            {
                'name': name,
                'field_name': name,
                'pandas_type': logical_type,
                'numpy_type': numpy_type,
                'metadata': None,
            },
        )
    return columns


def _write_pandas_metatata_dict(custom_attrs: dict, schema):
    """
    Cria o dicionário de metadados no formato esperado pelo Pandas.

    Args:
        custom_attrs (dict): Atributos personalizados a serem incluídos.
        schema: O esquema PyArrow da tabela.

    Returns:
        dict: O dicionário de metadados completo.
    """
    return {
        'attributes': custom_attrs or {},
        'columns': _map_columns_to_pandas_format(schema),
        'index_columns': [],
        'column_metadata': [],  # Opcional: pode ser expandido se precisar de tipos específicos
        'creator': {'library': 'pyarrow', 'version': pa.__version__},
    }


def export_parquet_with_attrs(
    query: str,
    output_path: str | Path,
    dependencies: dict[str, str | Path] | None = None,
    custom_attrs: dict | None = None,
):
    """
    Executa uma consulta DuckDB e salva o resultado em um arquivo Parquet,
    incluindo atributos personalizados nos metadados.

    Args:
        query (str): A consulta SQL a ser executada.
        output_path (str): O caminho do arquivo Parquet de saída.
        dependencies (dict): Um dicionário de dependências (views) a serem criadas
                             antes de executar a consulta. As chaves são os nomes das
                             views e os valores são os caminhos para os arquivos Parquet.
        custom_attrs (dict): Um dicionário de atributos personalizados para salvar
                             nos metadados do arquivo Parquet.
    """
    output_path = Path(output_path)
    try:
        with get_duckdb() as con:
            if dependencies:
                for name, path in dependencies.items():
                    if next(regex.finditer(r'\W+', name), None):
                        raise ValueError(f'Nome inválido: "{name}"')
                    str_path = Path(path).as_posix().replace("'", "''")
                    con.sql(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{str_path}');")
            result_reader = con.sql(query).fetch_arrow_reader()
            if custom_attrs:
                pandas_meta_dict = _write_pandas_metatata_dict(custom_attrs, result_reader.schema)
                new_metadata = result_reader.schema.metadata or {}
                new_metadata[b'pandas'] = json.dumps(pandas_meta_dict).encode('utf-8')
                schema_with_attrs = result_reader.schema.with_metadata(new_metadata)
            else:
                schema_with_attrs = result_reader.schema
            with pq.ParquetWriter(output_path, schema_with_attrs) as writer:
                for batch in result_reader:
                    writer.write_batch(batch)
    except:
        if output_path.exists():
            output_path.unlink()
        raise


def _collect_max_values(columns_to_max: list[str], table: pa.Table, max_values: dict):
    """Coleta os valores máximos das colunas especificadas de uma tabela PyArrow."""
    for col in columns_to_max:
        if col in table.column_names:
            m = pc.max(table.column(col)).as_py()
            if m is not None:
                current = max_values.get(col)
                if current is None or m > current:
                    max_values[col] = m.isoformat() if hasattr(m, 'isoformat') else m


def _inject_max_values_metadata(max_values: dict, parquet_schema: pa.Schema, output_path: str | Path):
    """Injeta os valores máximos coletados nos metadados de um arquivo Parquet existente."""
    pandas_meta = _write_pandas_metatata_dict(max_values, parquet_schema)
    new_meta = (parquet_schema.metadata or {}).copy()
    new_meta[b'pandas'] = json.dumps(pandas_meta).encode('utf-8')
    final_schema = parquet_schema.with_metadata(new_meta)
    pq.write_metadata(final_schema, str(output_path))


def _escpath(path: str | Path) -> str:
    """Escapa um caminho de arquivo para uso seguro em consultas SQL."""
    return Path(path).as_posix().replace("'", "''")
