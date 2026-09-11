"""
Opções da suíte e2e: qual Python executa o app e de onde vem o código.

    Mac:  pytest tests                      (alvo = este Python, app = o repo)
    CI:   pytest tests -m e2e --python-alvo <pasta>/python/python.exe
                              --app-dir <pasta>

O pytest roda no Python do host; o alvo é chamado por subprocesso, então
nada de teste vai para dentro da pasta distribuída.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
RAIZ = TESTS.parent


def pytest_addoption(parser):
    parser.addoption("--python-alvo", default=sys.executable,
                     help="Python que executa o app (padrão: o do pytest)")
    parser.addoption("--app-dir", default=str(RAIZ),
                     help="pasta com converter.py/server.py (padrão: o repo)")


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: roda o app no Python-alvo")


@pytest.fixture(scope="session")
def alvo(request) -> Path:
    return Path(request.config.getoption("--python-alvo"))


@pytest.fixture(scope="session")
def app_dir(request) -> Path:
    return Path(request.config.getoption("--app-dir")).resolve()


def rodar_no_alvo(alvo: Path, *args: str, cwd: Path | None = None) -> str:
    # errors="replace": mensagem de erro com acento na página de código do
    # Windows não pode derrubar o teste antes de ele mostrar o erro.
    r = subprocess.run([str(alvo), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=cwd, timeout=600)
    assert r.returncode == 0, f"alvo falhou ({r.returncode}):\n{r.stderr[-3000:]}"
    return r.stdout


@pytest.fixture(scope="session")
def ficha(alvo, tmp_path_factory) -> dict:
    d = tmp_path_factory.mktemp("ficha")
    return json.loads(rodar_no_alvo(alvo, str(TESTS / "ficha_ficticia.py"), str(d)))


@pytest.fixture
def converter_no_alvo(alvo, app_dir, tmp_path):
    def _conv(pdf: str, origem: str = "estado") -> dict:
        saida = tmp_path / "saida.xlsx"
        out = rodar_no_alvo(alvo, str(TESTS / "_converter_alvo.py"), str(app_dir),
                            pdf, str(saida), origem)
        return json.loads(out.strip().splitlines()[-1])
    return _conv
