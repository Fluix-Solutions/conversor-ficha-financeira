"""
Converte um PDF pelo servidor local e salva o resultado com o `Api.salvar` do
`app_desktop.py` de APP_DIR, no Python-ALVO. O "Salvar como" nativo é trocado
por uma janela falsa que devolve DESTINO; imprime em JSON o que o diálogo
recebeu, o que o salvar devolveu, o que foi gravado e o que foi aberto.

    python _salvar_alvo.py <app_dir> <pdf> <formato> <destino> <origem>

DESTINO vazio = usuário cancelou o diálogo.
"""
import json
import os
import sys
import threading
import time
from pathlib import Path

app_dir, pdf, formato, destino, origem = sys.argv[1:6]
sys.path.insert(0, app_dir)

import app_desktop  # noqa: E402
import openpyxl  # noqa: E402
from webview.util import parse_file_type  # noqa: E402

server = app_desktop.server

# os.startfile só existe no Windows; aqui só registra o que seria aberto.
abertos: list[str] = []
os.startfile = lambda caminho: abertos.append(Path(caminho).name)


class JanelaFalsa:
    def __init__(self) -> None:
        self.pedido = None

    def create_file_dialog(self, dialog_type, **kw):
        # Filtro fora do padrão do pywebview estoura ValueError na janela real.
        for filtro in kw.get("file_types", ()):
            parse_file_type(filtro)
        self.pedido = {"save_filename": kw.get("save_filename"),
                       "file_types": list(kw.get("file_types", ()))}
        return destino or None


porta = app_desktop._porta_livre()
base = f"http://127.0.0.1:{porta}"
threading.Thread(
    target=lambda: server.app.run(host="127.0.0.1", port=porta, threaded=True,
                                  debug=False, use_reloader=False),
    daemon=True,
).start()
assert app_desktop._esperar(f"{base}/api/versao", 90), "servidor local não subiu"

cli = server.app.test_client()
with open(pdf, "rb") as f:
    r = cli.post("/api/converter", content_type="multipart/form-data",
                 data={"pdf": (f, "ficticia.pdf"), "origem": origem,
                       "formato": formato})
job = r.get_json()["job"]
while (d := cli.get(f"/api/job/{job}").get_json())["estado"] == "processando":
    time.sleep(0.2)
assert d["estado"] == "pronto", d

janela = JanelaFalsa()
api = app_desktop.Api(base)
api._window = janela
resultado = api.salvar(job, d["arquivo_nome"])
if resultado.get("caminho"):
    resultado["caminho"] = Path(resultado["caminho"]).name

pasta = Path(destino).parent if destino else None
arquivos = sorted(p.name for p in pasta.iterdir()) if pasta else []
conteudo = None
if resultado.get("ok"):
    gravado = pasta / resultado["caminho"]
    try:
        conteudo = {"json": json.loads(gravado.read_text(encoding="utf-8"))}
    except ValueError:
        ws = openpyxl.load_workbook(gravado)["Proventos"]
        conteudo = {"xlsx": [list(r) for r in ws.iter_rows(values_only=True)]}

# JSON só em ASCII: ver _converter_alvo.py.
print(json.dumps({"arquivo_nome": d["arquivo_nome"], "pedido": janela.pedido,
                  "resultado": resultado, "arquivos": arquivos,
                  "abertos": abertos, "conteudo": conteudo}))
