"""
Converte um PDF com o `converter.py` de APP_DIR, no Python-ALVO, e imprime em
JSON o resumo e as linhas da aba Proventos.

    python _converter_alvo.py <app_dir> <pdf> <saida.xlsx> <origem>
"""
import json
import sys
from pathlib import Path

app_dir, pdf, saida, origem = sys.argv[1:5]
sys.path.insert(0, app_dir)

import converter  # noqa: E402
import openpyxl  # noqa: E402

resumo = converter.converter(Path(pdf), Path(saida), origem)
ws = openpyxl.load_workbook(saida)["Proventos"]
linhas = [list(r) for r in ws.iter_rows(values_only=True)]
# JSON só em ASCII ("Mês" -> "Mês"): no Windows a saída de um processo
# filho vem na página de código do console, e o Python embutido (modo isolado
# pelo ._pth) ignora PYTHONIOENCODING.
print(json.dumps({"resumo": resumo, "linhas": linhas}))
