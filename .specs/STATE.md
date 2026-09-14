# STATE

## Decisions

### AD-001
- **Decision**: A distribuição Windows é o zip da pasta portátil (Python embeddable assinado pela PSF), montado e verificado num runner Windows do GitHub Actions e publicado como GitHub Release por tag; não há `.exe`/instalador.
- **Reason**: O Smart App Control (ENFORCE) bloqueia executável não assinado; o desenvolvimento é no Mac, onde o build (que executa o `python.exe` da pasta) não roda.
- **Trade-off**: Sem atalho/desinstalador; download de ~360 MB descompactado; zip público (repo público).
- **Scope**: `construir_portatil.py`, `.github/workflows/windows.yml`, `release.py`, distribuição do app de desktop.
- **Date**: 2026-09-11
- **Status**: active

### AD-002
- **Decision**: As dependências da pasta Windows vêm só de `requirements-windows.lock` (versão exata + hash, gerado com `uv --python-platform x86_64-pc-windows-msvc --python-version 3.12`), e o Python fica na 3.12.x.
- **Reason**: Build reproduzível; `pip --platform` no Mac avalia marcadores do host e não resolve Windows; `rapidocr-onnxruntime` exige Python < 3.13.
- **Trade-off**: Atualizar dependência exige regenerar o lock; sem atualizações automáticas; preso à 3.12 até migrar o OCR.
- **Scope**: `requirements-windows.lock`, `requirements-desktop.txt`, `construir_portatil.py`.
- **Date**: 2026-09-11
- **Status**: active

## Handoff

- **Feature**: `.specs/features/build-windows/` — concluída e publicada
- **Phase / Task**: T1-T19 + correções; Verifier rodada 4 = PASS
- **Completed**: PR #1 mergeado na `main` (0724aa4); Release **v1.1** publicada com o zip (153,5 MB, sha256 23eff6c9…1c66); provas de produção nos runs 34846003592 (sem publicar), 34846236087 (publicou), 34846508283 (recusou republicar)
- **In-progress** (file:line): nenhum
- **Next step**: próxima sessão = investigar a **geração de JSON** (pedida para a v1.2). Relato do usuário em 2026-09-14: "o JSON acho que corrompeu porque não está fazendo" — ainda sem detalhe do que é o JSON, de quem o consome nem da mensagem de erro. Antes de especificar, levantar: (1) qual programa lê o JSON e se ele já existe hoje fora deste repositório; (2) um exemplo de JSON que funciona e um que "corrompeu"; (3) a mensagem/tela do erro; (4) se o JSON substitui ou acompanha o `.xlsx`, e se vale para Serra e Estado, inclusive ficha escaneada. Nada disso existe no código atual: hoje a saída é só `.xlsx` (aba Proventos). Ideias adiadas do build Windows seguem em `.specs/features/build-windows/context.md`
- **Blockers**: nenhum
- **Uncommitted files**: nenhum
- **Branch**: `main`
