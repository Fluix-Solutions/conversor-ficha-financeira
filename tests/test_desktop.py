"""
"Salvar como" do app de desktop, no Python-alvo (no CI: o python.exe da pasta).
A v1.1 gravava o resultado JSON como `.xlsx` e o abria no Excel ("corrompido").
"""
from __future__ import annotations

import json

import pytest
from conftest import TESTS, rodar_no_alvo
from test_portatil import MESES

pytestmark = pytest.mark.e2e

RUBRICAS = ["VENCIMENTO", "ADICIONAL TEMPO SERVICO", "GRATIFICACAO"]


@pytest.fixture
def salvar(alvo, app_dir, ficha, tmp_path):
    def _salvar(formato: str, escolhido: str) -> dict:
        saida = tmp_path / "saida"
        saida.mkdir()
        destino = str(saida / escolhido) if escolhido else ""
        out = rodar_no_alvo(alvo, str(TESTS / "_salvar_alvo.py"), str(app_dir),
                            ficha["texto"], formato, destino, "estado")
        return json.loads(out.strip().splitlines()[-1])
    return _salvar


def test_json_grava_no_caminho_escolhido_sem_virar_xlsx(salvar):
    r = salvar("json", "ficha.json")
    assert r["resultado"] == {"ok": True, "caminho": "ficha.json"}
    assert r["arquivos"] == ["ficha.json"]
    # Um download e uma gravação: também prova que o registro funciona.
    assert r["gravacoes"] == ["ficha.json"]
    assert r["downloads"] == 1


def test_json_sem_extensao_ganha_json(salvar):
    r = salvar("json", "minha_ficha")
    assert r["arquivos"] == ["minha_ficha.json"]


def test_json_com_extensao_maiuscula_nao_ganha_outra(salvar):
    r = salvar("json", "FICHA.JSON")
    assert r["arquivos"] == ["FICHA.JSON"]


def test_json_dialogo_sugere_nome_json_e_so_filtro_json(salvar):
    r = salvar("json", "ficha.json")
    assert r["arquivo_nome"] == "ficticia.json"
    assert r["pedido"] == {"save_filename": "ficticia.json",
                           "file_types": ["JSON (*.json)"]}


def test_json_gravado_traz_os_proventos_da_ficha(salvar, ficha):
    dados = salvar("json", "ficha.json")["conteudo"]["json"]
    linhas = dados["proventos"]
    assert [(ln["Ano"], ln["Mês"]) for ln in linhas] == [(2020, m) for m in MESES]
    for nome in RUBRICAS:
        assert [ln[nome] for ln in linhas] == ficha["rubricas"][nome]


def test_json_nao_abre_sozinho(salvar):
    assert salvar("json", "ficha.json")["abertos"] == []


def test_xlsx_continua_planilha_e_abre(salvar, ficha):
    r = salvar("xlsx", "planilha")
    assert r["pedido"]["file_types"] == ["Planilha Excel (*.xlsx)"]
    assert r["arquivos"] == ["planilha.xlsx"]
    assert r["abertos"] == ["planilha.xlsx"]
    cab, *linhas = r["conteudo"]["xlsx"]
    assert cab == ["Ano", "Mês", *RUBRICAS]
    assert [(ln[0], ln[1]) for ln in linhas] == [(2020, m) for m in MESES]
    for j, nome in enumerate(RUBRICAS):
        assert [ln[2 + j] for ln in linhas] == ficha["rubricas"][nome]


def test_cancelar_nao_grava_nada(salvar):
    r = salvar("json", "")
    assert r["resultado"] == {"cancelado": True}
    assert r["gravacoes"] == []
    assert r["downloads"] == 0
