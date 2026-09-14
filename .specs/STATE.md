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

- **Feature**: `.specs/features/build-windows/`
- **Phase / Task**: Execute concluído (T1-T16); Verifier rodada 3 = PASS
- **Completed**: T1-T16; CI Windows verde no PR #1 (runs 34632113906, 34633772453)
- **In-progress** (file:line): nenhum
- **Next step**: usuário faz UAT do zip do artefato com Smart App Control; depois merge do PR #1 e publicação da v1.1 (tag ou Run workflow com `publicar`) — conferências pós-merge listadas em `validation.md`
- **Blockers**: nenhum (merge e publicação dependem de ok explícito do usuário)
- **Uncommitted files**: nenhum
- **Branch**: `build-windows` (PR #1 → `main`)
