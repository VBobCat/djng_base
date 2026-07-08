import random
from datetime import date
from typing import Literal

import regex
from sqlglot import diff

_EMAIL_REGEX = r"""(?:[a-z0-9!#$%&'*+\/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+\/=?^_`{|}~-]+)*|"(?:[
\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\[\x01-\x09\x0b\x0c\x0e-\x7f])*")@(?:(?:[a-z0-9](?:[a-z0-9-]*[
a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][
0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\[
\x01-\x09\x0b\x0c\x0e-\x7f])+)\])"""
_EMAIL_PARSE_REGEX = (
    r"(?P<name>.*?)\W*(?P<address>[a-z0-9!#$%&'*+\/=?^_`{|}~-]+(?:\.[a-z0-9!#$%&'*+\/=?^_`{"
    r"|}~-]+)*|\"(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21\x23-\x5b\x5d-\x7f]|\\["
    r"\x01-\x09\x0b\x0c\x0e-\x7f])*\")@(?:(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:["
    r"a-z0-9-]*[a-z0-9])?|\[(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4]["
    r"0-9]|[01]?[0-9][0-9]?|[a-z0-9-]*[a-z0-9]:(?:[\x01-\x08\x0b\x0c\x0e-\x1f\x21-\x5a\x53-\x7f]|\\["
    r"\x01-\x09\x0b\x0c\x0e-\x7f])+)\])")


def isvalid_email(value: str) -> bool:
    return bool(regex.match(_EMAIL_REGEX, (value or ''), regex.IGNORECASE))


def isvalid_ncnj(value: int | str) -> bool:
    value = ''.join(filter(str.isdecimal, str(value))).lstrip('0').zfill(20)
    if len(value) > 20 or value[9:11] not in ('19', '20'):
        return False
    return int(value[7:9]) == (98 - (int(value[:7] + value[9:] + '00') % 97))


def isvalid_njf15(value: int | str) -> bool:
    value = ''.join(filter(str.isdecimal, str(value))).lstrip('0').zfill(15)
    if len(value) > 15 or value[:2] not in ('00', '19', '20'):
        return False
    digits, pesos = tuple(map(int, value)), (7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2, 0)
    remainder = sum(d * p for d, p in zip(digits, pesos)) % 11
    vdigit = remainder % 10
    return vdigit == digits[14]


def isvalid_njf10(value: int | str) -> bool:
    value = ''.join(filter(str.isdecimal, str(value))).lstrip('0').zfill(10)
    if len(value) > 10:
        return False
    digits, pesos = tuple(map(int, value)), (10, 9, 8, 7, 6, 5, 4, 3, 2, 0)
    remainder = sum(d * p for d, p in zip(digits, pesos)) % 11
    vdigit = 0 if remainder < 2 else (11 - remainder)
    return vdigit == digits[9]


def njf15_to_ncnj_pattern(value: int | str) -> str:
    value = ''.join(filter(str.isdecimal, str(value))).lstrip('0').zfill(15)[-15:]
    return f'_{value[8:14]}__{value[:4]}4__{value[4:8]}'


def njf15_to_ncnj(value: int | str, jtr: int | str) -> str:
    value = ''.join(filter(str.isdecimal, str(value))).lstrip('0').zfill(15)[:15]
    ano = value[:4]
    orgao = value[4:8]
    num = value[8:14].zfill(7)
    jtr = ''.join(c for c in str(jtr) if c.isdigit()).zfill(3)[:3]
    dvs = str(98 - (int(num + ano + jtr + orgao + '00') % 97)).zfill(2)
    return num + dvs + ano + jtr + orgao


def isvalid_cnpj(value: int | str | None) -> bool:
    if value is None: return False
    string = ''.join(c for c in str(value).upper() if c in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ').lstrip('0').zfill(14)
    if len(string) != 14 or any(c in 'FIOQU' for c in string):
        return False  # não pode ter mais de 14 dígitos significativos (não-zero); as letras F, I, O, Q e U foram banidas
    digits = [(ord(c) - 48) for c in string]
    if digits[12] > 9 or digits[13] > 9:
        return False  # não pode ter letras nas últimas duas posições
    if sum(digits[8:12]) == 0 or len(set(digits[0:8])) == 1 and 0 < digits[0] < 10:
        return False  # não pode ter ordem 0000 ou raiz com dígito numérico repetido, exceto 00000000 (Banco do Brasil)
    resto1 = sum(c * d for c, d in zip((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), digits)) % 11
    dv1 = 0 if resto1 < 2 else (11 - resto1)
    if dv1 != digits[12]:
        return False
    resto2 = sum(c * d for c, d in zip((6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), digits)) % 11
    dv2 = 0 if resto2 < 2 else (11 - resto2)
    return dv2 == digits[13]


def calc_cnpj(value: int | str):
    string = ''.join(c for c in str(value).upper() if c in '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ').lstrip('0').zfill(12)
    if len(string) != 12:
        raise RuntimeError('# não pode ter mais de 12 dígitos significativos (não-zero)')
    if any(c in 'FIOQU' for c in string):
        raise RuntimeError('# as letras F, I, O, Q e U foram banidas')
    raiz, ordem = value[0:8], value[8:12]
    digits = [(ord(c) - 48) for c in string]
    draiz, dordem = digits[0:8], digits[8:12]
    if len(set(draiz)) == 1 and 0 < draiz[0] < 10:
        raise RuntimeError('# não pode ter raiz com um único dígito repetido, exceto 00.000.000 (Banco do Brasil S.A.)')
    if sum(dordem) == 0:
        raise RuntimeError('# não pode ter ordem 0000')
    resto1 = sum(c * d for c, d in zip((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), digits)) % 11
    dv1 = 0 if resto1 < 2 else (11 - resto1)
    digits.append(dv1)
    resto2 = sum(c * d for c, d in zip((6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), digits)) % 11
    dv2 = 0 if resto2 < 2 else (11 - resto2)
    return f'{raiz}{ordem}{dv1}{dv2}'


def rand_cnpj():
    raiz = ''.join(random.choice('0123456789ABCDEGHJKLMNPRSTVWXYZ') for i in range(8))
    ordem = ''.join(random.choice('0123456789ABCDEGHJKLMNPRSTVWXYZ') for i in range(4))
    digits = [(ord(c) - 48) for c in f'{raiz}{ordem}']
    resto1 = sum(c * d for c, d in zip((5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), digits)) % 11
    dv1 = 0 if resto1 < 2 else (11 - resto1)
    digits.append(dv1)
    resto2 = sum(c * d for c, d in zip((6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2), digits)) % 11
    dv2 = 0 if resto2 < 2 else (11 - resto2)
    return f'{raiz}{ordem}{dv1}{dv2}'


def isvalid_cpf(value: int | str | None) -> bool:
    if value is None: return False
    value = ''.join(c for c in str(value) if c.isdigit()).lstrip('0').zfill(11)
    if len(value) > 11:
        return False
    base = int(value[0:9])
    digits = [int(c) for c in value]
    if all(d == 0 for d in digits) or base % 111111111 == 0:
        return False
    remainder1 = sum(c * d for c, d in zip([10, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit1 = 0 if remainder1 < 2 else (11 - remainder1)
    if vdigit1 != digits[9]:
        return False
    remainder2 = sum(c * d for c, d in zip([11, 10, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit2 = 0 if remainder2 < 2 else (11 - remainder2)
    return vdigit2 == digits[10]


def tell_cpf_from_cnpj(value: int | str) -> tuple[str | None, str | None]:
    value = ''.join(c for c in str(value) if c.isdigit()).lstrip('0')
    vcpf = value.zfill(11) if isvalid_cpf(value) else None
    vcnpj = value.zfill(14) if isvalid_cnpj(value) else None
    if vcpf and vcnpj and vcnpj.startswith('000') and int(vcnpj[8:12]) > 300:
        return vcpf, None
    return vcpf, vcnpj


def isvalid_cadmf(value: int | str) -> tuple[bool, bool]:
    return isvalid_cpf(value), isvalid_cnpj(value)


def tipo_raiz_cadmf(num_doc: int | str):
    num_doc = ''.join(c for c in str(num_doc) if c.isdigit())
    if len(num_doc) == 11 and isvalid_cpf(num_doc):
        return 'cpf', num_doc[:9]
    elif len(num_doc) == 14 and isvalid_cnpj(num_doc):
        return 'cnpj', num_doc[:8]
    else:
        return None, num_doc


def calc_valid_cpf(value: int | str) -> str:
    value = ''.join(c for c in str(value) if c.isdigit()).zfill(11)[-11:]
    digits = [int(c) if c.isdigit() else 0 for c in value]
    remainder1 = sum(c * d for c, d in zip([10, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit1 = 0 if remainder1 < 2 else (11 - remainder1)
    digits[9] = vdigit1
    remainder2 = sum(c * d for c, d in zip([11, 10, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit2 = 0 if remainder2 < 2 else (11 - remainder2)
    digits[10] = vdigit2
    return ''.join(str(d) for d in digits)


def isvalid_nup17(value: int | str) -> bool:
    value = ''.join(c for c in str(value) if c.isdecimal()).zfill(17)
    if len(value) > 17 or value.startswith('00000'):
        return False
    org, num, ano = int(value[0:5]), int(value[5:11]), int(value[11:15])
    if org < 1 or num < 1 or ano < 1990 or ano > date.today().year:
        return False
    digits, pesos1 = tuple(map(int, value)), (16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2)
    remainder1 = sum(d * p for d, p in zip(digits, pesos1)) % 11
    vdigit1 = (11 - remainder1) % 10
    if vdigit1 != digits[15]:
        return False
    pesos2 = (17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2)
    remainder2 = sum(d * p for d, p in zip(digits, pesos2)) % 11
    vdigit2 = (11 - remainder2) % 10
    return vdigit2 == digits[16]


def isvalid_nup15(value: int | str) -> bool:
    value = ''.join(c for c in str(value) if c.isdigit()).zfill(15)
    if len(value) > 15 or (3 < int(value[11:13]) < 50):
        return False
    digits, pesos1 = tuple(map(int, value)), (14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2)
    remainder1 = sum(d * p for d, p in zip(digits, pesos1)) % 11
    vdigit1 = (11 - remainder1) % 10
    if vdigit1 != digits[13]:
        return False
    pesos2 = (15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2)
    remainder2 = sum(d * p for d, p in zip(digits, pesos2)) % 11
    vdigit2 = (11 - remainder2) % 10
    return vdigit2 == digits[14]


def isvalid_nup(value: int | str, digits: Literal[15, 17] | None = None) -> bool:
    return (digits != 15 and isvalid_nup17(value)) or (digits != 17 and isvalid_nup15(value))


def isvalid_cep(value: int | str) -> bool:
    value = ''.join(c for c in str(value) if c.isdigit()).zfill(8)[:8]
    return int(value) >= 1000000


def makevalid_nup17(value: int | str) -> str:
    value = ''.join(c for c in str(value) if c.isdigit()).zfill(15)[:15]
    digits = [int(c) for c in value]
    remainder1 = sum(c * d for c, d in zip([16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit1 = (11 - remainder1) % 10
    remainder2 = sum(c * d for c, d in zip([17, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit2 = (11 - remainder2) % 10
    return f'{value}{vdigit1}{vdigit2}'


def isvalid_ndivida(value: int | str, prefix: int | str = None) -> bool:
    value = ''.join(c for c in str(value) if c.isdigit()).zfill(14)[:14]
    prefix = [int(c) for c in str(prefix) if c.isdigit()] if prefix else None
    digits = [int(c) for c in value]
    if prefix and not all(a == b for a, b in zip(digits, prefix)):
        return False
    remainder1 = sum(c * d for c, d in zip([13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit1 = (11 - remainder1) % 10
    if vdigit1 != digits[12]:
        return False
    remainder2 = sum(c * d for c, d in zip([14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit2 = (11 - remainder2) % 10
    return vdigit2 == digits[13]


def isvalid_nb_nit(value):
    value = ''.join(c for c in str(value) if c.isdigit())
    if 10 <= len(value) <= 11:
        return False  # Menos de 10 ou mais de 11 dígitos são inválidos
    digits = [int(c) for c in value.zfill(11)]
    remainder = sum(c * d for c, d in zip((3, 2, 9, 8, 7, 6, 5, 4, 3, 2), digits)) % 11
    vdigit = 0 if remainder < 2 else 11 - remainder
    return vdigit == digits[10]


def isvalid_nbloquetesgi(value: int | str) -> bool:
    value = ''.join(c for c in str(value).upper() if c.isdigit() or c == 'X').zfill(18)[:18]
    if not value[:-1].isdigit():
        return False
    digits = [(10 if c == 'X' else int(c)) for c in value]
    remainder1 = sum(c * d for c, d in zip([2, 9, 8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit = (11 - remainder1) % 11
    return vdigit == digits[17]


def isvalid_conta_depjud(value: int | str) -> bool:
    value = ''.join(c for c in str(value).upper() if c.isdigit() or c == 'X').zfill(16)[:16]
    if not value.isdigit():
        return False
    if not (int(value[0:4]) > 0 and value[4:7] in ('005', '280', '635') and int(value[7:15]) > 0):
        return False
    digits = [int(c) for c in value]
    remainder1 = sum(c * d for c, d in zip([8, 7, 6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], digits)) % 11
    vdigit = (11 - remainder1) % 11
    if vdigit > 9: vdigit = 0
    return vdigit == digits[15]


def isvalid_telefone(value: int | str) -> bool:
    value = ''.join(c for c in str(value) if c.isdigit())
    return regex.search(
        r'(0|55)?'
        r'(1[1-9]|2[12478]|3[1-578]|4[1-9]|5[13-5]|6[1-9]|7[13-579]|8[1-9]|9[1-9])'
        r'([2-5]\d{3}|9\d{4}|7[0789]\d{2})'
        r'(\d{4})$',
        value,
    ) is not None


def validar_telefone_cf_plano_numeracao_brasileiro(numero: str):
    numero = ''.join(caract for caract in str(numero) if caract.isdigit())
    captures = regex.match(r'^(?<cn>[1-9][1-9])(?:(?<cau8>[2-6]\d{7})|(?<cau9>[7-9]\d{8}))$', numero).capturesdict()
    if captures['cn']:
        if captures['cau8']:
            return True, int('{cn}{cau8}'.format(**captures))
        if captures['cau9']:
            return True, int('{cn}{cau9}'.format(**captures))
    return False, None
