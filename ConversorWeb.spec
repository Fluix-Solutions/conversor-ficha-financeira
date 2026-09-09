# PyInstaller spec - Conversor de Ficha Financeira (janela pywebview / visual Valorizei)
# Build:  python -m PyInstaller --noconfirm ConversorWeb.spec
# Saida:  dist/Conversor de Ficha Financeira.exe

from PyInstaller.utils.hooks import collect_all, collect_submodules

datas = [("ui", "ui")]
binaries = []
hiddenimports = ["openpyxl", "PIL"]

for pkg in ("webview", "pdfminer", "pdfplumber", "pymupdf"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["app_web.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=["pandas", "numpy", "matplotlib", "pytest", "IPython", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Conversor de Ficha Financeira",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon="icone.ico",
    version="version_info.txt",
)
