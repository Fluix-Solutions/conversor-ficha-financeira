# Validation: json-desktop — PASS ✅ (rodada 2)

**Data**: 2026-09-14
**Spec**: `.specs/features/json-desktop/spec.md`
**Faixa do diff**: `f9260de..22fcded` (4 commits: `b9f4995` spec, `aab8c81` fix(desktop), `7ed3710` chore(release) 1.2, `22fcded` test(desktop) cancelamento)
**Superfície**: `app_desktop.py`, `server.py`, `tests/_salvar_alvo.py`, `tests/test_desktop.py`, `tests/test_release.py`, `spec.md`
**Verificador**: sub-agente independente (autor ≠ verificador)

Veredito resumido: os 8 requisitos (JSONDESK-01..08) têm evidência, e o valor asserido bate com a spec. A lacuna da rodada 1 (M7) foi fechada: M7 e o novo M10 morrem. 10 de 11 mutantes morreram. O único sobrevivente (M11) é uma sonda do limite da instrumentação (cria arquivo vazio por `os.open`, sem baixar nada), não uma regressão plausível do `Api.salvar`. Fica registrado como observação não bloqueante, com correção sugerida.

Entre `7ed3710` e `22fcded` o código do app não mudou (`git diff 7ed3710..22fcded` só toca `spec.md`, `tests/_salvar_alvo.py` e `tests/test_desktop.py`).

---

## Histórico

| Rodada | Faixa | Veredito | Motivo |
| ------ | ----- | -------- | ------ |
| 1 | `f9260de..7ed3710` | FAIL | M7 sobrevivente: o teste de cancelamento listava só a pasta de saída, que o app nunca recebe |
| 2 | `f9260de..22fcded` | PASS | `22fcded` registra gravações (`builtins.open`/`io.open`) e downloads (`before_request`); M7 e M10 mortos |

---

## Conclusão das tarefas

Não existe `tasks.md` para esta feature (só `spec.md`). Gate usado: o comando informado pelo orquestrador.

---

## Checagem ancorada na spec

| Req. | Critério (WHEN X THEN Y) | Resultado definido pela spec | `arquivo:linha` + asserção | Situação |
| ---- | ------------------------ | ---------------------------- | -------------------------- | -------- |
| JSONDESK-01 (AC1) | Resultado JSON, nome `.json` confirmado | grava exatamente nesse caminho, sem `.xlsx` | `tests/test_desktop.py:32` - `r["resultado"] == {"ok": True, "caminho": "ficha.json"}`; `tests/test_desktop.py:33` - `r["arquivos"] == ["ficha.json"]` (lista a pasta escolhida, `tests/_salvar_alvo.py:102`); `tests/test_desktop.py:35` - `r["gravacoes"] == ["ficha.json"]` (nenhuma outra gravação) | ✅ Cumpre |
| JSONDESK-01 (AC2) | Resultado JSON, nome sem extensão | grava em `<nome>.json` | `tests/test_desktop.py:41` - `r["arquivos"] == ["minha_ficha.json"]` | ✅ Cumpre |
| JSONDESK-01 (edge `.JSON`) | Nome termina em `.JSON` | não acrescenta outra extensão | `tests/test_desktop.py:46` - `r["arquivos"] == ["FICHA.JSON"]` | ✅ Cumpre |
| JSONDESK-02 (AC3) | Resultado JSON | sugere o nome `.json` do servidor e só o filtro `JSON (*.json)` | `tests/test_desktop.py:51` - `r["arquivo_nome"] == "ficticia.json"`; `tests/test_desktop.py:52-53` - `r["pedido"] == {"save_filename": "ficticia.json", "file_types": ["JSON (*.json)"]}`; filtro validado pelo parser real em `tests/_salvar_alvo.py:41-42` (`parse_file_type`) | ✅ Cumpre |
| JSONDESK-03 (AC4) | JSON salvo | JSON válido; `proventos` com uma linha por mês e os valores impressos na ficha | `tests/_salvar_alvo.py:107` - `json.loads(...)`; `tests/test_desktop.py:59` - `[(ln["Ano"], ln["Mês"]) ...] == [(2020, m) for m in MESES]`; `tests/test_desktop.py:61` - `[ln[nome] for ln in linhas] == ficha["rubricas"][nome]` (valores variam mês a mês, `tests/ficha_ficticia.py:35`) | ✅ Cumpre |
| JSONDESK-04 (AC5) | JSON salvo | NÃO abre o arquivo | `tests/test_desktop.py:65` - `salvar("json", "ficha.json")["abertos"] == []` (`os.startfile` interceptado em `tests/_salvar_alvo.py:32`) | ✅ Cumpre |
| JSONDESK-05 (Planilha AC1) | Resultado `.xlsx` | filtro `Planilha Excel (*.xlsx)`; grava `.xlsx`, acrescentando a nome sem extensão | `tests/test_desktop.py:70` - `r["pedido"]["file_types"] == ["Planilha Excel (*.xlsx)"]`; `tests/test_desktop.py:71` - `r["arquivos"] == ["planilha.xlsx"]` | ✅ Cumpre |
| JSONDESK-05 (Planilha AC2) | Planilha salva | abre em seguida; planilha válida com aba `Proventos` | `tests/test_desktop.py:72` - `r["abertos"] == ["planilha.xlsx"]`; aba lida em `tests/_salvar_alvo.py:109` (`load_workbook(...)["Proventos"]`); `tests/test_desktop.py:74-77` - cabeçalho e valores | ✅ Cumpre |
| JSONDESK-06 (Build AC1) | Suíte e2e | exercita as histórias no Python-alvo | `tests/test_desktop.py:13` - `pytestmark = pytest.mark.e2e`; `tests/test_desktop.py:24` - `rodar_no_alvo(alvo, ...)`; CI em `.github/workflows/windows.yml:111-112` - `pytest tests -m e2e ... --python-alvo "$PASTA/python/python.exe"`; filtros de PR com `app_desktop.py` e `tests/**` (`.github/workflows/windows.yml:26`, `:31`) | ✅ Cumpre (execução no Windows não refeita aqui) |
| JSONDESK-07 (Build AC2) | Versão | `server.VERSAO == "1.2"` | `server.py:39` - `VERSAO = "1.2"`; `tests/test_release.py:19` - `release.versao_app(RAIZ / "server.py") == "1.2"` | ✅ Cumpre |
| JSONDESK-08 (edge cancelar) | Usuário cancela o "Salvar como" | devolve `{"cancelado": True}`, não baixa nem grava nada | `tests/test_desktop.py:82` - `r["resultado"] == {"cancelado": True}`; `tests/test_desktop.py:83` - `r["gravacoes"] == []` (qualquer caminho, `tests/_salvar_alvo.py:65-68`, `:93-97`); `tests/test_desktop.py:84` - `r["downloads"] == 0` (`tests/_salvar_alvo.py:53-56`). O registro prova que funciona no caminho feliz: `tests/test_desktop.py:35-36` - `gravacoes == ["ficha.json"]`, `downloads == 1` | ✅ Cumpre |

**Status**: 8/8 requisitos cobertos com o valor exato da spec. A rastreabilidade agora inclui o cancelamento (`spec.md`, linha de JSONDESK-08).

### Observações de precisão (não bloqueiam)

- Extensão desconhecida ou nome vazio em `arquivo_nome` cai em `.xlsx` (`app_desktop.py:97-100`). A spec não cobre isso, mas fica fora do domínio atual: o servidor só produz `xlsx`/`json` (`converter.py:1966`, nome montado em `server.py:224`).
- O registro de gravações usa só o nome do arquivo (`os.path.basename`, `tests/_salvar_alvo.py:67`), então não distingue a pasta. A pasta certa é garantida à parte por `r["arquivos"]` em `tests/test_desktop.py:33`.

---

## Sensor de discriminação

Rascunho isolado: cópias de `converter.py`, `server.py`, `app_desktop.py` e `web/`, uma por mutante, com `.venv/bin/python -m pytest tests/test_desktop.py -m e2e -q --app-dir <cópia>` rodado a partir da raiz. Controle sem mutação: 8 passed. Rascunho apagado ao fim. `git status --porcelain` da árvore real antes e depois: idêntico (` M .specs/LESSONS.md`, ` M .specs/lessons.json`, `?? .specs/features/json-desktop/validation.md`, `?? .agents/`, `?? .claude/skills/`, `?? .cursor/`, `?? .windsurf/`).

| Mutante | `arquivo:linha` | Descrição | Testes que falharam | Morto? |
| ------- | --------------- | --------- | ------------------- | ------ |
| M1 | `app_desktop.py:109-110` | Sempre acrescenta `.xlsx` (v1.1) | `test_json_grava_no_caminho_escolhido_sem_virar_xlsx`, `test_json_sem_extensao_ganha_json`, `test_json_com_extensao_maiuscula_nao_ganha_outra` | ✅ Morto |
| M2 | `app_desktop.py:104` | Filtro sempre de planilha | `test_json_dialogo_sugere_nome_json_e_so_filtro_json` | ✅ Morto |
| M3 | `app_desktop.py:124` | `if ext == ".xlsx"` → `if True` (abre também o JSON) | `test_json_nao_abre_sozinho` | ✅ Morto |
| M4 | `app_desktop.py:126` | Remove `os.startfile` (não abre a planilha) | `test_xlsx_continua_planilha_e_abre` | ✅ Morto |
| M5 | `app_desktop.py:109` | Comparação de extensão sensível a maiúsculas | `test_json_com_extensao_maiuscula_nao_ganha_outra` | ✅ Morto |
| M6 | `app_desktop.py:110` | Não acrescenta extensão a nome sem extensão | `test_json_sem_extensao_ganha_json`, `test_xlsx_continua_planilha_e_abre` | ✅ Morto |
| M7 | `app_desktop.py:106-107` | Ao cancelar, baixa e grava em outro caminho, e ainda devolve `{"cancelado": True}` | `test_cancelar_nao_grava_nada` | ✅ Morto (sobrevivia na rodada 1) |
| M8 | `app_desktop.py:103` | `save_filename` fixo `"ficha.xlsx"` | `test_json_dialogo_sugere_nome_json_e_so_filtro_json` | ✅ Morto |
| M9 | `app_desktop.py:116` | Grava conteúdo alterado (`1234.56` → `1234.57`) | `test_json_gravado_traz_os_proventos_da_ficha` | ✅ Morto |
| M10 | `app_desktop.py:106-107` | Ao cancelar, baixa o resultado sem gravar | `test_cancelar_nao_grava_nada` | ✅ Morto |
| M11 | `app_desktop.py:106-107` | Ao cancelar, cria arquivo vazio com `Path.touch()` (usa `os.open`), sem baixar | nenhum (8 passed) | ⚠️ Sobrevivente, sonda de limite (não bloqueia) |

**Profundidade**: expandida (11 mutações; todos os ramos de `Api.salvar`, mais 3 mutações do cancelamento).
**Result**: 10/11 mortos; 10/10 mutantes de comportamento plausível mortos — PASS

Por que o M11 não bloqueia: ele não representa uma falha plausível do `Api.salvar`. É código novo sem função, que só cria um arquivo vazio por uma chamada de baixo nível. O app grava por `Path.write_bytes` → `io.open` (Python 3.12), e esse caminho está coberto, como mostram os mortos M7 e M9. Serve para medir até onde a instrumentação enxerga: `os.open`/`os.write` e `Path.touch` ficam de fora. Sugestão opcional, que custa pouco: interceptar também `os.open` com flags de escrita em `tests/_salvar_alvo.py`.

---

## Gate

- **Comando**: `.venv/bin/python -m pytest tests -q` (árvore real)
- **Contagem**: 46 passed, 0 failed, 0 skipped (10,5 s)
- **Só desktop**: 8 testes em `tests/test_desktop.py` (13 e2e ao todo)
- **Antes da feature** (`f9260de`): 38 → **depois**: 46 (delta +8)
- **Asserções enfraquecidas**: nenhuma. A asserção vazia `r["pasta"] == []` foi trocada por `gravacoes == []` e `downloads == 0`, que são mais fortes (M7 prova isso).
- **Não verificado aqui**: execução do workflow Windows

---

## Qualidade de código

| Princípio | Status |
| --------- | ------ |
| Código mínimo | ✅ |
| Mudanças cirúrgicas | ✅ (`22fcded` só toca testes e rastreabilidade) |
| Sem escopo extra | ✅ (`converter.py`, `web/`, `app.py` intocados) |
| Segue os padrões do projeto | ✅ (helper no alvo por subprocesso, JSON ASCII no stdout) |
| Valores asseridos batem com a spec | ✅ |
| Todo teste mapeia para AC/edge | ✅ (8 testes ↔ JSONDESK-01..05, 08) |
| Diretrizes documentadas | `CLAUDE.md` (encoding, `--python-alvo`) seguidas |
| Instrumentação restaurada | ✅ (`builtins.open`/`io.open` voltam no `finally`, `tests/_salvar_alvo.py:96-97`) |

---

## Rastreabilidade (proposta; `spec.md` não foi alterada pelo verificador)

| Requisito | Antes | Proposto |
| --------- | ----- | -------- |
| JSONDESK-01 | Implementing | ✅ Verified |
| JSONDESK-02 | Implementing | ✅ Verified |
| JSONDESK-03 | Implementing | ✅ Verified |
| JSONDESK-04 | Implementing | ✅ Verified |
| JSONDESK-05 | Implementing | ✅ Verified |
| JSONDESK-06 | Implementing | ✅ Verified (Mac); Windows pendente de execução do workflow |
| JSONDESK-07 | Implementing | ✅ Verified |
| JSONDESK-08 | Implementing | ✅ Verified |

---

## Resumo

**Geral**: ✅ Pronto

**Checagem ancorada na spec**: 8/8 requisitos batem com a spec
**Sensor**: 11 injetados, 10 mortos, 1 sobrevivente não bloqueante (M11, sonda de limite)
**Gate**: 46 passed, 0 failed

**O que funciona**: JSON gravado com nome e extensão certos (inclusive `.JSON` e nome sem extensão), com filtro correto e sem abrir; planilha com filtro, extensão, abertura e aba `Proventos`; o cancelamento não baixa nem grava; versão 1.2.

**Próximos passos (opcionais)**: interceptar `os.open` no helper (M11); rodar o workflow Windows para fechar JSONDESK-06 no alvo real.
