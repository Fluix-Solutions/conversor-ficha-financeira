# Build Windows Tasks

## Execution Protocol (MANDATORY -- do not skip)

Implement these tasks with the `tlc-spec-driven` skill: **activate it by name and follow its Execute flow and Critical Rules.** Do not search for skill files by filesystem path. The skill is the source of truth for the full flow (per-task cycle, sub-agent delegation, adequacy review, Verifier, discrimination sensor).

**If the skill cannot be activated, STOP and tell the user - do not proceed without it.**

---

**Design**: `.specs/features/build-windows/design.md`
**Status**: In Progress (correções da 2ª rodada)

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

### Phase 4: Correções do Verifier (validation.md, 1ª rodada: FAIL)

```
T9 → T10 → T11 → T12 → T13 → T14
```

### Phase 5: Correções do Verifier (2ª rodada: FAIL)

```
T15 → T16
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

- [x] `tests/test_release.py`: `versao_app` lê `1.1` do `server.py` real; tag enviada igual à versão → devolve a tag; tag `v1.2` com versão `1.1` → erro com `1.2` e `1.1` na mensagem (WIN-19); tag `teste` e `v1` → erro de formato (edge case); sem tag → `v<versao>` (WIN-01); `nome_zip("v1.1") == "Conversor-de-Ficha-Financeira-v1.1-windows-x64.zip"` (WIN-11); notas contêm o SHA-256, `Windows 10/11 64 bits`, `.NET Framework 4.7.2`, `WebView2` (WIN-13); CLI `tag` sai com 1 em tag divergente
- [x] Gate check passes: `.venv/bin/python -m pytest tests -m "not e2e" -q`
- [x] Test count: 4 (T1) + 13 = 17 tests pass (9 funções; formato de tag parametrizado em 5 casos)

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

- [x] `tests/test_construir.py`: `conferir_sha256` aceita arquivo com o hash certo; com hash diferente levanta `RuntimeError` citando os dois hashes (WIN-03); `SHA256_EMBED` é o SHA-256 do `python-3.12.9-embed-amd64.zip` (`615861fb…5865`); o comando de instalação montado usa `--require-hashes` e `-r requirements-windows.lock` (WIN-16)
- [x] `main` chama `conferir_sha256` antes do `extractall`
- [x] Gate check passes: `.venv/bin/python -m pytest tests -m "not e2e" -q`
- [x] Test count: 17 + 5 = 22 tests pass (inclui `main` com download adulterado: nada extraído, pip não chamado)

**Tests**: unit
**Gate**: quick

**Commit**: `build(windows): verify embedded python hash and install from hashed lock`

---

### T4: Zip e registro do build

**What**: `construir_portatil.py --zip ARQ` gera o zip com raiz `Conversor de Ficha Financeira/` e imprime os pacotes com versão (`importlib.metadata`), tamanho e SHA-256.
**Where**: `construir_portatil.py`
**Depends on**: T3
**Reuses**: `construir_portatil.py:182-185`
**Requirement**: WIN-10, WIN-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/test_construir.py`: `zipar` numa pasta falsa gera zip cujas entradas começam todas por `Conversor de Ficha Financeira/` e contém `Conversor de Ficha Financeira/Conversor.bat` e `.../LEIA-ME.txt` (WIN-12); a função de registro imprime o tamanho e o SHA-256 real do zip (WIN-10)
- [x] Gate check passes (fim de fase): `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py`
- [x] Test count: 22 + 3 = 25 tests pass

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

- [x] `tests/test_portatil.py::test_ficha_texto`: convertendo `ficticia.pdf` com origem `estado`, a aba Proventos tem cabeçalho `Ano, Mês, VENCIMENTO, ADICIONAL TEMPO SERVICO, GRATIFICACAO`, 12 linhas de 2020 com os valores exatos esperados, e nenhuma coluna `IMPOSTO` (WIN-05)
- [x] O gerador só usa dados inventados (`FULANO DE TAL FICTICIO`) e grava num diretório temporário (WIN-09)
- [x] Gate check passes: `.venv/bin/python -m pytest tests -q`
- [x] Test count: 25 + 1 = 26 tests pass

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

- [x] `test_ficha_escaneada`: layout `OCR`, ano 2020, os 12 valores de cada rubrica batem (nome comparado sem diferenciar maiúsculas), nenhum aviso com `CONFERIR` (WIN-06)
- [x] `test_importa_tudo`: o alvo importa `pdfplumber, openpyxl, pymupdf, flask, webview, cv2, onnxruntime, rapidocr_onnxruntime, converter, server` e também `clr` quando o alvo é Windows (WIN-04)
- [x] `test_api_versao`: `server.py` sobe no alvo numa porta livre e `GET /api/versao` devolve `"ocr": true` (WIN-07)
- [x] `test_sem_pdf_real`: `git ls-files` não lista nenhum `.pdf` (WIN-09)
- [x] Gate check passes (fim de fase): `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py`
- [x] Test count: 26 + 4 = 30 tests pass

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

- [x] Gatilhos: tags `v[0-9]+.[0-9]+` e `v[0-9]+.[0-9]+.[0-9]+` + `workflow_dispatch`; `concurrency` por ref sem cancelar
- [x] `build` (`windows-latest`, `contents: read`): `release.py tag` → pytest unit → `construir_portatil.py` → pytest e2e com `--python-alvo` da pasta → `--zip` → `upload-artifact@v7` (`archive: false`, 14 dias)
- [x] `release` (`ubuntu-latest`, `needs: build`, `contents: write`): baixa o zip (`skip-decompress: true`, senão a action extrai o .zip), falha se `gh release view <tag>` achar Release (WIN-14), senão `gh release create <tag> <zip> --target <sha> --notes-file` com `release.py notas`
- [x] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`

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

- [x] README: gerar versão a partir do Mac (tag e botão manual → Release), atualizar o lock (comando do cabeçalho), subir `VERSAO` antes de cada Release (WIN-20)
- [x] CLAUDE.md: fluxo de build no Actions, repo `Fluix-Solutions/conversor-ficha-financeira`, `pip --platform` não resolve Windows no Mac, Python preso na 3.12, SHA-256 fixo do embed (WIN-21)
- [x] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`

**Tests**: none
**Gate**: build

**Commit**: `docs(windows): document the actions build, lock refresh and release flow`

---

### T9: Teste do `main` inteiro do build

**What**: Teste que roda `construir_portatil.main()` com rede e subprocessos simulados e confere o comando de instalação executado, o registro do `--zip` e os itens da pasta; `--python-alvo` passa a ser resolvido para caminho absoluto.
**Where**: `tests/test_construir.py`
**Depends on**: None
**Reuses**: `construir_portatil.py:main`
**Requirement**: WIN-02, WIN-10, WIN-16 (mutantes M5 e M6 do Verifier)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] O comando de instalação que o `main` executa contém `--require-hashes` e `-r requirements-windows.lock`, e nenhum `requirements-desktop.txt` (mata M5)
- [x] Com `--zip`, a saída traz o SHA-256 real do zip gerado e a lista de pacotes (mata M6)
- [x] A pasta montada tem `converter.py`, `server.py`, `app_desktop.py`, `web/index.html`, `Conversor.bat` e `LEIA-ME.txt`, e o zip tem a raiz `Conversor de Ficha Financeira/` (WIN-02)
- [x] `tests/conftest.py`: `alvo` vira caminho absoluto com `.absolute()` (`.resolve()` seguiria o link do python do venv até o Python do sistema — corrigido em commit próprio)
- [x] Mutantes M5 e M6 reaplicados num worktree descartável são mortos
- [x] Gate check passes: `.venv/bin/python -m pytest tests -m "not e2e" -q`
- [x] Test count: 30 + 1 = 31 tests pass

**Tests**: unit
**Gate**: quick

**Commit**: `test(windows): cover the build main flow, install command and zip log`

---

### T10: Tag já existente em outro commit

**What**: `release.py` falha quando a tag da Release já existe apontando para outro commit (`--sha-tag`, `--sha` no CLI `tag`).
**Where**: `release.py`
**Depends on**: T9
**Reuses**: `release.py:tag_release`
**Requirement**: WIN-23 (gap WIN-01 do Verifier)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `tests/test_release.py`: tag existente em outro commit → `ErroRelease` com os dois SHAs; mesmo commit → aceita; tag inexistente (SHA vazio) → aceita; CLI `tag --sha-tag X --sha Y` com X ≠ Y sai com 1
- [x] Gate check passes: `.venv/bin/python -m pytest tests -m "not e2e" -q`
- [x] Test count: 31 + 4 = 35 tests pass

**Tests**: unit
**Gate**: quick

**Commit**: `feat(release): refuse a release tag that points to another commit`

---

### T11: Opção `publicar` e checagem da tag no workflow

**What**: `workflow_dispatch` ganha o input booleano `publicar` (padrão `true`); o job `release` só roda quando é tag ou `publicar`; o passo da tag consulta o commit da tag existente e passa a `release.py`.
**Where**: `.github/workflows/windows.yml`
**Depends on**: T10
**Reuses**: `release.py tag --sha-tag --sha`
**Requirement**: WIN-01, WIN-22, WIN-23

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `workflow_dispatch.inputs.publicar` booleano, padrão `true`
- [x] Job `release` com `if: github.event_name == 'push' || inputs.publicar`
- [x] Passo da tag: `gh api repos/<repo>/commits/<tag>` (vazio se não existir — testando o código de saída: com tag inexistente o `gh` põe o JSON do erro no stdout) → `release.py tag ... --sha-tag --sha "$GITHUB_SHA"`
- [x] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`

**Tests**: none
**Gate**: build

**Commit**: `ci(windows): add publicar switch and stale-tag check to the workflow`

---

### T12: Documentação do disparo sem publicar

**What**: README explica testar sem publicar (`publicar` desmarcado / `gh workflow run -f publicar=false`); CLAUDE.md deixa de afirmar que o OCR já passou no Windows e registra a opção e a checagem de tag.
**Where**: `README.md`
**Depends on**: T11
**Reuses**: seções escritas na T8
**Requirement**: WIN-20, WIN-21

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] README: passo a passo de "testar sem publicar" e de baixar o zip do artefato
- [x] CLAUDE.md: frase sobre OCR no Windows corrigida; `publicar` e tag×commit documentados
- [x] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`

**Tests**: none
**Gate**: build

**Commit**: `docs(windows): document test runs without publishing`

---

### T13: Gatilho de pull request

**What**: O workflow roda também em pull request para a `main` que altera app, build ou testes (filtro `paths`); o job `release` não roda em PR.
**Where**: `.github/workflows/windows.yml`
**Depends on**: T12
**Reuses**: condição do job `release` da T11
**Requirement**: WIN-24

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `on.pull_request` com `branches: [main]` e `paths` cobrindo `converter.py`, `server.py`, `app_desktop.py`, `web/**`, `construir_portatil.py`, `release.py`, `requirements*`, `tests/**` e o próprio workflow
- [x] `release` continua com `if: github.event_name == 'push' || inputs.publicar` (falso em PR)
- [x] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`
- [x] Gate CI: o PR `build-windows → main` roda o job `build` verde no Windows e o job `release` fica pulado (run 34632113906)

**Tests**: none
**Gate**: build

**Commit**: `ci(windows): run the windows build on pull requests to main`

---

### T14: Dependência que só existe como código-fonte

**What**: `setuptools` entra no lock (`requirements-build-windows.txt`); o build instala primeiro o bloco do `setuptools` tirado do lock (com hash) e depois o lock inteiro com `--no-build-isolation`.
**Where**: `construir_portatil.py`
**Depends on**: T13
**Reuses**: `comando_instalar` (T3), lock (T1)
**Requirement**: WIN-16, WIN-17, WIN-25 (falha do 1º run no CI: `Cannot import 'setuptools.build_meta'` no `proxy-tools`)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Lock regenerado com `requirements-desktop.txt requirements-build-windows.txt`; `setuptools` presente com hash; versões já travadas mantidas
- [x] `tests/test_lock.py`: `setuptools` no lock; os pacotes de `requirements-build-windows.txt` também são cobertos
- [x] `tests/test_construir.py`: o `main` executa duas instalações, as duas com `--require-hashes`; a 1ª só com o bloco `setuptools==` tirado do lock (com `--hash`); a 2ª com `-r requirements-windows.lock` e `--no-build-isolation`
- [x] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`
- [x] Gate CI: job `build` verde no PR (run 34632113906; 1ª tentativa, run 34631686098, falhou no `proxy-tools` — motivo desta tarefa)

**Tests**: unit
**Gate**: build

**Commit**: `fix(windows): build sdist-only deps with the locked setuptools`

---

### T15: Checagem da tag só quando publica

**What**: No passo da tag, a consulta ao commit da tag existente e o `--sha-tag/--sha` só rodam quando a execução publica (`github.event_name == 'push'` ou `inputs.publicar`); PR e disparo sem publicar só calculam a tag.
**Where**: `.github/workflows/windows.yml`
**Depends on**: None
**Reuses**: passo da tag (T11)
**Requirement**: WIN-22, WIN-23, WIN-24 (gap G1 da 2ª rodada)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] Variável `PUBLICA` no passo da tag = `github.event_name == 'push' || inputs.publicar`; `gh api` + `--sha-tag` só com `PUBLICA=true`
- [x] Simulação local do passo: com `PUBLICA=false` e a tag existindo noutro commit, passa; com `PUBLICA=true`, falha mostrando os dois commits
- [x] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`
- [ ] Gate CI: PR verde

**Tests**: none
**Gate**: build

**Commit**: `fix(ci): check the release tag commit only on publishing runs`

---

### T16: Documentação: gatilho de PR e estado do OCR no Windows

**What**: README e CLAUDE.md citam o gatilho de PR e que o "Run workflow" só existe depois do merge; CLAUDE.md registra o OCR verde no Windows (run 34632113906) e a checagem de tag só em execução que publica; design.md registra T9-T16.
**Where**: `CLAUDE.md`
**Depends on**: T15
**Reuses**: seções da T8/T12
**Requirement**: WIN-20, WIN-21 (gap G2 da 2ª rodada)

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] CLAUDE.md: frase "No Windows, só depois do 1º run" substituída pelo resultado do run 34632113906; gatilho de PR; tag×commit só ao publicar
- [x] README: PR testa no Windows; "Run workflow" só após o workflow estar na `main`
- [x] design.md: seção com as correções T9-T16
- [x] Gate check passes: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`

**Tests**: none
**Gate**: build

**Commit**: `docs(windows): document the pr trigger and ci-verified ocr`

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
