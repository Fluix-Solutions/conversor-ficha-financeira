"""
Conversor de Ficha Financeira (PDF) -> Excel (.xlsx)

Uso:
    python converter.py "FF 1.pdf"
    python converter.py "FF 1.pdf" -o saida.xlsx

Lê o PDF "Relação Ficha Financeira" (modelo Prefeitura da Serra) e gera uma
planilha no formato "largo": uma linha por Ano+Mês, uma coluna por rubrica
(só o nome da verba, sem o código). Só a seção PROVENTOS é exportada.

Reconhece dois layouts automaticamente:
  A) Sistema FPFF902 (recente): linhas "001 Salário Base".
  B) Sistema antigo: linhas "Evento: 001 Salário Base" + linha "Ref.".
     Nesse layout a fonte do PDF não tem mapa de caracteres; o texto é
     decodificado por deslocamento fixo (ver `decode_cid`).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import pdfplumber
import openpyxl

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

# Nomes canônicos das rubricas (o PDF perde acentos e usa "13o.").
# Chave = código; valor = nome limpo como o sistema espera.
RUBRICAS_CANONICAS = {
    "001": "Salário Base",
    "010": "Saldo de Salário",
    "012": "Férias",
    "025": "Gratificação Assiduidade",
    "113": "Ext. Carga Horária Prof",
    "115": "Exten.C.Horaria M.Anter.",
    "130": "Triênio / Quinquênio",
    "183": "1/3 Férias",
    "200": "Adiantamento de 13º",
    "212": "13º Salário",
    "222": "13º Salário Proporcional",
    "234": "Abono",
    "498": "Líquido Mês Anterior",
    "613": "Extensão C.Horária 13º",
    "937": "13º Salário",
}

# Correções de acento para nomes de rubrica que não estão na tabela acima
# (o layout B perde todos os acentos).
_ACENTOS = {
    "Sal?rio": "Salário", "F?rias": "Férias", "Fun??o": "Função",
    "Gratifica??o": "Gratificação", "Contribui??o": "Contribuição",
    "Trienio": "Triênio", "Quinquenio": "Quinquênio", "M?dicas": "Médicas",
    "Empr?stimo": "Empréstimo", "P?blico": "Público",
    "Assiduidade": "Assiduidade", "N?o": "Não", "Servi?o": "Serviço",
    "Fam?lia": "Família", "Bi?nio": "Biênio", "Progress?o": "Progressão",
    "Prog.L": "Prog.L", "Devolu??o": "Devolução", "Devolu?ao": "Devolução",
    "Aux?lio": "Auxílio", "Auxilio": "Auxílio", "Perman?ncia": "Permanência",
    "Perman.m?s": "Perman.mês", "Rescis?o": "Rescisão", "Alimenta??o": "Alimentação",
    "Diferen?a": "Diferença", "M?s": "Mês", "Anterior": "Anterior",
    "Ass?d": "Assid", "Dire??o": "Direção", "Licen?a": "Licença",
    "M?dica": "Médica", "M?dico": "Médico", "Hor?ria": "Horária",
    "Hor?rio": "Horário", "13o.": "13º",
}
_13O_RE = re.compile(r"13\?(?=\s|$|\d)")

CID_RE = re.compile(r"\(cid:(\d+)\)")
VALOR_RE = re.compile(r"^-?\d{1,3}(?:\.\d{3})*,\d{2}$")
NUM_INLINE_RE = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}")
CODIGO_RE = re.compile(r"^\d{3}$")
EVENTO_RE = re.compile(r"^Evento:\s*(\d{3,4})\s+(.*)$")
PERIODO_RE = re.compile(r"(\d{2})/(\d{4})\s+a\s+(\d{2})/(\d{4})")
MATRICULA_RE = re.compile(r"Servidor:\s*(\d+)")


def _centros_meses(linhas_w) -> dict[int, float]:
    """Acha a linha de cabeçalho (a que casa com mais nomes de mês) e devolve
    {índice do mês: x central}. A altura da linha varia entre versões do
    relatório, e algumas fichas cobrem só parte do ano — por isso não exigimos
    y fixo nem os 12 meses."""
    melhor: dict[int, float] = {}
    for grupo in linhas_w:
        c: dict[int, float] = {}
        for w in grupo:
            nome = limpar_nome(w["text"])
            for idx, mes in enumerate(MESES):
                if nome[:3] == mes[:3] or (mes == "Março" and nome.startswith("Mar")):
                    c[idx] = (w["x0"] + w["x1"]) / 2
        if len(c) > len(melhor):
            melhor = c
    return melhor


def _cid_char(m: "re.Match") -> str:
    """Alguns PDFs não têm mapa de fonte: o texto sai como '(cid:N)'.
    Neste modelo, caractere = chr(N + 29) para toda a faixa ASCII."""
    n = int(m.group(1)) + 29
    return chr(n) if 32 <= n < 127 else "?"


def decode_cid(txt: str) -> str:
    return CID_RE.sub(_cid_char, txt) if "(cid:" in txt else txt


def parse_valor(txt: str) -> float:
    return float(txt.replace(".", "").replace(",", "."))


def limpar_nome(txt: str) -> str:
    txt = txt.replace("�", "?").strip()
    txt = _13O_RE.sub("13º", txt)
    for errado, certo in _ACENTOS.items():
        txt = txt.replace(errado, certo)
    return txt


def _coluna(codigo: str, nome: str) -> str:
    """Cabeçalho da coluna da rubrica: só o nome da verba, sem o código.
    Se o nome faltar, usa o código como último recurso."""
    return (nome or "").strip() or str(codigo)


def agrupar_linhas(itens, key_top, y_tol: float = 2.5):
    """Agrupa itens (words ou chars) em linhas por coordenada vertical."""
    linhas: list[list] = []
    for it in sorted(itens, key=lambda it: (round(key_top(it) / y_tol), it["x0"])):
        if linhas and abs(key_top(linhas[-1][0]) - key_top(it)) <= y_tol:
            linhas[-1].append(it)
        else:
            linhas.append([it])
    return linhas


# ----------------------------------------------------------------------------
# Layout A - Sistema FPFF902 (recente)
# ----------------------------------------------------------------------------
def _pagina_formato_a(page, avisos: list[str]):
    words = page.extract_words(use_text_flow=False)
    if not words:
        return None
    for w in words:
        w["text"] = decode_cid(w["text"])

    texto = decode_cid(page.extract_text() or "")
    m = PERIODO_RE.search(texto)
    if not m:
        return None
    ano = int(m.group(2))
    mm = MATRICULA_RE.search(texto)
    matricula = mm.group(1) if mm else None

    linhas = agrupar_linhas(words, lambda w: w["top"])
    centros = _centros_meses(linhas)
    if len(centros) < 2:
        return None  # página de continuação (sem a grade de meses)
    x_max = max(centros.values()) + 22

    y_ini = y_fim = None
    for grupo in linhas:
        plano = "".join(w["text"] for w in sorted(grupo, key=lambda w: w["x0"]))
        y = grupo[0]["top"]
        if plano == "Proventos" and min(w["x0"] for w in grupo) < 60:
            y_ini = y
        elif plano.startswith("TOTAL:Proventos") or plano.startswith("TOTAL:Vantagens"):
            y_fim = y
    if y_ini is None or y_fim is None:
        return None

    corpo = [w for w in words if y_ini < w["top"] < y_fim]
    linhas = agrupar_linhas(corpo, lambda w: w["top"])

    dados = {mes: {} for mes in MESES}
    ordem: list[str] = []
    codigo_atual = nome_atual = None
    for linha in linhas:
        linha = sorted(linha, key=lambda w: w["x0"])
        textos = [w["text"] for w in linha]
        if textos and CODIGO_RE.match(textos[0]):
            codigo_atual = textos[0]
            bruto = limpar_nome(" ".join(textos[1:]))
            nome_atual = RUBRICAS_CANONICAS.get(codigo_atual, bruto)
            if "?" in nome_atual:
                avisos.append(f"Nome incompleto (acento): {codigo_atual} '{nome_atual}'.")
            coluna = _coluna(codigo_atual, nome_atual)
            if coluna not in ordem:
                ordem.append(coluna)
            continue
        if codigo_atual is None:
            continue
        coluna = _coluna(codigo_atual, nome_atual)
        for w in linha:
            if not VALOR_RE.match(w["text"]):
                continue
            xc = (w["x0"] + w["x1"]) / 2
            if xc > x_max:
                continue
            idx = min(centros, key=lambda i: abs(centros[i] - xc))
            if abs(centros[idx] - xc) > 20:
                continue
            dados[MESES[idx]][coluna] = dados[MESES[idx]].get(coluna, 0.0) + parse_valor(w["text"])

    return {"ano": ano, "matricula": matricula, "dados": dados, "ordem": ordem}


# ----------------------------------------------------------------------------
# Layout B - Sistema antigo ("Evento:" + "Ref.")
# ----------------------------------------------------------------------------
def _tokens_numericos(chars):
    """Reconstrói os números de uma linha a partir dos caracteres, com x central.

    Alguns relatórios inserem espaços dentro do número (ex.: "1.50 9 , 8 9").
    Por isso ignoramos os espaços e cortamos um número do outro pela distância
    horizontal: dígitos do mesmo número ficam colados; entre números há um vão.
    """
    seq = sorted(
        (
            c
            for c in chars
            if (decode_cid(c["text"]) if "(cid:" in c["text"] else c["text"])
            in "0123456789.,-"
        ),
        key=lambda c: c["x0"],
    )
    tokens: list[tuple[str, float]] = []
    buf, xs, fim_ant = "", [], None
    for c in seq:
        ch = decode_cid(c["text"]) if "(cid:" in c["text"] else c["text"]
        if fim_ant is not None and c["x0"] - fim_ant > 4.0:
            if VALOR_RE.match(buf):
                tokens.append((buf, sum(xs) / len(xs)))
            buf, xs = "", []
        buf += ch
        xs.append((c["x0"] + c["x1"]) / 2)
        fim_ant = c["x1"]
    if VALOR_RE.match(buf):
        tokens.append((buf, sum(xs) / len(xs)))
    return tokens


def _converter_formato_b(pdf, avisos: list[str]):
    centros: dict[int, float] | None = None
    blocos: dict[tuple[int, int], dict] = {}
    ordem: list[str] = []
    ocorrencias: dict[int, int] = {}
    bloco_matricula: dict[tuple[int, int], str] = {}
    matricula_atual: str | None = None

    secao = None                # 'PROV', 'DESC', 'OUTROS' ou None
    bloco_key = None            # (ano, ocorrencia) atual
    aguardando_bloco = False    # vimos "Proventos", falta o 1o Evento

    for page in pdf.pages:
        words = page.extract_words(use_text_flow=False)
        for w in words:
            w["text"] = decode_cid(w["text"])
        texto = decode_cid(page.extract_text() or "")
        m = PERIODO_RE.search(texto)
        if not m:
            continue
        ano = int(m.group(2))
        mm = MATRICULA_RE.search(texto)
        if mm:
            matricula_atual = mm.group(1)

        chars = page.chars
        linhas_w = agrupar_linhas(words, lambda w: w["top"])

        # Centros das colunas de meses. A linha de cabeçalho só aparece na 1a
        # página de cada ano e a altura muda entre versões do relatório, então
        # procuramos a linha que casa com o maior número de nomes de mês.
        melhor: dict[int, float] = {}
        for grupo in linhas_w:
            c: dict[int, float] = {}
            for w in grupo:
                nome = limpar_nome(w["text"])
                for idx, mes in enumerate(MESES):
                    if nome[:3] == mes[:3] or (mes == "Março" and nome.startswith("Mar")):
                        c[idx] = (w["x0"] + w["x1"]) / 2
            if len(c) > len(melhor):
                melhor = c
        if len(melhor) == 12:
            centros = melhor
        if centros is None:
            continue
        x_min = min(centros.values()) - 28
        x_max = max(centros.values()) + 28
        linhas_c = agrupar_linhas(chars, lambda c: c["top"])
        # índice rápido: para cada linha de palavras, os chars da mesma faixa y
        chars_por_top = {}
        for grupo in linhas_c:
            chars_por_top[round(grupo[0]["top"])] = grupo

        for i, linha in enumerate(linhas_w):
            linha = sorted(linha, key=lambda w: w["x0"])
            txt = " ".join(w["text"] for w in linha).strip()
            plano = txt.replace(" ", "")

            if plano == "Proventos":
                secao = "PROV"
                aguardando_bloco = True
                continue
            if plano.startswith("TOTAL:Proventos") or plano.startswith("TOTAL:Vantagens"):
                secao = None
                aguardando_bloco = False
                continue
            if plano == "Descontos":
                secao = "DESC"
                continue
            if plano == "Outros":
                secao = "OUTROS"
                continue
            if plano.startswith("TOTAL:Descontos") or plano.startswith("TOTAL:Outros"):
                secao = None
                continue

            if secao != "PROV":
                continue

            me = EVENTO_RE.match(txt)
            if not me:
                continue
            codigo, bruto = me.group(1), limpar_nome(me.group(2))
            nome = RUBRICAS_CANONICAS.get(codigo, bruto)
            if "?" in nome:
                avisos.append(f"Nome incompleto (acento): {codigo} '{nome}'.")

            if aguardando_bloco:
                ocorrencias[ano] = ocorrencias.get(ano, 0) + 1
                bloco_key = (ano, ocorrencias[ano])
                blocos.setdefault(bloco_key, {mes: {} for mes in MESES})
                bloco_matricula[bloco_key] = matricula_atual or f"Contrato {ocorrencias[ano]}"
                aguardando_bloco = False
            if bloco_key is None:
                continue

            coluna = _coluna(codigo, nome)
            if coluna not in ordem:
                ordem.append(coluna)

            # A linha "Valor" é a próxima linha de palavras abaixo do Evento.
            if i + 1 >= len(linhas_w):
                continue
            top_valor = round(min(w["top"] for w in linhas_w[i + 1]))
            grupo_chars = None
            for dt in (0, 1, -1, 2, -2):
                if top_valor + dt in chars_por_top:
                    grupo_chars = chars_por_top[top_valor + dt]
                    break
            if not grupo_chars:
                continue

            dados = blocos[bloco_key]
            for valor, xc in _tokens_numericos(grupo_chars):
                if xc < x_min or xc > x_max:
                    continue
                idx = min(centros, key=lambda k: abs(centros[k] - xc))
                if abs(centros[idx] - xc) > 30:
                    continue
                dados[MESES[idx]][coluna] = dados[MESES[idx]].get(coluna, 0.0) + parse_valor(valor)

    resultado = []
    for (ano, occ) in sorted(blocos):
        resultado.append(
            {
                "ano": ano,
                "rotulo": bloco_matricula.get((ano, occ), f"Contrato {occ}"),
                "dados": blocos[(ano, occ)],
                "ordem": ordem,
            }
        )
    return resultado


# ----------------------------------------------------------------------------
# Layout C - SIARHES / PRODEST (Governo do Estado do ES)
# A fonte é Type3 (glifos desenhados). Cada PÁGINA usa uma cifra de
# substituição própria para as LETRAS; os dígitos também mudam por página.
# Estratégia: derivar a cifra de letras da linha de cabeçalho dos meses e a
# cifra de dígitos resolvendo "soma dos 12 meses = coluna Total" de cada linha.
# ----------------------------------------------------------------------------
MESES_CABECALHO = MESES + ["Total"]
# O relatório do Estado às vezes traz o cabeçalho dos meses abreviado.
MESES_ABREV = [m[:3] for m in MESES] + ["Total"]

# Separador interno entre parte inteira e centavos nas strings cifradas
# (_norm_num). Não pode ser "." porque em alguns relatórios o "." é um dos
# glifos usados para cifrar um dígito. Usamos NUL, que nunca aparece no texto.
_SEP_INT = "\x00"

# Nomes de rubrica conhecidos deste sistema (código -> nome).
# Nas fichas recentes (meses abreviados) a fonte da descrição não tem mapa de
# caracteres, então o nome NÃO é lido do PDF - vem daqui pelo código. Se
# aparecer "Rubrica <código>" numa conversão, é um código novo: conferir o
# nome na ficha impressa e acrescentar abaixo.
RUBRICAS_C = {
    # Fichas antigas (modelo "Estado Seguido", meses por extenso)
    "6": "Abono",
    "7": "Diferença de Abono",
    "1101": "Venc. Pessoal Fixo",
    "1138": "Horas Trabalhadas",
    "1159": "Féria Remunerada DT",
    "1190": "Abono Férias",
    "1199": "13. Vencimento",
    "1201": "Dif. Venc. Pess. Fixo",
    "1238": "Dif. Hora Trabalhada",
    "3000": "IPAJM / Benef. Família",
    "4311": "Rep. Abono",
    "9001": "IRRF",
    "9111": "Devol. IRRF Nov",
    # Fichas recentes (modelo FICHA 01/02/03, meses abreviados) - PROVENTOS
    "20": "Férias Remun. Carga Horária Extensão",
    "21": "Carga Horária Especial",
    "24": "13º Salário",
    "26": "13º Salário - DT",
    "28": "Abono Férias",
    "119": "Auxílio Alimentação Líquido",
    "192": "Subsídio",
    "231": "13º Salário sem IPAJM",
    "248": "Adiantamento Líquido Abono Férias",
    "339": "Bônus Desempenho SEDU",
    "348": "Bônus Desempenho SEDU (cód. 348)",
    "494": "Desconto INSS",
    "1010": "Auxílio Alimentação 13º Salário",
    "1025": "Adiant. 13º Salário Líquido",
    "1040": "Adiant. Auxílio Alim. 13º Salário Líquido",
    "1110": "Bônus FUNDEB",
    # Modelo "FICHA FINANCEIRA" cifrado, códigos de 3 dígitos (ex.: FICHA TESTE 2)
    "101": "Salário Nominal",
    "107": "13º Salário",
    "114": "Salário Mês Anterior",
    "127": "1/3 Férias",
    "128": "Dif. 1/3 Férias",
    "142": "A.T.S. Estatutário",
    "143": "Ajuda Custo Magistério Internet",
    "146": "Adic. L. Especial 30%",
    "148": "Dif. Mín. Profissional",
    "150": "Abono",
    "161": "Incorp. Gratif. Ref. 12",
    "185": "Indenização Férias",
    "190": "Devolução Caixa",
    "201": "13º Salário DT Rescisão",
    "317": "Abono Férias DT Indenização",
    "327": "Ajuda de Custo Magistério",
    "1011": "Aux. Alimentação 13º Salário Rescisão",
}

_CPF_RE = re.compile(
    r"(?P<z>.)(?P=z){2}(?P<s>(?!(?P=z)).)(?P=z){3}(?P=s)(?P=z){3}(?P<d>(?!(?P=z)).)(?P=z){2}"
)


def _glifos_numericos(linhas: list[str], zero: str):
    """Descobre, na página, os glifos de: prefixo, ponto decimal e separador de milhar.
    Usa os muitos tokens '0,00' (prefixo + zero + decimal + zero + zero)."""
    from collections import Counter
    pref, dec = Counter(), Counter()
    for ln in linhas:
        for t in ln.split():
            if len(t) == 5 and t[1] == zero and t[3] == zero and t[4] == zero and t[0] != zero:
                pref[t[0]] += 1
                dec[t[2]] += 1
    prefixo = pref.most_common(1)[0][0] if pref else None
    decimal = dec.most_common(1)[0][0] if dec else None
    return prefixo, decimal


def _valor_re(prefixo: str, decimal: str) -> "re.Pattern":
    return re.compile(f"^{re.escape(prefixo)}.+{re.escape(decimal)}..$")


def _mapa_letras_da_pagina(linhas: list[str]) -> dict:
    """Deriva cifra->letra a partir da linha 'Código Janeiro ... Total'
    (meses por extenso ou abreviados)."""
    for ln in linhas:
        toks = ln.split()
        if len(toks) < 14:
            continue
        for nomes in (MESES_CABECALHO, MESES_ABREV):
            mapa: dict[str, str] = {}
            for cifra, real in zip(toks[1:14], nomes):
                if len(cifra) != len(real):
                    continue
                for c, r in zip(cifra, real):
                    mapa.setdefault(c, r)
            teste = "".join(mapa.get(c, "?") for c in toks[1])
            if teste[:3].lower() == "jan":
                return mapa
    return {}


def _glifos_por_frequencia(linhas: list[str]):
    """(prefixo, glifo do zero, separador decimal) a partir do token de valor
    mais comum - quase sempre o zero, no formato '<pref>0<dec>00'. Serve de
    âncora quando o cabeçalho não tem um CPF 'dígitos todos iguais'."""
    from collections import Counter

    cnt: "Counter[str]" = Counter()
    for ln in linhas:
        for t in ln.split():
            if len(t) == 5 and t[1] == t[3] == t[4] and t[0] != t[1] and t[2] != t[1]:
                cnt[t] += 1
    if not cnt:
        return None
    tok = cnt.most_common(1)[0][0]
    return tok[0], tok[1], tok[2]


def _sep_milhar(tokens: list[str], prefixo: str, decimal: str) -> str | None:
    cand: set[str] = set()
    for t in tokens:
        corpo = t[len(prefixo):] if t.startswith(prefixo) else t
        if decimal not in corpo:
            continue
        ip = corpo.rsplit(decimal, 1)[0]
        for i in range(len(ip) - 4, -1, -4):
            cand.add(ip[i])
    return cand.pop() if len(cand) == 1 else None


def _norm_num(tok: str, sep, prefixo: str, decimal: str) -> str:
    """Token cifrado -> string cifrada '<inteiro>.<centavos>' (sem prefixo nem milhar)."""
    corpo = tok[len(prefixo):] if tok.startswith(prefixo) else tok
    ip, dp = corpo.rsplit(decimal, 1)
    if sep:
        chars = list(ip)
        for i in range(len(ip) - 4, -1, -4):
            if chars[i] == sep:
                chars[i] = ""
        ip = "".join(chars)
    return ip + _SEP_INT + dp


def _hashes_glifos(caminho, pageno: int) -> dict:
    """char (do texto) -> hash do desenho do glifo (fonte Type3). Estável entre páginas."""
    import hashlib
    try:
        import pymupdf
    except ImportError:  # pragma: no cover
        return {}
    d = pymupdf.open(caminho)
    try:
        p = d[pageno]
        t3 = [x for x in p.get_fonts(full=True) if x[2] == "Type3"]
        if not t3:
            return {}
        fobj = d.xref_object(t3[0][0])
        if "/CharProcs" not in fobj:
            return {}
        bloco = fobj.split("/CharProcs", 1)[1].split(">>")[0]
        out = {}
        for nome, xr in re.findall(r"/(\S+)\s+(\d+)\s+0\s+R", bloco):
            if nome.isdigit() and 32 <= int(nome) < 127:
                try:
                    out[chr(int(nome))] = hashlib.md5(d.xref_stream(int(xr))).hexdigest()
                except Exception:
                    pass
        return out
    finally:
        d.close()


# ----------------------------------------------------------------------------
# OCR (opcional) - só para ler os NOMES das rubricas nas fichas cifradas do
# Estado, quando o código não está em RUBRICAS_C. Os valores continuam vindo
# da decifragem; o OCR não toca em número nenhum.
# ----------------------------------------------------------------------------
_OCR_ENGINE = None
_OCR_ERRO = None  # por que o OCR não carregou (para conferir o deploy)
_OCR_CACHE: dict[tuple[str, int], list] = {}


def _cpus_disponiveis() -> float:
    """Quantas CPUs este processo pode realmente usar.

    Dentro de um container, `os.cpu_count()` mente: devolve os núcleos da
    máquina hospedeira, e não a fatia alocada. Quem sabe a verdade é o cgroup.
    """
    # cgroup v2
    try:
        txt = Path("/sys/fs/cgroup/cpu.max").read_text().split()
        if txt[0] != "max":
            return max(0.1, int(txt[0]) / int(txt[1]))
    except Exception:  # noqa: BLE001
        pass
    # cgroup v1
    try:
        q = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us").read_text())
        p = int(Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us").read_text())
        if q > 0 and p > 0:
            return max(0.1, q / p)
    except Exception:  # noqa: BLE001
        pass
    # fora de container: afinidade real, senão o total da máquina
    try:
        return float(len(os.sched_getaffinity(0)))  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        return float(os.cpu_count() or 1)


def _cpus_ocr() -> int:
    """Threads que o OCR pode usar. Com 2 CPUs ou mais deixa uma livre para o
    servidor continuar respondendo; com menos que isso, usa 1."""
    c = _cpus_disponiveis()
    return max(1, int(c) - 1) if c >= 2 else 1


def _ocr_engine():
    global _OCR_ENGINE, _OCR_ERRO
    if _OCR_ENGINE is None:
        # O OCR é puro CPU e o onnxruntime, por padrão, abre uma thread por
        # núcleo. Num container isso é uma armadilha: `os.cpu_count()` devolve
        # os núcleos do HOSPEDEIRO, não a fatia do container. Num host de 32
        # núcleos com 1 vCPU alocado, seriam 32 threads disputando 1 CPU —
        # muito mais lento do que rodar com uma. Por isso `_cpus_disponiveis()`
        # lê o limite real do cgroup.
        os.environ.setdefault("OMP_NUM_THREADS", str(_cpus_ocr()))
        try:
            from rapidocr_onnxruntime import RapidOCR
        except Exception as e:  # noqa: BLE001 - inclui falta de lib do sistema
            _OCR_ENGINE, _OCR_ERRO = False, f"{type(e).__name__}: {e}"
        else:
            # Montar o motor também pode falhar (modelo ausente, lib do
            # sistema faltando). Sem esse try o erro virava "erro inesperado".
            try:
                _OCR_ENGINE = RapidOCR()
            except Exception as e:  # noqa: BLE001
                _OCR_ENGINE, _OCR_ERRO = False, f"{type(e).__name__}: {e}"
    return _OCR_ENGINE or None


def ocr_status() -> dict:
    """Se o leitor de imagens (OCR) está disponível e, quando não, por quê.
    Serve para conferir um deploy: sem OCR, ficha escaneada é recusada."""
    ok = _ocr_engine() is not None
    return {
        "ocr": ok,
        "ocr_erro": None if ok else (_OCR_ERRO or "indisponível"),
        # Sem isto não dá para saber se o OCR está lento por falta de CPU.
        "cpus": round(_cpus_disponiveis(), 2),
        "ocr_threads": int(os.environ.get("OMP_NUM_THREADS", 0)) or None,
    }


def _ocr_pagina(caminho, page_idx: int) -> list[tuple[float, float, float, str]]:
    """OCR de uma página -> [(x0, y0, x1, texto), ...]. Cacheado."""
    chave = (str(caminho), page_idx)
    if chave in _OCR_CACHE:
        return _OCR_CACHE[chave]
    eng = _ocr_engine()
    out: list[tuple[float, float, float, str]] = []
    if eng is not None:
        try:
            import pymupdf

            d = pymupdf.open(caminho)
            png = d[page_idx].get_pixmap(dpi=300).tobytes("png")
            d.close()
            res, _ = eng(png)
            for box, txt, _conf in res or []:
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                out.append((min(xs), min(ys), max(xs), txt))
        except Exception:
            out = []
    _OCR_CACHE[chave] = out
    return out


_OCR_VALOR_RE = re.compile(r"^-?\d[\d.,]*$")


def _ocr_rubricas(caminho, page_idx: int) -> dict[str, str]:
    """{código -> nome} lidos por OCR da imagem da página. Considera qualquer
    linha 'código  nome  <13 valores>' (Vantagens ou Descontos); quem consome
    só pega os códigos que precisa."""
    itens = _ocr_pagina(caminho, page_idx)
    if not itens:
        return {}
    linhas: list[list[tuple[float, float, float, str]]] = []
    for it in sorted(itens, key=lambda t: (round(t[1] / 10), t[0])):
        if linhas and abs(linhas[-1][0][1] - it[1]) <= 9:
            linhas[-1].append(it)
        else:
            linhas.append([it])

    nomes: dict[str, str] = {}
    for grp in linhas:
        cells = sorted(grp, key=lambda t: t[0])
        if not cells:
            continue
        prim = cells[0][3].strip()
        resto_cells = cells[1:]
        if re.fullmatch(r"\d{1,4}", prim):
            codigo = prim
        elif re.match(r"^\d{1,4}\s+\S", prim):  # "231 13SALARIO..." (com espaço)
            codigo, resto = prim.split(None, 1)
            resto_cells = [(0, 0, 0, resto)] + resto_cells
        elif re.match(r"^(\d{1,4})([A-Za-zÀ-Ú/])", prim):  # "20FERIAS..." (colado)
            m = re.match(r"^(\d{1,4})(.*)$", prim)
            codigo = m.group(1)
            resto_cells = [(0, 0, 0, m.group(2))] + resto_cells
        else:
            continue
        partes, achou_valor = [], False
        for c in resto_cells:
            if _OCR_VALOR_RE.match(c[3].replace(" ", "")):
                achou_valor = True
                break
            partes.append(c[3])
        if not achou_valor or not partes:
            continue  # não é linha de tabela (sem colunas de valor depois do nome)
        nome = re.sub(r"\s{2,}", " ", " ".join(partes)).strip()
        nome = re.sub(r"\s*([./%-])\s*", r"\1", nome)  # "DIF . 1 / 3" -> "DIF.1/3"
        if nome:
            nomes.setdefault(codigo, nome)
    return nomes


def _norm_rubrica(s: str) -> str:
    """Normaliza p/ comparar (sem acento, sem espaço, sem pontuação, minúsculo)."""
    import unicodedata

    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


_RUBRICAS_NORM = None
_VOCAB = None

# Abreviações que aparecem coladas nos nomes de rubrica do SIARHES.
_VOCAB_EXTRA = """
SALARIO SALDO VENC VENCIMENTO PROVENTO PESSOAL CIVIL FIXO NOMINAL BASE
FERIAS ABONO TERCEIRO DECIMO PROPORCIONAL ADIANTAMENTO ADIANT ADIAT LIQUIDO LIQ LIQU
AUXILIO AUX ALIMENTACAO ALIMENT ALIM GRATIFICACAO GRATIF GRAT ESPECIAL ESPEC ESP
INCORPORACAO INCORP REFERENCIA REF CARGA CARG HORARIA HORAR HORARIO CH EXTENSAO EXTEN EXT
REMUNERADA REMUN ESTATUTARIO PROFISSIONAL PROF MINIMO MINIMA MIN DIFERENCA DIF
DESCONTO DESC INSS IPAJM IRRF IR IMPOSTO RENDA BONUS DESEMPENHO SEDU FUNDEB
ADICIONAL ADIC NOTURNO INSALUBRIDADE PERICULOSIDADE TEMPO SERVICO SERV DIRECAO
FUNCAO GRATIFICADA SUBSTITUICAO ANTERIOR ANT MES SOBRE PISO COMPLEMENTO COMPL
CONTRIBUICAO SINDICAL FAMILIA REP REPOSICAO DEVOLUCAO PERMANENCIA
TRIENIO QUINQUENIO BIENIO PROGRESSAO ATS LEI ESTADUAL PLANTAO SEM
INDENIZACAO RESCISAO CAIXA AJUDA CUSTO MAGISTERIO MAGISTER INTERNET
NOMINAL DEVOLUCAO NOTURNA
""".split()


def _vocab():
    global _VOCAB
    if _VOCAB is None:
        pal = set(_VOCAB_EXTRA)
        for v in list(RUBRICAS_C.values()) + list(RUBRICAS_CANONICAS.values()):
            for w in re.split(r"[\s./]+", _norm_rubrica_kw(v)):
                if len(w) >= 2:
                    pal.add(w)
        _VOCAB = sorted(pal, key=len, reverse=True)
    return _VOCAB


def _norm_rubrica_kw(s: str) -> str:
    import unicodedata

    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9\s./]", " ", s).upper()


def _quebrar(run: str) -> str:
    """Separa uma sequência de letras grudada em palavras conhecidas
    ('FERIASREMUNCARG' -> 'FERIAS REMUN CARG'). Guloso, maior prefixo primeiro."""
    if len(run) < 7 or not run.isalpha():
        return run
    voc = _vocab()
    out, i, orfas = [], 0, 0
    while i < len(run):
        for w in voc:
            if run.startswith(w, i):
                out.append(w)
                i += len(w)
                break
        else:
            out.append(run[i])
            orfas += 1
            i += 1
    # junta letras órfãs consecutivas à palavra vizinha
    junto = re.sub(r"(?<=\w) (?=\w\b)", "", " ".join(out)).strip()
    junto = re.sub(r"\b(\w) (\w)\b", r"\1\2", junto)
    return junto if orfas * 3 <= len(run) else run


def _nome_canonico(nome_ocr: str) -> str:
    """Se o nome lido por OCR bate (ignorando espaço/acento) com um nome já
    conhecido em RUBRICAS_C, usa a grafia canônica; senão tenta separar as
    palavras grudadas e devolve em Title Case."""
    global _RUBRICAS_NORM
    if _RUBRICAS_NORM is None:
        _RUBRICAS_NORM = {_norm_rubrica(v): v for v in RUBRICAS_C.values()}
    canon = _RUBRICAS_NORM.get(_norm_rubrica(nome_ocr))
    if canon:
        return canon
    partes = [_quebrar(p) for p in re.split(r"([ ./%\-\d]+)", nome_ocr)]
    nome = re.sub(r"\s{2,}", " ", "".join(partes)).strip()
    return nome.title() if nome.isupper() else nome


def _resolver_digitos(restricoes, zero_glifo: str, unico: bool = True) -> dict | None:
    """restricoes: lista de (termos, rhs) cifrados; exige sum(termos) == rhs.
    Com unico=True, devolve a solução só se ela for única."""
    glifos = sorted({c for termos, rhs in restricoes for s in (termos + [rhs]) for c in s if c != _SEP_INT} - {zero_glifo})
    if len(glifos) > 9:
        return None

    if not glifos:
        return {zero_glifo: "0"}

    # Antes, a poda só testava uma restrição quando TODOS os seus glifos já
    # estavam atribuídos, e refazia float("".join(...)) a cada nó - bilhões de
    # vezes numa ficha do Estado (dezenas de segundos a minutos).
    #
    # Agora: (1) descartamos as restrições que não carregam informação (as do
    # tipo "X = X" ou "0 = 0", sempre verdadeiras); (2) reduzimos cada restrição
    # a seu conjunto de glifos e a guardamos num "balde" indexado pelo último
    # glifo a ser atribuído, para conferi-la exatamente uma vez, no momento em
    # que fica completa; (3) escolhemos a ordem dos glifos para completar as
    # restrições o quanto antes. A conferência em si continua idêntica à
    # original (mesma soma de floats, mesma tolerância de 0.02).
    def _pesos(tok: str) -> dict[str, int]:
        ip, _, dp = tok.partition(_SEP_INT)
        pesos: dict[str, int] = {}
        for j, c in enumerate(ip):
            pesos[c] = pesos.get(c, 0) + 10 ** (len(ip) - 1 - j) * 100
        for j, c in enumerate(dp):
            pesos[c] = pesos.get(c, 0) + 10 ** (len(dp) - 1 - j)
        return pesos

    informativas: list[tuple[list[str], str, frozenset[str]]] = []
    for termos, rhs in restricoes:
        net: dict[str, int] = {}
        for t in termos:
            for c, p in _pesos(t).items():
                net[c] = net.get(c, 0) + p
        for c, p in _pesos(rhs).items():
            net[c] = net.get(c, 0) - p
        tem_info = any(p and c != zero_glifo for c, p in net.items())
        if not tem_info:
            continue
        # Todos os glifos que aparecem nos tokens (não só os de peso != 0): val()
        # lê atrib[c] para cada um, então a restrição só pode ser conferida
        # quando o último deles já foi atribuído.
        glifos_tok = frozenset(
            c for s in (termos + [rhs]) for c in s if c != _SEP_INT and c != zero_glifo
        )
        informativas.append((termos, rhs, glifos_tok))

    # Ordem dos glifos: guloso, priorizando os que completam mais restrições.
    conj_eq = [gs for _, _, gs in informativas]
    restantes = set(glifos)
    atribuidos: set[str] = set()
    ordem: list[str] = []
    while restantes:
        def _chave(g: str):
            depois = atribuidos | {g}
            completa = sum(1 for s in conj_eq if s <= depois and not s <= atribuidos)
            grau = sum(1 for s in conj_eq if g in s)
            return (completa, grau)
        g = max(sorted(restantes), key=_chave)
        ordem.append(g)
        atribuidos.add(g)
        restantes.discard(g)

    pos = {g: i for i, g in enumerate(ordem)}
    baldes: list[list[tuple[list[str], str]]] = [[] for _ in ordem]
    for termos, rhs, gs in informativas:
        baldes[max(pos[c] for c in gs)].append((termos, rhs))

    atrib = {zero_glifo: "0"}
    usados = {"0"}
    solucoes: list[dict] = []

    def val(s: str) -> float:
        return float("".join(atrib[c] if c != _SEP_INT else "." for c in s))

    def confere(termos, rhs) -> bool:
        return abs(sum(val(t) for t in termos) - val(rhs)) <= 0.02

    def bt(i: int):
        if len(solucoes) > 1:
            return
        if i == len(ordem):
            solucoes.append(dict(atrib))
            return
        g = ordem[i]
        for d in "123456789":
            if d in usados:
                continue
            atrib[g] = d
            if all(confere(tm, r) for tm, r in baldes[i]):
                usados.add(d)
                bt(i + 1)
                usados.discard(d)
            del atrib[g]

    bt(0)
    if not solucoes or (unico and len(solucoes) > 1):
        return None
    return solucoes[0]


def _extrair_ano(linhas, letras, digitos) -> int | None:
    """Acha 'Ano ... AAAA' no cabeçalho; resolve por bruteforce os dígitos que faltam."""
    import datetime
    import itertools

    limite = datetime.date.today().year + 1
    livres = [d for d in "0123456789" if d not in digitos.values()]

    for ln in linhas[:12]:
        for tok in ln.split():
            legras = "".join(letras.get(c, "?") for c in tok).lower()
            p = legras.find("ano")
            if p < 0:
                continue
            resto = [c for c in tok[p + 3:] if not c.isspace()]
            for ini in range(max(0, len(resto) - 3)):
                janela = resto[ini:ini + 4]
                if len(janela) < 4:
                    break
                faltam = sorted({c for c in janela if c not in digitos})
                if len(faltam) > 2:
                    continue
                achados = set()
                for perm in itertools.permutations(livres, len(faltam)):
                    mp = dict(zip(faltam, perm))
                    s = "".join(digitos.get(c) or mp.get(c, "") for c in janela)
                    if len(s) == 4 and s.isdigit() and 1950 <= int(s) <= limite:
                        achados.add(int(s))
                if len(achados) == 1:
                    return achados.pop()
    return None


def _parse_pagina_c(page):
    """Extrai a estrutura de uma página do layout C (sem decifrar os números)."""
    linhas = (page.extract_text() or "").splitlines()
    letras = _mapa_letras_da_pagina(linhas)
    if not letras:
        return None

    def dec_letras(s):
        return "".join(letras.get(c, "?") for c in s)

    freq = _glifos_por_frequencia(linhas)
    if freq:
        prefixo, zero_glifo, decimal = freq
    else:
        mcpf = _CPF_RE.search(" ".join(linhas[:12]))
        zero_glifo = mcpf.group("z") if mcpf else "Q"
        prefixo, decimal = _glifos_numericos(linhas, zero_glifo)
    if not prefixo or not decimal:
        return None
    valor_re = _valor_re(prefixo, decimal)

    def _eh_cabecalho_meses(toks) -> bool:
        if len(toks) < 13:
            return False
        achou = 0
        for t in toks:
            d = dec_letras(t).lower()
            for m in MESES:
                pre = "mar" if m == "Março" else m[:3].lower()
                if d[:3] == pre:
                    achou += 1
                    break
        return achou >= 8

    dados_rows: list[tuple] = []
    tot_v = tot_d = tot_l = None
    todos_val: list[str] = []
    secao = 0
    achou_palavra = False   # a seção foi identificada pelo nome ("Vantagens"...)?
    cab_vistos = 0          # nº de linhas de cabeçalho de meses já vistas
    for ln in linhas:
        toks = ln.split()
        if not toks:
            continue
        vals = [t for t in toks if valor_re.match(t)]
        t0 = dec_letras(toks[0]).lower()
        if len(toks) == 1 and "antagen" in t0:
            secao = 1
            achou_palavra = True
            continue
        if _eh_cabecalho_meses(toks):
            # Em algumas fichas o título da seção usa outra cifra e não dá para
            # ler "Vantagens"/"Descontos". Aí usamos a posição: o 1º bloco de
            # meses é Vantagens (proventos), o 2º Descontos, etc.
            cab_vistos += 1
            if not achou_palavra:
                secao = cab_vistos
            continue
        if t0.startswith("total") and len(vals) >= 13:
            todos_val += vals
            alvo = dec_letras(" ".join(toks)).lower()
            if "antagen" in alvo:
                tot_v = vals[:13]
                if secao == 1:
                    secao = 2
            elif "scont" in alvo:
                tot_d = vals[:13]
            elif "quido" in alvo or "iquid" in alvo:
                tot_l = vals[:13]
            continue
        if len(vals) >= 13 and len(toks) - len(vals) >= 1:
            nao_val = toks[: len(toks) - len(vals)]
            dados_rows.append((nao_val[0], " ".join(nao_val[1:]), vals[:12], vals[12], secao))
            todos_val += vals

    if not dados_rows:
        return None

    sep = _sep_milhar(todos_val, prefixo, decimal)

    # Alfabeto dos glifos usados como dígito nesta página (tirado dos valores).
    alfa_digito: set[str] = set()
    for v in todos_val:
        corpo = v[len(prefixo):] if v.startswith(prefixo) else v
        for c in corpo:
            if c != decimal and c != sep:
                alfa_digito.add(c)

    # Em algumas fichas o código da rubrica vem colado no nome, sem espaço
    # ("KMm/(cid:20)..." em vez de "KM  m/..."). Separa o código (sequência
    # inicial de glifos-dígito) do resto, que vira o nome. Pega até 5 glifos
    # aqui; a escolha final do tamanho (2..4) é feita em _converter_formato_c,
    # depois de decifrar, preferindo um código conhecido em RUBRICAS_C.
    def _split_cod(primeiro: str, resto_nome: str) -> tuple[str, str, bool]:
        if resto_nome or all(c in alfa_digito for c in primeiro):
            return primeiro, resto_nome, False  # código exato (tinha espaço)
        i = 0
        while i < len(primeiro) and i < 5 and primeiro[i] in alfa_digito:
            i += 1
        return primeiro[:i], primeiro[i:], True  # código estava colado no nome

    dados_rows = [
        (*_split_cod(cod, nome), meses, total, sec)
        for (cod, nome, meses, total, sec) in dados_rows
    ]
    return {
        "linhas": linhas, "letras": letras, "dec_letras": dec_letras,
        "zero_glifo": zero_glifo, "dados_rows": dados_rows,
        "tot_v": tot_v, "tot_d": tot_d, "tot_l": tot_l, "sep": sep,
        "prefixo": prefixo, "decimal": decimal,
        "num_pagina": page.page_number,
    }


def _restricoes_c(info) -> list:
    nz = lambda t: _norm_num(t, info["sep"], info["prefixo"], info["decimal"])
    restr = []
    for (_, _, _, meses, total, _) in info["dados_rows"]:
        restr.append(([nz(x) for x in meses], nz(total)))
    for tot in (info["tot_v"], info["tot_d"], info["tot_l"]):
        if tot:
            restr.append(([nz(x) for x in tot[:12]], nz(tot[12])))
    for tot, sec in ((info["tot_v"], 1), (info["tot_d"], 2)):
        if not tot:
            continue
        for j in range(13):
            termos = [nz((r[3] + [r[4]])[j]) for r in info["dados_rows"] if r[5] == sec]
            if termos:
                restr.append((termos, nz(tot[j])))
    if info["tot_v"] and info["tot_d"] and info["tot_l"]:
        for j in range(13):
            restr.append(([nz(info["tot_l"][j]), nz(info["tot_d"][j])], nz(info["tot_v"][j])))
    return restr


def _converter_formato_c(pdf, avisos: list[str], caminho=None, progresso=None):
    prog = progresso or _noop_progresso
    # --- passa 1: analisa páginas e resolve as que dão solução única ---
    paginas = []
    mapa_hash: dict[str, str] = {}
    _tot = len(pdf.pages)
    for _i, page in enumerate(pdf.pages):
        prog("Decifrando a página", _i + 1, _tot)
        info = _parse_pagina_c(page)
        if not info:
            continue
        info["hashes"] = _hashes_glifos(caminho, page.page_number - 1) if caminho else {}
        sol = _resolver_digitos(_restricoes_c(info), info["zero_glifo"], unico=True)
        if sol:
            for glifo, dig in sol.items():
                h = info["hashes"].get(glifo)
                if h:
                    mapa_hash.setdefault(h, dig)
        info["solo"] = sol
        paginas.append(info)

    # --- passa 2: decifra cada página (preferindo o mapa por desenho do glifo) ---
    blocos: dict[tuple[int, int], dict] = {}
    ordem: list[str] = []
    ocorrencias: dict[int, int] = {}
    ocr_por_codigo: dict[str, str] = {}  # nome lido por OCR, 1x por código

    for info in paginas:
        npag = info["num_pagina"]
        digitos = dict(info["solo"] or {})
        # completa/ajusta pelo desenho dos glifos
        for glifo, h in info["hashes"].items():
            if h in mapa_hash:
                digitos[glifo] = mapa_hash[h]
        digitos[info["zero_glifo"]] = "0"

        sep, pfx, dcm = info["sep"], info["prefixo"], info["decimal"]
        dec_letras = info["dec_letras"]

        # verifica se dá para decifrar tudo desta página
        chars_valores = {c for r in info["dados_rows"] for tok in (r[3] + [r[4]])
                         for c in _norm_num(tok, sep, pfx, dcm) if c != _SEP_INT}
        if not chars_valores <= digitos.keys():
            avisos.append(f"Página {npag}: não consegui decifrar todos os números.")
            continue

        def dec_num(tok, _dig=digitos, _sep=sep, _p=pfx, _d=dcm):
            s = _norm_num(tok, _sep, _p, _d)
            return float("".join(_dig.get(c, c) if c != _SEP_INT else "." for c in s))

        ano = _extrair_ano(info["linhas"], info["letras"], digitos)
        if not ano:
            avisos.append(f"Página {npag}: ano não encontrado.")
            continue

        ocorrencias[ano] = ocorrencias.get(ano, 0) + 1
        dados = blocos.setdefault((ano, ocorrencias[ano]), {mes: {} for mes in MESES})

        def _resolver_cod(bruto: str, glued: bool, ocr_map=None) -> str | None:
            m = re.match(r"\d{1,5}", bruto)
            if not m:
                return None
            d = m.group(0)
            if not glued:
                return d[:4]  # tinha espaço: `d` é o código
            cand = [d[:L] for L in (4, 3, 2) if len(d) >= L]
            if ocr_map:  # 2ª passada: o código lido por OCR é a verdade
                for c in cand:
                    if c in ocr_map:
                        return c
            for c in cand:  # prefixo que já esteja na tabela
                if c in RUBRICAS_C:
                    return c
            return d[:4]

        # 1º passo: resolve os códigos das linhas de proventos.
        linhas_prov: list[tuple] = []
        for (cod_c, nome_c, glued, meses_c, total_c, sec) in info["dados_rows"]:
            if sec != 1:
                continue
            bruto = "".join(digitos.get(c, "?") for c in cod_c)
            codigo = _resolver_cod(bruto, glued)
            if codigo is None:
                continue
            linhas_prov.append((codigo, bruto, glued, nome_c, meses_c, total_c))

        # Se algum código não tem nome conhecido, lê os nomes por OCR da imagem
        # (a fonte da descrição não é legível como texto).
        falta_nome = any(
            c not in RUBRICAS_C and c not in ocr_por_codigo
            for (c, *_) in linhas_prov
        )
        if falta_nome and caminho:
            for cod, nm in _ocr_rubricas(caminho, npag - 1).items():
                ocr_por_codigo.setdefault(cod, _nome_canonico(nm))
            # com os códigos lidos por OCR, refina os que ficaram ambíguos
            linhas_prov = [
                (_resolver_cod(bruto, glued, ocr_por_codigo) or codigo,
                 bruto, glued, nome_c, meses_c, total_c)
                for (codigo, bruto, glued, nome_c, meses_c, total_c) in linhas_prov
            ]

        for (codigo, bruto, glued, nome_c, meses_c, total_c) in linhas_prov:
            nome = RUBRICAS_C.get(codigo)
            if not nome:
                cru = re.sub(r"\(cid:\d+\)", "", nome_c).strip((sep or "") + pfx)
                nome = limpar_nome(dec_letras(cru))
                legivel = nome and nome.count("?") * 2 < len(nome)
                if not legivel or "?" in nome:
                    ocr = ocr_por_codigo.get(codigo)
                    if ocr and "?" not in ocr:
                        nome = ocr
                    elif not legivel:
                        avisos.append(
                            f"Rubrica {codigo}: nome não disponível nesta ficha - "
                            f"a coluna sai como 'Rubrica {codigo}'."
                        )
                        nome = f"Rubrica {codigo}"
                    else:
                        avisos.append(f"Rubrica {codigo}: nome parcial ('{nome}').")
            coluna = _coluna(codigo, nome)
            if coluna not in ordem:
                ordem.append(coluna)
            soma = sum(dec_num(t) for t in meses_c)
            if abs(soma - dec_num(total_c)) > 0.02:
                avisos.append(
                    f"Página {npag}, rubrica {codigo}: soma dos meses ({soma:.2f}) "
                    f"difere do total impresso ({dec_num(total_c):.2f}) - conferir."
                )
            for mes, tok in zip(MESES, meses_c):
                dados[mes][coluna] = dados[mes].get(coluna, 0.0) + dec_num(tok)

    return [
        {"ano": a, "rotulo": f"Contrato {o}", "dados": blocos[(a, o)], "ordem": ordem}
        for (a, o) in sorted(blocos)
    ]


# ----------------------------------------------------------------------------
# Layout D - Estado do ES, modelo "FICHA FINANCEIRA" antigo (PRD/PRODEST).
# Texto limpo (sem cifra), uma página por ano/servidor. Seções Vantagens /
# Descontos / Informativo / IRRF. Linhas "<código> <nome> <12 valores> <total>"
# com número no estilo americano (1,234.56). O nome da rubrica pode continuar
# na linha seguinte.
# ----------------------------------------------------------------------------
_US_NUM_RE = re.compile(r"-?\d{1,3}(?:,\d{3})*\.\d{2}")
_LINHA_D_RE = re.compile(
    r"^(\d{1,4})\s+(.+?)\s+((?:-?\d{1,3}(?:,\d{3})*\.\d{2}\s+){12}-?\d{1,3}(?:,\d{3})*\.\d{2})$"
)


def _converter_formato_d(pdf, avisos: list[str]):
    blocos: list[dict] = []
    for page in pdf.pages:
        texto = page.extract_text() or ""
        # "Ano Ref:2002" (modelo antigo) ou "ANO: 2006" (modelo "por funcionário")
        ma = re.search(r"(?:ANO|Ano\s*Ref)\s*:\s*(\d{4})", texto)
        if not ma:
            continue
        ano = int(ma.group(1))
        mf = re.search(r"FUNCION[ÁA]RIO:\s*(.+?)\s+CPF:", texto)
        mm = re.search(
            r"\n\s*(\d+)\s+([A-ZÁÀÂÃÉÊÍÓÔÕÚÜÇ][^\n]*?)\s+\d{2}/\d{2}/\d{4}", texto
        )
        if mf:
            rotulo = mf.group(1).strip()
        elif mm:
            rotulo = f"{mm.group(1)} {mm.group(2).strip()}"
        else:
            rotulo = f"Contrato {len(blocos) + 1}"

        dados = {mes: {} for mes in MESES}
        ordem: list[str] = []
        secao = None
        ult_col = None
        for ln in texto.splitlines():
            s = ln.strip()
            if not s:
                continue
            if s == "Vantagens":
                secao, ult_col = "V", None
                continue
            # Fim da seção Vantagens: linha "TOTAL ..." ou "Total de Vantagens:",
            # ou início de outra seção.
            if (
                s in ("Descontos", "Informativo", "Líquido", "L�quido")
                or s == "TOTAL"
                or s.startswith(("TOTAL ", "IRRF", "Total de ", "Total L"))
            ):
                secao, ult_col = None, None
                continue
            # Cabeçalho dos meses (por extenso ou abreviado).
            if ("Janeiro" in s and "Dezembro" in s) or re.match(
                r"C[ÓO�]DIGO\s+JAN\b", s
            ):
                continue
            if secao != "V":
                continue
            m = _LINHA_D_RE.match(s)
            if not m:
                # Continuação do nome da rubrica anterior (ex.: "AP.AT.SAUDE").
                if (
                    ult_col
                    and not s[:1].isdigit()
                    and not _US_NUM_RE.search(s)
                    and len(s) <= 25
                    and s.upper() == s
                ):
                    novo = f"{ult_col} {s}"
                    ordem[ordem.index(ult_col)] = novo
                    for mes in MESES:
                        if ult_col in dados[mes]:
                            dados[mes][novo] = dados[mes].pop(ult_col)
                    ult_col = novo
                continue
            codigo, nome = m.group(1), m.group(2).strip()
            nums = _US_NUM_RE.findall(m.group(3))
            if len(nums) < 13:
                continue
            meses_v = [float(x.replace(",", "")) for x in nums[:12]]
            total_v = float(nums[12].replace(",", ""))
            coluna = _coluna(codigo, nome)
            if coluna not in ordem:
                ordem.append(coluna)
            ult_col = coluna
            if abs(sum(meses_v) - total_v) > 0.02:
                avisos.append(
                    f"Página {page.page_number}, rubrica {codigo} ({nome}): soma dos "
                    f"meses ({sum(meses_v):.2f}) difere do total impresso "
                    f"({total_v:.2f}) - conferir."
                )
            for mes, v in zip(MESES, meses_v):
                dados[mes][coluna] = dados[mes].get(coluna, 0.0) + v

        if ordem:
            blocos.append({"ano": ano, "rotulo": rotulo, "dados": dados, "ordem": ordem})

    nomes = list(dict.fromkeys(b["rotulo"] for b in blocos))
    if len(nomes) > 1:
        avisos.append(
            "ATENÇÃO: este PDF contém " + str(len(nomes)) + " servidores diferentes ("
            + ", ".join(nomes) + "). A planilha juntou TODOS por ano/mês. "
            "Se cada servidor é um processo/cálculo separado, gere um PDF por "
            "servidor e converta um de cada vez."
        )
    return blocos


# ----------------------------------------------------------------------------
# Fichas do Estado ESCANEADAS (PDF de imagem, sem texto). OCR da imagem de
# cada página e remonta a tabela no mesmo formato do layout D. Como o OCR de
# scan erra, cada linha é validada (soma dos 12 meses == total impresso) e o
# que não fecha vira aviso "conferir".
# ----------------------------------------------------------------------------
_OCR_NUM_RE = re.compile(r"^-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2}$")


def _ocr_num(tok: str) -> float | None:
    t = tok.strip().replace(" ", "").replace("O", "0").replace("o", "0")
    t = re.sub(r"[:']", ".", t)                       # "100:00" / "00'0" -> ponto
    if re.fullmatch(r"0+\.?0*", t) or t in ("000", "00.0"):
        return 0.0
    if not _OCR_NUM_RE.match(t):
        return None
    corpo = t[:-3].replace(".", "").replace(",", "")  # tira milhar
    return float(corpo + "." + t[-2:]) if corpo.lstrip("-").isdigit() else None


def _converter_ocr(caminho, avisos: list[str], progresso=None):
    eng = _ocr_engine()
    if eng is None:
        raise ConversaoError(
            "Este PDF é uma digitalização (imagem) e o leitor de imagens (OCR) "
            "não está disponível nesta instalação.\n"
            "Instale as dependências de OCR ou use o app de computador."
        )
    import pymupdf

    doc = pymupdf.open(caminho)
    blocos: list[dict] = []
    prog = progresso or _noop_progresso
    for pi in range(len(doc)):
        prog("Lendo a imagem da página", pi + 1, len(doc))
        page = doc[pi]
        png = None
        imgs = page.get_images(full=True)
        if imgs:
            big = max(imgs, key=lambda im: im[2] * im[3])
            b = doc.extract_image(big[0])
            if b["width"] * b["height"] >= 700 * 500:
                png = b["image"]
        if png is None:
            png = page.get_pixmap(dpi=300).tobytes("png")

        try:
            res, _ = eng(png)
        except Exception:
            res = None
        if not res:
            continue

        itens = [(min(p[0] for p in box), min(p[1] for p in box), txt)
                 for box, txt, _c in res]
        linhas: list[list[tuple[float, float, str]]] = []
        for it in sorted(itens, key=lambda z: (round(z[1] / 12), z[0])):
            if linhas and abs(linhas[-1][0][1] - it[1]) < 11:
                linhas[-1].append(it)
            else:
                linhas.append([it])

        texto_pag = " ".join(t for ln in linhas for _x, _y, t in ln)
        ma = re.search(r"(?:ANO|Ano\s*Ref)[:\s]*?(\d{4})", texto_pag)
        if not ma:
            mp = re.search(r"[Pp]er[ií]odo[:\s]*\d{2}/(\d{4})", texto_pag) or \
                 re.search(r"[Pp]er[ií]odo[:\s]*(\d{4})", texto_pag)
            if not mp:
                continue
            ano = int(mp.group(1))
        else:
            ano = int(ma.group(1))
        msv = re.search(
            r"(?:[Nn]ome\s*[Ss]ervidor|FUNCION[ÁA]RIO)[:\s]*([A-Z][A-Za-zÀ-Ú ]+?)\s*"
            r"(?:CPF|Fonte|N[°º]|$)", texto_pag
        )
        rotulo = msv.group(1).strip() if msv else f"Contrato {len(blocos) + 1}"

        dados = {mes: {} for mes in MESES}
        ordem: list[str] = []
        secao = None
        for ln in linhas:
            cells = sorted(ln, key=lambda c: c[0])
            nums, rotulos = [], []
            for _x, _y, t in cells:
                v = _ocr_num(t)
                if v is not None:
                    nums.append(v)
                elif re.match(r"^\d{1,4}\s*[A-Za-zÀ-Ú]", t):
                    rotulos.append(t)

            plano = _norm_rubrica(" ".join(t for _x, _y, t in cells))
            # Linha de seção (poucos/nenhum número) ou a linha "TOTAL ...".
            if len(nums) < 12 or plano.startswith("total"):
                if plano.startswith(("vantagens", "proventos")):
                    secao = "V"
                elif plano.startswith(
                    ("descontos", "liquido", "informativo", "total")
                ):
                    secao = None
                continue
            if secao != "V" or len(rotulos) != 1:
                continue
            mrot = re.match(r"^(\d{1,4})\s*(.+)$", rotulos[0])
            codigo, nome_bruto = mrot.group(1), mrot.group(2)
            nome = RUBRICAS_C.get(codigo) or _nome_canonico(nome_bruto)
            meses_v, total_v = nums[:12], (nums[12] if len(nums) >= 13 else sum(nums[:12]))
            if abs(sum(meses_v) - total_v) > 0.02:
                avisos.append(
                    f"Página {pi + 1}, rubrica {codigo} ({nome}): a leitura por "
                    f"imagem não fechou (meses {sum(meses_v):.2f} x total "
                    f"{total_v:.2f}) - CONFERIR na ficha."
                )
            coluna = _coluna(codigo, nome)
            if coluna not in ordem:
                ordem.append(coluna)
            for mes, v in zip(MESES, meses_v):
                dados[mes][coluna] = dados[mes].get(coluna, 0.0) + v

        if ordem:
            blocos.append({"ano": ano, "rotulo": rotulo, "dados": dados, "ordem": ordem})

    if not blocos:
        raise ConversaoError(
            "Este PDF é uma digitalização e não consegui remontar a tabela pela "
            "imagem (qualidade baixa ou layout não reconhecido).\n"
            "Tente obter o PDF exportado direto do sistema (com texto)."
        )
    nomes = list(dict.fromkeys(b["rotulo"] for b in blocos))
    if len(nomes) > 1:
        avisos.append(
            f"ATENÇÃO: este PDF tem {len(nomes)} servidores diferentes "
            f"({', '.join(nomes)}). A planilha juntou todos por ano/mês."
        )
    avisos.append(
        "Esta ficha foi lida por OCR de imagem - confira os valores contra o PDF "
        "antes de usar no cálculo."
    )
    return blocos


# ----------------------------------------------------------------------------
# Fichas do MUNICÍPIO DA SERRA escaneadas (PDF de imagem, sem texto).
# OCR da imagem de cada página e remontagem da tabela de Proventos. Cada
# rubrica é validada contra a coluna TOTAL impressa; o que não fecha vira
# aviso "CONFERIR". OCR de scan erra, então nada aqui é usado sem conferência.
# ----------------------------------------------------------------------------
_SERRA_PERIODO_OCR = re.compile(r"(\d{2})/(\d{4})a(\d{2})/(\d{4})")
_COD_NOME_OCR = re.compile(r"^(\d{3})\s*[-.]?\s*(.*)$")


def _ocr_orient_score(linhas) -> float:
    """Quão bem a página lida representa uma ficha da Serra na orientação certa:
    conta os pares de meses consecutivos que aparecem em ordem crescente de x
    (Janeiro à esquerda, Dezembro à direita). Página de cabeça para baixo casa
    os 12 meses mas em ordem decrescente -> pontua baixo."""
    cen, xt = _centros_meses_ocr(linhas)
    if len(cen) < 4:
        return 0.0
    ok = sum(
        1 for i in range(11)
        if i in cen and i + 1 in cen and cen[i] < cen[i + 1]
    )
    return ok * 4 + len(cen) + (3 if xt is not None else 0)


_OCR_CACHE_ROT: dict[tuple, list] = {}


def _ocr_itens_rot(caminho, pi: int, deg: int):
    """OCR de uma página girada `deg` graus -> [(x0, y0, x1, texto), ...]."""
    ch = (str(caminho), pi, deg)
    if ch in _OCR_CACHE_ROT:
        return _OCR_CACHE_ROT[ch]
    eng = _ocr_engine()
    out: list[tuple] = []
    if eng is not None:
        try:
            import pymupdf

            d = pymupdf.open(caminho)
            mat = pymupdf.Matrix(300 / 72, 300 / 72).prerotate(deg)
            png = d[pi].get_pixmap(matrix=mat).tobytes("png")
            d.close()
            res, _ = eng(png)
            for box, txt, _c in res or []:
                xs = [p[0] for p in box]
                ys = [p[1] for p in box]
                out.append((min(xs), min(ys), max(xs), txt))
        except Exception:
            out = []
    _OCR_CACHE_ROT[ch] = out
    return out


def _linhas_de_itens(itens):
    linhas: list[list[tuple]] = []
    for x0, y0, x1, t in sorted(itens, key=lambda z: (round(z[1] / 12), z[0])):
        if linhas and abs(linhas[-1][0][3] - y0) < 12:
            linhas[-1].append((x0, x1, t, y0))
        else:
            linhas.append([(x0, x1, t, y0)])
    return [sorted([(x0, x1, t) for x0, x1, t, _y in ln], key=lambda c: c[0])
            for ln in linhas]


_OCR_SCORE_BOM = 11 * 4 + 8  # 12 meses em ordem + coluna TOTAL
_OCR_SCORE_USAVEL = 20       # meses suficientes e em ordem p/ confiar no ângulo


def _ocr_linhas_serra(caminho, pi, deg_pref=None):
    """OCR da página -> (linhas, ângulo usado). Muitas fichas da Serra são
    digitalizadas deitadas (a folha é paisagem); tenta 0°, 90°, 270°, 180° e
    fica com a orientação em que o cabeçalho de meses aparece na horizontal e
    em ordem crescente.

    `deg_pref` é o ângulo que já funcionou numa página anterior: o documento
    inteiro é digitalizado do mesmo jeito, então tentá-lo primeiro evita as 4
    passadas de OCR por página (numa ficha de 28 páginas isso é a diferença
    entre minutos e ~4x isso)."""
    ordem = (0, 90, 270, 180)
    if deg_pref is not None:
        ordem = (deg_pref,) + tuple(d for d in ordem if d != deg_pref)

    melhor, melhor_sc, melhor_deg = [], -1.0, None
    for i, deg in enumerate(ordem):
        linhas = _linhas_de_itens(_ocr_itens_rot(caminho, pi, deg))
        sc = _ocr_orient_score(linhas)
        if sc > melhor_sc:
            melhor, melhor_sc, melhor_deg = linhas, sc, deg
        if sc >= _OCR_SCORE_BOM:
            break
        # No ângulo que já funcionou antes, um score só razoável (meses achados
        # e em ordem crescente) basta: numa página um pouco pior, procurar nos
        # outros 3 ângulos custa 3 OCRs e nunca acha nada melhor.
        if i == 0 and deg_pref is not None and sc >= _OCR_SCORE_USAVEL:
            break
    return melhor, (melhor_deg if melhor_sc >= _OCR_SCORE_USAVEL else None)


def _centros_meses_ocr(linhas):
    """Acha a linha de cabeçalho (a que casa com mais nomes de mês) e devolve
    ({idx do mês: x central}, x central da coluna TOTAL)."""
    melhor: dict[int, float] = {}
    x_total = None
    for ln in linhas:
        c: dict[int, float] = {}
        xt = None
        for x0, x1, t in ln:
            base = _norm_rubrica(t)
            for idx, m in enumerate(MESES):
                p = _norm_rubrica(m)[:3]
                k = base.find(p)
                if k >= 0:
                    c[idx] = x0 + (x1 - x0) * (k + 1.5) / max(len(base), 1)
            if "total" in base:
                xt = (x0 + x1) / 2
        if len(c) > len(melhor):
            melhor, x_total = c, xt
    return melhor, x_total


def _converter_ocr_serra(caminho, avisos: list[str], progresso=None):
    eng = _ocr_engine()
    if eng is None:
        raise ConversaoError(
            "Este PDF do Município da Serra é uma digitalização (imagem) e o "
            "leitor de imagens (OCR) não está disponível nesta instalação.\n"
            "Instale as dependências de OCR ou use o aplicativo de computador."
        )
    import pymupdf

    n = len(pymupdf.open(caminho))
    blocos: list[dict] = []
    n_conferir = 0
    nomes_cod: dict[str, str] = {}  # nome canônico por código (1ª leitura boa vence)
    deg_pref = None   # orientação que já deu certo (o scan é igual no doc todo)
    fichas_vazias = 0  # páginas que SÃO ficha mas o OCR não conseguiu remontar
    prog = progresso or _noop_progresso
    for pi in range(n):
        prog("Lendo a imagem da página", pi + 1, n)
        # Se várias páginas de ficha seguidas não renderam nada, o scan não tem
        # qualidade para este layout — parar aqui em vez de gastar minutos de
        # OCR em dezenas de páginas para no fim recusar do mesmo jeito.
        if fichas_vazias >= 6 and not blocos:
            avisos.append(
                f"Parei na página {pi}: a leitura por imagem não conseguiu "
                f"remontar nenhuma das primeiras fichas."
            )
            break

        linhas, deg_ok = _ocr_linhas_serra(caminho, pi, deg_pref)
        if deg_ok is not None:
            deg_pref = deg_ok
        if not linhas:
            continue
        texto = " ".join(t for ln in linhas for _a, _b, t in ln)
        texto_c = _norm_rubrica(texto)
        if not re.search(r"fichas?financeira", texto_c):
            continue  # capa do processo / página sem ficha
        fichas_vazias += 1  # zerado no fim da página se ela render alguma coluna

        import unicodedata
        texto_s = re.sub(r"\s+", "", unicodedata.normalize("NFKD", texto)
                         .encode("ascii", "ignore").decode().lower())
        mp = _SERRA_PERIODO_OCR.search(texto_s)
        if not mp:
            continue
        ano, ano_fim = int(mp.group(2)), int(mp.group(4))
        if ano != ano_fim:
            avisos.append(
                f"Pág. {pi + 1}: período cruza dois anos ({ano} a {ano_fim}); "
                f"os valores foram lançados em {ano}."
            )

        mm = re.search(r"(\d{4,7})\s*([A-ZÀ-Ú][A-Za-zÀ-Ú]{5,})\s*Admiss", texto)
        rotulo = mm.group(1) if mm else f"Contrato {len(blocos) + 1}"

        centros, x_total = _centros_meses_ocr(linhas)
        if len(centros) < 6 or x_total is None:
            continue  # não localizou a grade de meses nesta página
        cs = sorted(centros.values())
        gaps = [b - a for a, b in zip(cs, cs[1:])]
        tol = (sorted(gaps)[len(gaps) // 2] * 0.55) if gaps else 60.0
        x_lo = min(cs) - tol

        # 1ª passada: separa (código, nome, números, total impresso) de cada
        # linha da seção Proventos e junta todos os x dos valores mensais num
        # "pool" para calibrar a grade de 12 colunas pelos próprios números
        # (o cabeçalho é alinhado à esquerda e os números à direita — usar o x
        #  do cabeçalho desloca o mês).
        dados = {m: {} for m in MESES}
        ordem: list[str] = []
        cruas: list[tuple] = []
        pool: list[float] = []
        secao = None
        cod = nome = None
        for ln in linhas:
            # O carimbo/assinatura do PJe às vezes cai na mesma linha (mesmo y)
            # de um rótulo de seção; por isso o marcador é procurado em cada
            # célula isolada, não no texto da linha inteira concatenada.
            palavras = [_norm_rubrica(t) for _a, _b, t in ln]
            if any(w.startswith(("proventos", "vantagens")) and len(w) < 15 for w in palavras):
                secao, cod = "P", None
                continue
            if any(w.startswith((
                "total", "descontos", "outros", "liquido", "salariobase",
                "fpff", "municipio", "digitalizado", "assinado", "https",
            )) and len(w) < 20 for w in palavras):
                secao, cod = None, None
                continue
            if secao != "P":
                continue

            nums, rot_txt = [], []
            for x0, x1, t in ln:
                v = _ocr_num(t)
                xc = (x0 + x1) / 2
                if v is not None and xc > x_lo:
                    nums.append((xc, v))
                else:
                    rot_txt.append(t)

            joined = re.sub(r"\s+", " ", " ".join(rot_txt)).strip()
            m = _COD_NOME_OCR.match(joined)
            if m:
                cod_novo = m.group(1)
                nb = limpar_nome(m.group(2)).strip(" -.")
                if re.sub(r"\W", "", nb):
                    nome_novo = RUBRICAS_CANONICAS.get(cod_novo) or _nome_canonico(nb) or nb
                else:
                    nome_novo = RUBRICAS_CANONICAS.get(cod_novo) or f"Rubrica {cod_novo}"
                if "?" not in nome_novo and not nome_novo.startswith("Rubrica "):
                    nomes_cod.setdefault(cod_novo, nome_novo)
                nome_novo = nomes_cod.get(cod_novo, nome_novo)
                if re.search(r"[A-Za-zÀ-Ú]{3,}", nome_novo):
                    cod, nome = cod_novo, nome_novo
                else:
                    # nome sem letras reconhecíveis (ruído de OCR): descarta a
                    # linha em vez de criar uma coluna sem sentido na planilha.
                    cod, nome = None, None
                    n_conferir += 1
            if cod is None or not nums:
                continue

            total_lido = None
            mensais: list[tuple] = []
            for xc, v in sorted(nums):
                if xc > x_total - tol:
                    if total_lido is None:
                        total_lido = v
                    continue
                mensais.append((xc, v))
                pool.append(xc)
            if mensais:
                cruas.append((pi, cod, nome, mensais, total_lido))

        if len(pool) < 6:
            continue
        # Grade de 12 colunas: o espaçamento vem do cabeçalho (regular mesmo
        # quando o OCR desloca tudo), a âncora é a coluna TOTAL, e o ajuste
        # fino é o deslocamento que melhor encaixa o conjunto de números lidos.
        cabec = sorted(centros.values())
        hgaps = sorted(b - a for a, b in zip(cabec, cabec[1:]))
        g = hgaps[len(hgaps) // 2] if hgaps else 0.0
        if g < 15:
            continue

        def _grade(d, k):
            return x_total - g * (12 - k) + d

        melhor_d, melhor_c, passo, d = 0.0, None, g / 30, -g * 0.7
        while d <= g * 0.7:
            c = sum(min(abs(xc - _grade(d, k)) for k in range(12)) for xc in pool)
            if melhor_c is None or c < melhor_c:
                melhor_c, melhor_d = c, d
            d += passo

        def _mes_idx(xc):
            return min(range(12), key=lambda k: abs(xc - _grade(melhor_d, k)))

        # 2ª passada: posiciona cada valor na grade e valida contra o total.
        for pi_r, cod, nome, mensais, total_lido in cruas:
            coluna = _coluna(cod, nome)
            mesv: dict[int, float] = {}
            idxs = [_mes_idx(xc) for xc, _v in mensais]
            for (xc, v), idx in zip(mensais, idxs):
                mesv[idx] = mesv.get(idx, 0.0) + v
            if not any(mesv.values()):
                continue
            if len(set(idxs)) < len(idxs):
                n_conferir += 1
                avisos.append(
                    f"Pág. {pi_r + 1}, {cod} {nome}: dois valores caíram no mesmo "
                    f"mês na leitura por imagem — CONFERIR os meses na ficha."
                )
            soma = sum(mesv.values())
            if total_lido is not None and abs(soma - total_lido) > 0.02:
                n_conferir += 1
                avisos.append(
                    f"Pág. {pi_r + 1}, {cod} {nome}: a leitura por imagem não "
                    f"fechou (meses {soma:.2f} × total impresso {total_lido:.2f}) "
                    f"— CONFERIR na ficha."
                )
            elif total_lido is None:
                n_conferir += 1
                avisos.append(
                    f"Pág. {pi_r + 1}, {cod} {nome}: não achei a coluna TOTAL para "
                    f"conferir esta linha — CONFERIR na ficha."
                )
            if coluna not in ordem:
                ordem.append(coluna)
            for idx, v in mesv.items():
                dados[MESES[idx]][coluna] = dados[MESES[idx]].get(coluna, 0.0) + v

        if ordem:
            blocos.append({"ano": ano, "rotulo": rotulo, "dados": dados, "ordem": ordem})
            fichas_vazias = 0

    total_colunas = len({v for b in blocos for v in b["ordem"]})
    if not blocos or (n > 3 and total_colunas < 2):
        raise ConversaoError(
            "Este PDF do Município da Serra é uma digitalização e a leitura por "
            "imagem não conseguiu remontar a tabela de forma confiável (qualidade "
            "do scan muito baixa para este layout).\n"
            "Tente obter o PDF exportado direto do sistema (com texto) ou uma "
            "digitalização de melhor qualidade."
        )
    nomes = list(dict.fromkeys(b["rotulo"] for b in blocos))
    if len(nomes) > 1:
        avisos.append(
            f"ATENÇÃO: este PDF tem {len(nomes)} contratos/matrículas "
            f"({', '.join(nomes)}). A planilha somou todos por ano/mês."
        )
    avisos.append(
        "Esta ficha foi lida por OCR de imagem — confira TODOS os valores contra "
        "o PDF antes de usar no cálculo"
        + (f" ({n_conferir} linha(s) marcada(s) para conferência)." if n_conferir else ".")
    )
    return blocos


# ----------------------------------------------------------------------------
def _detectar_formato(pdf) -> str:
    bruto = ""
    amostra = ""
    for page in pdf.pages[:3]:
        t = page.extract_text() or ""
        bruto += t
        amostra += decode_cid(t)
    if "GOVERNO DO ESTADO" in bruto and "Ano Ref:" in bruto:
        return "D"
    if "HIJK$LMNJOJPI" in bruto or "\nfls. " in bruto:
        return "C"
    return "B" if "Evento:" in amostra else "A"


class ConversaoError(Exception):
    """Erro previsível de conversão, com mensagem amigável para o usuário."""


# Rótulos amigáveis das origens de ficha que o usuário escolhe no seletor.
ORIGENS = {
    "serra": "Município da Serra",
    "estado": "Estado do Espírito Santo",
}


def _noop_progresso(etapa: str, atual: int = 0, total: int = 0) -> None:
    """Callback de progresso padrão: não faz nada."""


FORMATOS_SAIDA = ("xlsx", "json")


def converter(
    pdf_path: Path, out_path: Path, origem: str, progresso=None, formato: str | None = None
) -> dict:
    """Converte o PDF conforme a origem escolhida ('serra' ou 'estado') e grava
    o resultado em `out_path` no formato pedido: **xlsx** (planilha, aba
    "Proventos") ou **json**. Sem `formato`, é deduzido pela extensão de
    `out_path` (`.json` → json; qualquer outra coisa → xlsx).

    Os dois formatos carregam a MESMA informação — uma linha por Ano+Mês, uma
    coluna/campo por rubrica — só muda a embalagem. O JSON é um objeto com os
    metadados de sempre (`origem`, `layout`, `anos`, `avisos`, ...) mais
    `colunas` (ordem das rubricas) e `proventos` (lista de linhas, cada uma
    `{"Ano":, "Mês":, "<rubrica>": valor, ...}` — mesmas chaves do cabeçalho
    da planilha).

    Retorna um resumo; levanta ConversaoError quando o PDF não pode ser
    convertido ou quando não corresponde à origem escolhida.

    `progresso(etapa, atual, total)` é chamado ao longo da conversão para quem
    quiser mostrar andamento (a versão web usa isso). Conversão por OCR leva
    dezenas de segundos por ficha, então sem esse retorno a tela fica muda."""
    origem = (origem or "").lower()
    if origem not in ORIGENS:
        raise ValueError(f"origem inválida: {origem!r} (use 'serra' ou 'estado')")
    formato = (formato or Path(out_path).suffix.lstrip(".").lower() or "xlsx")
    if formato not in FORMATOS_SAIDA:
        raise ValueError(f"formato inválido: {formato!r} (use {' ou '.join(FORMATOS_SAIDA)})")
    prog = progresso or _noop_progresso
    prog("Abrindo o PDF", 0, 0)

    # Os caches de OCR são indexados pelo caminho do PDF. No servidor cada
    # requisição usa um arquivo temporário novo, então nada é reaproveitado e
    # as entradas antigas só acumulariam memória — o cache vale dentro de uma
    # conversão (várias páginas / várias rotações), não entre conversões.
    _OCR_CACHE.clear()
    _OCR_CACHE_ROT.clear()

    avisos: list[str] = []
    blocos: list[dict] = []

    with pdfplumber.open(pdf_path) as pdf:
        # "Tem texto" = o corpo da ficha veio como texto. PDFs escaneados de
        # processo (PJe) ainda trazem o carimbo de assinatura como texto — esse
        # boilerplate é descartado antes de medir.
        _lixo = ("assinado eletronicamente", "https://pje", "num.", "núm",
                 "número do documento", "numero do documento", "este documento",
                 "digitalizado com", "consultadocumento")
        _uteis = []
        for _p in pdf.pages[:5]:
            for _ln in decode_cid(_p.extract_text() or "").splitlines():
                _s = _ln.strip()
                if _s and not any(_s.lower().startswith(k) for k in _lixo):
                    _uteis.append(_s)
        tem_texto = len("\n".join(_uteis)) > 300
        if not tem_texto:
            if origem == "estado":
                # Ficha do Estado escaneada: converte por OCR da imagem.
                blocos = _converter_ocr(pdf_path, avisos, prog)
                fmt = "OCR"
                pdf = None  # não usa mais o pdfplumber
            else:
                # Ficha da Serra escaneada: converte por OCR da imagem.
                blocos = _converter_ocr_serra(pdf_path, avisos, prog)
                fmt = "OCR"
                pdf = None  # não usa mais o pdfplumber
        else:
            fmt = _detectar_formato(pdf)

        if not blocos:  # ainda não veio pelo OCR
            if origem == "serra" and fmt in ("C", "D"):
                raise ConversaoError(
                    f"Você escolheu '{ORIGENS['serra']}', mas este PDF parece ser "
                    f"uma ficha do {ORIGENS['estado']}.\n"
                    f"Troque o seletor para '{ORIGENS['estado']}' e converta de novo."
                )
            if origem == "estado" and fmt not in ("C", "D"):
                raise ConversaoError(
                    f"Você escolheu '{ORIGENS['estado']}', mas este PDF parece ser "
                    f"uma ficha do {ORIGENS['serra']}.\n"
                    f"Troque o seletor para '{ORIGENS['serra']}' e converta de novo."
                )

            if origem == "estado":
                blocos = (
                    _converter_formato_d(pdf, avisos)
                    if fmt == "D"
                    else _converter_formato_c(pdf, avisos, pdf_path, prog)
                )
            elif fmt == "A":
                matricula_atual = None
                for page in pdf.pages:
                    res = _pagina_formato_a(page, avisos)
                    if not res:
                        continue
                    matricula_atual = res.pop("matricula") or matricula_atual
                    res["rotulo"] = matricula_atual or "Contrato 1"
                    blocos.append(res)
            else:
                blocos = _converter_formato_b(pdf, avisos)

    if not blocos:
        alvo = (
            f"uma 'Relação Ficha Financeira' do {ORIGENS['serra']}"
            if origem == "serra"
            else f"uma 'Ficha Financeira' do {ORIGENS['estado']} (SIARHES)"
        )
        raise ConversaoError(
            "Não encontrei nenhuma seção de Proventos/Vantagens neste PDF.\n"
            f"Confirme que o arquivo é {alvo} e que o seletor está na origem certa."
        )

    # Uma linha por Ano+Mês (nunca anos repetidos empilhados).
    # Quando a pessoa tem mais de um contrato (matrícula) pagando no mesmo mês,
    # os valores da mesma verba são SOMADOS.
    contratos = list(dict.fromkeys(b["rotulo"] for b in blocos))

    colunas: list[str] = []
    for b in blocos:
        for verba in b["ordem"]:
            if verba not in colunas:
                colunas.append(verba)

    consol: dict[tuple[int, str], dict[str, float]] = {}
    for b in blocos:
        for mes, cols in b["dados"].items():
            for verba, val in cols.items():
                cel = consol.setdefault((b["ano"], mes), {})
                cel[verba] = cel.get(verba, 0.0) + val

    anos = sorted({b["ano"] for b in blocos})

    # Linhas em comum aos dois formatos: uma por Ano+Mês, valores arredondados.
    linhas = [
        {"Ano": ano, "Mês": mes,
         **{c: round(consol.get((ano, mes), {}).get(c, 0.0), 2) for c in colunas}}
        for ano in anos for mes in MESES
    ]

    if formato == "json":
        Path(out_path).write_text(
            json.dumps({
                "origem": ORIGENS[origem],
                "layout": fmt,
                "anos": anos,
                "contratos": contratos,
                "multiplos_blocos": len(contratos) > 1,
                "avisos": list(dict.fromkeys(avisos)),
                "colunas": colunas,
                "proventos": linhas,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Proventos"
        ws.append(["Ano", "Mês"] + colunas)
        for linha in linhas:
            ws.append([linha["Ano"], linha["Mês"]] + [linha[c] for c in colunas])
        wb.save(out_path)

    return {
        "arquivo": str(out_path),
        "formato": formato,
        "origem": ORIGENS[origem],
        "layout": fmt,
        "anos": anos,
        "contratos": contratos,
        "blocos": len(contratos),
        "rubricas": len(colunas),
        "multiplos_blocos": len(contratos) > 1,
        "avisos": list(dict.fromkeys(avisos)),
    }


def main():
    ap = argparse.ArgumentParser(description="Converte Ficha Financeira PDF em Excel.")
    ap.add_argument("pdf", type=Path, help="Caminho do PDF da ficha financeira")
    ap.add_argument(
        "-t", "--tipo", required=True, choices=("serra", "estado"),
        help="Origem da ficha: 'serra' (Prefeitura da Serra) ou 'estado' (Governo do Estado)",
    )
    ap.add_argument("-o", "--out", type=Path, help="Arquivo de saída (.xlsx ou .json)")
    ap.add_argument(
        "-f", "--formato", choices=FORMATOS_SAIDA,
        help="Formato de saída; se omitido, é deduzido da extensão de -o (padrão xlsx)",
    )
    args = ap.parse_args()

    if not args.pdf.exists():
        print(f"Arquivo não encontrado: {args.pdf}", file=sys.stderr)
        sys.exit(1)
    out = args.out or args.pdf.with_suffix("." + (args.formato or "xlsx"))
    try:
        r = converter(args.pdf, out, args.tipo, formato=args.formato)
    except ConversaoError as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {r['arquivo']}  ({r['origem']}, layout {r['layout']})")
    print(f"Anos: {r['anos'][0]}-{r['anos'][-1]}" if r["anos"] else "Anos: -")
    print(f"Contratos: {r['blocos']}   Colunas: {r['rubricas']}")
    if r["multiplos_blocos"]:
        print(
            f"Mais de um contrato ({', '.join(r['contratos'])}). Nos meses com "
            "dois contratos, os valores da mesma verba foram somados."
        )
    for a in r["avisos"]:
        print(f"  - {a}")


if __name__ == "__main__":
    main()
