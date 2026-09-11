# Build Windows Context

**Gathered:** 2026-09-11
**Spec:** `.specs/features/build-windows/spec.md`
**Status:** Ready for design

---

## Feature Boundary

Gerar, a partir do Mac, a pasta portátil Windows do conversor num runner Windows do GitHub Actions, verificá-la com o Python da própria pasta e publicá-la como zip numa GitHub Release por tag, com dependências travadas por versão e hash. O app em si (`converter.py`, `server.py`, `app_desktop.py`, `web/`) é empacotado como está.

---

## Implementation Decisions

### Onde o build roda

- GitHub Actions, `windows-latest`. Repo `Fluix-Solutions/conversor-ficha-financeira` é público → runner gratuito.
- Build local no Mac com `uv` fica fora (sem o teste com o Python da pasta).

### Formato de entrega

- Zip da pasta portátil (Python embutido assinado pela PSF). Sem instalador, sem assinatura de código.

### Publicação

- Tag `vX.Y`/`vX.Y.Z` → GitHub Release com o zip anexado. Download público (repo é público) — aceito.
- Botão manual (`workflow_dispatch`) também publica a Release, com a tag `v<server.VERSAO>` (usuário, 2026-09-11).

### Escopo das melhorias

- Entra: lock de dependências com versão exata + hash.
- Não entra: log de erro visível, aviso de WebView2 ausente.

### Agent's Discretion

- Ficha fictícia de layout D gerada no teste (texto e escaneada) como verificação de conversão.
- SHA-256 fixo do Python embutido; falhar em Release duplicada; versão da tag = `server.VERSAO`.

### Declined / Undiscussed Gray Areas → Assumptions

- Todos registrados na tabela Assumptions & Open Questions do spec (disparo, versão do Python, versões iniciais do lock, ficha fictícia, `get-pip.py`, Release duplicada, retenção do artefato, Smart App Control com download).

---

## Specific References

- Fluxo atual de build: `construir_portatil.py` (6 passos; o 6/6 roda o Python da pasta e pegou os dois bugs anteriores: `flask` faltando e `..` no `._pth`).
- Resolução cruzada testada no Mac em 2026-09-11: `pip --platform win_amd64` falha (`ResolutionImpossible`, puxa `pyobjc`); `uv pip compile --python-platform x86_64-pc-windows-msvc --python-version 3.12` resolve (324 MB instalados, 158 binários, caminho mais longo 102 caracteres).
- `rapidocr-onnxruntime 1.4.4` exige Python `<3.13`.

---

## Deferred Ideas

- Log de erro visível quando o app não abre (hoje o `pythonw` engole o erro).
- Aviso de WebView2 ausente (hoje o pywebview cai no motor do IE sem avisar).
- Instalador assinado (ex.: Azure Trusted Signing).
- Migrar para o pacote `rapidocr` novo e Python 3.13+.
- Zip sem `__pycache__` de `converter`/`server` (o autoteste 6/6 importa depois da limpeza; rodar com `python -B`). Cosmético — gap G3 da 2ª verificação.
