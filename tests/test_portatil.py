"""
O app empacotado funciona no Python-alvo (no CI: o python.exe da pasta
portátil, num Windows). Só fichas fictícias - ver ficha_ficticia.py.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
         "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]


def test_ficha_texto(ficha, converter_no_alvo):
    r = converter_no_alvo(ficha["texto"])
    cab, *linhas = r["linhas"]

    assert cab == ["Ano", "Mês", "VENCIMENTO", "ADICIONAL TEMPO SERVICO",
                   "GRATIFICACAO"]
    assert "IMPOSTO" not in cab  # Descontos não vão para a planilha
    assert [(ln[0], ln[1]) for ln in linhas] == [(2020, m) for m in MESES]
    for i, ln in enumerate(linhas):
        assert ln[2:] == [
            ficha["rubricas"]["VENCIMENTO"][i],
            ficha["rubricas"]["ADICIONAL TEMPO SERVICO"][i],
            ficha["rubricas"]["GRATIFICACAO"][i],
        ]
    assert ficha["rubricas"]["VENCIMENTO"][0] == 1234.56
    assert ficha["rubricas"]["GRATIFICACAO"][11] == 461.00
