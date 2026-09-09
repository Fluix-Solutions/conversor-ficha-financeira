"""
Conversor de Ficha Financeira — versão web (Flask).

Local:   python server.py           -> http://127.0.0.1:8000
Deploy:  gunicorn server:app        (Railway/Render usam o Procfile)

Privacidade: o PDF enviado é gravado num arquivo temporário só durante a
conversão e apagado logo em seguida (bloco finally). Nada é persistido e o
conteúdo dos arquivos nunca é registrado em log.

Acesso: se a variável de ambiente CONVERSOR_SENHA estiver definida, o site
passa a exigir login (HTTP Basic): usuário = CONVERSOR_USUARIO (padrão
"conversor"), senha = CONVERSOR_SENHA.
"""
from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_from_directory

from converter import ORIGENS, ConversaoError, converter

VERSAO = "1.0"
MAX_MB = 25

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

WEB = Path(__file__).resolve().parent / "web"

_USUARIO = os.environ.get("CONVERSOR_USUARIO", "conversor")
_SENHA = os.environ.get("CONVERSOR_SENHA")  # sem senha => site aberto


def _autorizado() -> bool:
    if not _SENHA:
        return True
    a = request.authorization
    return bool(a) and a.type == "basic" and a.username == _USUARIO and a.password == _SENHA


@app.before_request
def _porteiro():
    if _autorizado():
        return None
    return Response(
        "Login necessário.", 401, {"WWW-Authenticate": 'Basic realm="Conversor"'}
    )


@app.after_request
def _seguranca(resp: Response):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return resp


# ---------- páginas / assets ----------
@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/<path:nome>")
def asset(nome: str):
    return send_from_directory(WEB, nome)


# ---------- API ----------
@app.get("/api/origens")
def api_origens():
    return jsonify([{"chave": k, "rotulo": v} for k, v in ORIGENS.items()])


@app.get("/api/versao")
def api_versao():
    return jsonify({"versao": VERSAO})


@app.post("/api/converter")
def api_converter():
    arq = request.files.get("pdf")
    origem = (request.form.get("origem") or "").strip()

    if arq is None or not arq.filename:
        return jsonify({"erro": "Nenhum arquivo enviado."}), 400
    if not arq.filename.lower().endswith(".pdf"):
        return jsonify({"erro": "O arquivo precisa ser um PDF."}), 400
    if origem not in ORIGENS:
        return jsonify({"erro": "Escolha a origem da ficha."}), 400

    fd_in, cin = tempfile.mkstemp(suffix=".pdf")
    fd_out, cout = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd_in)
    os.close(fd_out)
    p_in, p_out = Path(cin), Path(cout)
    try:
        arq.save(p_in)
        try:
            resumo = converter(p_in, p_out, origem)
        except ConversaoError as e:
            return jsonify({"erro": str(e), "tipo": "aviso"}), 422
        except Exception:  # noqa: BLE001
            return jsonify({"erro": "Erro inesperado ao converter.", "tipo": "erro"}), 500

        dados = p_out.read_bytes()
        nome = Path(arq.filename).stem + ".xlsx"
        resumo.pop("arquivo", None)  # caminho temporário do servidor, não interessa ao cliente
        return jsonify(
            {
                "ok": True,
                "resumo": resumo,
                "arquivo_nome": nome,
                "arquivo_b64": base64.b64encode(dados).decode("ascii"),
            }
        )
    finally:
        for p in (p_in, p_out):
            try:
                p.unlink()
            except OSError:
                pass


@app.errorhandler(413)
def _grande(_e):
    return jsonify({"erro": f"Arquivo maior que {MAX_MB} MB.", "tipo": "aviso"}), 413


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", "8000"))
    app.run(host="127.0.0.1", port=porta, debug=bool(os.environ.get("DEBUG")))
