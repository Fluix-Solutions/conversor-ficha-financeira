# Build Windows Validation (rodada 2)

## Validation: build-windows - FAIL

**Date**: 2026-09-11
**Spec**: `.specs/features/build-windows/spec.md` (WIN-01..WIN-25)
**Diff range**: feature inteira `main..build-windows` (4888924..a804d83, 17 commits); correções desde a rodada 1: `053e45e..a804d83` (e614080, f1d00c5, 4d794aa, 39c7e9e, 6ebf207, 3ae38e7, c32eb9e, a804d83)
**Verifier**: sub-agente independente (autor ≠ verificador), rodada 2 de no máximo 3

Veredito: **FAIL**. Todos os gaps da rodada 1 foram resolvidos, os 6 mutantes desta rodada morreram (inclusive M5 e M6, que sobreviveram na rodada 1), o gate passa (36/36) e o CI no Windows ficou verde com o Python da pasta. Mas a checagem nova de "tag já existente em outro commit" (WIN-23) roda em **toda** execução, inclusive nas que só testam. Depois da 1ª Release, todo PR para a `main` (e todo "Run workflow" com `publicar` desmarcado) num commit diferente do da tag vai falhar no 3º passo sem rodar o build, até alguém subir o `VERSAO`. Isso quebra WIN-22 e WIN-24, e a própria spec se contradiz (WIN-23 não diz a que execuções se aplica).

Critério usado para `Verified` na rastreabilidade: **(a)** asserção de teste que mira o valor da spec (e, quando mutada, é morta), **ou (b)** execução real no CI Windows com linha de log citável. Evidência só estática (YAML) conta como `Verified` apenas para ACs declarativos (permissões, conteúdo de documentação). Os caminhos de runtime que nunca executaram (job `release`, `workflow_dispatch`, push de tag) ficam `Implementing` com "estrutura verificada; execução pendente (só ocorre após merge/tag)".

Fontes de evidência de CI (repo `Fluix-Solutions/conversor-ficha-financeira`):
- **Run 34632113906** (pull_request, commit c32eb9e; checkout do merge 5586d6f): job `build` success em todos os passos, job `release` **skipped**. Log salvo em `scratchpad/run2.log` (citado como `run2.log:N`).
- **Run 34631686098** (pull_request, commit 3ae38e7): job `build` falhou em "Monta a pasta e o zip", upload **skipped**, `release` skipped, **0 artefatos** (`gh api .../runs/34631686098/artifacts` → `total_count: 0`). Linhas citadas de `gh run view 34631686098 --log-failed`.
- Artefato 10277020812 baixado pela API e inspecionado (depois apagado do rascunho): SHA-256 `ba718e86…4ff9`, 4566 entradas, raiz única.
- `gh api .../tags` → vazio; `gh release list` → vazio (nenhuma tag nem Release criada pelos runs).

---

## Rodada 1 → Rodada 2

| Gap da rodada 1 | Correção | Evidência | Situação |
| --------------- | -------- | --------- | -------- |
| Fix 1: sem caminho que não publique; README sem "testar sem publicar" (WIN-20); o gate CI publicaria a `v1.1` | T11: input `publicar` (`.github/workflows/windows.yml:33-38`), `release` com `if: github.event_name == 'push' \|\| inputs.publicar` (`:119`); T13: gatilho `pull_request` (`:21-32`); T12: `README.md:129-134` | Run 34632113906: `release` skipped; `gh api .../tags` e `gh release list` vazios | ✅ Resolvido (com o gap novo G1 abaixo) |
| Fix 2: M5 sobreviveu (WIN-16 no `main` sem teste) | T9/T14: `tests/test_construir.py:96-135` roda o `main` inteiro e afirma o que ele executa | M5 morto (ver sensor); CI `run2.log:216-221`: 1º o setuptools de `_tmp\setuptools.txt`, depois cada pacote `from -r ...requirements-windows.lock (line N)` | ✅ Resolvido |
| Fix 3: M6 sobreviveu (ramo `--zip` sem teste) | T9: `tests/test_construir.py:144-150` | M6 morto; CI `run2.log:332-374` (pacotes, tamanho, sha256) | ✅ Resolvido |
| Fix 4: tag `v<VERSAO>` já existente em outro commit prenderia a Release (WIN-01) | T10: `release.py:51-59`; T11: `.github/workflows/windows.yml:84-89` | `tests/test_release.py:43-72`; M9 morto; ramo "tag inexistente" executado no CI (`run2.log:165`) | ✅ Resolvido, mas **sem escopo** → G1 |
| Fix 5a: WIN-02 sem afirmação da pasta montada | `tests/test_construir.py:137-142` | Teste + artefato real (ver WIN-02) | ✅ Resolvido |
| Fix 5b: `CLAUDE.md` afirmava OCR "(Mac e Windows)" | T12 trocou por "No Windows, só depois do 1º run" | `CLAUDE.md:180-181` — agora **desatualizado** (o CI já rodou e passou) | ⚠️ Obs. baixa (G2) |
| Fix 5c: `--python-alvo` relativo | `tests/conftest.py:39` `.absolute()` (não `.resolve()`, que seguiria o link do venv) | CI com alvo relativo `"$PASTA/python/python.exe"` (`run2.log:376-377`) → 5 e2e PASSED (`run2.log:393-399`) | ✅ Resolvido |
| (novo, só no CI) 1º run falhou: `proxy-tools` só tem sdist e o Python embutido ignora `PYTHONPATH` | T14: `setuptools` no lock (`requirements-build-windows.txt`), `bloco_do_lock` + `comandos_instalar` em duas etapas (`construir_portatil.py:98-126`) → WIN-25 | Run 34631686098 `--log-failed` linha 154 `Cannot import 'setuptools.build_meta'`; run 34632113906 `run2.log:298`, `:310-315` (`Successfully built proxy-tools`) | ✅ Resolvido |

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1-T8 | ✅ Done | Ver rodada 1; lacunas fechadas pelas T9-T14 |
| T9 `main` inteiro | ✅ Done | M5/M6 mortos nesta rodada |
| T10 tag em outro commit | ✅ Done | M9 morto |
| T11 `publicar` + checagem de tag | ⚠️ Partial | A checagem roda também em PR e em `publicar=false` (G1) |
| T12 docs sem publicar | ✅ Done | Obs. G2 (docs não citam o gatilho de PR; linha desatualizada) |
| T13 gatilho de PR | ✅ Done | Run 34632113906 verde, `release` skipped |
| T14 dependência só em código-fonte | ✅ Done | CI verde; M10/M11/M12 mortos |

---

## Spec-Anchored Acceptance Criteria

Legenda: **CI✔** = executado no run 34632113906/34631686098; **Estrutura** = verificado pelo YAML, execução pendente (só ocorre após merge/tag).

| Criterion | Spec-defined outcome | `file:line` + assertion / linha do workflow / linha do log | Result |
| --------- | -------------------- | ---------------------------------------------------------- | ------ |
| WIN-01 dispatch com `publicar` marcado | Build em `windows-latest`; Release `v<server.VERSAO>` no commit escolhido | `.github/workflows/windows.yml:33-38` (`publicar` boolean, `default: true`); `:49` `runs-on: windows-latest`; `:80` `release.py tag` sem `--ref-tag` → `tests/test_release.py:39-40` `tag_release(None, "1.1") == "v1.1"`; `:84-89` tag antiga em outro commit falha antes; `:119` `if: ... \|\| inputs.publicar`; `:149-150` `gh release create "$TAG" ... --target "$GITHUB_SHA"` | ✅ Estrutura (execução pendente: `workflow_dispatch` só existe após o merge) |
| WIN-02 conteúdo da pasta | Embutido 3.12.9 amd64 + `converter.py`, `server.py`, `app_desktop.py`, `web/`, `Conversor.bat`, `LEIA-ME.txt` | `tests/test_construir.py:35-39` `cp.PY == "3.12.9"` + hash; `:139-141` `(alvo / item).is_file()` para os 6 itens + `python/python.exe`; CI `run2.log:321` `baixando python-3.12.9-embed-amd64.zip`; artefato real: `Conversor.bat`, `LEIA-ME.txt`, `app_desktop.py`, `converter.py`, `server.py`, `web/index.html`, `python/python312.dll` presentes | ✅ PASS (CI✔) |
| WIN-03 SHA-256 diferente | Falha antes de instalar | `construir_portatil.py:178` antes de `:179-180`; `tests/test_construir.py:29-32` `real in str(e.value)` e `esperado in str(e.value)`; `:164-167` `pytest.raises(RuntimeError)`, nada extraído, `chamou_pip == []`; CI passou o hash (sem erro após `run2.log:321`) | ✅ PASS (M1 morto na rodada 1; código inalterado) |
| WIN-04 importações | 11 módulos, incluindo `clr`; falha se algum falhar | `tests/test_portatil.py:64` `clr` quando `win32`; `:75` `sorted(out["mods"]) == sorted(esperados)`; `:76` `{...if v != "ok"} == {}`; CI `run2.log:395` `test_importa_tudo PASSED` com o alvo `python.exe` da pasta (`run2.log:376-377`), e `run2.log:319` `tudo importa e o OCR carrega` (passo 6/6, `construir_portatil.py:238-239` inclui `clr`) | ✅ PASS (CI✔) |
| WIN-05 ficha de texto | Proventos com exatamente os valores por Ano+Mês e rubrica | `tests/test_portatil.py:30-31` cabeçalho exato; `:33` `(2020, m)` para os 12 meses; `:35-39` `ln[2:] == [...]`; CI `run2.log:393` `test_ficha_texto PASSED` | ✅ PASS (CI✔) |
| WIN-06 ficha escaneada | layout `OCR`, 12 valores por rubrica, sem `CONFERIR` | `tests/test_portatil.py:49` `resumo["layout"] == "OCR"`; `:51` `[... "CONFERIR" in a] == []`; `:57` valores exatos; CI `run2.log:394` `test_ficha_escaneada PASSED` | ✅ PASS (CI✔) |
| WIN-07 `/api/versao` | `"ocr": true` | `tests/test_portatil.py:106` `dados["ocr"] is True`; CI `run2.log:396` `test_api_versao_informa_ocr PASSED` | ✅ PASS (CI✔) |
| WIN-08 falha não publica | Nenhum artefato nem Release | Run 34631686098: passo "Monta a pasta e o zip" = failure, "Run actions/upload-artifact@v7" = skipped, job `release` = skipped, artefatos = 0; `--log-failed` linha 169 `CalledProcessError` → linha 170 `exit code 1`; `.github/workflows/windows.yml:55` bash `-e -o pipefail` (`run2.log:152`) | ✅ PASS (CI✔ — o caminho de falha aconteceu de verdade) |
| WIN-09 só fichas fictícias | Nenhum PDF real no repo nem nos logs | `tests/test_portatil.py:115` `r.stdout.strip() == ""`; CI `run2.log:397` `test_repositorio_sem_pdf_real PASSED`; artefato real: 0 entradas `.pdf` | ✅ PASS (CI✔) |
| WIN-10 registro no log | Pacotes com versão, tamanho e SHA-256 do zip | `tests/test_construir.py:149` `f"sha256: {sha256(arq_zip)}" in saida`, `:150` pacote na saída; `:83-84`, `:92-93`; CI `run2.log:332-371` (37 pacotes `nome==versão`), `:373` `tamanho do zip: 153.5 MB`, `:374` `sha256: ba718e86…4ff9` = `run2.log:443` digest do upload = digest da API = SHA-256 do artefato baixado | ✅ PASS (CI✔; M6 morto) |
| WIN-11 Release por tag | Release com a tag + `Conversor-de-Ficha-Financeira-<tag>-windows-x64.zip` | `tests/test_release.py:76` nome exato; `.github/workflows/windows.yml:14-18` filtros de tag; `:79` `--ref-tag "$REF_NAME"`; `:90` nome do zip; nome do artefato = nome do arquivo com `archive: false` (CI `run2.log:445` `Artifact Conversor-de-Ficha-Financeira-v1.1-windows-x64.zip successfully finalized`); `:135` download pelo mesmo nome; `:149` `gh release create "$TAG" "dist/$ZIP"` | ✅ Estrutura (job `release` e push de tag nunca executaram) |
| WIN-12 pasta raiz única | `Conversor de Ficha Financeira/` com `.bat` e `LEIA-ME.txt` no 1º nível | `tests/test_construir.py:70-72`, `:146-147`; artefato real: raízes = `['Conversor de Ficha Financeira']`, `.../Conversor.bat` e `.../LEIA-ME.txt` presentes | ✅ PASS (CI✔) |
| WIN-13 notas | SHA-256 + Windows 10/11 64 bits, .NET Framework 4.7.2+, WebView2 Runtime | `tests/test_release.py:82-85`; `:111` SHA-256 real no CLI; `release.py:74-76` traz "WebView2 Runtime"; workflow `:148` | ✅ PASS (obs.: o teste afirma `"WebView2"`, não `"WebView2 Runtime"`) |
| WIN-14 Release existente | Falhar sem alterar | `.github/workflows/windows.yml:139-144` `gh release view "$TAG"` → `exit 1` antes do `create` (`:146-152`) | ✅ Estrutura (execução pendente) |
| WIN-15 permissões | `contents: write` só no job de publicação | `.github/workflows/windows.yml:44-45` padrão `read`, `:51-52` build `read`, `:122-123` release `write`; CI `run2.log:21-24` `GITHUB_TOKEN Permissions: Contents: read, Metadata: read` no `build` | ✅ PASS (build CI✔; release declarativo) |
| WIN-16 lock com hash | Instala do lock com `--require-hashes` | `tests/test_construir.py:128-135` (2 instalações, `--require-hashes` nas duas, `-r cp.LOCK`, nenhum `requirements-desktop.txt`); `tests/test_lock.py:57-62`; CI `run2.log:221-309` cada pacote `from -r ...requirements-windows.lock (line N)`; comando real com `--require-hashes -r ...requirements-windows.lock` em 34631686098 `--log-failed` linha 169 | ✅ PASS (CI✔; M5 morto) |
| WIN-17 lock cobre requirements | Todo pacote de `requirements-desktop.txt` e `requirements-base.txt` | `tests/test_lock.py:45-51` `faltando == set()` (inclui `requirements-build-windows.txt`) | ✅ PASS |
| WIN-18 comando único no Mac | Um comando regenera o lock para Windows | `tests/test_lock.py:66-72` (comando do cabeçalho com `requirements-desktop.txt`, `--python-platform x86_64-pc-windows-msvc`, `--python-version 3.12`, `--generate-hashes`, `-o requirements-windows.lock`); rodado nesta rodada no worktree descartável: lock regenerado **idêntico** (`git diff` vazio) | ✅ PASS |
| WIN-19 tag ≠ VERSAO | Falha antes do build com os dois valores | `tests/test_release.py:29-30`; `:93-94` CLI `returncode == 1`, `"9.9"` e `"1.1"` no stderr; passo da tag é o 1º após setup (`.github/workflows/windows.yml:70-80`), executado no CI (`run2.log:165`) | ✅ PASS |
| WIN-20 README | Gerar versão pelo Mac, testar sem publicar, atualizar lock | `README.md:115-127` (tag e botão → Release), `:129-134` (testar sem publicar + artefato), `:154-169` (lock) | ✅ PASS (obs. G1: o "testar sem publicar" documentado quebra depois da 1ª Release; G2: o gatilho de PR não é citado) |
| WIN-21 CLAUDE.md | Fluxo, repo `Fluix-Solutions/...`, `pip --platform`, Python 3.12 | `CLAUDE.md:131-190`; `:135` repo; `:166-170` `pip --platform`; `:171-177` `proxy-tools`; `:178-179` 3.12 | ✅ PASS (obs. G2: `:180-181` desatualizado; PR não citado) |
| WIN-22 dispatch com `publicar` desmarcado | Build + testes; zip só como artefato por 14 dias; sem tag nem Release | `.github/workflows/windows.yml:119` (job `release` pulado com `inputs.publicar == false`); `:113` `retention-days: 14`. Caminho análogo executado no PR (artefato `expires_at` = criação + 14 dias; `release` skipped). **Mas** `:70-89` roda a checagem de tag sem condição: com a tag `v<VERSAO>` já publicada num commit anterior, o run falha em `release.py:55-59` antes do build | ❌ GAP (G1, latente: aparece após a 1ª Release) |
| WIN-23 tag existente em outro commit | Falha antes do build mostrando os dois commits | `release.py:55-59`; `tests/test_release.py:43-47` (os dois SHAs na mensagem), `:50-51`, `:54-55`, `:58-72` (CLI sai 1 / 0); `.github/workflows/windows.yml:84-89`; ramo "tag inexistente" executado no CI (`run2.log:165` imprimiu `v1.1`: o JSON de erro do `gh` não vazou para `SHA_TAG`) | ⚠️ Spec-precision gap (G1): o AC não restringe às execuções que publicam e contradiz WIN-22/WIN-24 |
| WIN-24 PR para a `main` | Build + testes no Windows; zip só como artefato; sem tag nem Release | `.github/workflows/windows.yml:21-32` (`branches: [main]` + `paths`); `:119` falso em PR; run 34632113906 verde, `release` skipped, sem tags/Releases. **Mas** no PR o `$GITHUB_SHA` é o commit de merge (`run2.log:90`, `:117-120`: `5586d6f Merge c32eb9e into aca6229`), que nunca é o commit de uma tag → depois da 1ª Release, todo PR que não suba o `VERSAO` falha no passo da tag | ❌ GAP (G1, latente: hoje verde porque não há tag) |
| WIN-25 dependência só em código-fonte | Compilar com o `setuptools` do lock, instalado antes com hash, sem `PYTHONPATH` | `construir_portatil.py:98-126`, `:212-213`; `tests/test_construir.py:47-56` (2 comandos, 1º só `setuptools==` com `--hash`, `count("==") == 1`; 2º `--no-build-isolation`); `:128-134` no `main`; `tests/test_lock.py:83-87`; CI `run2.log:216-220` (setuptools 84.0.0 de `_tmp\setuptools.txt`), `:298` (já satisfeito no site-packages da pasta), `:310-315` (`Successfully built proxy-tools`); contraprova: 34631686098 `--log-failed` linha 154 | ✅ PASS (CI✔; M10/M11/M12 mortos) |

**Status**: ❌ Gaps presentes: 19 ACs com evidência de teste ou de execução no CI; 3 só por estrutura (WIN-01, WIN-11, WIN-14 — execução pendente, sem erro de lógica encontrado); 2 com gap (WIN-22, WIN-24) e 1 spec-precision gap (WIN-23), todos com a mesma causa (G1).

---

## Edge Cases

- [x] python.org / bootstrap.pypa.io / PyPI fora do ar → falha com a URL/pacote: `construir_portatil.py:83` imprime o arquivo baixado; pip com `check=True` (`:207-208`, `:213`). A falha real do run 34631686098 mostra o nome do pacote (`--log-failed` linha 70 `proxy-tools==0.1.0`) e derrubou o build sem artefato.
- [x] Tag fora de `vX.Y`/`vX.Y.Z` não roda: `.github/workflows/windows.yml:14-18` (só `tags` no `push` → push de branch não dispara; a doc do GitHub confirma que o tipo de ref sem filtro não dispara); defesa extra em `release.py:40-42` + `tests/test_release.py:33-36`.
- [x] Duas tags ao mesmo tempo: `.github/workflows/windows.yml:40-42` (grupo por `github.ref`, sem cancelar). Estrutura. Obs.: a doc do GitHub diz que um push com **mais de 3 tags** não gera evento — fora do caso "duas tags".
- [x] Escaneada com `CONFERIR` → falha: `tests/test_portatil.py:51`; CI `run2.log:394`.

---

## Discrimination Sensor

Rodado num `git worktree add --detach scratchpad/wt2 HEAD`, com o `.venv/bin/python` do repo (caminho absoluto), `PYTHONDONTWRITEBYTECODE=1` e `-p no:cacheprovider`. Cada mutação foi aplicada, testada com o gate rápido (`-m "not e2e"`) e desfeita. Linha de base no worktree: 31 passed, 5 deselected. `git status --porcelain` da árvore real **idêntico** antes e depois (só os 4 diretórios não rastreados de sempre); worktree removido (`git worktree list` só com a árvore real).

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M5 (repetida) | `construir_portatil.py:212-213` | `main` volta a `pip install -r requirements-desktop.txt`, sem lock nem hash | ✅ Killed (`test_main_monta_instala_do_lock_e_registra_o_zip`) |
| M6 (repetida) | `construir_portatil.py:267` | `main --zip` não chama `registrar` | ✅ Killed (`test_main_monta_instala_do_lock_e_registra_o_zip`) |
| M9 | `release.py:55` | `sha_da_tag != sha_atual` → `==` | ✅ Killed (3 testes: outro commit, mesmo commit, CLI) |
| M10 | `construir_portatil.py:126` | 2ª instalação sem `--no-build-isolation` | ✅ Killed (2 testes) |
| M11 | `construir_portatil.py:125-126` | sem a pré-instalação do `setuptools` (só o lock) | ✅ Killed (2 testes) |
| M12 | `construir_portatil.py:104-105` | `bloco_do_lock` não para no próximo pacote (devolve setuptools + tudo o que vem depois) | ✅ Killed (`test_instala_do_lock_exigindo_hashes_em_duas_etapas`, `count("==") == 1`) |

**Sensor depth**: lightweight (6 mutações, focadas nos sobreviventes da rodada 1 e no código novo)
**Resultado do sensor**: 6/6 mortos, sem sobreviventes

Não mutado: `tests/conftest.py:39` (`.absolute()`, harness de teste; a execução no CI com alvo relativo já o prova) e o YAML do workflow (sem teste executável; julgado por leitura + `actionlint`).

---

## Interactive UAT Results

Não realizado (infra de build). O UAT do Smart App Control com o zip **baixado** segue previsto nas Success Criteria da spec, antes de divulgar a 1ª Release.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ `bloco_do_lock`/`comandos_instalar` curtos; `conferir_commit_da_tag` é uma condição |
| Surgical changes | ✅ `git diff main..HEAD -- converter.py server.py app_desktop.py web/ Dockerfile requirements.txt requirements-desktop.txt requirements-base.txt` = vazio. Lock: só o cabeçalho e o bloco `setuptools` mudaram desde a rodada 1 (versões mantidas) |
| No scope creep | ✅ |
| Matches patterns | ✅ Português, comentários com o porquê, só stdlib em `release.py` |
| Spec-anchored outcome check | ✅ asserções miram o valor da spec (os dois SHAs na mensagem, nome exato do zip, `--require-hashes` + `--no-build-isolation` no comando executado, SHA-256 real do zip na saída) |
| Per-layer Coverage Expectation | ✅ funções e orquestração do build cobertas (M5/M6/M10-M12 mortos); workflow por `actionlint` + CI |
| Every test maps to a spec requirement | ✅ os 36 mapeiam para AC ou Done-when (T9-T14 incluídos) |
| Documented guidelines followed: `CLAUDE.md` ("Como validar uma conversão": soma dos 12 meses × Total) | ✅ refletido no `CONFERIR` do WIN-06 |

Observações de qualidade (não bloqueiam):
- `design.md` não foi atualizado com `publicar`, gatilho de PR, checagem de tag nem a instalação em duas etapas (T9-T14) — deriva de documentação de design.
- O zip leva `__pycache__/converter.cpython-312.pyc` e `server.cpython-312.pyc` (visto no artefato real): o passo 6/6 importa `converter`/`server` **depois** do "5/6 enxugando". Inofensivo.
- `.github/workflows/windows.yml:84-88`: qualquer erro do `gh api` (rede, limite de taxa), não só "tag inexistente", vira `SHA_TAG=""` e desliga a checagem. Risco baixo.

---

## Gate Check

- **Gate command**: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`
- **Resultado do gate**: 36 passed, 0 failed, 0 skipped (6,9 s, e2e incluídos); `py_compile` exit 0; `actionlint` exit 0
- **Test count before feature**: 0 (o repo não tinha testes); rodada 1: 30
- **Test count after feature**: 36
- **Delta**: +36 (+6 desde a rodada 1: `main` inteiro, 4 de tag×commit, setuptools no lock); nenhum teste removido; `test_instala_do_lock...` ficou mais estrito (2 comandos)
- **Skipped tests**: nenhum
- **Failures**: nenhuma
- **CI Windows** (run 34632113906): `31 passed, 5 deselected` com o Python do host (`run2.log:198`) e `5 passed, 31 deselected` com o Python da pasta, `platform win32` (`run2.log:388`, `:399`)

---

## Fix Plans

### Fix G1 (Major): a checagem de tag×commit bloqueia as execuções que só testam (WIN-22, WIN-24; spec-precision em WIN-23)

- **Root cause**: o passo "Tag da Release" (`.github/workflows/windows.yml:70-93`) roda em todo evento e sempre passa `--sha-tag`/`--sha "$GITHUB_SHA"` (`:84-89`). Em PR o `$GITHUB_SHA` é o commit de merge (`run2.log:117-120`), nunca o da tag; num "Run workflow" de teste ele é a ponta da branch. Cenário real: publica-se a `v1.1` (tag no commit X). O próximo PR que corrige o `converter.py` sem subir o `VERSAO` → `release.py:55-59` "a tag v1.1 já existe no commit X…" → build nunca roda, PR vermelho. O mesmo vale para `gh workflow run -f publicar=false` num commit novo — exatamente o "testar sem publicar" do `README.md:129-134`. A spec permite as duas leituras: WIN-23 não diz a que execuções se aplica, e o motivo dela (a Release presa ao commit antigo) só existe quando se publica.
- **Fix task**: (1) na spec, restringir WIN-23: "IF, numa execução que publica (tag enviada ou `publicar` marcado), a tag…"; (2) no workflow, consultar e comparar a tag só quando publica — p.ex. `env: PUBLICA: ${{ github.event_name == 'push' || inputs.publicar }}` no passo e `if [ "$PUBLICA" = "true" ]; then ...gh api... ; python release.py tag ... --sha-tag "$SHA_TAG" --sha "$GITHUB_SHA"; fi`; (3) uma linha no README/CLAUDE.md: PR e `publicar=false` não conferem a tag. Alternativa (decisão do usuário): manter como está e documentar que **todo PR que mexe no app precisa subir o `VERSAO`** — nesse caso, reescrever WIN-22/WIN-24 para dizer isso.
- **Verify**: `actionlint`; revisão da condição; CI do PR continua verde. Opcional, para provar o ramo: criar uma tag descartável `v<VERSAO>` num commit antigo **só se o usuário autorizar** (repo público), rodar o PR e apagar a tag.
- **Priority**: Major (latente hoje; aparece na 1ª Release e trava o gate de PR)

### Fix G2 (Minor, documentação)

- `CLAUDE.md:180-181` ("No Windows, só depois do 1º run do workflow") → o run 34632113906 já passou OCR/texto no Windows com opencv 5.0.0.93 + numpy 2.5.3.
- README e CLAUDE.md não citam o gatilho de **PR** (WIN-24), e o "Run workflow"/`gh workflow run` do `README.md:129-130` só existe depois que o workflow está na `main` (o próprio YAML diz isso em `.github/workflows/windows.yml:19-20`).
- `design.md`: registrar T9-T14 (opcional).

### Fix G3 (Cosmetic, opcional)

- Tirar os `__pycache__` do `converter`/`server` gerados pelo passo 6/6 antes do `zipar` (`construir_portatil.py:226-229` roda antes de `:256`).

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| WIN-01 | Implementing | Implementing (estrutura verificada; execução pendente — só ocorre após o merge) |
| WIN-02 | Implementing | ✅ Verified (teste do `main` + CI + artefato real) |
| WIN-03 | Verified | ✅ Verified |
| WIN-04 | Verified | ✅ Verified (agora com o Python da pasta no Windows) |
| WIN-05 | Verified | ✅ Verified (CI✔) |
| WIN-06 | Verified | ✅ Verified (CI✔) |
| WIN-07 | Verified | ✅ Verified (CI✔) |
| WIN-08 | Implementing | ✅ Verified (run 34631686098: falhou, 0 artefatos, `release` skipped) |
| WIN-09 | Verified | ✅ Verified |
| WIN-10 | Implementing | ✅ Verified (M6 morto + log do CI) |
| WIN-11 | Implementing | Implementing (estrutura verificada; execução pendente — só ocorre com a 1ª tag) |
| WIN-12 | Verified | ✅ Verified (+ artefato real) |
| WIN-13 | Verified | ✅ Verified |
| WIN-14 | Implementing | Implementing (estrutura verificada; execução pendente) |
| WIN-15 | Implementing | ✅ Verified (build: log de permissões; release: declarativo) |
| WIN-16 | Implementing | ✅ Verified (M5 morto + log do CI) |
| WIN-17 | Verified | ✅ Verified |
| WIN-18 | Verified | ✅ Verified (regenerado idêntico nesta rodada) |
| WIN-19 | Verified | ✅ Verified |
| WIN-20 | Implementing | ✅ Verified |
| WIN-21 | Verified | ✅ Verified |
| WIN-22 | Implementing | ❌ Needs Fix (G1) |
| WIN-23 | Implementing | ❌ Needs Fix (G1 — spec-precision: escopo) |
| WIN-24 | Implementing | ❌ Needs Fix (G1) |
| WIN-25 | Implementing | ✅ Verified (CI✔ + M10/M11/M12 mortos) |

---

## Summary

**Overall**: ❌ Not Ready (1 correção Major pequena, 1 decisão do usuário)

**Spec-anchored check**: 19/25 ACs com asserção ou execução no CI que bate com a spec; 3 só por estrutura (WIN-01, WIN-11, WIN-14; execução pendente, lógica sem defeito); 2 gaps (WIN-22, WIN-24) + 1 spec-precision gap (WIN-23), mesma causa
**Sensor**: 6/6 mutações mortas (M5 e M6 da rodada 1 agora morrem)
**Gate**: 36 passed, 0 failed; `py_compile` e `actionlint` ok; CI Windows verde (run 34632113906)

**What works**: build no Windows real com o Python da pasta (imports com `clr`, OCR, ficha de texto e escaneada com valores exatos, `/api/versao`), lock com hash instalado em duas etapas (o `proxy-tools` compila), zip com raiz única e SHA-256 registrado e igual ao digest do artefato, "nada publica se falhar" provado por um run que falhou de verdade, PR que não publica, regras de tag/versão/commit com testes que discriminam.

**Issues found**: G1 (a checagem de tag×commit precisa valer só para execuções que publicam — ou o usuário aceita que todo PR suba o `VERSAO`), G2 (docs), G3 (cosmético).

**Next steps**: decidir G1 com o usuário e aplicar (condição no passo da tag + texto do WIN-23); corrigir G2; rodada 3 de verificação. Depois do merge: `gh workflow run windows.yml -f publicar=false` (WIN-22) e a 1ª tag (WIN-01/11/14) fecham os ACs pendentes de execução.
