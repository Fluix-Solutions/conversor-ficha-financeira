"""
Conversor de Ficha Financeira — app de desktop com a MESMA tela da versão web.

Rodar:  python app_desktop.py     (ou duplo clique em Conversor.bat)

Como funciona: em vez de duplicar a interface, este app sobe o próprio
`server.py` numa porta local e abre uma janela apontando para ele. Ou seja,
`server.py` e a pasta `web/` são usados **sem nenhuma alteração** — a fila de
conversão, a barra de progresso e as mensagens são exatamente as mesmas.

Por que usar o desktop em vez do site: o OCR de ficha escaneada roda na sua
máquina. Medido: ~72 s aqui contra ~14 min na instância do Railway (3 vCPU).

Diferença em relação ao site, e a razão de este arquivo existir:
o `web/app.js` baixa o .xlsx por um link do navegador, o que não funciona bem
numa janela pywebview. Aqui a função `baixar()` é substituída depois que a
página carrega (sem tocar no arquivo), passando a abrir um "Salvar como"
nativo. Nada em `web/` precisa saber que está rodando no desktop.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import webview

# Um app local é de uso pessoal: nunca pedir login na própria máquina.
# Precisa vir ANTES de importar o server, que lê a senha no import.
os.environ.pop("CONVERSOR_SENHA", None)

import server  # noqa: E402  (depende do ajuste de ambiente acima)

TITULO = "Conversor de Ficha Financeira"

# Troca o download do navegador por um "Salvar como" nativo. `baixar` é uma
# função global do web/app.js, então dá para substituí-la por fora.
SHIM_JS = """
(function () {
  if (!window.pywebview || window.__shimDesktop) return;
  window.__shimDesktop = true;
  window.baixar = function (job, nome) {
    window.pywebview.api.salvar(job, nome).then(function (r) {
      if (r && r.erro) {
        var box = document.getElementById('result');
        if (box) { box.className = 'result err'; box.textContent = r.erro; }
      }
    });
  };
})();
"""


def _porta_livre() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]
    s.close()
    return porta


def _esperar(url: str, segundos: float = 20.0) -> bool:
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            urllib.request.urlopen(url, timeout=1).read()
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.15)
    return False


class Api:
    """Ponte com a janela — só o que o navegador não consegue fazer sozinho."""

    def __init__(self, base: str) -> None:
        # Underscore de propósito: o pywebview inspeciona os atributos
        # PÚBLICOS do js_api para expor à página, e ao encontrar a janela
        # entra numa recursão infinita dentro do objeto nativo dela
        # (window.native.AccessibilityObject.Bounds.Empty.Empty...).
        self._base = base
        self._window = None

    def salvar(self, job: str, nome: str):
        destino = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=nome or "ficha.xlsx",
            file_types=("Planilha Excel (*.xlsx)",),
        )
        if not destino:
            return {"cancelado": True}
        destino = destino if isinstance(destino, str) else destino[0]
        if not destino.lower().endswith(".xlsx"):
            destino += ".xlsx"
        try:
            with urllib.request.urlopen(
                f"{self._base}/api/job/{job}/arquivo", timeout=60
            ) as r:
                dados = r.read()
            Path(destino).write_bytes(dados)
        except urllib.error.HTTPError:
            return {"erro": "A conversão expirou. Converta o PDF de novo."}
        except Exception as e:  # noqa: BLE001
            return {"erro": f"Não consegui salvar o arquivo: {e}"}
        try:
            os.startfile(destino)  # Windows: abre a planilha pronta
        except Exception:  # noqa: BLE001
            pass
        return {"ok": True, "caminho": destino}


def main() -> int:
    porta = _porta_livre()
    base = f"http://127.0.0.1:{porta}"

    threading.Thread(
        target=lambda: server.app.run(
            host="127.0.0.1", port=porta, threaded=True,
            debug=False, use_reloader=False,
        ),
        daemon=True,
    ).start()

    if not _esperar(f"{base}/api/versao"):
        print("Não consegui iniciar o servidor local.", file=sys.stderr)
        return 1

    api = Api(base)
    win = webview.create_window(
        TITULO, base, js_api=api,
        width=1000, height=760, min_size=(820, 600),
    )
    api._window = win

    def ao_carregar(*_args) -> None:
        """Injeta o shim. Recebe *args porque algumas versões do pywebview
        passam a janela ao handler, e NÃO retorna nada: devolver o resultado
        do evaluate_js faz o pywebview tentar serializar o objeto da janela e
        despejar um erro gigante no console."""
        try:
            win.evaluate_js(SHIM_JS)
        except Exception:  # noqa: BLE001 - shim nunca deve derrubar a janela
            pass

    # `loaded` dispara a cada navegação; o shim é idempotente.
    win.events.loaded += ao_carregar
    webview.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
