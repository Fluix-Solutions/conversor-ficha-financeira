# Build Windows Validation

## Validation: build-windows - FAIL

**Date**: 2026-09-11
**Spec**: `.specs/features/build-windows/spec.md`
**Diff range**: `main..build-windows` (4888924..c19ed46, 9 commits)
**Verifier**: sub-agente independente (autor ≠ verificador)

Veredito: **FAIL** — o gate passa (30/30) e a lógica nova está bem testada, mas dois mutantes sobreviveram (a ligação de WIN-16 e de WIN-10 dentro do `main()` não tem teste), o WIN-20 não está atendido e há um caso de borda do WIN-01 em que a Release fica apontando para o commit errado. A execução real no Windows (GitHub Actions) ainda não aconteceu; os ACs que só ela prova foram julgados pela estrutura do workflow.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1 Lock | ✅ Done | Lock regenerado no rascunho com o comando do cabeçalho: **idêntico** (`git diff` vazio) |
| T2 `release.py` | ✅ Done | - |
| T3 Integridade | ⚠️ Partial | `comando_instalar` testado, mas a chamada em `construir_portatil.py:187` não (mutante M5 sobreviveu) |
| T4 Zip e registro | ⚠️ Partial | `zipar`/`registrar` testados, mas o ramo `--zip` do `main` (`construir_portatil.py:239-241`) não (mutante M6 sobreviveu) |
| T5 Ficha fictícia | ✅ Done | - |
| T6 Verificações e2e | ✅ Done | Rodado com o alvo = `.venv` (Mac); com o Python da pasta, pendente do CI |
| T7 Workflow | ⚠️ Partial | `actionlint` limpo; caso de tag pré-existente no disparo manual (gap 3) |
| T8 Docs | ⚠️ Partial | README não diz como testar o build sem publicar (WIN-20) |

---

## Spec-Anchored Acceptance Criteria

Legenda: **CI** = coberto pela estrutura do workflow; evidência de execução pendente do CI (não é gap por si só).

| Criterion | Spec-defined outcome | `file:line` + assertion / linha do workflow | Result |
| --------- | -------------------- | ------------------------------------------- | ------ |
| WIN-01 disparo manual | Build em `windows-latest`; Release `v<server.VERSAO>` no commit escolhido | `.github/workflows/windows.yml:16` `workflow_dispatch`; `:27` `runs-on: windows-latest`; `:57` `TAG=$(python release.py tag)`; `tests/test_release.py:40` - `tag_release(None, "1.1") == "v1.1"`; `.github/workflows/windows.yml:116-117` `gh release create "$TAG" ... --target "$GITHUB_SHA"` | ❌ GAP (CI + borda): se a tag `v<VERSAO>` já existir sem Release (ex.: build de tag que falhou), o `gh release create` **ignora** `--target` (só vale para tag nova — confirmado em `gh release create --help`) e a Release fica na tag antiga, com um zip de outro commit |
| WIN-02 conteúdo da pasta | Python embutido 3.12.9 amd64 + `converter.py`, `server.py`, `app_desktop.py`, `web/`, `Conversor.bat`, `LEIA-ME.txt` | `construir_portatil.py:31-32` (PY/URL amd64), `:48-49` (ARQUIVOS/PASTAS), `:191-197` (cópia + .bat + LEIA-ME); `tests/test_construir.py:35-38` - `cp.PY == "3.12.9"` e `SHA256_EMBED == "6158…5865"` (hash conferido contra o download real do python.org: bate) | ✅ CI (código; nenhum teste afirma a presença de `app_desktop.py`/`web/`/`.bat`/`LEIA-ME` na pasta gerada — sugestão de reforço, baixa severidade) |
| WIN-03 SHA-256 diferente | Falha antes de instalar qualquer dependência | `construir_portatil.py:153` `conferir_sha256` antes do `extractall` (`:154-155`); `tests/test_construir.py:30-31` - `real in str(e.value)` / `esperado in str(e.value)`; `tests/test_construir.py:97-100` - `pytest.raises(RuntimeError)`, `not (... "python.exe").exists()`, `chamou_pip == []` | ✅ PASS (M1 morto) |
| WIN-04 importações | Importa `pdfplumber, openpyxl, pymupdf, flask, webview, cv2, onnxruntime, rapidocr_onnxruntime, clr, converter, server`; falha se alguma falhar | `tests/test_portatil.py:19-20` (lista) + `:64` (`clr` quando `win32`); `:75` - `sorted(out["mods"]) == sorted(esperados)`; `:76` - `{m: v ... if v != "ok"} == {}` | ✅ PASS (no Mac; `clr` só no Windows → execução com o Python da pasta pendente do CI) |
| WIN-05 ficha de texto | Aba Proventos com exatamente os valores por Ano+Mês e rubrica | `tests/test_portatil.py:30-31` - `cab == ["Ano", "Mês", "VENCIMENTO", "ADICIONAL TEMPO SERVICO", "GRATIFICACAO"]`; `:33` - `[(ln[0], ln[1]) ...] == [(2020, m) for m in MESES]`; `:35-39` - `ln[2:] == [...]`; `:40-41` âncoras `1234.56` / `461.00` | ✅ PASS (M7 morto) |
| WIN-06 ficha escaneada | layout `OCR`, 12 valores de cada rubrica, nenhum `CONFERIR` | `tests/test_portatil.py:49` - `resumo["layout"] == "OCR"`; `:51` - `[a ... if "CONFERIR" in a] == []`; `:54` - `[c.upper() for c in cab[2:]] == esperadas`; `:57` - `[ln[2 + j] for ln in linhas] == ficha["rubricas"][nome]` | ✅ PASS (M7 morto) |
| WIN-07 `/api/versao` | `"ocr": true` | `tests/test_portatil.py:106` - `dados["ocr"] is True` | ✅ PASS (M8 morto) |
| WIN-08 falha não publica | Nenhum artefato nem Release se qualquer passo falhar | `.github/workflows/windows.yml:31-33` (`shell: bash` → `-eo pipefail`); upload só no fim (`:78-83`, condição implícita `success()`); `:86` `needs: build`; `:83` `if-no-files-found: error` | ✅ CI |
| WIN-09 só fichas fictícias | Nenhum PDF real no repo nem nos logs | `tests/test_portatil.py:115` - `r.stdout.strip() == ""` (`git ls-files *.pdf *.PDF`); `tests/ficha_ficticia.py:61` `FULANO DE TAL FICTICIO`, dados inventados (`:25-31`) | ✅ PASS |
| WIN-10 registro no log | Pacotes com versão, tamanho e SHA-256 do zip | `tests/test_construir.py:73-74` - `f"pytest=={version('pytest')}" in saida.splitlines()`; `:82-83` - sha256 e `"2.5 MB" in saida`; chamada em `construir_portatil.py:239-241`; workflow `:70` `--zip` | ❌ GAP: função testada, mas a chamada no `main` não (M6 sobreviveu); log real pendente do CI |
| WIN-11 Release por tag | Release com a tag + `Conversor-de-Ficha-Financeira-<tag>-windows-x64.zip` | `tests/test_release.py:44` - `nome_zip("v1.1") == "Conversor-de-Ficha-Financeira-v1.1-windows-x64.zip"`; `.github/workflows/windows.yml:13-15`, `:59`, `:80-81` (`archive: false` → nome do artefato = nome do arquivo, conferido no `action.yml` do upload-artifact@v7), `:100-104`, `:116` | ✅ CI |
| WIN-12 pasta raiz única | `Conversor de Ficha Financeira/` com `.bat` e `LEIA-ME.txt` no 1º nível | `tests/test_construir.py:60` - `all(n.startswith("Conversor de Ficha Financeira/") for n in nomes)`; `:61-62` - `.bat` e `LEIA-ME.txt` in `nomes` | ✅ PASS (M3 morto) |
| WIN-13 notas | SHA-256 + Windows 10/11 64 bits, .NET Framework 4.7.2+, WebView2 Runtime | `tests/test_release.py:50-53` - `sha in notas`, `"Windows 10/11 64 bits"`, `".NET Framework 4.7.2"`, `"WebView2"`; `tests/test_release.py:79` - SHA-256 real do arquivo na saída do CLI; workflow `:115` | ✅ PASS |
| WIN-14 Release existente | Falhar sem alterar Release nem zip | `.github/workflows/windows.yml:106-111` - `if gh release view "$TAG"; then ... exit 1` antes do `create` | ✅ CI |
| WIN-15 permissões | `contents: write` só no job de publicação | `.github/workflows/windows.yml:22-23` (padrão `read`), `:29-30` (build `read`), `:89-90` (release `write`) | ✅ CI |
| WIN-16 lock com hash | Instala do lock (versão exata + hash, win_amd64/cp312) com `--require-hashes` | `tests/test_lock.py:58` - `sem_hash == []`; `:62` - toda linha casa `nome==versão`; `tests/test_construir.py:43` - `"--require-hashes" in cmd`; `:45` - `Path(cmd[i + 1]) == RAIZ / "requirements-windows.lock"`; chamada em `construir_portatil.py:187` | ❌ GAP: M5 sobreviveu — trocar a linha 187 pelo `pip install -r requirements-desktop.txt` antigo passa em todos os testes (e no CI o build ficaria verde) |
| WIN-17 lock cobre requirements | Todo pacote de `requirements-desktop.txt` e `requirements-base.txt` no lock | `tests/test_lock.py:51` - `faltando == set()` (+ `:49-50` sanidade do conjunto pedido) | ✅ PASS |
| WIN-18 comando único no Mac | Um comando regenera o lock para Windows | `tests/test_lock.py:68-72` - comando no cabeçalho com `--python-platform x86_64-pc-windows-msvc`, `--python-version 3.12`, `--generate-hashes`, `-o requirements-windows.lock`; execução real no rascunho: lock regenerado **idêntico** | ✅ PASS |
| WIN-19 tag ≠ VERSAO | Falha antes do build mostrando os dois valores | `tests/test_release.py:29-30` - `"1.2" in str(e.value)` e `"1.1" in str(e.value)`; `:61-62` - CLI `returncode == 1` e `"9.9" in r.stderr and "1.1" in r.stderr`; workflow `:55` é o 1º passo após checkout/setup | ✅ PASS (M2 morto) |
| WIN-20 README | Gerar versão pelo Mac (tag → Release), **testar o build sem publicar**, atualizar o lock | `README.md:115-141` (gerar versão), `README.md:143-157` (lock); nada sobre testar o build sem publicar — e o workflow não tem caminho que não publique | ❌ GAP |
| WIN-21 CLAUDE.md | Fluxo novo, repo `Fluix-Solutions/...`, `pip --platform`, Python preso na 3.12 | `CLAUDE.md:131-170`; `:135` repo; `:157-161` `pip --platform`; `:162-163` 3.12/`rapidocr-onnxruntime` | ✅ PASS (obs.: `CLAUDE.md:165` afirma "Mac e Windows" para os testes de OCR, mas o Windows ainda não rodou) |

**Status**: ❌ Gaps presentes (WIN-01 borda, WIN-10, WIN-16, WIN-20). Nenhum spec-precision gap bloqueante; observação: WIN-13 testa `"WebView2"`, não `"WebView2 Runtime"` (o texto das notas tem os dois).

---

## Discrimination Sensor

Rodado num `git worktree` descartável em `scratchpad/wt`, com `.venv/bin/python` (caminho absoluto) e `PYTHONDONTWRITEBYTECODE=1` (a 1ª rodada foi descartada: M1/M2 não mudam o tamanho do arquivo e um `.pyc` velho contaminou o M2). `git status --porcelain` da árvore real idêntico antes e depois; worktree removido.

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M1 | `construir_portatil.py:90` | `real != esperado` → `real == esperado` | ✅ Killed (3 testes) |
| M2 | `release.py:42` | igualdade tag × VERSAO desligada (`if False:`) | ✅ Killed (2 testes) |
| M3 | `construir_portatil.py:110` | `relative_to(alvo.parent)` → `relative_to(alvo)` (zip sem pasta raiz) | ✅ Killed |
| M4 | `construir_portatil.py:101` | remove `--require-hashes` de `comando_instalar` | ✅ Killed |
| M5 | `construir_portatil.py:187` | `main` volta a instalar `requirements-desktop.txt` sem lock nem hash | ❌ Survived → fix task 2 |
| M6 | `construir_portatil.py:241` | `main --zip` deixa de chamar `registrar` | ❌ Survived → fix task 3 |
| M7 | `tests/ficha_ficticia.py:56` | PDF recebe +0,01 em abril, esperado inalterado (e2e texto + OCR) | ✅ Killed (2 testes e2e) |
| M8 | `converter.py:642` | `ocr_status` responde `"ocr": False` | ✅ Killed (`test_api_versao_informa_ocr`) |

**Sensor depth**: lightweight (8 mutações)
**Result**: 6/8 mortos - FAIL

---

## Interactive UAT Results

Não realizado (infra de build). O UAT do Smart App Control com o zip baixado já está previsto nas Success Criteria da spec, antes de divulgar a 1ª Release.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ `release.py` com 4 funções coesas; `construir_portatil.py` ganhou só o pedido |
| Surgical changes | ✅ `converter.py`, `server.py`, `app_desktop.py`, `web/`, `Dockerfile`, `requirements*.txt` intocados (`git diff main..HEAD` = 0 linhas) |
| No scope creep | ✅ |
| Matches patterns | ✅ Português, comentários explicando o porquê, só biblioteca padrão onde precisa |
| Spec-anchored outcome check | ✅ asserções miram o valor da spec (nome exato do zip, valores exatos, `"ocr" is True`, dois valores na mensagem) |
| Per-layer Coverage Expectation | ❌ funções do build 1:1, mas a orquestração do `main` (WIN-10/WIN-16) sem teste — M5/M6 |
| Every test maps to a spec requirement | ✅ (os 30 mapeiam para AC ou Done-when; `test_lock_e_de_windows` = Done-when da T1) |
| Documented guidelines followed: `CLAUDE.md` ("Como validar uma conversão": soma dos 12 meses × Total) | ✅ refletido no `CONFERIR` do WIN-06 |

Riscos específicos de Windows revistos (sem gap):

- Suíte unitária num Python só com pytest: rodada num venv limpo (`pytest`, `pluggy`, `iniconfig`, `packaging`, `pygments`) → **25 passed, 5 deselected**. Nenhum teste unitário importa dependência do app.
- Encoding: o alvo só imprime JSON ASCII (`tests/_converter_alvo.py:23`, `tests/ficha_ficticia.py:106`), e `tests/conftest.py:48-49` decodifica com `errors="replace"`. As mensagens com acento do `release.py` vão para stderr e são lidas com a mesma página de código dos dois lados.
- `--python-alvo` relativo com espaço (`windows.yml:75`): o fixture `alvo` não faz `.resolve()` (`tests/conftest.py:37`), e `test_api_versao_informa_ocr` passa `cwd=app_dir` (`tests/test_portatil.py:90`). No Windows o executável relativo é resolvido pelo diretório do processo pai (docs do `subprocess`), então funciona; num POSIX quebraria. É frágil, mas não é defeito no alvo do CI.
- `core.autocrlf=true` no runner Windows: todo arquivo lido pelos testes usa `read_text` (newline universal); o pip aceita o lock com CRLF.
- Actions: `checkout@v7`, `setup-python@v7`, `upload-artifact@v7`, `download-artifact@v8` existem; `archive: false` e `skip-decompress: true` existem nos `action.yml`; com `skip-decompress`, o toolkit grava o arquivo com o nome do `Content-Disposition` → `dist/<zip>`.
- SHA-256 fixado conferido contra o download real do `python-3.12.9-embed-amd64.zip`: `615861fb…5865` ✅.

---

## Edge Cases

- [x] python.org / bootstrap.pypa.io / PyPI fora do ar: `urllib` levanta e o pip roda com `check=True` (`construir_portatil.py:84`, `:182-183`, `:187`); `construir_portatil.py:83` imprime o nome do arquivo sendo baixado e o pip nomeia o pacote. Coberto por WIN-08 (CI).
- [x] Tag fora de `vX.Y`/`vX.Y.Z` não roda: `.github/workflows/windows.yml:13-15` (padrões `v[0-9]+.[0-9]+` e `v[0-9]+.[0-9]+.[0-9]+`; o `.` é literal no filtro do Actions); defesa extra em `release.py:39-41` + `tests/test_release.py:33-36` (`teste`, `v1`, `1.1`, `v1.1.1.1`, `v1.1-rc1`). CI.
- [x] Duas tags ao mesmo tempo, independentes: `.github/workflows/windows.yml:18-20` (`group: windows-${{ github.ref }}`, `cancel-in-progress: false`) → um grupo por tag. CI. Obs.: tag `v1.1` e disparo manual no `main` com `VERSAO = 1.1` caem em grupos diferentes e podem correr juntos; o 2º `gh release create` é recusado pelo GitHub (tag já tem Release), então a Release existente não muda.
- [x] Escaneada com `CONFERIR` → falha: `tests/test_portatil.py:51`.

---

## Gate Check

- **Gate command**: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`
- **Result**: 30 passed, 0 failed, 0 skipped (e2e ~7 s); `py_compile` ok; `actionlint` sem erros
- **Test count before feature**: 0 (o repo não tinha testes)
- **Test count after feature**: 30
- **Delta**: +30
- **Skipped tests**: nenhum
- **Failures**: nenhuma
- Extra: `-m "not e2e"` num venv só com pytest (simula o host do CI) → 25 passed, 5 deselected

---

## Fix Plans

### Fix 1: não existe build de teste que não publique (WIN-20) — e o gate CI da tasks.md publica de verdade

- **Root cause**: a spec decidiu que o `workflow_dispatch` também publica (WIN-01), então todo run verde cria tag + Release. O README (`README.md:115-141`) não traz o "como testar o build sem publicar" que o WIN-20 pede, e não há como trazer sem mudar o workflow. **Consequência imediata**: o gate "CI" da `tasks.md:38` (`gh workflow run windows.yml --ref <branch>`) criaria a tag `v1.1` e a Release `v1.1` **permanentes** a partir da branch `build-windows` (repo público, hoje sem tags nem Releases), e depois disso só dá para publicar subindo o `VERSAO`.
- **Fix task**: decisão do usuário antes do 1º push/run. Opções: (a) input `publicar` (boolean, padrão `false`) no `workflow_dispatch`, com o job `release` condicionado a `github.ref_type == 'tag' || inputs.publicar`; ou (b) gatilho sem publicação (ex.: push em branch/`pull_request`) que roda só o job `build`. Documentar no README. Verify: run manual sem `publicar` fica verde e não cria tag/Release.
- **Priority**: Major (urgente: vale antes de rodar o gate CI)

### Fix 2: a instalação pelo lock no `main` não tem teste (WIN-16, M5)

- **Root cause**: `tests/test_construir.py:41-46` testa `comando_instalar`, mas nada garante que `main` (`construir_portatil.py:187`) o use.
- **Fix task**: estender o teste do `main` com um zip falso de hash **certo** (monkeypatch `cp.SHA256_EMBED`) e capturar as chamadas de `subprocess.run`, afirmando que uma delas é `cp.comando_instalar(...)`; ou comparar no CI a lista do `registrar` com o lock (isso também cobre a Success Criteria "mesma lista de pacotes"). Verify: M5 passa a ser morto.
- **Priority**: Major

### Fix 3: o ramo `--zip` do `main` não tem teste (WIN-10, M6)

- **Root cause**: `zipar`/`registrar` são testados isoladamente; `construir_portatil.py:239-241` não.
- **Fix task**: no mesmo teste do `main` (Fix 2), rodar com `--zip` e afirmar que o zip existe com a raiz certa e que a saída tem `sha256:` e `tamanho do zip:`. Verify: M6 passa a ser morto.
- **Priority**: Minor

### Fix 4: disparo manual com tag `v<VERSAO>` já existente sem Release (WIN-01)

- **Root cause**: `gh release create --target` só vale quando a tag ainda não existe (`.github/workflows/windows.yml:116-117`). Cenário real: a tag `v1.2` falha no build, o erro é corrigido no `main` e o "Run workflow" é disparado → a Release `v1.2` fica na tag do commit quebrado, com o zip do `main`.
- **Fix task**: no job `release` (ou no passo da tag), quando `github.ref_type != 'tag'`, consultar `gh api repos/$GH_REPO/git/ref/tags/$TAG` e falhar se a tag existir apontando para commit ≠ `$GITHUB_SHA`, com mensagem clara. Verify: revisão do workflow + `actionlint`; execução no CI.
- **Priority**: Minor

### Fix 5 (baixa): reforços de evidência

- WIN-02: afirmar, no CI, que a pasta tem `app_desktop.py`, `web/`, `Conversor.bat` e `LEIA-ME.txt` (ex.: teste e2e que confere `--app-dir`).
- `CLAUDE.md:165`: tirar o "(Mac e Windows)" até o CI rodar.
- `tests/conftest.py:37`: `.resolve()` no `--python-alvo` para não depender da regra de resolução do Windows.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| WIN-01 | Implementing | Implementing (CI pendente + Fix 4) |
| WIN-02 | Implementing | Implementing (CI pendente) |
| WIN-03 | Implementing | ✅ Verified |
| WIN-04 | Implementing | ✅ Verified (execução com o Python da pasta pendente do CI) |
| WIN-05 | Implementing | ✅ Verified |
| WIN-06 | Implementing | ✅ Verified |
| WIN-07 | Implementing | ✅ Verified |
| WIN-08 | Implementing | Implementing (CI pendente) |
| WIN-09 | Implementing | ✅ Verified |
| WIN-10 | Implementing | Implementing — ❌ Needs Fix (Fix 3) |
| WIN-11 | Implementing | Implementing (CI pendente) |
| WIN-12 | Implementing | ✅ Verified |
| WIN-13 | Implementing | ✅ Verified |
| WIN-14 | Implementing | Implementing (CI pendente) |
| WIN-15 | Implementing | Implementing (CI pendente) |
| WIN-16 | Implementing | Implementing — ❌ Needs Fix (Fix 2) |
| WIN-17 | Implementing | ✅ Verified |
| WIN-18 | Implementing | ✅ Verified |
| WIN-19 | Implementing | ✅ Verified |
| WIN-20 | Implementing | Implementing — ❌ Needs Fix (Fix 1) |
| WIN-21 | Implementing | ✅ Verified |

No `spec.md` só os ✅ viraram `Verified`; o resto segue `Implementing`.

---

## Summary

**Overall**: ❌ Not Ready

**Spec-anchored check**: 12/21 ACs verificados com asserção que bate com a spec; 5 cobertos só pela estrutura do workflow (CI pendente); 4 com gap (WIN-01 borda, WIN-10, WIN-16, WIN-20); 0 spec-precision gaps bloqueantes
**Sensor**: 6/8 mutações mortas (M5 e M6 sobreviveram)
**Gate**: 30 passed, 0 failed; `py_compile` e `actionlint` ok

**What works**: regras de tag/versão/nome/notas (`release.py`), SHA-256 do Python embutido (conferido contra o arquivo real), lock com hash reproduzível (regenerado idêntico), zip com pasta raiz única, e2e de ficha fictícia de texto e escaneada com valores exatos, importações e `/api/versao`; permissões mínimas e "nada publica se falhar" no workflow; arquivos fora do escopo intocados.

**Issues found**: Fix 1 (sem build de teste que não publique; o gate CI planejado publicaria a `v1.1` de verdade), Fix 2 (M5), Fix 3 (M6), Fix 4 (tag pré-existente no disparo manual), Fix 5 (reforços de baixa severidade).

**Next steps**: decidir o Fix 1 com o usuário **antes** de autorizar o push e o `gh workflow run`; implementar os Fixes 2-4; reverificar; depois rodar o CI no Windows para fechar WIN-01/02/08/10/11/14/15.
