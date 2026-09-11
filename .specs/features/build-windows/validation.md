# Build Windows Validation (rodada 3)

## Validation: build-windows - PASS

**Date**: 2026-09-11
**Spec**: `.specs/features/build-windows/spec.md` (WIN-01..WIN-25; WIN-23 reescrito na rodada 3 para valer só em execução que publica)
**Diff range**: feature inteira `main..build-windows` (4888924..7983506, 21 commits); correções da rodada 3: `f6d99fd..7983506` (70e4392 `fix(ci)`, 7983506 `docs(windows)`)
**Verifier**: sub-agente independente (autor ≠ verificador), rodada 3 de no máximo 3

Veredito: **PASS**. O G1 (a checagem tag×commit rodava em execuções que só testam) está corrigido: o passo da tag só consulta o commit da tag quando a execução publica. O run 34633772453 (PR, HEAD 7983506) comprova isso no Windows: `PUBLICA` vazio e a 2ª chamada de `release.py tag` não aparece no log. A simulação local, que roda o corpo real do passo tirado do YAML com um `gh` falso, mostra que PR e `publicar=false` passam mesmo com a tag em outro commit, e que a execução que publica falha mostrando os dois commits. O gate passa (36/36, `py_compile` e `actionlint` ok). Os 2 mutantes de regressão no código morreram. Os 3 mutantes no YAML sobreviveram à suíte, o que era esperado pela matriz de cobertura acordada ("none (lint)"); fica registrado como limitação conhecida, com recomendação abaixo. A documentação (G2) foi corrigida. O G3, que é cosmético, foi para as Deferred Ideas, e aceito isso.

Cinco ACs ficam com execução pendente **por desenho**, porque só rodam depois do merge ou com a 1ª tag: WIN-01, WIN-11, WIN-14, WIN-22 e o ramo "publica" do WIN-23. Nenhum defeito de lógica foi encontrado neles. A lista de conferências pós-merge está no fim deste relatório.

**Critério para `Verified` na rastreabilidade** (o mesmo da rodada 2): **(a)** uma asserção de teste que mira o valor definido na spec (e que, quando mutada, é morta), **ou (b)** uma execução real no CI Windows com linha de log citável. Evidência só estática (YAML ou texto) conta como `Verified` apenas para ACs declarativos (permissões, conteúdo de documentação). Caminhos de runtime que nunca executaram ficam como `Implementing` com a nota "estrutura verificada; execução pendente pós-merge", sem contar como gap.

Fontes de evidência de CI (repo `Fluix-Solutions/conversor-ficha-financeira`):
- **Run 34633772453** (pull_request, `headSha` 7983506 = HEAD; checkout do merge `1fd53c2`): job `build` success em todos os passos, job `release` **skipped**. Log em `scratchpad/run3.log`, citado como `run3.log:N`. Artefato 10277047881: `digest sha256:1589bee2…4555` (igual a `run3.log:378`), `expires_at` = criação + 14 dias.
- **Run 34632113906** (rodada 2, commit c32eb9e), citado como `run2.log:N`, e **run 34631686098** (falha real, 0 artefatos). Os dois continuam valendo: o código e os testes não mudaram desde a804d83 (`git diff --quiet a804d83..HEAD -- tests release.py construir_portatil.py requirements-windows.lock requirements-build-windows.txt` → sem diferença).
- `gh api .../tags` → `0`; `gh release list` → vazio.

---

## Rodada 2 → Rodada 3

| Gap da rodada 2 | Correção | Evidência | Situação |
| --------------- | -------- | --------- | -------- |
| **G1 (Major)**: checagem tag×commit em todo evento; quebraria PRs e `publicar=false` depois da 1ª Release (WIN-22/24); WIN-23 sem escopo | T15: `PUBLICA: ${{ github.event_name == 'push' \|\| inputs.publicar }}` (`.github/workflows/windows.yml:77-78`); `gh api` e `--sha-tag/--sha` só dentro de `if [ "$PUBLICA" = "true" ]` (`:88-95`); a mesma condição do job `release` (`:125`). Spec: WIN-23 reescrito (`spec.md:73`) | **CI**: `run3.log:168` `PUBLICA: ` (vazio em PR; o contexto `inputs` não existe fora do `workflow_dispatch`); `run3.log:169-170`, depois do `##[endgroup]` vem direto `Release v1.1 -> ...`, **sem** a linha `v1.1` impressa pela 2ª chamada de `release.py tag`, que aparecia na rodada 2 (`run2.log:165`); o passo caiu de 10 s para 1,6 s (sem o `gh api`). **Simulação independente** (corpo real do passo extraído do YAML via `yaml.safe_load`, `bash -e -o pipefail` como no runner, `gh` falso): 9 casos, tabela abaixo. **Docs** do GitHub (Context7): o contexto `inputs` preserva booleanos → `publicar` vira `"true"`/`"false"` | ✅ Resolvido |
| **G2 (Minor)**: `CLAUDE.md` com a frase "No Windows, só depois do 1º run"; gatilho de PR e "dispatch só após merge" não documentados; `design.md` sem T9-T14 | T16 | `CLAUDE.md:186-188` (OCR verde no Windows, run 34632113906); `CLAUDE.md:147-150` (PR; `workflow_dispatch` só existe com o arquivo na `main`); `CLAUDE.md:151-153` (tag×commit só em execução que publica); `README.md:136-138` (PR; botão só depois da `main`); `README.md:142-143` (teste e PR não checam); `design.md:179-191` (T9-T16) | ✅ Resolvido |
| **G3 (Cosmetic)**: `__pycache__` de `converter`/`server` no zip | Adiado: `context.md:61` (Deferred Ideas, com a correção descrita: `python -B` no 6/6) | Nenhum AC trata disso (WIN-02 exige a presença de itens, não proíbe extras); o arquivo é inofensivo | ✅ Adiamento aceito (cosmético, registrado, com correção concreta) |

**Simulação do passo da tag** (corpo real de `.github/workflows/windows.yml:79-99`; `GITHUB_SHA=bbbb…`; `server.VERSAO = 1.1`):

| PUBLICA | Ref | `gh api` devolve | Saída | `gh` chamado | Resultado |
| ------- | --- | ---------------- | ----- | ------------ | --------- |
| `""` (PR) | branch `1/merge` | tag noutro commit `aaaa…` | 0, `tag=v1.1` | 0× | ✅ PR não é bloqueado (WIN-24) |
| `""` (PR) | branch `1/merge` | tag inexistente | 0 | 0× | ✅ |
| `false` | branch `main` | tag noutro commit | 0, `tag=v1.1` | 0× | ✅ `publicar=false` não é bloqueado (WIN-22) |
| `true` | branch `main` | tag noutro commit | **1**, `ERRO: a tag v1.1 já existe no commit aaaa…, mas este build é do commit bbbb…` | 1× | ✅ WIN-23 (os dois commits) |
| `true` | branch `main` | mesmo commit | 0 | 1× | ✅ |
| `true` | branch `main` | inexistente (JSON no stdout, sai 1) | 0 | 1× | ✅ o JSON do erro não vaza para `SHA_TAG` |
| `true` | tag `v1.1` | mesmo commit | 0 | 1× | ✅ push de tag normal |
| `true` | tag `v1.1` | outro commit | 1 | 1× | ✅ |
| `true` | tag `v9.9` | - | 1, `v9.9 (9.9) difere ... 1.1` | 0× | ✅ WIN-19 falha antes da consulta |

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1-T14 | ✅ Done | Verificadas nas rodadas 1-2; código inalterado desde a804d83 |
| T15 checagem só quando publica | ✅ Done | O critério "Gate CI: PR verde" está desmarcado em `tasks.md:477`, mas o run 34633772453 (HEAD 7983506) está verde. Falta só marcar a caixa (o Verifier não edita `tasks.md`) |
| T16 docs | ✅ Done | O "Where" (`tasks.md:489`) cita só o `CLAUDE.md`; o commit também mexeu no README e no `design.md`, como o próprio "Done when" pede |

Obs.: `tasks.md:12` ainda diz "In Progress (correções da 2ª rodada)". O status precisa ser atualizado pelo orquestrador.

---

## Spec-Anchored Acceptance Criteria

Legenda: **CI✔** = executado num run do Windows com linha citável; **Estrutura** = verificado pelo YAML (e, quando indicado, por simulação local), com execução pendente pós-merge.

| Criterion | Spec-defined outcome | `file:line` + assertion / linha do workflow / linha do log | Result |
| --------- | -------------------- | ---------------------------------------------------------- | ------ |
| WIN-01 dispatch com `publicar` marcado | Build em `windows-latest`; Release `v<server.VERSAO>` no commit escolhido | `.github/workflows/windows.yml:35-38` (`publicar` boolean, `default: true`); `:49` `runs-on: windows-latest`; `:82` `release.py tag` sem `--ref-tag` → `tests/test_release.py:40` `tag_release(None, "1.1") == "v1.1"`; `:88-95` checagem de tag (simulação `true`/`main`); `:125` `if: ... \|\| inputs.publicar`; `:155-156` `gh release create "$TAG" ... --target "$GITHUB_SHA"` | ✅ Estrutura (execução pendente: `workflow_dispatch` só existe após o merge) |
| WIN-02 conteúdo da pasta | Embutido 3.12.9 amd64 + `converter.py`, `server.py`, `app_desktop.py`, `web/`, `Conversor.bat`, `LEIA-ME.txt` | `tests/test_construir.py:36` `cp.PY == "3.12.9"`; `:141` `(alvo / item).is_file()` para os itens; CI `run3.log:325` `baixando python-3.12.9-embed-amd64.zip` | ✅ PASS (CI✔) |
| WIN-03 SHA-256 diferente | Falha antes de instalar | `tests/test_construir.py:31-32` os dois hashes na mensagem; `:166-167` nada extraído, `chamou_pip == []` | ✅ PASS |
| WIN-04 importações | 11 módulos, incluindo `clr`; falha se algum falhar | `tests/test_portatil.py:75` `sorted(out["mods"]) == sorted(esperados)`; `:76` `{... if v != "ok"} == {}`; CI `run3.log:399` `test_importa_tudo PASSED`; `run3.log:323` `tudo importa e o OCR carrega` | ✅ PASS (CI✔) |
| WIN-05 ficha de texto | Proventos com exatamente os valores por Ano+Mês e rubrica | `tests/test_portatil.py:30` cabeçalho exato; `:33` 12 meses de 2020; `:35` `ln[2:] == [...]`; CI `run3.log:397` `test_ficha_texto PASSED` | ✅ PASS (CI✔) |
| WIN-06 ficha escaneada | layout `OCR`, 12 valores por rubrica, sem `CONFERIR` | `tests/test_portatil.py:49` `resumo["layout"] == "OCR"`; `:51` sem `CONFERIR`; `:57` valores exatos; CI `run3.log:398` `test_ficha_escaneada PASSED` | ✅ PASS (CI✔) |
| WIN-07 `/api/versao` | `"ocr": true` | `tests/test_portatil.py:106` `dados["ocr"] is True`; CI `run3.log:400` `test_api_versao_informa_ocr PASSED` | ✅ PASS (CI✔) |
| WIN-08 falha não publica | Nenhum artefato nem Release | Run 34631686098: "Monta a pasta e o zip" falhou, upload e `release` skipped, 0 artefatos (rodada 2); bash `-e -o pipefail` (`run3.log:156`) | ✅ PASS (CI✔) |
| WIN-09 só fichas fictícias | Nenhum PDF real no repo nem nos logs | `tests/test_portatil.py:115` `r.stdout.strip() == ""`; CI `run3.log:401` `test_repositorio_sem_pdf_real PASSED` | ✅ PASS (CI✔) |
| WIN-10 registro no log | Pacotes com versão, tamanho e SHA-256 do zip | `tests/test_construir.py:149` `f"sha256: {sha256(arq_zip)}" in saida`, `:150`; CI `run3.log:370` (`setuptools==84.0.0` na lista de pacotes), `:377` `tamanho do zip: 153.5 MB`, `:378` `sha256: 1589bee2…4555` = digest do artefato na API | ✅ PASS (CI✔; M5 também morto nesta rodada) |
| WIN-11 Release por tag | Release com a tag + `Conversor-de-Ficha-Financeira-<tag>-windows-x64.zip` | `tests/test_release.py:76` nome exato; `.github/workflows/windows.yml:16-18` filtros de tag; `:81` `--ref-tag "$REF_NAME"`; `:96` nome do zip; `:141` download pelo mesmo nome; `:155` `gh release create "$TAG" "dist/$ZIP"`; simulação `true`/tag `v1.1`/mesmo commit → 0 | ✅ Estrutura (push de tag e job `release` nunca executaram) |
| WIN-12 pasta raiz única | `Conversor de Ficha Financeira/` com `.bat` e `LEIA-ME.txt` no 1º nível | `tests/test_construir.py:70-72`, `:146-147`; artefato real inspecionado na rodada 2 (raiz única) | ✅ PASS |
| WIN-13 notas | SHA-256 + Windows 10/11 64 bits, .NET Framework 4.7.2+, WebView2 Runtime | `tests/test_release.py:82-85`; `:111` SHA-256 real no CLI; `release.py:74-76` | ✅ PASS (obs.: o teste afirma `"WebView2"`, não `"WebView2 Runtime"`; o texto real traz "WebView2 Runtime") |
| WIN-14 Release existente | Falhar sem alterar | `.github/workflows/windows.yml:145-150` `gh release view "$TAG"` → `exit 1` antes do `create` (`:152-158`) | ✅ Estrutura (execução pendente) |
| WIN-15 permissões | `contents: write` só no job de publicação | `.github/workflows/windows.yml:44-45` padrão `read`, `:51-52` build `read`, `:128-129` release `write`; CI `run3.log:22` `Contents: read` no `build` | ✅ PASS (build CI✔; release declarativo) |
| WIN-16 lock com hash | Instala do lock com `--require-hashes` | `tests/test_construir.py:130` `--require-hashes` nas duas instalações, `:133` `-r cp.LOCK`, `:135` nenhum `requirements-desktop.txt`; CI `run3.log:220` (setuptools de `_tmp\setuptools.txt`), `:302` (lock) | ✅ PASS (CI✔; M5 morto) |
| WIN-17 lock cobre requirements | Todo pacote de `requirements-desktop.txt` e `requirements-base.txt` | `tests/test_lock.py:51` `faltando == set()` | ✅ PASS |
| WIN-18 comando único no Mac | Um comando regenera o lock para Windows | `tests/test_lock.py:68-72` (comando do cabeçalho); regenerado idêntico na rodada 2 (lock inalterado desde então) | ✅ PASS |
| WIN-19 tag ≠ VERSAO | Falha antes do build com os dois valores | `tests/test_release.py:29-30`; `:93-94` CLI `returncode == 1`, `"9.9"` e `"1.1"` no stderr; o passo da tag é o 1º depois do setup (`.github/workflows/windows.yml:70-82`, fora do `if PUBLICA`); simulação `v9.9` → 1 sem chamar o `gh` | ✅ PASS |
| WIN-20 README | Gerar versão pelo Mac, testar sem publicar, atualizar lock | `README.md:115-127` (tag e botão → Release), `:129-134` (testar sem publicar), `:136-138` (PR; botão só após a `main`), `:140-143` (tag×commit só ao publicar), `:160+` (lock) | ✅ PASS |
| WIN-21 CLAUDE.md | Fluxo, repo `Fluix-Solutions/...`, `pip --platform`, Python 3.12 | `CLAUDE.md:131-195`; `:135` repo; `:172-176` `pip --platform`; `:184-185` 3.12; `:186-188` OCR verde no Windows | ✅ PASS |
| WIN-22 dispatch com `publicar` desmarcado | Build + testes; zip só como artefato por 14 dias; sem tag nem Release | `.github/workflows/windows.yml:78` + `:88` (com `publicar=false`, `PUBLICA="false"` → sem checagem); `:125` (`release` pulado); `:119` `retention-days: 14`. Simulação `false`/tag noutro commit → 0, `gh` 0×. O mesmo job `build` rodou no PR (run 34633772453: artefato com `expires_at` = +14 dias, `release` skipped, 0 tags) | ✅ Estrutura + simulação (execução pendente: `workflow_dispatch` só após o merge). O G1 foi fechado |
| WIN-23 tag existente em outro commit | Em execução que publica: falha antes do build com os dois commits. Em PR ou `publicar=false`: **não** checa | Lógica: `release.py:55-59`; `tests/test_release.py:46-47` (os dois SHAs), `:64-65` (CLI sai 1, os dois SHAs no stderr), `:71-72` (tag inexistente aceita); M9 morto de novo. Escopo: `.github/workflows/windows.yml:78`, `:88-95`. "Não checa" em PR: **CI✔** `run3.log:168` + ausência da linha `v1.1` em `run3.log:169-170` (compare `run2.log:165`). "Checa" ao publicar: simulação `true` → 1 com `aaaa…` e `bbbb…` | ✅ PASS no escopo de teste (CI✔) + lógica (teste); ramo que publica: Estrutura + simulação, execução pendente |
| WIN-24 PR para a `main` | Build + testes no Windows; zip só como artefato; sem tag nem Release | `.github/workflows/windows.yml:21-32` (`branches: [main]` + `paths`); `:125` falso em PR; **run 34633772453** verde em HEAD 7983506: `release` skipped, artefato de 14 dias, 0 tags/Releases; `run3.log:168` sem checagem de tag. Falha latente do G1 (PR depois da 1ª Release): simulação `""`/tag noutro commit → 0, `gh` 0× | ✅ PASS (CI✔ + simulação) |
| WIN-25 dependência só em código-fonte | Compilar com o `setuptools` do lock, instalado antes com hash, sem `PYTHONPATH` | `tests/test_construir.py:47-56`, `:129-134`; `tests/test_lock.py:86-87`; CI `run3.log:220-224` (setuptools 84.0.0 instalado primeiro), `:302`, `:317-319` (`Successfully built proxy-tools`) | ✅ PASS (CI✔) |

**Status**: ✅ Todos os ACs têm evidência. 20 estão Verified (teste ou CI); 5 estão com execução pendente por desenho (WIN-01, WIN-11, WIN-14, WIN-22 e o ramo "publica" do WIN-23), com lógica verificada por estrutura e simulação; 0 spec-precision gaps (o WIN-23 agora diz a que execuções se aplica).

---

## Edge Cases

- [x] python.org / bootstrap.pypa.io / PyPI fora do ar → falha com a URL ou o pacote: `construir_portatil.py:83` imprime o que baixa; o pip roda com `check=True` (`:207-208`, `:213`); na falha real do run 34631686098 aparecia o nome do pacote e o build caiu sem artefato (rodada 2).
- [x] Tag fora de `vX.Y`/`vX.Y.Z` não roda: `.github/workflows/windows.yml:15-18` (o `push` só tem `tags`, então push de branch não dispara); defesa extra em `release.py:40-42` + `tests/test_release.py:33-36`.
- [x] Duas tags ao mesmo tempo: `.github/workflows/windows.yml:40-42` (grupo por `github.ref`, sem cancelar). Verificado pela estrutura. Obs.: a doc do GitHub diz que um push com **mais de 3 tags** não gera evento, o que está fora do caso "duas tags".
- [x] Escaneada com `CONFERIR` → falha: `tests/test_portatil.py:51`; CI `run3.log:398`.

---

## Discrimination Sensor

Rodado num `git worktree add --detach scratchpad/wt3 HEAD`, com o `.venv/bin/python` do repo por caminho absoluto, `PYTHONDONTWRITEBYTECODE=1` e `-p no:cacheprovider`. A linha de base no worktree deu 31 passed, 5 deselected; `actionlint` ok; o simulador bateu com a tabela acima. Cada mutação foi aplicada, testada com o gate rápido + `actionlint` + o simulador (este só para o YAML) e desfeita com `git checkout -- .` dentro do worktree. Depois o worktree foi removido (`git worktree list` mostra só a árvore real) e o `git status --porcelain` da árvore real ficou **idêntico** antes e depois (só os 4 diretórios não rastreados de sempre).

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M13 | `.github/workflows/windows.yml:88` | Guarda invertida: `[ "$PUBLICA" = "true" ]` → `!=` | ⚠️ Sobreviveu à suíte e ao `actionlint` (esperado: matriz "none (lint)"). **Morto pelo simulador**: PR e `publicar=false` com a tag noutro commit passam a sair com 1, e o `true` passa a sair com 0 |
| M14 | `.github/workflows/windows.yml:78` | Linha `PUBLICA:` removida do `env` (a variável fica vazia, a checagem nunca roda e o WIN-23 some em silêncio) | ⚠️ Sobreviveu à suíte, ao `actionlint` e ao simulador (que injeta `PUBLICA` ele mesmo). Só pega quem lê o YAML |
| M15 | `.github/workflows/windows.yml:78` | `PUBLICA` só com `github.event_name == 'push'` (ignora `inputs.publicar`; o disparo manual que publica deixa de checar) | ⚠️ Sobreviveu à suíte e ao `actionlint`; o simulador não avalia expressões do GitHub |
| M9 (regressão) | `release.py:55` | `sha_da_tag != sha_atual` → `==` | ✅ Killed (3 testes: outro commit, mesmo commit, CLI) |
| M5 (regressão) | `construir_portatil.py:212-213` | `main` volta a `pip install -r requirements-desktop.txt`, sem lock nem hash | ✅ Killed (`test_main_monta_instala_do_lock_e_registra_o_zip`) |

**Sensor depth**: lightweight (5 mutações: 3 no código novo da rodada 3 e 2 de regressão)
**Resultado do sensor**: 2/2 mortos no código Python coberto pela matriz; 3/3 mutantes de YAML sobreviveram à suíte, como a matriz (`tasks.md:26`, workflow = "none (lint)") prevê. Isso vira **limitação conhecida**, não gap de teste.

Avaliação da matriz: ela foi escrita quando o workflow era declarativo. Com T11/T15, o passo da tag ganhou lógica de shell com ramos (`PUBLICA`, o código de saída do `gh`) que decide WIN-22/23/24, e o ramo "publica" só executa depois do merge. Não considero a matriz errada a ponto de bloquear. A lógica foi provada por leitura, pela execução no CI (ramo de PR) e pela simulação do corpo real do passo. Mas uma regressão futura nesse `if` passaria pelo gate sem aviso. Recomendação (Minor, fora desta feature, ver Fix R1).

---

## Interactive UAT Results

Não realizado (infra de build, sem interação de UI nesta feature). O UAT do Smart App Control com o zip **baixado da Release** continua previsto nas Success Criteria da spec (`spec.md:193`), antes de divulgar a 1ª Release.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ A correção do G1 é uma variável de ambiente e um `if` em volta de 2 comandos (`.github/workflows/windows.yml:77-78`, `:88-95`), reaproveitando a condição do job `release` |
| Surgical changes | ✅ A rodada 3 só tocou o workflow, a documentação e as specs. `converter.py`, `server.py`, `app_desktop.py`, `web/`, `Dockerfile` e `requirements.txt` continuam sem diferença contra a `main` |
| No scope creep | ✅ |
| Matches patterns | ✅ Comentário com o porquê (`:84-85`: "num PR o commit é o de merge…"), português, mesmo estilo dos passos existentes |
| Spec-anchored outcome check | ✅ As asserções miram os valores da spec (os dois SHAs na mensagem, nome exato do zip, `--require-hashes`/`--no-build-isolation` no comando executado, SHA-256 real) |
| Per-layer Coverage Expectation | ✅ Funções e orquestração do build e regras de Release cobertas (M5/M9 mortos); workflow por `actionlint` + CI, conforme a matriz. ⚠️ Limitação conhecida: a lógica de shell do passo da tag não tem teste automatizado (M13-M15) |
| Every test maps to a spec requirement | ✅ Os 36 testes mapeiam para AC ou Done-when (sem teste novo nesta rodada) |
| Documented guidelines followed: `CLAUDE.md` ("Como validar uma conversão": soma dos 12 meses × Total) | ✅ Refletido no `CONFERIR` do WIN-06 |

Observações (não bloqueiam):
- **O1** `README.md:140-141`: o exemplo "(por exemplo, um build anterior que falhou)" é pouco provável, porque um build com falha nunca chega ao job `release`, que é o único que cria a tag. O caso real é uma tag criada à mão em outro commit ou uma Release anterior do mesmo `VERSAO`. Cosmético.
- **O2** (ainda aberta desde a rodada 2) `.github/workflows/windows.yml:89-93`: qualquer erro do `gh api` (rede, limite de taxa) vira `SHA_TAG=""` e desliga a checagem. Agora isso só acontece em execução que publica, e o WIN-14 continua impedindo a sobrescrita de uma Release existente. Risco baixo.
- **O3** Push de tag **anotada**: pela doc do GitHub, o `GITHUB_SHA` do push é o "tip commit" e o `gh api .../commits/<tag>` devolve o commit (desreferenciado), então os dois batem. O README ensina tag leve (`README.md:123` `git tag v1.2`). Confirmar no 1º push de tag.
- **O4** Bookkeeping: `tasks.md:477` (caixa "Gate CI: PR verde" da T15) e `tasks.md:12` (Status "In Progress") estão desatualizados em relação ao run 34633772453.

---

## Gate Check

- **Gate command**: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`
- **Resultado do gate**: 36 passed, 0 failed, 0 skipped (8,4 s, e2e incluídos); `py_compile` exit 0; `actionlint` exit 0
- **Test count before feature**: 0 (o repo não tinha testes); rodada 1: 30; rodada 2: 36
- **Test count after feature**: 36
- **Delta**: +36 (nenhum teste novo nem removido na rodada 3; a rodada só mexeu em YAML e docs)
- **Skipped tests**: nenhum
- **Failures**: nenhuma
- **CI Windows** (run 34633772453, HEAD 7983506): `31 passed, 5 deselected` com o Python do host (`run3.log:202`) e `5 passed, 31 deselected` com o `python.exe` da pasta (`run3.log:397-403`)

---

## Fix Plans

Nenhum bloqueante. Recomendações opcionais:

### Fix R1 (Minor, fora desta feature): teste da lógica do passo da tag

- **Root cause**: o `if` do `PUBLICA` e o tratamento do código de saída do `gh` são lógica com ramos, e hoje só o `actionlint` os cobre (M13-M15 sobrevivem).
- **Fix task**: um teste em `tests/` que (a) carrega `.github/workflows/windows.yml` e afirma que a expressão `PUBLICA` do passo `tag` é igual ao `if` do job `release` (mata M14/M15); (b) extrai o `run` do passo e o executa em bash com `gh`/`python` falsos para `PUBLICA ∈ {"", "false", "true"}` × tag noutro commit, afirmando saída 0/0/1 e os dois SHAs no stderr (mata M13). O runner Windows tem bash (Git Bash). Alternativa: mover o corpo do passo para `release.py` e testar em Python.
- **Priority**: Minor

### Fix R2 (Cosmetic): `README.md:140-141`, trocar o exemplo por "uma tag criada à mão em outro commit".

### Fix R3 (bookkeeping): marcar `tasks.md:477` e atualizar `tasks.md:12`.

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| WIN-01 | Implementing | Implementing (estrutura verificada; execução pendente pós-merge) |
| WIN-02 | Verified | ✅ Verified |
| WIN-03 | Verified | ✅ Verified |
| WIN-04 | Verified | ✅ Verified |
| WIN-05 | Verified | ✅ Verified |
| WIN-06 | Verified | ✅ Verified |
| WIN-07 | Verified | ✅ Verified |
| WIN-08 | Verified | ✅ Verified |
| WIN-09 | Verified | ✅ Verified |
| WIN-10 | Verified | ✅ Verified |
| WIN-11 | Implementing | Implementing (estrutura verificada; execução pendente: 1ª tag) |
| WIN-12 | Verified | ✅ Verified |
| WIN-13 | Verified | ✅ Verified |
| WIN-14 | Implementing | Implementing (estrutura verificada; execução pendente) |
| WIN-15 | Verified | ✅ Verified |
| WIN-16 | Verified | ✅ Verified |
| WIN-17 | Verified | ✅ Verified |
| WIN-18 | Verified | ✅ Verified |
| WIN-19 | Verified | ✅ Verified |
| WIN-20 | Verified | ✅ Verified |
| WIN-21 | Verified | ✅ Verified |
| WIN-22 | Needs Fix | Implementing (G1 fechado; estrutura + simulação; execução pendente: dispatch após o merge) |
| WIN-23 | Needs Fix | Implementing (lógica Verified por teste + escopo de teste CI✔; ramo que publica: estrutura + simulação, execução pendente) |
| WIN-24 | Needs Fix | ✅ Verified (run 34633772453 + simulação do cenário pós-1ª Release) |
| WIN-25 | Verified | ✅ Verified |

---

## Summary

**Overall**: ✅ Ready para o merge. Cinco ACs dependem de conferência pós-merge, que só pode acontecer depois dele.

**Spec-anchored check**: 25/25 ACs com evidência que bate com a spec (20 Verified por teste ou CI; 5 por estrutura + simulação, com execução pendente por desenho); 0 spec-precision gaps
**Sensor**: 2/2 mutações no código Python mortas; 3 mutações no YAML sobreviveram à suíte (limitação conhecida da matriz; M13 morto pelo simulador independente)
**Gate**: 36 passed, 0 failed; `py_compile` e `actionlint` ok; CI Windows verde em HEAD (run 34633772453)

**What works**: build no Windows real com o Python da pasta (imports com `clr`, OCR, ficha de texto e escaneada com valores exatos, `/api/versao`), lock com hash em duas etapas, zip com raiz única e SHA-256 igual ao digest do artefato, "nada publica se falhar" (provado por uma falha real), PR que só testa e não é bloqueado por tag antiga (G1 fechado), regras de tag, versão e commit com testes que discriminam, documentação coerente com o comportamento.

**Issues found**: nenhum bloqueante. R1 (teste da lógica de shell do workflow, Minor), R2 (exemplo do README, cosmético), R3 (caixas do `tasks.md`).

**Next steps (pós-merge, para o usuário)**:
1. `gh workflow run windows.yml -f publicar=false` na `main` → build verde, artefato de 14 dias, **nenhuma** tag nem Release (fecha WIN-22 e o "não checa" do WIN-23 no dispatch).
2. Testar o zip do artefato numa máquina com Smart App Control ligado (UAT, `spec.md:193`).
3. Publicar a 1ª versão (`git tag v1.1 && git push origin v1.1`, ou "Run workflow" com `publicar` marcado) → Release `v1.1` com `Conversor-de-Ficha-Financeira-v1.1-windows-x64.zip` e SHA-256 nas notas (fecha WIN-01/WIN-11 e o ramo "publica" do WIN-23; confirma O3 se a tag for anotada).
4. Reenviar o workflow para a mesma `v1.1` → falha em "Release não pode existir" sem alterar a Release (fecha WIN-14).
5. Abrir um PR qualquer que mexa no app **depois** da `v1.1` → build verde sem subir o `VERSAO` (prova de ponta a ponta do G1).
