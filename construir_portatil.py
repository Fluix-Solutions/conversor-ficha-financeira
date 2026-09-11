"""
Monta a PASTA PORTÁTIL do Conversor para levar a outros computadores.

    python construir_portatil.py [destino]

Gera `portatil/Conversor de Ficha Financeira/`, com um Python embutido e todas
as dependências dentro. Na máquina de destino não se instala nada: copia a
pasta e dá duplo clique em `Conversor.bat`.

Por que Python embutido e não um .exe: um .exe gerado por PyInstaller não é
assinado, e o Windows com Smart App Control (ENFORCE) o bloqueia — foi o que
inviabilizou esse caminho neste projeto. O `python.exe` embutido é assinado
pela Python Software Foundation, então passa.

Requisitos na máquina de destino (presentes num Windows 10/11 atualizado):
  - .NET Framework 4.7.2+  (o pywebview usa pythonnet)
  - WebView2 Runtime       (vem com o Edge)
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

PY = "3.12.9"
URL_EMBED = f"https://www.python.org/ftp/python/{PY}/python-{PY}-embed-amd64.zip"
URL_GETPIP = "https://bootstrap.pypa.io/get-pip.py"

RAIZ = Path(__file__).resolve().parent
NOME = "Conversor de Ficha Financeira"

# O que roda na máquina de destino. `ui/` e `app_web.py` (janela antiga) e o
# `app.py` (Tkinter, que o Python embutido nem tem) ficam de fora.
ARQUIVOS = ["converter.py", "server.py", "app_desktop.py"]
PASTAS = ["web"]

LANCADOR = """@echo off
cd /d "%~dp0"
start "" "python\\pythonw.exe" app_desktop.py
"""

LEIAME = """CONVERSOR DE FICHA FINANCEIRA
=============================

COMO USAR
  Duplo clique em "Conversor.bat". Abre uma janela com 3 passos:
  origem da ficha, arquivo PDF, converter.

  Nao precisa instalar nada. Nao precisa de internet.

FICHA ESCANEADA (PDF que e so imagem)
  Funciona. Leva de 1 a 2 minutos e a tela mostra o andamento.
  IMPORTANTE: nesse caso, CONFIRA os valores contra o PDF antes de usar no
  calculo. Cada verba e conferida contra a coluna TOTAL da ficha, e o que nao
  fecha aparece como aviso na tela.

PRIVACIDADE
  Tudo e processado neste computador. Nenhum arquivo e enviado para a
  internet.

SE NAO ABRIR
  Requer Windows 10/11 atualizado (.NET Framework e WebView2 do Edge).
  Se a janela nao aparecer, rode "python\\python.exe app_desktop.py" pelo
  Prompt de Comando dentro desta pasta para ver a mensagem de erro.
"""


def _baixar(url: str, destino: Path) -> None:
    print(f"  baixando {url.rsplit('/', 1)[-1]} ...")
    with urllib.request.urlopen(url, timeout=120) as r, open(destino, "wb") as f:
        shutil.copyfileobj(r, f)


def main() -> int:
    saida = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "portatil"
    alvo = saida / NOME
    pydir = alvo / "python"

    if alvo.exists():
        print(f"limpando {alvo} ...")
        shutil.rmtree(alvo)
    pydir.mkdir(parents=True)

    tmp = saida / "_tmp"
    tmp.mkdir(exist_ok=True)

    # 1. Python embutido
    print("1/5 Python embutido")
    z = tmp / "python-embed.zip"
    if not z.exists():
        _baixar(URL_EMBED, z)
    with zipfile.ZipFile(z) as zf:
        zf.extractall(pydir)

    # O Python embutido vem com o sys.path travado num arquivo ._pth e com
    # `import site` desligado — sem isso ele não enxerga o site-packages e
    # nenhuma dependência carrega.
    # Além disso, com um ._pth presente o Python entra em modo isolado e NÃO
    # acrescenta a pasta do script ao sys.path — `python app_desktop.py` não
    # acharia `converter`/`server`. O ".." aponta para a pasta do app (o ._pth
    # é relativo ao diretório do python.exe).
    for pth in pydir.glob("python*._pth"):
        txt = pth.read_text(encoding="utf-8")
        txt = re.sub(r"^\s*#\s*import\s+site\s*$", "import site", txt,
                     flags=re.M)
        if "import site" not in txt:
            txt += "\nimport site\n"
        if not re.search(r"^\.\.$", txt, flags=re.M):
            txt = txt.replace("\n.\n", "\n.\n..\n", 1)
            if not re.search(r"^\.\.$", txt, flags=re.M):
                txt = "..\n" + txt
        pth.write_text(txt, encoding="utf-8")
        print(f"  {pth.name}: site habilitado + pasta do app no sys.path")

    # 2. pip
    print("2/5 pip")
    getpip = tmp / "get-pip.py"
    if not getpip.exists():
        _baixar(URL_GETPIP, getpip)
    subprocess.run([str(pydir / "python.exe"), str(getpip), "--no-warn-script-location"],
                   check=True)

    # 3. dependências
    print("3/5 dependencias (demora — sao ~400 MB)")
    subprocess.run(
        [str(pydir / "python.exe"), "-m", "pip", "install",
         "--no-warn-script-location", "-r", str(RAIZ / "requirements-desktop.txt")],
        check=True,
    )

    # 4. aplicação
    print("4/5 aplicacao")
    for nome in ARQUIVOS:
        shutil.copy2(RAIZ / nome, alvo / nome)
    for nome in PASTAS:
        shutil.copytree(RAIZ / nome, alvo / nome,
                        ignore=shutil.ignore_patterns("__pycache__"))
    (alvo / "Conversor.bat").write_text(LANCADOR, encoding="utf-8")
    (alvo / "LEIA-ME.txt").write_text(LEIAME, encoding="utf-8")

    # 5. enxugar
    print("5/6 enxugando")
    for p in list(pydir.rglob("__pycache__")) + list(alvo.rglob("__pycache__")):
        shutil.rmtree(p, ignore_errors=True)
    shutil.rmtree(tmp, ignore_errors=True)

    # 6. conferir com o Python DA PASTA, não com o do sistema.
    # Sem isto, uma dependência faltando só apareceria na máquina de destino —
    # foi assim que o Flask passou batido na 1ª versão (o app de desktop
    # reaproveita o server.py, mas ele não estava no requirements-desktop).
    print("6/6 conferindo a pasta gerada")
    codigo = """
import sys
mods = ['pdfplumber', 'openpyxl', 'fitz', 'flask', 'webview', 'cv2',
        'onnxruntime', 'rapidocr_onnxruntime', 'clr', 'converter', 'server']
ruins = []
for m in mods:
    try:
        __import__(m)
    except Exception as e:
        ruins.append(f'{m}: {type(e).__name__}: {e}')
import converter
if not converter.ocr_status()['ocr']:
    ruins.append('OCR indisponivel: ' + str(converter.ocr_status()['ocr_erro']))
if ruins:
    print('FALTANDO:')
    for r in ruins:
        print('  -', r)
    sys.exit(1)
print('  tudo importa e o OCR carrega')
"""
    r = subprocess.run([str(pydir / "python.exe"), "-c", codigo], cwd=str(alvo))
    if r.returncode != 0:
        print("\nBUILD INVALIDO: a pasta nao roda sozinha (veja acima).",
              file=sys.stderr)
        return 1

    tam = sum(f.stat().st_size for f in alvo.rglob("*") if f.is_file())
    print(f"\nPRONTO: {alvo}")
    print(f"tamanho: {tam / 1e6:.0f} MB")
    print("Teste com um duplo clique no Conversor.bat de dentro dessa pasta.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
