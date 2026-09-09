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
    def _split_cod(primeiro: str, resto_nome: str) -> tuple[str, str]:
        if resto_nome or all(c in alfa_digito for c in primeiro):
            return primeiro, resto_nome
        i = 0
        while i < len(primeiro) and i < 5 and primeiro[i] in alfa_digito:
            i += 1
        return primeiro[:i], primeiro[i:]

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
    for (_, _, meses, total, _) in info["dados_rows"]:
        restr.append(([nz(x) for x in meses], nz(total)))
    for tot in (info["tot_v"], info["tot_d"], info["tot_l"]):
        if tot:
            restr.append(([nz(x) for x in tot[:12]], nz(tot[12])))
    for tot, sec in ((info["tot_v"], 1), (info["tot_d"], 2)):
        if not tot:
            continue
        for j in range(13):
            termos = [nz((r[2] + [r[3]])[j]) for r in info["dados_rows"] if r[4] == sec]
            if termos:
                restr.append((termos, nz(tot[j])))
    if info["tot_v"] and info["tot_d"] and info["tot_l"]:
        for j in range(13):
            restr.append(([nz(info["tot_l"][j]), nz(info["tot_d"][j])], nz(info["tot_v"][j])))
    return restr


def _converter_formato_c(pdf, avisos: list[str], caminho=None):
    # --- passa 1: analisa páginas e resolve as que dão solução única ---
    paginas = []
    mapa_hash: dict[str, str] = {}
    for page in pdf.pages:
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
        chars_valores = {c for r in info["dados_rows"] for tok in (r[2] + [r[3]])
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

        for (cod_c, nome_c, meses_c, total_c, sec) in info["dados_rows"]:
            if sec != 1:
                continue
            bruto = "".join(digitos.get(c, "?") for c in cod_c)
            # Se o nome veio colado no código, `bruto` pode ter dígitos a mais
            # (ex.: rubrica 231 "13 SALARIO..." -> "2311"). Prefere um prefixo
            # que seja um código conhecido; senão, os 2-4 primeiros dígitos.
            codigo = next(
                (bruto[:L] for L in (4, 3, 2)
                 if bruto[:L].isdigit() and bruto[:L] in RUBRICAS_C),
                None,
            )
            if codigo is None:
                m = re.match(r"\d{2,4}", bruto)
                if not m:
                    continue
                codigo = m.group(0)
            nome = RUBRICAS_C.get(codigo)
            if not nome:
                cru = re.sub(r"\(cid:\d+\)", "", nome_c).strip((sep or "") + pfx)
                nome = limpar_nome(dec_letras(cru))
                if nome.count("?") * 2 >= max(len(nome), 1):
                    # Nome ilegível (a fonte da descrição não tem mapa de
                    # caracteres nesta ficha): usa o código como rótulo.
                    avisos.append(
                        f"Rubrica {codigo}: nome não disponível nesta ficha - "
                        f"a coluna sai como 'Rubrica {codigo}'."
                    )
                    nome = f"Rubrica {codigo}"
                elif "?" in nome:
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
def _detectar_formato(pdf) -> str:
    bruto = ""
    amostra = ""
    for page in pdf.pages[:3]:
        t = page.extract_text() or ""
        bruto += t
        amostra += decode_cid(t)
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


def converter(pdf_path: Path, out_path: Path, origem: str) -> dict:
    """Converte o PDF em .xlsx conforme a origem escolhida ('serra' ou 'estado').
    Retorna um resumo; levanta ConversaoError quando o PDF não pode ser convertido
    ou quando não corresponde à origem escolhida."""
    origem = (origem or "").lower()
    if origem not in ORIGENS:
        raise ValueError(f"origem inválida: {origem!r} (use 'serra' ou 'estado')")

    avisos: list[str] = []
    blocos: list[dict] = []
    ordem_colunas: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        tem_texto = any((p.extract_text() or "").strip() for p in pdf.pages[:5])
        if not tem_texto:
            raise ConversaoError(
                "Este PDF é uma digitalização (imagem), sem texto selecionável.\n"
                "Para converter seria necessário OCR, que ainda não está disponível "
                "neste programa. Tente obter o PDF exportado direto do sistema."
            )
        fmt = _detectar_formato(pdf)

        if origem == "serra" and fmt == "C":
            raise ConversaoError(
                f"Você escolheu '{ORIGENS['serra']}', mas este PDF parece ser uma "
                f"ficha do {ORIGENS['estado']} (SIARHES).\n"
                f"Troque o seletor para '{ORIGENS['estado']}' e converta de novo."
            )
        if origem == "estado" and fmt != "C":
            raise ConversaoError(
                f"Você escolheu '{ORIGENS['estado']}', mas este PDF parece ser uma "
                f"ficha do {ORIGENS['serra']}.\n"
                f"Troque o seletor para '{ORIGENS['serra']}' e converta de novo."
            )

        if origem == "estado":
            blocos = _converter_formato_c(pdf, avisos, pdf_path)
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

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Proventos"
    ws.append(["Ano", "Mês"] + colunas)
    for ano in anos:
        for mes in MESES:
            cel = consol.get((ano, mes), {})
            ws.append([ano, mes] + [round(cel.get(c, 0.0), 2) for c in colunas])
    wb.save(out_path)

    return {
        "arquivo": str(out_path),
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
    ap.add_argument("-o", "--out", type=Path, help="Arquivo .xlsx de saída")
    args = ap.parse_args()

    if not args.pdf.exists():
        print(f"Arquivo não encontrado: {args.pdf}", file=sys.stderr)
        sys.exit(1)
    out = args.out or args.pdf.with_suffix(".xlsx")
    try:
        r = converter(args.pdf, out, args.tipo)
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
