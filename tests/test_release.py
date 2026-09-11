"""Regras da Release: versão do app, tag, nome do zip e notas."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import release  # noqa: E402


def test_versao_app_le_o_server_py():
    assert release.versao_app(RAIZ / "server.py") == "1.1"


def test_tag_enviada_igual_a_versao_e_aceita():
    assert release.tag_release("v1.1", "1.1") == "v1.1"
    assert release.tag_release("v2.0.3", "2.0.3") == "v2.0.3"


def test_tag_diferente_da_versao_falha_mostrando_os_dois():
    with pytest.raises(release.ErroRelease) as e:
        release.tag_release("v1.2", "1.1")
    assert "1.2" in str(e.value)
    assert "1.1" in str(e.value)


@pytest.mark.parametrize("tag", ["teste", "v1", "1.1", "v1.1.1.1", "v1.1-rc1"])
def test_tag_fora_do_formato_falha(tag):
    with pytest.raises(release.ErroRelease):
        release.tag_release(tag, "1.1")


def test_sem_tag_usa_a_versao_do_app():
    assert release.tag_release(None, "1.1") == "v1.1"


def test_tag_existente_em_outro_commit_falha_mostrando_os_dois():
    with pytest.raises(release.ErroRelease) as e:
        release.conferir_commit_da_tag("v1.1", "a" * 40, "b" * 40)
    assert "a" * 40 in str(e.value)
    assert "b" * 40 in str(e.value)


def test_tag_existente_no_mesmo_commit_e_aceita():
    release.conferir_commit_da_tag("v1.1", "c" * 40, "c" * 40)


def test_tag_que_ainda_nao_existe_e_aceita():
    release.conferir_commit_da_tag("v1.1", "", "c" * 40)


def test_cli_tag_em_outro_commit_sai_com_1():
    r = subprocess.run(
        [sys.executable, str(RAIZ / "release.py"), "tag",
         "--sha-tag", "a" * 40, "--sha", "b" * 40],
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "a" * 40 in r.stderr and "b" * 40 in r.stderr
    ok = subprocess.run(
        [sys.executable, str(RAIZ / "release.py"), "tag",
         "--sha-tag", "", "--sha", "b" * 40],
        capture_output=True, text=True,
    )
    assert ok.returncode == 0
    assert ok.stdout.strip() == "v1.1"


def test_nome_do_zip():
    assert release.nome_zip("v1.1") == "Conversor-de-Ficha-Financeira-v1.1-windows-x64.zip"


def test_notas_trazem_sha256_e_requisitos():
    sha = "ab" * 32
    notas = release.notas_release("v1.1", sha)
    assert sha in notas
    assert "Windows 10/11 64 bits" in notas
    assert ".NET Framework 4.7.2" in notas
    assert "WebView2" in notas


def test_cli_tag_divergente_sai_com_1():
    r = subprocess.run(
        [sys.executable, str(RAIZ / "release.py"), "tag", "--ref-tag", "v9.9"],
        capture_output=True, text=True,
    )
    assert r.returncode == 1
    assert "9.9" in r.stderr and "1.1" in r.stderr
    ok = subprocess.run(
        [sys.executable, str(RAIZ / "release.py"), "tag"],
        capture_output=True, text=True,
    )
    assert ok.returncode == 0
    assert ok.stdout.strip() == "v1.1"


def test_cli_notas_calcula_o_sha256_do_zip(tmp_path):
    z = tmp_path / "x.zip"
    z.write_bytes(b"conteudo qualquer")
    r = subprocess.run(
        [sys.executable, str(RAIZ / "release.py"), "notas", "--tag", "v1.1",
         "--zip", str(z)],
        capture_output=True, text=True, check=True,
    )
    assert hashlib.sha256(b"conteudo qualquer").hexdigest() in r.stdout
