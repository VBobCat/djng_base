import base64
import platform
import time
from base64 import b64decode
from datetime import datetime, date
from os import getenv, path
from pathlib import Path
from typing import Literal, Any

import fastparquet
import oracledb
from oracledb.exceptions import DatabaseError as OracleDBError
import pandas as pd
from django.utils.timezone import localtime, get_current_timezone


class Oracle:
    __initialized = False

    def __new__(cls, *args, **kwargs):
        if not cls.__initialized:
            oracledb.defaults.fetch_lobs = False
            oracledb.defaults.datetime_types = oracledb.DATETIME
            oracledb.defaults.tzinfo = get_current_timezone()
            if platform.system() == "Windows":
                instant_client_lib_dir = Path(envvalue) \
                    if (envvalue := getenv('ORACLE_INSTANT_CLIENT_DIR')) and path.isdir(envvalue) \
                    else None
                instant_client_config_dir = instant_client_lib_dir / 'network' / 'admin' \
                    if (instant_client_lib_dir and instant_client_lib_dir.is_dir()) \
                    else None
                if instant_client_lib_dir and instant_client_config_dir:
                    oracledb.init_oracle_client(
                        lib_dir=str(instant_client_lib_dir),
                        config_dir=str(instant_client_config_dir),
                    )
            else:
                try:
                    oracledb.init_oracle_client()
                except OracleDBError:
                    pass
            cls.__initialized = True
        return super(Oracle, cls).__new__(cls, *args, **kwargs)

    def __init__(self, *, host=None, port=None, service_name=None, user=None, password=None):
        host = host or getenv('ORACLE_DB_HOST', 'localhost')
        port = port or getenv('ORACLE_DB_PORT', '1521')
        service_name = service_name or getenv('ORACLE_DB_SERVICE_NAME') or None
        if user and password:
            self.credentials = base64.b64encode(f'{user}:{password}'.encode()).decode()
        if not (user and password):
            self.credentials = getenv('ORACLE_DB_CREDENTIALS')
        if not (host and port and service_name and self.credentials):
            raise AssertionError('Missing parameters')
        self.dsn = oracledb.makedsn(host=host, port=port, service_name=service_name)
        self._schema_items_info = {}

    def get_connection(self) -> oracledb.Connection:
        user, password = base64.b64decode(self.credentials).decode().split(':')
        return oracledb.connect(dsn=self.dsn, user=user, password=password)

    def get_schema_items_info(self):
        query = """
                SELECT obj.owner, obj.object_name, obj.object_type, col.column_name, col.data_type, col.nullable
                FROM all_objects obj
                         JOIN all_tab_columns col
                              ON obj.owner = col.owner AND obj.object_name = col.table_name
                WHERE obj.object_type IN ('TABLE', 'VIEW')
                  AND obj.status = 'VALID'
                ORDER BY obj.owner, obj.object_type, obj.object_name, col.column_id \
                """

        result = {}
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                for owner, object_name, object_type, column_name, data_type, nullable in cursor:
                    if owner not in result:
                        result[owner] = {}
                    key = (object_type, object_name)
                    if key not in result[owner]:
                        result[owner][key] = {
                            'object_type': object_type,
                            'object_name': object_name,
                            'columns': [],
                        }
                    result[owner][key]['columns'].append(
                        {
                            'column_name': column_name,
                            'data_type': data_type,
                            'nullable': nullable,
                        },
                    )

        return {k: list(v.values()) for k, v in sorted(result.items())}

    @property
    def schema_items_info(self):
        if not self._schema_items_info:
            self._schema_items_info = self.get_schema_items_info()
        return self._schema_items_info

    def dump_from_owner(
            self,
            owner: str,
            target_folder: str | Path,
            object_names: list = None,
            fileformat: Literal['csv', 'excel', 'parquet'] = 'parquet',
    ):
        target_folder = Path(target_folder)
        if owner not in self.schema_items_info:
            raise AssertionError(f'Owner {owner} not found')
        schema_items = self.schema_items_info[owner]
        for schema_item in schema_items:
            object_name = schema_item['object_name']
            if object_names and object_name not in object_names:
                continue
            clist = ', '.join(c['column_name'] for c in schema_item['columns'])
            query = f"SELECT {clist} FROM {owner}.{object_name}"
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    nomes_colunas = [col[0] for col in cursor.description]
                    df = pd.DataFrame(cursor.fetchall(), columns=nomes_colunas)
            fn = target_folder / f'{owner}_{object_name}_{localtime():%Y%m%d_%H%M%S}.{fileformat}'
            if fileformat == 'csv':
                df.to_csv(fn, index=False, sep=';', encoding='iso-8859-1')
            elif fileformat == 'excel':
                df.to_excel(fn, index=False)
            elif fileformat == 'parquet':
                df.to_parquet(fn, index=False)
            print(f'Dumped {fn}')
            if not object_names:
                time.sleep(10)

    def get_ddls(self, owner: str):
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM all_views WHERE owner = '{owner}'")
                nomes_colunas = [col[0] for col in cursor.description]
                lista = cursor.fetchall()
        return [dict(zip(nomes_colunas, row)) for row in lista]

    def dump_query(self, sql_query: str, target_file: str | Path):
        target_file = Path(target_file)
        fileformat = target_file.suffix.lower().lstrip('.')
        if fileformat not in ('csv', 'excel', 'json', 'parquet'):
            raise AssertionError(f'File format "{fileformat}" not supported')
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql_query)
                nomes_colunas = [col[0] for col in cursor.description]
                df = pd.DataFrame(cursor.fetchall(), columns=nomes_colunas)
                if fileformat == 'csv':
                    df.to_csv(target_file, index=False, sep=';', encoding='iso-8859-1')
                elif fileformat == 'excel':
                    df.to_excel(target_file, index=False)
                elif fileformat == 'json':
                    df.to_json(target_file, orient='records')
                elif fileformat == 'parquet':
                    df.to_parquet(target_file, index=False)

PANDAS_TS_MIN = pd.Timestamp("1677-09-21 00:00:00")
PANDAS_TS_MAX = pd.Timestamp("2262-04-11 23:47:16.854775")

def type_check_dataframe(df: pd.DataFrame, view_schema: dict[str, Any]):
    dttypes = (datetime, oracledb.DB_TYPE_TIMESTAMP, oracledb.DB_TYPE_TIMESTAMP_TZ, oracledb.DB_TYPE_TIMESTAMP_LTZ)
    for col_name, col_type in view_schema.items():
        if col_type in dttypes:
            df[col_name] = pd.to_datetime(df[col_name], errors="coerce").dt.tz_localize(None)
            mask_out_of_range = (df[col_name] < PANDAS_TS_MIN) | (df[col_name] > PANDAS_TS_MAX)
            if mask_out_of_range.any():
                df[col_name] = df[col_name].mask(mask_out_of_range)
        elif col_type in (date, oracledb.DB_TYPE_DATE):
            df[col_name] = pd.to_datetime(df[col_name], errors="coerce").dt.date
        elif col_type in (int, float, oracledb.DB_TYPE_NUMBER):
            if col_type == int or col_name == 'ID' or col_name.endswith('_ID'):
                df[col_name] = pd.to_numeric(df[col_name], errors="coerce").astype('Int64')
            else:
                df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
        elif col_type in (str, oracledb.DB_TYPE_VARCHAR):
            df[col_name] = df[col_name].astype('string')


def dump_oracle_query_to_parquet(target: str | Path, sql: str, *, oracle: Oracle = None, block_size: int = 10_000,
                                 skip_existing: bool = False):
    target = Path(target)
    if not target.is_absolute():
        target = Path(getenv('USERPROFILE')).joinpath(Path('desktop')).joinpath(target).resolve()
    if skip_existing and target.exists():
        return target
    if oracle is None:
        oracle = Oracle()
    bindex, bsize = 0, 0
    with oracle.get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            view_schema = {c.name: c.type for c in cursor.description}
            print(f'\rImportados {bindex} blocos, {bsize} registros...', end=' ', flush=True)
            while rows := cursor.fetchmany(block_size):
                rows_frame = pd.DataFrame(rows, columns=list(view_schema.keys()))
                type_check_dataframe(rows_frame, view_schema)
                fastparquet.write(
                    target.as_posix(),
                    rows_frame,
                    append=bindex > 0,
                    compression='SNAPPY',
                    file_scheme='simple'
                )
                bindex += 1
                bsize += len(rows_frame)
                print(f'\rImportados {bindex} blocos, {bsize} registros...', end=' ', flush=True)
            print(f'\rImportados {bindex} blocos, {bsize} registros. Concluído.')
    return target


def get_oracle_conn_kw():
    dsn = oracledb.makedsn(
        host=getenv('ORACLE_DB_HOST'),
        port=int(getenv('ORACLE_DB_PORT') or '1521'),
        service_name=getenv('ORACLE_DB_SERVICE_NAME')
    )
    user, password = b64decode(getenv('ORACLE_DB_CREDENTIALS') or 'Og==').decode().split(':')
    return dict(dsn=dsn, user=user, password=password)
