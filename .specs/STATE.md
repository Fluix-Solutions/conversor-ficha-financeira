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

- **Feature**: `.specs/features/json-desktop/` — concluída e publicada (Verifier rodada 2 = PASS)
- **Phase / Task**: Execute concluído; Release **v1.2** publicada (run 34858280003, tag no commit b6a8dba)
- **Completed**: JSONDESK-01..08. Causa do "JSON corrompeu" (relato 2026-09-14, app do zip Windows): `Api.salvar` forçava `.xlsx` e gravava o JSON como `ficha.json.xlsx`. No Windows: 33 unitários + 13 e2e passaram com o `python.exe` da pasta (8 de `test_desktop.py`). Zip `Conversor-de-Ficha-Financeira-v1.2-windows-x64.zip`, 153,5 MB, sha256 907b32e9…3070
- **In-progress** (file:line): nenhum
- **Next step**: UAT do usuário — baixar o zip v1.2, desbloquear, extrair em Downloads, converter uma ficha escolhendo JSON e confirmar que sai `.json` e o sistema de cálculo importa
- **Blockers**: nenhum
- **Uncommitted files**: nenhum (pastas de skill `.agents/`, `.claude/skills/`, `.cursor/`, `.windsurf/` seguem fora do git)
- **Branch**: `main` (sincronizada com `origin/main`)
