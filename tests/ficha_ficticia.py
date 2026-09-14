"""
Gera uma Ficha Financeira FICTÍCIA do Estado (layout D, texto limpo) e a mesma
ficha "escaneada" (só imagem, 300 DPI). Roda no Python-ALVO (o da pasta
portátil no CI), que tem pymupdf:

    python ficha_ficticia.py <diretório>

Imprime em JSON os valores esperados. Nenhum dado real: nome, matrícula e
valores são inventados.

Os valores ficam em colunas espaçadas, como numa ficha de verdade. Com um
espaço só entre eles, o OCR lê a linha inteira como uma caixa e não remonta a
tabela (visto no spike de 2026-09-11).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pymupdf

ANO = 2020
# (código, nome, valor de janeiro); cada mês seguinte soma 1,00.
PROVENTOS = [
    ("0001", "VENCIMENTO", 1234.56),
    ("0002", "ADICIONAL TEMPO SERVICO", 98.70),
    ("0003", "GRATIFICACAO", 450.00),
]
# Descontos: estão na ficha e NÃO podem ir para a planilha.
DESCONTOS = [("0500", "IMPOSTO", 10.00)]


def _meses(jan: float) -> list[float]:
    return [round(jan + i, 2) for i in range(12)]


def _br(v: float) -> str:
    return f"{v:,.2f}"  # estilo americano, como no layout D: 1,234.56


def gerar_texto(caminho: Path) -> None:
    doc = pymupdf.open()
    pg = doc.new_page(width=842, height=595)  # A4 deitado
    y = 40

    def linha(texto: str, tam: float = 8) -> None:
        nonlocal y
        pg.insert_text((30, y), texto, fontsize=tam, fontname="cour")
        y += 16

    def rubrica(rotulo: str, nums: list[float]) -> None:
        nonlocal y
        pg.insert_text((30, y), rotulo, fontsize=7, fontname="helv")
        for i, n in enumerate(nums):
            pg.insert_text((215 + i * 47, y), _br(n), fontsize=7, fontname="helv")
        y += 16

    linha("GOVERNO DO ESTADO DO ESPIRITO SANTO", tam=10)
    linha(f"FICHA FINANCEIRA          Ano Ref:{ANO}")
    linha("123456 FULANO DE TAL FICTICIO 01/02/2010")
    linha("Codigo Descricao Janeiro Fevereiro Marco Abril Maio Junho Julho "
          "Agosto Setembro Outubro Novembro Dezembro Total")
    linha("Vantagens")
    for cod, nome, jan in PROVENTOS:
        m = _meses(jan)
        rubrica(f"{cod} {nome}", m + [round(sum(m), 2)])
    linha("Total de Vantagens:")
    linha("Descontos")
    for cod, nome, jan in DESCONTOS:
        m = [jan] * 12
        rubrica(f"{cod} {nome}", m + [round(sum(m), 2)])
    # O conversor só trata como "PDF com texto" acima de ~300 caracteres úteis.
    for _ in range(4):
        linha("Observacao ficticia gerada para teste automatizado, sem dados "
              "reais de pessoa alguma.")
    doc.save(caminho)


def gerar_scan(origem: Path, caminho: Path) -> None:
    """Mesma ficha como imagem pura (sem camada de texto), 300 DPI."""
    src = pymupdf.open(origem)
    dst = pymupdf.open()
    for p in src:
        pix = p.get_pixmap(dpi=300)
        nova = dst.new_page(width=p.rect.width, height=p.rect.height)
        nova.insert_image(nova.rect, pixmap=pix)
    dst.save(caminho)


def main(diretorio: Path) -> dict:
    diretorio.mkdir(parents=True, exist_ok=True)
    texto, scan = diretorio / "ficticia.pdf", diretorio / "ficticia_scan.pdf"
    gerar_texto(texto)
    gerar_scan(texto, scan)
    return {
        "ano": ANO,
        "rubricas": {nome: _meses(jan) for _cod, nome, jan in PROVENTOS},
        "descontos": [nome for _cod, nome, _jan in DESCONTOS],
        "texto": str(texto),
        "scan": str(scan),
    }


if __name__ == "__main__":
    print(json.dumps(main(Path(sys.argv[1]))))
