"""
Regras da Release Windows, usadas pelo workflow `.github/workflows/windows.yml`.

    python release.py tag [--ref-tag vX.Y] [--sha-tag S --sha S]
                                                -> imprime a tag da Release
    python release.py notas --tag vX.Y --zip Z  -> imprime as notas (Markdown)

Só biblioteca padrão: roda no runner antes de qualquer dependência instalada.
A versão vem do `VERSAO` do server.py (a mesma que o app mostra em
/api/versao), lida por regex — importar o server puxaria Flask e o OCR.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
_TAG_RE = re.compile(r"^v(\d+\.\d+(?:\.\d+)?)$")


class ErroRelease(Exception):
    """Tag inválida ou diferente da versão do app."""


def versao_app(server_py: Path = RAIZ / "server.py") -> str:
    m = re.search(r'^VERSAO\s*=\s*"([^"]+)"', server_py.read_text(encoding="utf-8"),
                  flags=re.M)
    if not m:
        raise ErroRelease(f"VERSAO não encontrada em {server_py}")
    return m.group(1)


def tag_release(ref_tag: str | None, versao: str) -> str:
    """Tag enviada ao GitHub (validada) ou, no disparo manual, `v<versao>`."""
    if ref_tag is None:
        return f"v{versao}"
    m = _TAG_RE.match(ref_tag)
    if not m:
        raise ErroRelease(f"tag '{ref_tag}' fora do formato vX.Y ou vX.Y.Z")
    if m.group(1) != versao:
        raise ErroRelease(
            f"a tag {ref_tag} ({m.group(1)}) difere da versão do app "
            f"(server.VERSAO = {versao}). Suba o VERSAO ou corrija a tag."
        )
    return ref_tag


def conferir_commit_da_tag(tag: str, sha_da_tag: str, sha_atual: str) -> None:
    """A tag já existe (sha_da_tag não vazio) num commit diferente do que está
    sendo construído? Então a Release ficaria presa ao commit antigo, com o
    zip de outro — o `gh release create --target` não move tag existente."""
    if sha_da_tag and sha_da_tag != sha_atual:
        raise ErroRelease(
            f"a tag {tag} já existe no commit {sha_da_tag}, mas este build é do "
            f"commit {sha_atual}. Suba o VERSAO ou apague a tag antiga."
        )


def nome_zip(tag: str) -> str:
    return f"Conversor-de-Ficha-Financeira-{tag}-windows-x64.zip"


def notas_release(tag: str, sha256: str) -> str:
    return f"""Conversor de Ficha Financeira {tag} para Windows (pasta portátil).

## Como usar
Descompacte o zip e dê duplo clique em `Conversor.bat`, dentro da pasta
`Conversor de Ficha Financeira`. Não precisa instalar nada nem de internet.

## Requisitos
- Windows 10/11 64 bits
- .NET Framework 4.7.2 ou mais novo
- WebView2 Runtime (vem com o Microsoft Edge)

## Integridade
SHA-256 de `{nome_zip(tag)}`:

```
{sha256}
```
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tag")
    t.add_argument("--ref-tag")
    t.add_argument("--sha-tag", default="", help="commit da tag, se já existir")
    t.add_argument("--sha", default="", help="commit que está sendo construído")
    n = sub.add_parser("notas")
    n.add_argument("--tag", required=True)
    n.add_argument("--zip", required=True, type=Path)
    args = ap.parse_args(argv)

    try:
        if args.cmd == "tag":
            tag = tag_release(args.ref_tag, versao_app())
            conferir_commit_da_tag(tag, args.sha_tag, args.sha)
            print(tag)
        else:
            sha = hashlib.sha256(args.zip.read_bytes()).hexdigest()
            print(notas_release(args.tag, sha))
    except ErroRelease as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
