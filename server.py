"""
Conversor de Ficha Financeira — versão web (Flask).

Local:   python server.py           -> http://127.0.0.1:8000
Deploy:  gunicorn server:app        (Railway/Render usam o Procfile)

Conversão em FILA: converter uma ficha escaneada leva dezenas de segundos
(OCR), tempo demais para uma requisição HTTP ficar aberta — proxy, navegador
ou uma queda de rede derrubariam o trabalho inteiro no meio. Por isso o POST
só enfileira e devolve um `job`; o cliente acompanha por `GET /api/job/<id>`
e baixa em `GET /api/job/<id>/arquivo`.

Como os jobs vivem na memória do processo, o Procfile usa **--workers 1**
(com --threads): com mais de um worker, a consulta cairia num processo que
não conhece o job.

Privacidade: o PDF enviado é gravado num arquivo temporário só durante a
conversão e apagado logo em seguida. O .xlsx gerado fica em um temporário até
o download e é apagado pela faxina automática em no máximo JOB_TTL. Nada é
persistido e o conteúdo dos arquivos nunca é registrado em log.

Acesso: se a variável de ambiente CONVERSOR_SENHA estiver definida, o site
passa a exigir login (HTTP Basic): usuário = CONVERSOR_USUARIO (padrão
"conversor"), senha = CONVERSOR_SENHA.
"""
from __future__ import annotations

import os
import tempfile
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file, send_from_directory

from converter import ORIGENS, ConversaoError, converter, ocr_status

VERSAO = "1.1"
MAX_MB = 25
JOB_TTL = 20 * 60      # tempo máximo que um resultado fica disponível (s)
JOB_FAXINA = 2 * 60    # intervalo da faxina (s)

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_MB * 1024 * 1024

WEB = Path(__file__).resolve().parent / "web"

_USUARIO = os.environ.get("CONVERSOR_USUARIO", "conversor")
_SENHA = os.environ.get("CONVERSOR_SENHA")  # sem senha => site aberto

# ---------- fila de conversões ----------
_JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()


def _novo_job() -> str:
    jid = uuid.uuid4().hex
    with _LOCK:
        _JOBS[jid] = {
            "estado": "processando",
            "etapa": "Na fila",
            "atual": 0,
            "total": 0,
            "criado": time.time(),
            "saida": None,
            "nome": None,
            "resumo": None,
            "erro": None,
            "tipo": None,
        }
    return jid


def _set(jid: str, **campos) -> None:
    with _LOCK:
        job = _JOBS.get(jid)
        if job is not None:
            job.update(campos)


def _apagar(*caminhos) -> None:
    for c in caminhos:
        if not c:
            continue
        try:
            Path(c).unlink()
        except OSError:
            pass


def _rodar(jid: str, entrada: Path, saida: Path, origem: str, nome: str) -> None:
    """Converte fora do ciclo da requisição e guarda o resultado no job."""
    def progresso(etapa: str, atual: int = 0, total: int = 0) -> None:
        _set(jid, etapa=etapa, atual=atual, total=total)

    try:
        resumo = converter(entrada, saida, origem, progresso=progresso)
        resumo.pop("arquivo", None)  # caminho no servidor, não interessa ao cliente
        _set(jid, estado="pronto", etapa="Pronto", saida=str(saida),
             nome=nome, resumo=resumo)
    except ConversaoError as e:
        _apagar(saida)
        _set(jid, estado="erro", erro=str(e), tipo="aviso")
    except Exception:  # noqa: BLE001
        _apagar(saida)
        _set(jid, estado="erro", erro="Erro inesperado ao converter.", tipo="erro")
    finally:
        _apagar(entrada)  # o PDF enviado não fica no servidor


def _faxina() -> None:
    """Descarta jobs vencidos (e os .xlsx deles) de tempos em tempos."""
    while True:
        time.sleep(JOB_FAXINA)
        limite = time.time() - JOB_TTL
        with _LOCK:
            velhos = [j for j, d in _JOBS.items() if d["criado"] < limite]
            saidas = [_JOBS[j].get("saida") for j in velhos]
            for j in velhos:
                _JOBS.pop(j, None)
        _apagar(*saidas)


threading.Thread(target=_faxina, daemon=True).start()


def _aquecer_ocr() -> None:
    """Carrega o modelo de OCR no arranque, fora do caminho das requisicoes.

    Sem isso a primeira chamada paga o carregamento (~2,5 s) — e como o front
    consulta /api/versao ao abrir a pagina, quem pagava era o usuario."""
    try:
        ocr_status()
    except Exception:  # noqa: BLE001 - aquecer nunca deve derrubar o servidor
        pass


threading.Thread(target=_aquecer_ocr, daemon=True).start()


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
    # `ocr` diz se o servidor consegue ler ficha escaneada. Sem ele o
    # deploy parece saudável e só quebra quando alguém manda um scan.
    # O modelo já foi aquecido no arranque, então aqui é só leitura.
    return jsonify({"versao": VERSAO, **ocr_status()})


@app.post("/api/converter")
def api_converter():
    """Enfileira a conversão e devolve o id do job (não converte aqui)."""
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
    except Exception:  # noqa: BLE001
        _apagar(p_in, p_out)
        return jsonify({"erro": "Não consegui ler o arquivo enviado."}), 400

    jid = _novo_job()
    nome = Path(arq.filename).stem + ".xlsx"
    threading.Thread(
        target=_rodar, args=(jid, p_in, p_out, origem, nome), daemon=True
    ).start()
    return jsonify({"job": jid}), 202


@app.get("/api/job/<jid>")
def api_job(jid: str):
    with _LOCK:
        job = _JOBS.get(jid)
        d = dict(job) if job else None
    if d is None:
        return jsonify({"erro": "Conversão não encontrada (ou já expirou)."}), 404

    if d["estado"] == "erro":
        return jsonify({"estado": "erro", "erro": d["erro"], "tipo": d["tipo"]})
    if d["estado"] == "pronto":
        return jsonify({
            "estado": "pronto",
            "resumo": d["resumo"],
            "arquivo_nome": d["nome"],
        })
    return jsonify({
        "estado": "processando",
        "etapa": d["etapa"],
        "atual": d["atual"],
        "total": d["total"],
    })


@app.get("/api/job/<jid>/arquivo")
def api_job_arquivo(jid: str):
    with _LOCK:
        job = _JOBS.get(jid)
        saida = job.get("saida") if job else None
        nome = job.get("nome") if job else None
    if not saida or not Path(saida).exists():
        return jsonify({"erro": "Arquivo não disponível (ou já expirou)."}), 404
    return send_file(
        saida,
        as_attachment=True,
        download_name=nome,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.errorhandler(413)
def _grande(_e):
    return jsonify({"erro": f"Arquivo maior que {MAX_MB} MB.", "tipo": "aviso"}), 413


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", "8000"))
    app.run(host="127.0.0.1", port=porta, debug=bool(os.environ.get("DEBUG")),
            threaded=True)
