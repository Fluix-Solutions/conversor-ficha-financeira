# Build Windows Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/build-windows/design.md`
**Status**: In Progress

---

## Test Coverage Matrix

> Generated from codebase, project guidelines, and spec - confirm before Execute. Guidelines found: `CLAUDE.md` ("Como validar uma conversão": soma dos 12 meses × coluna Total) - no test suite, no test config; strong defaults applied. Framework proposto: pytest (repo não tem testes).

| Code Layer | Required Test Type | Coverage Expectation | Location Pattern | Run Command |
| ---------- | ------------------ | -------------------- | ---------------- | ----------- |
| Regras de Release (`release.py`) | unit | Todos os ramos; 1:1 com WIN-11, WIN-13, WIN-19 + edge case de formato de tag | `tests/test_release.py` | `.venv/bin/python -m pytest tests -m "not e2e" -q` |
| Funções do build (`construir_portatil.py`) | unit | 1:1 com WIN-03, WIN-10, WIN-12, WIN-16 | `tests/test_construir.py` | `.venv/bin/python -m pytest tests -m "not e2e" -q` |
| Lock de dependências | unit | WIN-16 (versão exata + hash), WIN-17, WIN-18 | `tests/test_lock.py` | `.venv/bin/python -m pytest tests -m "not e2e" -q` |
| App empacotado (pasta / alvo) | e2e | WIN-04..07, WIN-09: caminho feliz + Descontos ausente + nenhum `CONFERIR` | `tests/test_portatil.py` | Mac: `.venv/bin/python -m pytest tests -q`; CI: `python -m pytest tests -m e2e --python-alvo <pasta>\python\python.exe --app-dir <pasta>` |
| Workflow (`.github/workflows/windows.yml`) | none (lint) | `actionlint` sem erros; comportamento (WIN-01, 08, 11, 14, 15) provado pela execução no CI | `.github/workflows/*.yml` | `actionlint` |
| Documentação | none | - | - | build gate only |

## Gate Check Commands

> Generated from codebase - confirm before Execute. Ambiente: `uv venv -p 3.12 .venv && uv pip install -p .venv -r requirements-desktop.txt -r requirements-dev.txt`.

| Gate Level | When to Use | Command |
| ---------- | ----------- | ------- |
| Quick | Tarefas só com testes unitários | `.venv/bin/python -m pytest tests -m "not e2e" -q` |
| Full | Tarefas com e2e | `.venv/bin/python -m pytest tests -q` |
| Build | Fim de fase / tarefas sem teste | `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py` (+ `actionlint` a partir da T7) |
| CI | Depois do push autorizado | `gh workflow run windows.yml --ref <branch>` + `gh run watch` (roda o build e os e2e com o Python da pasta num Windows) |

---

## Execution Plan

Phases are ordered and run sequentially - each phase completes before the next begins, and tasks within a phase execute in order.

### Phase 1: Regras e integridade do build

```
T1 → T2 → T3 → T4
```

### Phase 2: Verificação e2e

```
T5 → T6
```

### Phase 3: Pipeline e documentação

```
T7 → T8
```

---

## Task Breakdown

### T1: Lock das dependências do Windows

**What**: Gerar `requirements-windows.lock` (win_amd64/cp312, com hashes) e `requirements-dev.txt` (pytest), com testes que conferem o lock.
**Where**: `requirements-windows.lock`
**Depends on**: None
**Reuses**: `requirements-desktop.txt`, `requirements-base.txt`
**Requirement**: WIN-16, WIN-17, WIN-18

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Lock gerado com `uv pip compile requirements-desktop.txt --python-platform x86_64-pc-windows-msvc --python-version 3.12 --generate-hashes -o requirements-windows.lock`
- [x] `tests/test_lock.py`: todo pacote de `requirements-desktop.txt`/`requirements-base.txt` está no lock (WIN-17); toda linha de pacote tem `==` e ao menos um `--hash=sha256:` (WIN-16); o cabeçalho traz o comando de regeneração com `--python-platform x86_64-pc-windows-msvc`, `--python-version 3.12` e `--generate-hashes` (WIN-18); `pywebview`/`pythonnet` presentes e `pyobjc` ausente (lock é de Windows)
- [x] Gate check passes: `.venv/bin/python -m pytest tests -m "not e2e" -q`
- [x] Test count: 4 tests pass

**Tests**: unit
**Gate**: quick

**Commit**: `build(windows): add hashed dependency lock for the portable folder`

---

### T2: Regras de versão, tag e notas da Release

**What**: Criar `release.py` (versão do app, tag, nome do zip, notas) com CLI para o workflow.
**Where**: `release.py`
**Depends on**: T1
**Reuses**: `server.py:39` (`VERSAO`)
**Requirement**: WIN-11, WIN-13, WIN-19

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/test_release.py`: `versao_app` lê `1.1` do `server.py` real; tag enviada igual à versão → devolve a tag; tag `v1.2` com versão `1.1` → erro com `1.2` e `1.1` na mensagem (WIN-19); tag `teste` e `v1` → erro de formato (edge case); sem tag → `v<versao>` (WIN-01); `nome_zip("v1.1") == "Conversor-de-Ficha-Financeira-v1.1-windows-x64.zip"` (WIN-11); notas contêm o SHA-256, `Windows 10/11 64 bits`, `.NET Framework 4.7.2`, `WebView2` (WIN-13); CLI `tag` sai com 1 em tag divergente
- [ ] Gate check passes: `.venv/bin/python -m pytest tests -m "not e2e" -q`
- [ ] Test count: 4 (T1) + 9 = 13 tests pass

**Tests**: unit
**Gate**: quick

**Commit**: `feat(release): add version, tag and release-notes rules for windows builds`

---

### T3: Integridade no build (SHA-256 do Python + lock com hash)

**What**: `construir_portatil.py` confere o SHA-256 do embed zip antes de extrair, instala do lock com `--require-hashes` e o autoteste importa `pymupdf` em vez de `fitz`.
**Where**: `construir_portatil.py`
**Depends on**: T2
**Reuses**: `construir_portatil.py:91-133`
**Requirement**: WIN-03, WIN-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/test_construir.py`: `conferir_sha256` aceita arquivo com o hash certo; com hash diferente levanta `RuntimeError` citando os dois hashes (WIN-03); `SHA256_EMBED` é o SHA-256 do `python-3.12.9-embed-amd64.zip` (`615861fb…5865`); o comando de instalação montado usa `--require-hashes` e `-r requirements-windows.lock` (WIN-16)
- [ ] `main` chama `conferir_sha256` antes do `extractall`
- [ ] Gate check passes: `.venv/bin/python -m pytest tests -m "not e2e" -q`
- [ ] Test count: 13 + 4 = 17 tests pass

**Tests**: unit
**Gate**: quick

**Commit**: `build(windows): verify embedded python hash and install from hashed lock`

---

### T4: Zip e registro do build

**What**: `construir_portatil.py --zip ARQ` gera o zip com raiz `Conversor de Ficha Financeira/` e imprime `pip freeze`, tamanho e SHA-256.
**Where**: `construir_portatil.py`
**Depends on**: T3
**Reuses**: `construir_portatil.py:182-185`
**Requirement**: WIN-10, WIN-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/test_construir.py`: `zipar` numa pasta falsa gera zip cujas entradas começam todas por `Conversor de Ficha Financeira/` e contém `Conversor de Ficha Financeira/Conversor.bat` e `.../LEIA-ME.txt` (WIN-12); a função de registro imprime o tamanho e o SHA-256 real do zip (WIN-10)
- [ ] Gate check passes (fim de fase): `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py`
- [ ] Test count: 17 + 3 = 20 tests pass

**Tests**: unit
**Gate**: build

**Commit**: `build(windows): zip the portable folder and log packages, size and sha256`

---

### T5: Ficha fictícia e conversão de texto no alvo

**What**: Criar o gerador da ficha fictícia, o conversor-no-alvo e o `conftest.py` (`--python-alvo`, `--app-dir`, marcador `e2e`), com o teste da ficha de texto.
**Where**: `tests/ficha_ficticia.py`
**Depends on**: None
**Reuses**: spike validado em 2026-09-11 (colunas espaçadas; 300 DPI)
**Requirement**: WIN-05, WIN-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `tests/test_portatil.py::test_ficha_texto`: convertendo `ficticia.pdf` com origem `estado`, a aba Proventos tem cabeçalho `Ano, Mês, VENCIMENTO, ADICIONAL TEMPO SERVICO, GRATIFICACAO`, 12 linhas de 2020 com os valores exatos esperados, e nenhuma coluna `IMPOSTO` (WIN-05)
- [ ] O gerador só usa dados inventados (`FULANO DE TAL FICTICIO`) e grava num diretório temporário (WIN-09)
- [ ] Gate check passes: `.venv/bin/python -m pytest tests -q`
- [ ] Test count: 20 + 1 = 21 tests pass

**Tests**: e2e
**Gate**: full

**Commit**: `test(windows): add synthetic ficha and text conversion check on target python`

---

### T6: Verificações do app empacotado (OCR, imports, servidor, privacidade)

**What**: Completar `tests/test_portatil.py` com OCR da ficha escaneada, importações, `/api/versao` e ausência de PDF real no repositório.
**Where**: `tests/test_portatil.py`
**Depends on**: T5
**Reuses**: `server.py:268-271` (`PORT`), `converter.py:637` (`ocr_status`)
**Requirement**: WIN-04, WIN-06, WIN-07, WIN-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `test_ficha_escaneada`: layout `OCR`, ano 2020, os 12 valores de cada rubrica batem (nome comparado sem diferenciar maiúsculas), nenhum aviso com `CONFERIR` (WIN-06)
- [ ] `test_importa_tudo`: o alvo importa `pdfplumber, openpyxl, pymupdf, flask, webview, cv2, onnxruntime, rapidocr_onnxruntime, converter, server` e também `clr` quando o alvo é Windows (WIN-04)
- [ ] `test_api_versao`: `server.py` sobe no alvo numa porta livre e `GET /api/versao` devolve `"ocr": true` (WIN-07)
- [ ] `test_sem_pdf_real`: `git ls-files` não lista nenhum `.pdf` (WIN-09)
- [ ] Gate check passes (fim de fase): `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py`
- [ ] Test count: 21 + 4 = 25 tests pass

**Tests**: e2e
**Gate**: build

**Commit**: `test(windows): verify ocr, imports and server on the packaged python`

---

### T7: Workflow de build e Release

**What**: Criar `.github/workflows/windows.yml` com os jobs `build` (Windows) e `release` (Ubuntu).
**Where**: `.github/workflows/windows.yml`
**Depends on**: None
**Reuses**: `release.py`, `construir_portatil.py --zip`, `tests/`
**Requirement**: WIN-01, WIN-02, WIN-08, WIN-10, WIN-11, WIN-14, WIN-15

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Gatilhos: tags `v[0-9]+.[0-9]+` e `v[0-9]+.[0-9]+.[0-9]+` + `workflow_dispatch`; `concurrency` por ref sem cancelar
- [ ] `build` (`windows-latest`, `contents: read`): `release.py tag` → pytest unit → `construir_portatil.py` → pytest e2e com `--python-alvo` da pasta → `--zip` → `upload-artifact@v7` (`archive: false`, 14 dias)
- [ ] `release` (`ubuntu-latest`, `needs: build`, `contents: write`): baixa o zip, falha se `gh release view <tag>` achar Release (WIN-14), senão `gh release create <tag> <zip> --target <sha> --notes-file` com `release.py notas`
- [ ] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`

**Tests**: none
**Gate**: build

**Commit**: `ci(windows): build, verify and release the portable folder on github actions`

---

### T8: Documentação do fluxo

**What**: README e CLAUDE.md descrevem o novo fluxo, o lock e as pegadinhas.
**Where**: `README.md`
**Depends on**: T7
**Reuses**: seção "Levar para outros computadores" do README; seção "Pasta portátil" do CLAUDE.md
**Requirement**: WIN-20, WIN-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] README: gerar versão a partir do Mac (tag e botão manual → Release), atualizar o lock (comando do cabeçalho), subir `VERSAO` antes de cada Release (WIN-20)
- [ ] CLAUDE.md: fluxo de build no Actions, repo `Fluix-Solutions/conversor-ficha-financeira`, `pip --platform` não resolve Windows no Mac, Python preso na 3.12, SHA-256 fixo do embed (WIN-21)
- [ ] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`

**Tests**: none
**Gate**: build

**Commit**: `docs(windows): document the actions build, lock refresh and release flow`

---

## Phase Execution Map

```
Phase 1 → Phase 2 → Phase 3

Phase 1:  T1 ------→ T2 ------→ T3 ------→ T4
Phase 2:  T5 ------→ T6
Phase 3:  T7 ------→ T8
```

Execution is strictly sequential. 8 tarefas cabem num único lote → execução inline, sem sub-agentes. Depois da T8: push da branch (**precisa de autorização explícita**), gate CI no Windows, e o Verifier independente.

---

## Task Granularity Check

| Task | Scope | Status |
| ---- | ----- | ------ |
| T1: Lock | 1 arquivo gerado + seu teste | ✅ Granular |
| T2: `release.py` | 1 módulo pequeno (4 funções coesas) | ✅ Granular |
| T3: Integridade no build | 2 mudanças coesas no mesmo arquivo (hash do embed + hash do lock) | ⚠️ OK (coeso) |
| T4: Zip e registro | 1 função + opção de CLI | ✅ Granular |
| T5: Ficha fictícia + harness | gerador + conversor-no-alvo + conftest, inseparáveis para o 1º e2e rodar | ⚠️ OK (merge backward para ser testável) |
| T6: Verificações e2e | 4 testes no mesmo arquivo | ✅ Granular |
| T7: Workflow | 1 arquivo | ✅ Granular |
| T8: Docs | 2 arquivos de documentação do mesmo fluxo | ⚠️ OK (coeso) |

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
| ---- | ---------------------- | ------------- | ------ |
| T1 | None | início da Fase 1 | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T2 | T2 → T3 | ✅ Match |
| T4 | T3 | T3 → T4 | ✅ Match |
| T5 | None (Fase 1 concluída) | início da Fase 2 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | None (Fase 2 concluída) | início da Fase 3 | ✅ Match |
| T8 | T7 | T7 → T8 | ✅ Match |

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
| ---- | --------------------------- | --------------- | --------- | ------ |
| T1 | Lock de dependências | unit | unit | ✅ OK |
| T2 | Regras de Release | unit | unit | ✅ OK |
| T3 | Funções do build | unit | unit | ✅ OK |
| T4 | Funções do build | unit | unit | ✅ OK |
| T5 | App empacotado (alvo) | e2e | e2e | ✅ OK |
| T6 | App empacotado (alvo) | e2e | e2e | ✅ OK |
| T7 | Workflow | none (lint) | none | ✅ OK |
| T8 | Documentação | none | none | ✅ OK |
