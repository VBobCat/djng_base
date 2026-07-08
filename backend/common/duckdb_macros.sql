
CREATE OR REPLACE MACRO zfill (value VARCHAR, width INTEGER) AS (
  WITH
    pre1 AS (
      SELECT
        ltrim(regexp_replace(value, '\D+', '', 'g'), '0') AS clean
    )
  SELECT
    CASE
      WHEN length(clean) >= width THEN clean
      ELSE lpad(clean, width, '0')
    END
  FROM
    pre1
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE MACRO isvalid_cpf (value) AS (
  WITH
    prepared AS (
      SELECT
        zfill (value::VARCHAR, 11) AS numero
    ),
    checked AS (
      SELECT
        numero.split ('').apply (lambda x: x::INTEGER) AS d,
        -- Regra: len > 11 ou todos zeros ou base repetida (base % 111111111 == 0)
        (
          len(numero) = 11
          AND numero != '00000000000'
          AND (numero[: 9]::BIGINT % 111111111 != 0)
        ) AS pre_valido
      FROM
        prepared
    )
  SELECT
    CASE
      WHEN NOT pre_valido THEN FALSE
      ELSE (
        (
          CASE -- Cálculo Dígito 1
            WHEN (
              (
                d[1] * 10 + d[2] * 9 + d[3] * 8 + d[4] * 7 + d[5] * 6 + d[6] * 5 + d[7] * 4 + d[8] * 3 + d[9] * 2
              ) % 11
            ) < 2 THEN 0
            ELSE 11 - (
              (
                d[1] * 10 + d[2] * 9 + d[3] * 8 + d[4] * 7 + d[5] * 6 + d[6] * 5 + d[7] * 4 + d[8] * 3 + d[9] * 2
              ) % 11
            )
          END
        ) = d[10]
        AND (
          CASE -- Cálculo Dígito 2
            WHEN (
              (
                d[1] * 11 + d[2] * 10 + d[3] * 9 + d[4] * 8 + d[5] * 7 + d[6] * 6 + d[7] * 5 + d[8] * 4 + d[9] * 3 + d[10] * 2
              ) % 11
            ) < 2 THEN 0
            ELSE 11 - (
              (
                d[1] * 11 + d[2] * 10 + d[3] * 9 + d[4] * 8 + d[5] * 7 + d[6] * 6 + d[7] * 5 + d[8] * 4 + d[9] * 3 + d[10] * 2
              ) % 11
            )
          END
        ) = d[11]
      )
    END
  FROM
    checked
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE MACRO isvalid_cnpj (value) AS (
  WITH
    prepared AS (
      SELECT
        zfill (value::VARCHAR, 14) AS c
    ),
    checked AS (
      SELECT
        c,
        c.split ('').apply (lambda x: x::INT) AS d,
        CAST(c[1: 8] AS INT) AS base,
        CAST(c[9: 12] AS INT) AS ordem,
        (
          LENGTH(c) = 14
          AND c <> '00000000000000'
          AND ordem <> 0
          AND NOT (
            base > 0
            AND base % 11111111 = 0
          )
        ) AS preliminar_ok
      FROM
        prepared
    )
  SELECT
    CASE
      WHEN NOT preliminar_ok THEN FALSE
      ELSE (
        (
          CASE
            WHEN (
              (
                d[1] * 5 + d[2] * 4 + d[3] * 3 + d[4] * 2 + d[5] * 9 + d[6] * 8 + d[7] * 7 + d[8] * 6 + d[9] * 5 + d[10] * 4 + d[11] * 3 + d[12] * 2
              ) % 11
            ) < 2 THEN 0
            ELSE 11 - (
              (
                d[1] * 5 + d[2] * 4 + d[3] * 3 + d[4] * 2 + d[5] * 9 + d[6] * 8 + d[7] * 7 + d[8] * 6 + d[9] * 5 + d[10] * 4 + d[11] * 3 + d[12] * 2
              ) % 11
            )
          END
        ) = d[13]
        AND (
          CASE
            WHEN (
              (
                d[1] * 6 + d[2] * 5 + d[3] * 4 + d[4] * 3 + d[5] * 2 + d[6] * 9 + d[7] * 8 + d[8] * 7 + d[9] * 6 + d[10] * 5 + d[11] * 4 + d[12] * 3 + d[13] * 2
              ) % 11
            ) < 2 THEN 0
            ELSE 11 - (
              (
                d[1] * 6 + d[2] * 5 + d[3] * 4 + d[4] * 3 + d[5] * 2 + d[6] * 9 + d[7] * 8 + d[8] * 7 + d[9] * 6 + d[10] * 5 + d[11] * 4 + d[12] * 3 + d[13] * 2
              ) % 11
            )
          END
        ) = d[14]
      )
    END
  FROM
    checked
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE MACRO isvalid_ncnj (value) AS (
  WITH
    prepared AS (
      SELECT
        zfill (value::VARCHAR, 20) AS c
    )
  SELECT
    CASE
      WHEN len(c) != 20
      OR c[10: 11] NOT IN ('19', '20') THEN FALSE
      ELSE (c[8: 9]::INTEGER = (98 - ((c[1: 7] || c[10: 20] || '00')::HUGEINT % 97)))
    END
  FROM
    prepared
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE MACRO isvalid_nup17 (value) AS (
  WITH
    prepared AS (
      SELECT
        zfill (value::VARCHAR, 17) AS c
    ),
    checked AS (
      SELECT
        c.split ('').apply (x -> x::INTEGER) AS d,
        c[1: 5]::INTEGER AS org,
        c[6: 11]::INTEGER AS num,
        c[12: 15]::INTEGER AS ano,
        -- Validações: tamanho, prefixo '00000', limites de org, num e ano
        (
          len(c) = 17
          AND NOT c.starts_with ('00000')
          AND org >= 1
          AND num >= 1
          AND ano >= 1990
          AND ano <= date_part('year', today())
        ) AS preliminar_ok
      FROM
        prepared
    )
  SELECT
    CASE
      WHEN NOT preliminar_ok THEN FALSE
      ELSE (
        -- Cálculo Dígito 1 (pesos: 16, 15, ..., 2)
        (
          (
            11 - (
              d[1] * 16 + d[2] * 15 + d[3] * 14 + d[4] * 13 + d[5] * 12 + d[6] * 11 + d[7] * 10 + d[8] * 9 + d[9] * 8 + d[10] * 7 + d[11] * 6 + d[12] * 5 + d[13] * 4 + d[14] * 3 + d[15] * 2
            ) % 11
          ) % 10
        ) = d[16]
        AND
        -- Cálculo Dígito 2 (pesos: 17, 16, ..., 2)
        (
          (
            11 - (
              d[1] * 17 + d[2] * 16 + d[3] * 15 + d[4] * 14 + d[5] * 13 + d[6] * 12 + d[7] * 11 + d[8] * 10 + d[9] * 9 + d[10] * 8 + d[11] * 7 + d[12] * 6 + d[13] * 5 + d[14] * 4 + d[15] * 3 + d[16] * 2
            ) % 11
          ) % 10
        ) = d[17]
      )
    END
  FROM
    checked
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE MACRO isvalid_njf15 (value) AS (
  WITH
    digits AS (
      SELECT
        zfill (value::VARCHAR, 15).split('').apply(lambda c: c::INT) AS d
    )
  SELECT
    CASE
      WHEN length(d) != 15 THEN FALSE
      WHEN d[1]||d[2] NOT IN ('19','20') THEN FALSE
      ELSE (
        (
          (
            d[1] * 7 + d[2] * 6 + d[3] * 5 + d[4] * 4 + d[5] * 3 + d[6] * 2 + d[7] * 9 + d[8] * 8 + d[9] * 7 + d[10] * 6 + d[11] * 5 + d[12] * 4 + d[13] * 3 + d[14] * 2
          ) % 11
        ) % 10
      ) = d[15]
    END
  FROM
    digits
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE MACRO isvalid_njf10 (value) AS (
  WITH
    digits AS (
      SELECT
        zfill (value::VARCHAR, 10).split ('').apply (lambda c: c::INT) AS d
    )
  SELECT
    CASE
      WHEN length(d) != 10 THEN FALSE
      ELSE (
        CASE
          WHEN (
            (
              d[1] * 10 + d[2] * 9 + d[3] * 8 + d[4] * 7 + d[5] * 6 + d[6] * 5 + d[7] * 4 + d[8] * 3 + d[9] * 2
            ) % 11
          ) < 2 THEN 0
          ELSE 11 - (
            (
              d[1] * 10 + d[2] * 9 + d[3] * 8 + d[4] * 7 + d[5] * 6 + d[6] * 5 + d[7] * 4 + d[8] * 3 + d[9] * 2
            ) % 11
          )
        END
      ) = d[10]
    END
  FROM
    digits
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE
MACRO likemask_num_proc_jud(num) AS (
    WITH cleaned AS (
        -- Limpa apenas os dígitos para as validações
        SELECT regexp_replace(num::VARCHAR, '\D', '', 'g') AS raw
    ),
    logic AS (
        SELECT
            raw,
            isvalid_ncnj(raw) AS ncnj_ok,
            lpad(right(raw,15),15,'0') AS p15,
            isvalid_njf15(p15) AS njf15_ok,
        FROM cleaned
    )
    SELECT
        CASE
            -- Caso 0: não há dígitos
            WHEN raw = '' THEN ''
            -- Caso 1: NCNJ válido -> Retorna 20 dígitos (zfill 20)
            WHEN ncnj_ok  THEN lpad(raw, 20, '0')
            -- Caso 2: NJF15 válido -> Monta a string com underscores para LIKE
            WHEN njf15_ok THEN ('_' || p15[9:14] || '__' || p15[1:4] || '40_' || p15[5:8])
            -- Caso 3: Inválido ou não identificado
            ELSE ''
        END
    FROM logic
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE MACRO mascara_num_proc_jf (value) AS (
  WITH
    numero AS (
      SELECT
        zfill (value::VARCHAR, 20) as n
    ),
    verif AS (
      SELECT
        n,
        n[14] = 4
        and isvalid_ncnj (n) as val_ncnj,
        isvalid_njf15 (n) as val_njf15
      FROM
        numero
    )
  SELECT
    CASE
      WHEN val_ncnj THEN '_' || n[2: 7] || '__' || n[10: 14] || '__' || n[17: 20]
      WHEN val_njf15 THEN '_' || n[14: 19] || '__' || n[6: 9] || '4__' || n[10: 13]
      ELSE ''
    END
  FROM
    verif
),
(value, numreg) AS (
  WITH
    numero AS (
      SELECT
        zfill (value::VARCHAR, 20) as n,
        zfill (numreg::VARCHAR, 2) as r
    ),
    verif AS (
      SELECT
        n,
        r,
        n[14] = 4
        and isvalid_ncnj (n) as val_ncnj,
        isvalid_njf15 (n) as val_njf15
      FROM
        numero
    )
  SELECT
    CASE
      WHEN val_ncnj THEN '_' || n[2: 7] || '__' || n[10: 20]
      WHEN val_njf15 THEN '_' || n[14: 19] || '__' || n[6: 9] || '4' || r || n[10: 13]
      ELSE ''
    END
  FROM
    verif
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE MACRO decompor_njf15 (value, tt) AS (
  WITH
    validados AS (
      SELECT
        if(isvalid_njf15(value), zfill(value::VARCHAR, 15), NULL) as njf15
    )
  SELECT
    CASE
      WHEN njf15 IS NOT NULL THEN {
        'NNNNNN': CAST(njf15[9:14] AS INTEGER),
        'AAAA':   CAST(njf15[1:4]  AS INTEGER),
        'J':      4,
        'TT':     try_cast(regexp_replace(CAST(tt AS VARCHAR),'\D+','','g') AS INTEGER),
        'OOOO':   CAST(njf15[5:8]  AS INTEGER)
      }
      ELSE NULL
    END
  FROM validados
);
------------------------------------------------------------------------------------------------------------------------
CREATE OR REPLACE MACRO decompor_ncnj (value, tt) AS (
  WITH
    validados AS (
      SELECT
        if(isvalid_ncnj(value), zfill(value::VARCHAR, 20), NULL) as ncnj,
    )
  SELECT
    CASE
      WHEN ncnj IS NOT NULL THEN {
        'NNNNNN': CAST(ncnj[2:7]   AS INTEGER),
        'AAAA':   CAST(ncnj[10:13] AS INTEGER),
        'J':      CAST(ncnj[14:14] AS INTEGER),
        'TT':     CAST(ncnj[15:16] AS INTEGER),
        'OOOO':   CAST(ncnj[17:20] AS INTEGER)
      }
      ELSE NULL
    END
  FROM validados
);
CREATE OR REPLACE MACRO is_etiqueta_subs (etiqueta) AS starts_with(trim(etiqueta), 'SUBS_');
CREATE OR REPLACE MACRO is_etiqueta_uf (etiqueta) AS starts_with(trim(etiqueta), 'UF_');
CREATE OR REPLACE MACRO is_etiqueta_arq (etiqueta) AS starts_with(trim(etiqueta), 'ARQ_');
CREATE OR REPLACE MACRO is_etiqueta_pip (etiqueta) AS starts_with(trim(etiqueta), 'PIP_');
CREATE OR REPLACE MACRO is_etiqueta_ajuiza (etiqueta) AS starts_with(trim(etiqueta), 'AJUIZA_');
CREATE OR REPLACE MACRO is_etiqueta_b (etiqueta) AS regexp_matches(trim(etiqueta), '^B\d+$');
CREATE OR REPLACE MACRO is_etiqueta_consequencia (etiqueta) AS regexp_full_match(trim(etiqueta) , 'DOEN[CÇ]A_TRAB|INCAPACIDADE|MORTE');
CREATE OR REPLACE MACRO is_etiqueta_outras (e) AS NOT (
  e IS NULL OR 
  is_etiqueta_subs(e) OR 
  is_etiqueta_uf(e) OR 
  is_etiqueta_arq(e) OR 
  is_etiqueta_pip(e) OR 
  is_etiqueta_ajuiza(e) OR 
  is_etiqueta_b(e) OR 
  is_etiqueta_consequencia(e)
);