import random

import httpx
import regex


class BuscaCep:
    def __init__(self):
        self.http = httpx.Client(follow_redirects=True, timeout=10.0)
        self.buscas = ['_busca_viacep', '_busca_opencep', '_busca_brasilapi']
        self._municipios: list[dict] = []

    @property
    def municipios(self):
        if not self._municipios:
            try:
                resp = self.http.get(
                    'https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome&view=nivelado',
                )
                resp.raise_for_status()
                self._municipios = resp.json()
            except httpx.HTTPError:
                pass
        return self._municipios

    def _busca_viacep(self, cep: str):
        try:
            resp = self.http.get(f'https://viacep.com.br/ws/{cep}/json/')
            resp.raise_for_status()
            body: dict = resp.json()
        except httpx.HTTPError:
            return None
        if body.get('erro'):
            return None
        logradouro = body.get('logradouro', '') or ''
        complemento = body.get('complemento', '') or ''
        unidade = body.get('unidade', '') or ''
        bairro = body.get('bairro', '') or ''
        localidade = body.get('localidade', '') or ''
        uf = body.get('uf', '') or ''
        ibge = body.get('ibge', '') or ''
        siafi = body.get('siafi', '') or ''
        estado = body.get('estado', '') or ''
        numero = complemento if complemento.isdigit() else ''
        complemento = unidade if numero else complemento
        return {
            'logradouro': logradouro,
            'complemento': complemento,
            'bairro': bairro,
            'numero': numero,
            'municipio': {
                'nome': localidade,
                'codigoIBGE': ibge,
                'codigoSIAFI': siafi,
                'estado': {
                    'nome': estado,
                    'uf': uf,
                }
            }
        }

    def _busca_opencep(self, cep: str):
        try:
            resp = self.http.get(f'https://opencep.com/v1/{cep}')
            resp.raise_for_status()
            body: dict = resp.json()
        except httpx.HTTPError:
            return None
        if body.get('error'):
            return None
        logradouro = body.get('logradouro', '') or ''
        complemento = body.get('complemento', '') or ''
        bairro = body.get('bairro', '') or ''
        localidade = body.get('localidade', '') or ''
        uf = body.get('uf', '') or ''
        ibge = body.get('ibge', '') or ''
        logradouro, numero = regex.split(r'(?=\d*$)', logradouro)
        try:
            resp2 = self.http.get(
                f'https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{ibge}?view=nivelado',
            )
            resp2.raise_for_status()
            body2: dict = resp2.json()
        except httpx.HTTPError:
            body2 = {}
        estado = body2.get('UF-nome', '')
        return {
            'logradouro': logradouro,
            'complemento': complemento,
            'bairro': bairro,
            'numero': numero,
            'municipio': {
                'nome': localidade,
                'codigoIBGE': ibge,
                'codigoSIAFI': '',
                'estado': {
                    'nome': estado,
                    'uf': uf,
                }
            }
        }

    def _busca_brasilapi(self, cep: str):
        try:
            resp = self.http.get(f'https://brasilapi.com.br/api/cep/v2/{cep}')
            resp.raise_for_status()
            body: dict = resp.json()
        except httpx.HTTPError:
            return None
        if body.get('erro'):
            return None
        state = body.get('state', '') or ''
        city = body.get('city', '') or ''
        neighborhood = body.get('neighborhood', '') or ''
        street = body.get('street', '') or ''
        logradouro, numero = regex.split(r'(?=\d*$)', street)
        municipio_ibge = next((
            m for m in self.municipios
            if m.get('municipio-nome', '') == city and m.get('UF-sigla', '') == state
        ), {})
        return {
            'logradouro': logradouro,
            'complemento': '',
            'bairro': neighborhood,
            'numero': numero,
            'municipio': {
                'nome': city,
                'codigoIBGE': str(municipio_ibge.get('municipio-id', '')),
                'codigoSIAFI': '',
                'estado': {
                    'nome': municipio_ibge.get('UF-nome', ''),
                    'uf': municipio_ibge.get('UF-sigla', ''),
                }
            }
        }

    def busca(self, cep: str):
        cep = regex.sub(r'\D', '', cep).zfill(8)
        for busca in self.buscas:
            result = getattr(self, busca)(cep)
            if result:
                return result
        return None
