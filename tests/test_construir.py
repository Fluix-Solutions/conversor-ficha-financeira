"""Funções do build da pasta portátil que não dependem de Windows."""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import construir_portatil as cp  # noqa: E402


def test_conferir_sha256_aceita_o_hash_certo(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"python embutido")
    cp.conferir_sha256(f, hashlib.sha256(b"python embutido").hexdigest())


def test_conferir_sha256_rejeita_hash_diferente_citando_os_dois(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"adulterado")
    real = hashlib.sha256(b"adulterado").hexdigest()
    esperado = "0" * 64
    with pytest.raises(RuntimeError) as e:
        cp.conferir_sha256(f, esperado)
    assert real in str(e.value)
    assert esperado in str(e.value)


def test_sha256_do_python_312_9_embed_esta_fixado():
    assert cp.PY == "3.12.9"
    assert cp.SHA256_EMBED == (
        "615861fb801e8b04c847598db4e1e46e4b046295017caa37cb5486dde72b5865"
    )


def test_instala_do_lock_exigindo_hashes():
    cmd = cp.comando_instalar(Path("python/python.exe"))
    assert "--require-hashes" in cmd
    i = cmd.index("-r")
    assert Path(cmd[i + 1]) == RAIZ / "requirements-windows.lock"
    assert cmd[1:4] == ["-m", "pip", "install"]


def test_zip_tem_uma_pasta_raiz_com_o_lancador(tmp_path):
    alvo = tmp_path / cp.NOME
    (alvo / "python").mkdir(parents=True)
    (alvo / "Conversor.bat").write_text("@echo off")
    (alvo / "LEIA-ME.txt").write_text("leia")
    (alvo / "python" / "python.exe").write_bytes(b"MZ")
    destino = tmp_path / "saida.zip"

    cp.zipar(alvo, destino)

    nomes = zipfile.ZipFile(destino).namelist()
    assert all(n.startswith("Conversor de Ficha Financeira/") for n in nomes)
    assert "Conversor de Ficha Financeira/Conversor.bat" in nomes
    assert "Conversor de Ficha Financeira/LEIA-ME.txt" in nomes
    assert "Conversor de Ficha Financeira/python/python.exe" in nomes


def test_registro_lista_pacotes_com_versao(tmp_path, capsys):
    z = tmp_path / "x.zip"
    z.write_bytes(b"zip")
    cp.registrar(Path(sys.executable), z)
    saida = capsys.readouterr().out
    # pytest e pluggy existem em qualquer Python que rode esta suíte (Mac ou CI).
    from importlib.metadata import version
    assert f"pytest=={version('pytest')}" in saida.splitlines()
    assert f"pluggy=={version('pluggy')}" in saida.splitlines()


def test_registro_mostra_tamanho_e_sha256_do_zip(tmp_path, capsys):
    z = tmp_path / "x.zip"
    z.write_bytes(b"a" * 2_500_000)
    cp.registrar(Path(sys.executable), z)
    saida = capsys.readouterr().out
    assert hashlib.sha256(b"a" * 2_500_000).hexdigest() in saida
    assert "2.5 MB" in saida


def test_main_monta_instala_do_lock_e_registra_o_zip(tmp_path, monkeypatch, capsys):
    """`main` inteiro com rede e subprocessos simulados: o que ele EXECUTA."""
    embed = tmp_path / "embed.zip"
    with zipfile.ZipFile(embed, "w") as z:
        z.writestr("python.exe", "MZ")
        z.writestr("python312._pth", "python312.zip\n.\n\n#import site\n")
    monkeypatch.setattr(cp, "SHA256_EMBED",
                        hashlib.sha256(embed.read_bytes()).hexdigest())

    def baixar(url, destino):
        destino.write_bytes(embed.read_bytes() if url == cp.URL_EMBED else b"# get-pip")

    chamadas = []

    def run(cmd, *a, **k):
        chamadas.append([str(c) for c in cmd])
        return SimpleNamespace(returncode=0, stdout="pacote-falso==1.0\n")

    monkeypatch.setattr(cp, "_baixar", baixar)
    monkeypatch.setattr(cp.subprocess, "run", run)
    arq_zip = tmp_path / "saida.zip"
    monkeypatch.setattr(sys, "argv", ["construir_portatil.py",
                                      str(tmp_path / "saida"), "--zip", str(arq_zip)])

    assert cp.main() == 0

    # WIN-16: a instalação que o main executa é a do lock, com hash.
    instalar = [c for c in chamadas if "install" in c]
    assert len(instalar) == 1
    assert "--require-hashes" in instalar[0]
    assert Path(instalar[0][instalar[0].index("-r") + 1]) == cp.LOCK
    assert not any("requirements-desktop.txt" in arg for c in chamadas for arg in c)

    # WIN-02: a pasta tem o app, a interface e o lançador.
    alvo = tmp_path / "saida" / cp.NOME
    for item in ["converter.py", "server.py", "app_desktop.py", "web/index.html",
                 "Conversor.bat", "LEIA-ME.txt", "python/python.exe"]:
        assert (alvo / item).is_file(), item
    assert "..\n" in (alvo / "python" / "python312._pth").read_text()

    # WIN-12 + WIN-10: zip com a pasta raiz e registro no log.
    nomes = zipfile.ZipFile(arq_zip).namelist()
    assert "Conversor de Ficha Financeira/Conversor.bat" in nomes
    assert all(n.startswith("Conversor de Ficha Financeira/") for n in nomes)
    saida = capsys.readouterr().out
    assert f"sha256: {hashlib.sha256(arq_zip.read_bytes()).hexdigest()}" in saida
    assert "pacote-falso==1.0" in saida


def test_main_para_antes_de_extrair_se_o_hash_nao_bate(tmp_path, monkeypatch):
    """Zip do Python adulterado: o build falha e nada é extraído/instalado."""
    def falso(url, destino):
        with zipfile.ZipFile(destino, "w") as z:
            z.writestr("python.exe", "nao e o python da PSF")

    chamou_pip = []
    monkeypatch.setattr(cp, "_baixar", falso)
    monkeypatch.setattr(cp.subprocess, "run", lambda *a, **k: chamou_pip.append(a))
    monkeypatch.setattr(sys, "argv", ["construir_portatil.py", str(tmp_path)])

    with pytest.raises(RuntimeError):
        cp.main()
    assert not (tmp_path / cp.NOME / "python" / "python.exe").exists()
    assert chamou_pip == []
