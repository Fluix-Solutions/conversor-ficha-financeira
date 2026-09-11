"""
O app empacotado funciona no Python-alvo (no CI: o python.exe da pasta
portátil, num Windows). Só fichas fictícias - ver ficha_ficticia.py.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request

import pytest
from conftest import RAIZ, rodar_no_alvo

pytestmark = pytest.mark.e2e

MODULOS = ["pdfplumber", "openpyxl", "pymupdf", "flask", "webview", "cv2",
           "onnxruntime", "rapidocr_onnxruntime", "converter", "server"]

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


def test_ficha_escaneada(ficha, converter_no_alvo):
    r = converter_no_alvo(ficha["scan"])
    resumo = r["resumo"]
    cab, *linhas = r["linhas"]

    assert resumo["layout"] == "OCR"
    assert resumo["anos"] == [2020]
    assert [a for a in resumo["avisos"] if "CONFERIR" in a] == []
    # O OCR normaliza o nome ("Vencimento"); o que importa é o valor.
    esperadas = list(ficha["rubricas"])
    assert [c.upper() for c in cab[2:]] == esperadas
    assert [(ln[0], ln[1]) for ln in linhas] == [(2020, m) for m in MESES]
    for j, nome in enumerate(esperadas):
        assert [ln[2 + j] for ln in linhas] == ficha["rubricas"][nome]


def test_importa_tudo(alvo, app_dir):
    codigo = (
        "import importlib, json, sys\n"
        f"sys.path.insert(0, {str(app_dir)!r})\n"
        f"mods = {MODULOS!r} + (['clr'] if sys.platform == 'win32' else [])\n"
        "res = {}\n"
        "for m in mods:\n"
        "    try:\n"
        "        importlib.import_module(m); res[m] = 'ok'\n"
        "    except Exception as e:\n"
        "        res[m] = f'{type(e).__name__}: {e}'\n"
        "print(json.dumps({'plataforma': sys.platform, 'mods': res}))\n"
    )
    out = json.loads(rodar_no_alvo(alvo, "-c", codigo).strip().splitlines()[-1])
    esperados = MODULOS + (["clr"] if out["plataforma"] == "win32" else [])
    assert sorted(out["mods"]) == sorted(esperados)
    assert {m: v for m, v in out["mods"].items() if v != "ok"} == {}


def _porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def test_api_versao_informa_ocr(alvo, app_dir):
    porta = _porta_livre()
    proc = subprocess.Popen(
        [str(alvo), str(app_dir / "server.py")], cwd=app_dir,
        env={**os.environ, "PORT": str(porta)},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        dados, limite = None, time.time() + 90
        while time.time() < limite and dados is None:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{porta}/api/versao", timeout=30
                ) as r:
                    dados = json.load(r)
            except OSError:
                assert proc.poll() is None, "server.py morreu ao subir"
                time.sleep(0.5)
        assert dados is not None, "server.py não respondeu em 90 s"
        assert dados["ocr"] is True, dados.get("ocr_erro")
    finally:
        proc.terminate()
        proc.wait(timeout=30)


def test_repositorio_sem_pdf_real():
    r = subprocess.run(["git", "ls-files", "*.pdf", "*.PDF"], cwd=RAIZ,
                       capture_output=True, text=True, check=True)
    assert r.stdout.strip() == ""
