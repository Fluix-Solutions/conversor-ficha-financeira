"""Funções do build da pasta portátil que não dependem de Windows."""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

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
