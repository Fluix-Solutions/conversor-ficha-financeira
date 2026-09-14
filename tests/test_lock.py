"""O lock da pasta Windows: versões exatas, hashes e cobertura dos requirements."""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOCK = RAIZ / "requirements-windows.lock"

_PACOTE_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\;]+)")


def _norm(nome: str) -> str:
    return re.sub(r"[-_.]+", "-", nome).lower()


def _requisitos(arquivo: Path) -> set[str]:
    """Nomes pedidos num requirements (sem comentários nem includes)."""
    nomes = set()
    for ln in arquivo.read_text(encoding="utf-8").splitlines():
        ln = ln.split("#", 1)[0].strip()
        if not ln or ln.startswith("-"):
            continue
        nomes.add(_norm(re.split(r"[<>=!~\[;\s]", ln, 1)[0]))
    return nomes


def _pacotes_lock() -> dict[str, dict]:
    """{nome: {"versao": str, "hashes": [str]}} lido do lock."""
    pacotes: dict[str, dict] = {}
    atual = None
    for ln in LOCK.read_text(encoding="utf-8").splitlines():
        m = _PACOTE_RE.match(ln)
        if m:
            atual = _norm(m.group(1))
            pacotes[atual] = {"versao": m.group(2), "hashes": []}
            continue
        h = re.search(r"--hash=sha256:([0-9a-f]{64})", ln)
        if h and atual:
            pacotes[atual]["hashes"].append(h.group(1))
    return pacotes


def test_lock_cobre_todos_os_requirements():
    pedidos = (_requisitos(RAIZ / "requirements-desktop.txt")
               | _requisitos(RAIZ / "requirements-base.txt")
               | _requisitos(RAIZ / "requirements-build-windows.txt"))
    faltando = pedidos - set(_pacotes_lock())
    assert pedidos >= {"pdfplumber", "openpyxl", "pymupdf", "pywebview", "flask",
                       "rapidocr-onnxruntime"}
    assert faltando == set()


def test_todo_pacote_tem_versao_exata_e_hash():
    pacotes = _pacotes_lock()
    assert len(pacotes) >= 20
    sem_hash = [n for n, p in pacotes.items() if not p["hashes"]]
    assert sem_hash == []
    # Nenhuma linha de dependência fora do formato `nome==versão`.
    for ln in LOCK.read_text(encoding="utf-8").splitlines():
        if ln and not ln[0].isspace() and not ln.startswith("#"):
            assert _PACOTE_RE.match(ln), ln


def test_cabecalho_traz_o_comando_de_regeneracao():
    cabecalho = LOCK.read_text(encoding="utf-8").split("\n\n", 1)[0]
    cmd = next(ln for ln in cabecalho.splitlines() if "uv pip compile" in ln)
    assert "requirements-desktop.txt" in cmd
    assert "--python-platform x86_64-pc-windows-msvc" in cmd
    assert "--python-version 3.12" in cmd
    assert "--generate-hashes" in cmd
    assert "-o requirements-windows.lock" in cmd


def test_lock_e_de_windows():
    pacotes = _pacotes_lock()
    # pywebview no Windows usa pythonnet (WinForms/WebView2); no Mac usaria pyobjc.
    assert "pythonnet" in pacotes
    assert "pywebview" in pacotes
    assert not any(n.startswith("pyobjc") for n in pacotes)


def test_lock_traz_setuptools_para_compilar_o_que_so_tem_codigo_fonte():
    # proxy-tools (do pywebview) só existe como .tar.gz no PyPI.
    pacotes = _pacotes_lock()
    assert "proxy-tools" in pacotes
    assert pacotes["setuptools"]["hashes"]
