"""
Conversor de Ficha Financeira — janela com visual do Valorizei (pywebview).

Rodar:   python app_web.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import webview

from converter import ORIGENS, ConversaoError, converter

VERSAO = "1.0"


def _base() -> Path:
    """Pasta dos recursos — funciona rodando o .py e o .exe do PyInstaller."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


class Api:
    def __init__(self) -> None:
        self._window = None

    # --- dados p/ a interface ---
    def origens(self):
        return [{"chave": k, "rotulo": v} for k, v in ORIGENS.items()]

    def versao(self):
        return VERSAO

    # --- ações ---
    def escolher_pdf(self):
        r = self._window.create_file_dialog(
            webview.OPEN_DIALOG, file_types=("Arquivo PDF (*.pdf)",)
        )
        if not r:
            return None
        return r[0] if isinstance(r, (list, tuple)) else r

    def abrir(self, caminho: str):
        try:
            os.startfile(caminho)  # Windows
        except Exception:
            pass
        return True

    def converter(self, pdf_path: str, origem: str):
        pdf = Path(pdf_path)
        destino = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            directory=str(pdf.parent),
            save_filename=pdf.with_suffix(".xlsx").name,
            file_types=("Planilha Excel (*.xlsx)",),
        )
        if not destino:
            return {"erro": "Conversão cancelada.", "tipo": "aviso"}
        destino = destino if isinstance(destino, str) else destino[0]
        if not destino.lower().endswith(".xlsx"):
            destino += ".xlsx"

        try:
            return converter(pdf, Path(destino), origem)
        except ConversaoError as e:
            return {"erro": str(e), "tipo": "aviso"}
        except Exception as e:  # noqa: BLE001
            return {"erro": f"Erro inesperado: {e}", "tipo": "erro"}


def _selftest(tipo: str, pdf: str) -> int:
    saida = Path(tempfile.gettempdir()) / "selftest_web.xlsx"
    try:
        r = converter(Path(pdf), saida, tipo)
    except Exception as e:  # noqa: BLE001
        print("FALHOU:", e)
        return 1
    print("OK", r["origem"], r["anos"], r["rubricas"])
    return 0


def main() -> int:
    if len(sys.argv) >= 4 and sys.argv[1] == "--selftest":
        return _selftest(sys.argv[2], sys.argv[3])

    api = Api()
    win = webview.create_window(
        "Conversor de Ficha Financeira",
        str(_base() / "ui" / "index.html"),
        js_api=api,
        width=980,
        height=720,
        min_size=(820, 600),
    )
    api._window = win
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
