# Build Windows Validation (rodada 4 — achados do UAT com Smart App Control)

## Validation: build-windows - PASS

**Date**: 2026-09-14
**Spec**: `.specs/features/build-windows/spec.md` (WIN-01..WIN-28; WIN-26/27/28 novos nesta rodada)
**Diff range**: lote desta rodada `c632333..HEAD` (`3d9c1ea`, `3433e80`, `642d692`, `1b59f7b`); feature inteira `main..HEAD` (27 commits)
**Verifier**: sub-agente independente (autor ≠ verificador), rodada 4

Veredito: **PASS**. Os dois bloqueios que o UAT manual encontrou na máquina do usuário (Windows 11 com Smart App Control) estão tratados no lugar certo: as instruções que o usuário lê (notas da Release, `LEIA-ME.txt`, README) e uma **guarda no build** que impede publicar um zip que não dá para extrair. As três ACs novas têm asserção que mira o valor da spec, e cada uma morre quando mutada.

Além do gate local, esta rodada tem uma evidência que as anteriores não tinham: **eu baixei o zip que o CI produziu em HEAD e o inspecionei**. O `sha256` do arquivo baixado (`2ec1ffde…c1c8`) bate com o log do build (`run4.log:378`) e com o `digest` do artefato na API do GitHub, então o que eu abri é exatamente o que seria publicado. Dentro dele: 4566 entradas, **uma** pasta raiz, `Conversor.bat` e `LEIA-ME.txt` no 1º nível, a **maior entrada tem 155 caracteres** (o número que o `CLAUDE.md` afirma) e o `LEIA-ME.txt` real tem 1354 bytes, **só ASCII**, com as duas mensagens de erro do Windows e o código `0x80010135`.

Um mutante sobreviveu: remover o `reconfigure(encoding="utf-8")` de `release.py` **passa** o gate no Mac. O comportamento não está sem prova — o CI do Windows reprovou o commit anterior exatamente por isso (run 34843217833, `test_cli_notas_calcula_o_sha256_do_zip`, exit 1) e ficou verde depois da correção (run 34843464216) — mas o gate que o autor roda no Mac não pega a regressão. Isso vira a única lacuna desta rodada (Minor, `Fix R4`), com correção de uma linha e prova de que funciona (abaixo).

Continuam pendentes **por desenho** os 5 ACs que só executam depois do merge/da 1ª tag (WIN-01, WIN-11, WIN-14, WIN-22 e o ramo "publica" do WIN-23). Nada mudou neles nesta rodada — o diff não toca `.github/workflows/windows.yml`.

**Critério para `Verified`** (o mesmo das rodadas 2-3): **(a)** asserção de teste que mira o valor definido na spec e que morre quando mutada, **ou (b)** execução real no CI Windows com linha de log citável. Evidência só estática vale como `Verified` apenas para ACs declarativos (permissões, conteúdo de documentação).

Fontes de evidência de CI (repo `Fluix-Solutions/conversor-ficha-financeira`):
- **Run 34843464216** (pull_request, `headSha` `1b59f7b` = HEAD): job `build` **success**, job `release` **skipped**. Log em `scratchpad/run4.log`, citado como `run4.log:N`. `run4.log:22` `Contents: read`; `:168` `PUBLICA: ` (vazio em PR); `:202` `33 passed, 5 deselected` com o Python do host; `:395` `38 items / 33 deselected / 5 selected` e `:403` `5 passed, 33 deselected` com o `python.exe` da pasta; `:377` `tamanho do zip: 153.5 MB`; `:378` `sha256: 2ec1ffde…c1c8`.
- **Run 34843217833** (pull_request, `headSha` `642d692` = commit anterior): **failure**. `FAILED tests/test_release.py::test_cli_notas_calcula_o_sha256_do_zip - subprocess.CalledProcessError: … 'release.py', 'notas', … returned non-zero exit status 1` / `1 failed, 32 passed, 5 deselected`. É a prova de que o bug de encoding era real e de que a suíte o pega **no Windows**.
- **Artefato 10346614659** (`Conversor-de-Ficha-Financeira-v1.1-windows-x64.zip`, 153 514 174 bytes, `expired=false`): baixado e inspecionado; `digest sha256:2ec1ffde…c1c8`.

---

## Rodada 3 → Rodada 4 (UAT)

O UAT manual com Smart App Control, que a rodada 3 deixou como pendência (`spec.md:202`), **foi feito** (2026-09-11/14) e achou dois bloqueios. Esta rodada verifica as correções deles.

| Achado do UAT | O que quebrava | Correção (T17-T19 + fix) | Evidência | Situação |
| ------------- | -------------- | ------------------------ | --------- | -------- |
| **B1 (Blocker)**: o SAC bloqueia o `Conversor.bat` vindo do zip **baixado** — `.bat` com Mark-of-the-Web está na lista de tipos barrados e o diálogo **não** oferece "executar assim mesmo". Desbloquear o zip antes de extrair resolve, e o app converteu ficha escaneada | O usuário não conseguia abrir o programa e não tinha como saber o motivo | Passo a passo nas notas (`release.py:69-81`), no `LEIA-ME.txt` (`construir_portatil.py:77-85`) e no README (`README.md:114-128`); assunção da spec atualizada (`spec.md:46`) | `tests/test_release.py:88-95` (6 termos + ordem), `tests/test_construir.py:165-168` (LEIA-ME montado pelo `main`), e o `LEIA-ME.txt` do **zip real** do CI | ✅ Resolvido |
| **B2 (Blocker)**: extrair de uma pasta funda (transferência do WhatsApp) falha com `0x80010135: Caminho muito longo`. Mover o zip para Downloads resolve | Extração abortada no meio, sem pasta utilizável | Instrução nas mesmas 3 fontes **+ guarda no build**: `zipar` recusa entrada acima de `LIMITE_CAMINHO = 160` (`construir_portatil.py:46`, `:149-156`); assunção nova (`spec.md:47`) | `tests/test_construir.py:76-93` (161 → `RuntimeError` citando entrada e tamanho; 160 → zip gerado); zip real do CI com maior entrada = **155** | ✅ Resolvido |
| **B3 (Minor, achado pelo CI)**: o "→" das notas novas não existe em cp1252 e o `print` morria com `UnicodeEncodeError` no console do Windows | O job de testes unitários do Windows ficava vermelho; num Windows local, `release.py notas` não rodaria | `main()` força UTF-8 em stdout/stderr (`release.py:109-116`) | Run 34843217833 (vermelho, pré-fix) → run 34843464216 (verde, HEAD). Reprodução local: em `642d692` com `PYTHONIOENCODING=cp1252` o CLI sai **1** com `UnicodeEncodeError: 'charmap' codec can't encode character '→'`; em HEAD sai **0** e o stdout é UTF-8 | ✅ Resolvido (mas sem teste que pegue no Mac → `Fix R4`) |

Pendências da rodada 3: **R1** (teste da lógica de shell do passo da tag) e **G3** (`__pycache__` no zip) continuam nas Deferred Ideas (`context.md:61-62`) — o `__pycache__` ainda está no zip real, como esperado. **R2**/**R3** (cosméticos/bookkeeping) não foram tratados; não bloqueiam.

---

## Task Completion

| Task | Status | Notes |
| ---- | ------ | ----- |
| T1-T16 | ✅ Done | Verificadas nas rodadas 1-3; código inalterado nesta rodada (`git diff c632333..HEAD` não toca `.github/`, `requirements-windows.lock`, `tests/test_lock.py`, `tests/test_portatil.py`) |
| T17 notas com o passo a passo | ✅ Done | `release.py:69-81`; teste em `tests/test_release.py:88-95`. O 3º "Done when" (saída em UTF-8) foi cumprido no commit próprio `1b59f7b` |
| T18 LEIA-ME + limite de caminho | ✅ Done | `construir_portatil.py:46`, `:77-85`, `:149-156`; testes em `tests/test_construir.py:76-93` e `:165-168`. A caixa "Gate CI: PR verde" (`tasks.md:562`) está **desmarcada**, mas o run 34843464216 em HEAD está verde e o maior caminho real é 155 — falta só marcar (o Verifier não edita `tasks.md`) |
| T19 README + CLAUDE.md | ✅ Done | `README.md:114-128`, `:171-172`; `CLAUDE.md:191-208`. O "Where" da task cita só o `README.md`, mas o próprio "Done when" pede o `CLAUDE.md` também |

Bookkeeping para o orquestrador: `design.md` para em "Correções depois da verificação (T9-T16)" (`design.md:179`) e não descreve T17-T19; a matriz de cobertura (`tasks.md:22-23`) não lista WIN-26/27/28; os checkboxes de Goals e Success Criteria da spec (`spec.md:9-11`, `:201-203`) seguem desmarcados, embora o UAT com SAC (`spec.md:202`) já tenha acontecido.

---

## Spec-Anchored Acceptance Criteria

Legenda: **CI✔** = executado num run do Windows com linha citável; **Zip✔** = conferido no zip real que o CI produziu em HEAD; **Estrutura** = verificado pelo YAML (e por simulação local), com execução pendente pós-merge.

### ACs novos desta rodada

| Criterion (WHEN X THEN Y) | Spec-defined outcome | `file:line` + assertion | Result |
| ------------------------- | -------------------- | ----------------------- | ------ |
| **WIN-26** — WHEN a Release é criada THEN as notas trazem o passo a passo (Downloads → Desbloquear → Extrair tudo → `Conversor.bat`) citando "Controle de Aplicativo Inteligente" e "Caminho muito longo" | As 6 cadeias presentes **e** Desbloquear antes de Extrair tudo | `tests/test_release.py:91-94` - `for termo in ("Downloads", "Desbloquear", "Extrair tudo", "Conversor.bat", "Controle de Aplicativo Inteligente", "Caminho muito longo"): assert termo in notas`; `tests/test_release.py:95` - `assert notas.index("Desbloquear") < notas.index("Extrair tudo")`. Texto: `release.py:69-81`. Caminho até a Release: `.github/workflows/windows.yml:154` `python3 release.py notas … > notas.md` + `:158` `--notes-file notas.md`. Execução do CLI conferida localmente (saída com os 4 passos, exit 0) | ✅ PASS (M19 morto) |
| **WIN-27** — IF alguma entrada do zip tiver mais de 160 caracteres THEN the build SHALL falhar antes de publicar, citando a entrada e o tamanho | `RuntimeError` com o nome da entrada **e** o número de caracteres; 160 exatos passam | `tests/test_construir.py:88` - `assert nome in str(e.value)`; `:89` - `assert str(cp.LIMITE_CAMINHO + 1) in str(e.value)`; `:92-93` - com 160 o zip é gerado e `max(len(n) …) == cp.LIMITE_CAMINHO`. Código: `construir_portatil.py:152-156`. "Antes de publicar": `zipar` roda dentro do passo `Monta a pasta e o zip` (`.github/workflows/windows.yml:107`), antes do upload (`:115`) e do job `release` (`:122`); WIN-08 garante que falha não publica | ✅ PASS (M16b e M17 mortos; **Zip✔** maior entrada real = 155) |
| **WIN-28** — The `LEIA-ME.txt` SHALL explicar "Controle de Aplicativo Inteligente bloqueou" (desbloquear e extrair de novo) e "Caminho muito longo" (mover para Downloads) | As duas mensagens e as duas saídas no arquivo que vai na pasta | `tests/test_construir.py:165-168` - `leiame = (alvo / "LEIA-ME.txt").read_text(…)` e `for termo in ("Desbloquear", "Controle de Aplicativo Inteligente", "Caminho muito longo", "Downloads"): assert termo in leiame` (lido da pasta montada pelo `main`, não da constante). Texto: `construir_portatil.py:77-85` | ✅ PASS (M20 morto; **Zip✔** `LEIA-ME.txt` real com os 4 termos + `0x80010135`, 1354 bytes, só ASCII) |

### ACs reconfirmados nesta rodada

| Criterion | Spec-defined outcome | `file:line` + assertion | Result |
| --------- | -------------------- | ----------------------- | ------ |
| **WIN-13** notas | SHA-256 + Windows 10/11 64 bits, .NET Framework 4.7.2+, WebView2 Runtime | `tests/test_release.py:82-85` - `assert sha in notas`, `"Windows 10/11 64 bits"`, `".NET Framework 4.7.2"`, `"WebView2"`; `:121` SHA-256 real pelo CLI. Texto: `release.py:83-93`. A reescrita da seção "Como instalar" **não** mexeu em "Requisitos"/"Integridade": conferido na saída real do CLI (`Windows 10/11 64 bits`, `.NET Framework 4.7.2 ou mais novo`, `WebView2 Runtime`, `SHA-256 de …`) | ✅ PASS (sem regressão) |
| **WIN-12** pasta raiz única | `Conversor de Ficha Financeira/` com `.bat` e `LEIA-ME.txt` no 1º nível | `tests/test_construir.py:70-72`, `:146-147`. **Zip✔**: o zip real tem `raizes de 1º nível == {'Conversor de Ficha Financeira'}` em 4566 entradas, com `Conversor de Ficha Financeira/Conversor.bat` e `…/LEIA-ME.txt` presentes | ✅ PASS (reforçado) |
| **WIN-10** registro no log | Pacotes com versão, tamanho e SHA-256 do zip | `tests/test_construir.py:149-150`; CI `run4.log:377-378`. **Zip✔**: o `sha256` do log é igual ao do arquivo baixado e ao `digest` do artefato na API | ✅ PASS (CI✔ + Zip✔) |
| **WIN-20** README | Gerar versão pelo Mac, testar sem publicar, atualizar lock (+ agora o procedimento de instalação) | `README.md:114-128` (instalação validada com SAC: Downloads, Desbloquear, Extrair tudo, `Conversor.bat`, as duas mensagens de erro), `:133-158` (tag/botão, testar sem publicar, tag×commit), `:171-172` (limite de 160), `:174+` (lock) | ✅ PASS |
| **WIN-21** CLAUDE.md | Fluxo, repo, `pip --platform`, Python 3.12 (+ agora o UAT e o limite) | `CLAUDE.md:191-193` (UTF-8 no `release.py`), `:197-208` (UAT com SAC: bloqueio do `.bat` com MotW, Desbloquear, `0x80010135` da pasta do WhatsApp, `LIMITE_CAMINHO` 160 com a maior real em 155, converteu ficha escaneada); `:135` repo; `:172-176` `pip --platform`; `:184-185` 3.12 | ✅ PASS |
| **WIN-02/03/04/05/06/07/08/09/15/16/17/18/19/24/25** | (ver rodada 3) | Reconferidos por varredura: nenhuma linha de teste ou de código desses caminhos foi tocada nesta rodada (`git diff c632333..HEAD` mexe só em `construir_portatil.py`, `release.py`, `tests/test_construir.py`, `tests/test_release.py`, docs e specs); os 38 testes passam; o CI em HEAD repete os mesmos PASSED (`run4.log:395-403`) | ✅ PASS (carregados da rodada 3, sem regressão) |
| **WIN-01/11/14/22** e o ramo "publica" do **WIN-23** | (ver rodada 3) | `.github/workflows/windows.yml` **não mudou** nesta rodada; a estrutura e a simulação da rodada 3 continuam valendo | ⏳ Estrutura — execução pendente por desenho (pós-merge / 1ª tag) |

**Status**: ✅ 28/28 ACs com evidência. 23 `Verified` (teste, CI ou zip real); 5 com execução pendente por desenho; **0 spec-precision gaps** — as três ACs novas nomeiam as cadeias exatas e a ordem, e os testes miram exatamente essas cadeias.

---

## Discrimination Sensor

Rodado em `git worktree add --detach scratchpad/wt4 HEAD`, com o `.venv/bin/python` do repo por caminho absoluto, `PYTHONDONTWRITEBYTECODE=1` e `-p no:cacheprovider`. Baseline no worktree: **38 passed**. Cada mutação foi aplicada por script, testada com `pytest tests -q` e desfeita com `git checkout -- .`. Worktrees auxiliares em `c632333` e `642d692` foram usados só para reproduzir o bug de encoding. Os três worktrees foram removidos (`git worktree list` mostra só a árvore real) e o `git status --porcelain` da árvore real ficou **idêntico** antes e depois (só os 4 diretórios não rastreados de sempre).

| Mutation | File:line | Description | Killed? |
| -------- | --------- | ----------- | ------- |
| M16 | `construir_portatil.py:46` | `LIMITE_CAMINHO = 160` → `10000` (a guarda nunca dispara) | ✅ Killed — `test_zip_recusa_caminho_longo_demais` falha. Ressalva: morre por `OSError` do sistema de arquivos (o teste deriva o nome do fixture da própria constante e 10001 caracteres não cabem num nome de arquivo), não pela asserção. Por isso rodei a variante M16b |
| M16b | `construir_portatil.py:152-156` | Guarda inteira (`if` + `raise`) removida de `zipar` | ✅ Killed — `tests/test_construir.py:86` `pytest.raises(RuntimeError)` falha (`Failed: DID NOT RAISE`) |
| M17 | `construir_portatil.py:152` | `len(maior) > LIMITE_CAMINHO` → `>=` (off-by-one no limite exato) | ✅ Killed — o caso de 160 caracteres passa a levantar `RuntimeError` (`construir_portatil.py:153`) |
| M18 | `release.py:112-116` | Bloco `reconfigure(encoding="utf-8")` removido de `main()` | ❌ **Sobreviveu** ao gate no Mac (38 passed). **Morto com `PYTHONIOENCODING=cp1252`**: `tests/test_release.py` cai de 18 passed para `3 failed, 15 passed` (`test_cli_notas_calcula_o_sha256_do_zip`, `test_cli_tag_divergente_sai_com_1`, `test_cli_tag_em_outro_commit_sai_com_1`); HEAD intacto no mesmo ambiente = 18 passed. E o CI do Windows já matou de verdade em `642d692` (run 34843217833). → `Fix R4` |
| M19 | `release.py:77` | Passo 3 das notas trocado de "Botão direito no zip → **Extrair tudo** → **Extrair**." para "Descompacte o zip." | ✅ Killed — `tests/test_release.py:94` `AssertionError` (termo `Extrair tudo`) |
| M20 | `construir_portatil.py:83-85` | Parágrafo "Caminho muito longo" removido do `LEIAME` | ✅ Killed — `test_main_monta_instala_do_lock_e_registra_o_zip` falha em `tests/test_construir.py:168` |

**Sensor depth**: lightweight (6 mutações, todas no código novo desta rodada)
**Result**: 5/6 killed pelo gate; o 6º (M18) é morto pelo CI do Windows e por um `PYTHONIOENCODING=cp1252` local, mas **não** pelo gate que o autor roda no Mac → `Fix R4` (Minor).

---

## Interactive UAT Results

Realizado pelo usuário na própria máquina (Windows 11 com Smart App Control em ENFORCE), 2026-09-11/14, com o zip **baixado**. Registrado aqui a partir do relato do orquestrador.

| # | Test | Result | Details |
| - | ---- | ------ | ------- |
| 1 | Abrir `Conversor.bat` do zip baixado, sem desbloquear | ❌ Issue | "SAC blocked `Conversor.bat`… no override offered" — Severidade inferida: **Blocker** (contém "blocked"). Corrigido por instrução (B1) |
| 2 | Desbloquear o zip (Propriedades) → extrair → abrir `Conversor.bat` | ✅ Pass | "the app then opened and converted a scanned ficha" |
| 3 | Extrair de uma pasta funda (transferência do WhatsApp) | ❌ Issue | "`0x80010135: Caminho muito longo`" — Severidade inferida: **Blocker** ("failed"/erro). Corrigido por instrução + guarda no build (B2) |
| 4 | Extrair a partir de Downloads | ✅ Pass | "Moving the zip to Downloads fixed it" |

Os dois problemas são de **ambiente do Windows**, não de código do app: nenhum deles pede mudança em `converter.py`/`server.py`/`app_desktop.py`, e nenhum foi feito.

---

## Code Quality

| Principle | Status |
| --------- | ------ |
| Minimum code | ✅ A guarda de caminho são 8 linhas dentro de `zipar`, reaproveitando a lista de entradas que o laço do zip já precisava (`construir_portatil.py:149-159`: o `rglob`+`relative_to` passou a ser calculado uma vez e reusado, em vez de duplicado). A correção de encoding é um laço de 5 linhas |
| Surgical changes | ✅ O diff da rodada mexe em 2 arquivos de código, 2 de teste, 2 de documentação e 2 de spec. `converter.py`, `server.py`, `app_desktop.py`, `web/`, `Dockerfile`, `requirements.txt` e `.github/workflows/windows.yml` **sem nenhuma diferença** (o app inteiro segue idêntico à `main`: `git diff --stat main..HEAD -- converter.py server.py app_desktop.py app.py app_web.py web/ ui/ Dockerfile requirements.txt Procfile` → vazio) |
| No scope creep | ✅ Nada além do que o UAT pediu. Não tentaram lançador assinado, nem encurtar caminhos de dependência, nem mexer no `__pycache__` |
| No abstractions for single-use code | ✅ `LIMITE_CAMINHO` é uma constante com comentário do porquê no lugar de um número solto (`construir_portatil.py:45-46`); não há função nova |
| Matches patterns | ✅ Português nas mensagens e comentários; `RuntimeError` com mensagem explicativa, como as outras guardas do arquivo (`:103`, `:121`); `except Exception:  # noqa: BLE001 - <motivo>` é exatamente o padrão do repo (`server.py:135`, `app_desktop.py:147`); docstring do `zipar` explica o *porquê* do limite, não o *o quê* |
| **`LEIA-ME.txt` só ASCII** | ✅ Conferido nos dois lados: `cp.LEIAME.encode("ascii")` passa (1321 caracteres) e o `LEIA-ME.txt` **do zip real** tem 1354 bytes todos < 128. O texto novo foi escrito sem acento de propósito ("nao ser seguro", "esta numa pasta funda", "extraia de la"), igual ao resto do arquivo. Nada renderiza torto num Bloco de Notas em cp1252 |
| Spec-anchored outcome check | ✅ As asserções miram as cadeias exatas que a spec nomeia (as 6 das notas + a ordem; entrada e tamanho na mensagem de erro; os 4 termos do LEIA-ME) |
| Per-layer Coverage Expectation | ⚠️ Regras de Release e funções do build cobertas 1:1 com WIN-26/27/28 e mortas quando mutadas — **exceto** o caminho de encoding do `main()` de `release.py`, que a matriz cobriria em "todos os ramos" (`tasks.md:22`) e que hoje só o Windows pega (M18). Documentação segue "none" na matriz, como acordado |
| Every test maps to a spec requirement | ✅ Os 2 testes novos mapeiam para WIN-26 e WIN-27/28; nenhum teste órfão |
| Documented guidelines followed: `CLAUDE.md` ("Como validar uma conversão") | ✅ Não se aplica a esta rodada (nada mexe em conversão); o `CONFERIR` do WIN-06 continua valendo |

Observações que não bloqueiam:
- **O5** `release.py:112-116`: o `reconfigure` roda **depois** do `parse_args`, então mensagens do próprio argparse (`--help`, erro de argumento) ainda saem na página de código do console. Inofensivo hoje — a descrição e as opções são ASCII —, mas mover o bloco para antes do `parse_args` seria mais robusto.
- **O6** O passo que publica roda em **`ubuntu-latest`** (`.github/workflows/windows.yml:126`, `:154`), onde o stdout redirecionado já sairia em UTF-8. O que o `UnicodeEncodeError` derrubava era o **job de testes unitários do Windows** (e um `release.py notas` rodado à mão num Windows). Ou seja: o risco retirado era de CI vermelho e de uso local, não de Release com nota corrompida. O `reconfigure` continua sendo um ganho (deixa explícito o que hoje depende do locale do runner).
- **O7** A margem entre a maior entrada real (**155**) e o limite (**160**) é de **5 caracteres**, e a entrada mais comprida vem de uma dependência: `…/site-packages/onnxruntime/tools/ort_format_model/ort_flatbuffers_py/fbs/RuntimeOptimizationRecordContainerEntry.py`. Uma atualização do `onnxruntime` com um nome de arquivo mais longo derruba o build — que é o comportamento desejado (falhar alto), mas exigirá uma decisão na hora: subir o limite encurta o orçamento de caminho da pasta do usuário. Vale saber disso antes de mexer no lock.
- **O8** `README.md:170-172`: uma linha em branco separa o último item da lista "O que o workflow faz" dos anteriores, e esse item novo ("recusa o zip se algum caminho interno passar de 160 caracteres") vem **depois** do item que fecha a lista ("só publica se tudo passar"). Cosmético.
- **O9** `README.md:128` diz "Esses dois passos" depois de uma lista de **quatro** passos (refere-se aos passos 1 e 2). Cosmético.
- **O10** `CLAUDE.md:202` diz que acabar com o passo de desbloquear "exige um lançador assinado (ideia adiada)", mas as Deferred Ideas registram "Instalador assinado" (`context.md:59`), que não é a mesma coisa. Um item explícito ("lançador assinado no lugar do `.bat`, para o SAC não barrar o zip baixado") evitaria perder a ideia.
- **O11** Continua valendo a **O2** da rodada 3 (erro do `gh api` vira `SHA_TAG=""` e desliga a checagem) e a **O3** (push de tag anotada). Nada nesta rodada mexe nisso.

---

## Edge Cases

- [x] Entrada com exatamente 160 caracteres é aceita (limite é `>`, não `>=`): `tests/test_construir.py:92-93`; M17 prova que a asserção discrimina.
- [x] Pasta sem arquivo nenhum não quebra o `max`: `construir_portatil.py:151` usa `default=""` — `len("") = 0`, nenhuma exceção. Sem teste dedicado (caso impossível no fluxo: o `main` copia os itens antes de zipar). Cosmético.
- [x] Console sem UTF-8 (cp1252) ao gerar as notas: `release.py:112-116`; provado com `PYTHONIOENCODING=cp1252` (HEAD 18 passed; `642d692` exit 1 com `'→'`).
- [x] Fluxo sem `reconfigure` (stdout substituído, p.ex. pelo `capsys`): `except Exception: pass` em `release.py:115-116` — os 38 testes, que rodam com stdout capturado, passam.
- [x] Edge cases das rodadas anteriores (python.org fora do ar, tag fora do formato, tags simultâneas, `CONFERIR` no OCR): inalterados, ver rodada 3.

---

## Gate Check

- **Gate command**: `.venv/bin/python -m pytest tests -q && .venv/bin/python -m py_compile construir_portatil.py release.py && actionlint`
- **Result**: **38 passed**, 0 failed, 0 skipped (6,33 s, e2e incluídos); `py_compile` exit 0; `actionlint` exit 0. Saída lida sem `pipe` que engolisse o código de retorno (`set -o pipefail` + `PYTEST_EXIT=0` registrado)
- **Test count before feature**: 0 (o repo não tinha testes)
- **Test count after feature**: 38
- **Delta**: +38 no total da feature; **+2 nesta rodada** (rodada 3 = 36): `test_notas_ensinam_desbloquear_antes_de_extrair`, `test_zip_recusa_caminho_longo_demais`. Nenhum teste removido nem enfraquecido — `test_main_monta_instala_do_lock_e_registra_o_zip` **ganhou** 4 asserções (`tests/test_construir.py:165-168`)
- **Skipped tests**: nenhum
- **Failures**: nenhuma
- **CI Windows** (run 34843464216, HEAD `1b59f7b`): `33 passed, 5 deselected` com o Python do host (`run4.log:202`) e `5 passed, 33 deselected` com o `python.exe` da pasta (`run4.log:403`); job `release` skipped; 0 tags e 0 Releases no repo

---

## Fix Plans

Nenhum bloqueante.

### Fix R4 (Minor): o gate do Mac não pega a regressão de encoding

- **Root cause**: o único teste que executa o CLI de notas (`tests/test_release.py:113-121`) chama `subprocess.run(..., text=True)` herdando o ambiente. No Mac o locale é UTF-8, então o `print` funciona com ou sem o `reconfigure` — o mutante M18 sobrevive. Só o console cp1252 do runner Windows expõe o problema, e a matriz de cobertura (`tasks.md:22`) promete "todos os ramos" para `release.py`.
- **Fix task**: em um dos testes de CLI, passar o ambiente com a página de código do Windows e afirmar que a saída chega inteira. Ex.: `env={**os.environ, "PYTHONIOENCODING": "cp1252"}` no `subprocess.run` de `test_cli_notas_calcula_o_sha256_do_zip`, com `encoding="utf-8"` na leitura e `assert "→" in r.stdout`. Verificado: com essa variável, HEAD passa e M18 falha em 3 testes — a asserção discrimina em qualquer host.
- **Where**: `tests/test_release.py:113-121`
- **Done when**: o teste passa em HEAD e falha quando o bloco `release.py:112-116` é removido, sem depender do locale da máquina.
- **Priority**: Minor

### Fix R5 (bookkeeping)

- `design.md` para em T16 (`design.md:179`): acrescentar T17-T19 (mesma lacuna que a G2 da rodada 3, que foi corrigida).
- Matriz de cobertura (`tasks.md:22-23`): incluir WIN-26 na linha de `release.py` e WIN-27/28 na de `construir_portatil.py`.
- `tasks.md:562`: marcar "Gate CI: PR verde" (run 34843464216 verde, maior caminho real 155).
- `spec.md:202`: o UAT com Smart App Control **aconteceu** — o checkbox pode ser marcado quando o usuário confirmar que é o zip da Release (o UAT usou o zip baixado do build).
- Registrar em `context.md` (Deferred Ideas) a ideia do **lançador assinado** que a `CLAUDE.md:202` menciona.
- **Priority**: Minor / cosmético

### Fix R6 (cosmético)

- `README.md:170-172`: tirar a linha em branco e mover o item do limite de 160 para antes do item "só publica se tudo passar".
- `README.md:128`: "Esses dois passos" → "O desbloqueio e a pasta curta".
- **Priority**: Cosmetic

---

## Requirement Traceability Update

| Requirement | Previous Status | New Status |
| ----------- | --------------- | ---------- |
| WIN-01 | Implementing | Implementing (estrutura verificada; execução pendente pós-merge) |
| WIN-02..WIN-10 | Verified | ✅ Verified (sem regressão; WIN-10 agora com Zip✔) |
| WIN-11 | Implementing | Implementing (estrutura verificada; execução pendente: 1ª tag) |
| WIN-12 | Verified | ✅ Verified (reforçado: zip real do CI com raiz única) |
| WIN-13 | Verified | ✅ Verified (reconfirmado após a reescrita das notas) |
| WIN-14 | Implementing | Implementing (estrutura verificada; execução pendente) |
| WIN-15..WIN-19 | Verified | ✅ Verified |
| WIN-20 | Verified | ✅ Verified (agora com o procedimento de instalação) |
| WIN-21 | Verified | ✅ Verified (agora com o UAT e o limite de caminho) |
| WIN-22 | Implementing | Implementing (inalterado: o workflow não mudou) |
| WIN-23 | Implementing | Implementing (inalterado: o workflow não mudou) |
| WIN-24 | Verified | ✅ Verified (run 34843464216 repete o resultado em HEAD) |
| WIN-25 | Verified | ✅ Verified |
| **WIN-26** | Implementing | ✅ **Verified** (`tests/test_release.py:91-95`; M19 morto) |
| **WIN-27** | Implementing | ✅ **Verified** (`tests/test_construir.py:88-93`; M16b/M17 mortos; zip real = 155) |
| **WIN-28** | Implementing | ✅ **Verified** (`tests/test_construir.py:165-168`; M20 morto; `LEIA-ME.txt` do zip real) |

---

## Summary

**Overall**: ✅ Ready para o merge e para a publicação da `v1.1`.

**Spec-anchored check**: 28/28 ACs com evidência que bate com a spec (23 Verified por teste, CI ou zip real; 5 com execução pendente por desenho); **0 spec-precision gaps**
**Sensor**: 6 mutações, **5 mortas** pelo gate; 1 (M18, o `reconfigure` de UTF-8) sobreviveu no Mac e é morta pelo CI do Windows e por `PYTHONIOENCODING=cp1252` → `Fix R4`
**Gate**: 38 passed, 0 failed, 0 skipped; `py_compile` e `actionlint` exit 0; CI Windows verde em HEAD (run 34843464216, `release` skipped)

**What works**: os dois bloqueios do UAT estão cobertos onde o usuário olha (notas da Release, `LEIA-ME.txt`, README) e onde o build pode impedir o dano (`zipar` recusa caminho acima de 160; o zip real fica em 155). O `LEIA-ME.txt` embarcado é só ASCII, então abre sem caractere torto no Bloco de Notas. As notas chegam à Release por `--notes-file` e o CLI que as gera não morre mais em console cp1252. O zip que o CI produziu em HEAD foi baixado e conferido byte a byte contra o `sha256` do log: raiz única, `Conversor.bat` e `LEIA-ME.txt` no 1º nível. Nenhuma linha do app foi tocada nesta feature.

**Issues found**: `Fix R4` (Minor: o gate do Mac não mata M18 — uma linha de `env` resolve), `Fix R5` (bookkeeping: `design.md` sem T17-T19, matriz sem WIN-26/27/28, checkboxes), `Fix R6` (cosmético no README). Observações O5-O11 sem ação obrigatória, das quais vale destacar a **O7**: só 5 caracteres de folga até o limite de 160, e a entrada mais longa vem do `onnxruntime`.

**Next steps**:

Antes de publicar a `v1.1` (pós-merge, na `main`):
1. `gh workflow run windows.yml -f publicar=false` → build verde, artefato de 14 dias, **nenhuma** tag nem Release (fecha WIN-22 e o "não checa" do WIN-23 no dispatch).
2. Opcional, barato: aplicar o `Fix R4` para que a regressão de encoding também caia no gate do Mac.

Publicando:
3. `git tag v1.1 && git push origin v1.1` (ou "Run workflow" com `publicar` marcado) → Release `v1.1` com `Conversor-de-Ficha-Financeira-v1.1-windows-x64.zip`, SHA-256 e o novo passo a passo nas notas (fecha WIN-01/WIN-11/WIN-26 na Release e o ramo "publica" do WIN-23; confirma a O3 se a tag for anotada).
4. Reenviar o workflow para a mesma `v1.1` → falha em "Release não pode existir" sem alterar a Release (fecha WIN-14).

Depois de publicar:
5. Baixar o zip **da Release** (não do artefato) na máquina com SAC e repetir Downloads → Desbloquear → Extrair tudo → `Conversor.bat`, agora seguindo as instruções das próprias notas — é o que fecha o Success Criteria de `spec.md:202`.
6. Abrir um PR qualquer que mexa no app **depois** da `v1.1` → build verde sem subir o `VERSAO` (prova de ponta a ponta do G1 da rodada 3).
