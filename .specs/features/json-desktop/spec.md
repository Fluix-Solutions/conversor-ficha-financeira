# Saída JSON no app de desktop Specification

## Problem Statement

A v1.1 já gera JSON (motor, CLI e tela web, commit `6c0cfea`), mas no app de desktop do zip Windows o resultado JSON sai "corrompido". Causa confirmada no código: `Api.salvar` (`app_desktop.py:89-114`) abre o "Salvar como" só com o filtro de planilha, acrescenta `.xlsx` a qualquer nome que não termine assim e abre o arquivo em seguida — o conteúdo JSON vai parar em `ficha.json.xlsx` e o Excel acusa arquivo inválido. Nenhum teste cobre saída JSON, por isso o erro chegou à Release.

## Goals

- [ ] No app de desktop, escolher JSON e salvar produz um arquivo `.json` válido com os proventos da ficha.
- [ ] O build Windows falha se o caminho "converter em JSON → salvar no desktop" quebrar de novo.
- [ ] A correção sai numa versão nova (`1.2`), já que a Release v1.1 não é sobrescrita.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Mudar a estrutura do JSON (`origem`, `layout`, `anos`, `contratos`, `multiplos_blocos`, `avisos`, `colunas`, `proventos`) | Usuário confirmou (2026-09-14) que o problema foi o arquivo salvo pelo app do Windows, não o conteúdo |
| Mudanças em `converter.py`, `server.py` (fora `VERSAO`) e `web/` | O motor e o download web já entregam o JSON certo (verificado com a ficha fictícia) |
| `app.py` (Tkinter) e `app_web.py` (reserva) | Não oferecem JSON e não vão no zip |
| Publicar a Release v1.2 (tag/push) | Operação remota: exige ok explícito do usuário à parte |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Onde o erro aconteceu | App de desktop do zip Windows, com JSON escolhido na tela | Relato do usuário, 2026-09-14 | y |
| Como o app sabe o formato do resultado | Pela extensão do nome que o servidor devolve em `arquivo_nome` (`<pdf>.json` / `<pdf>.xlsx`) | O nome já carrega o formato (`server.py:224`); não precisa mexer em `web/` nem no shim | n |
| Abrir o arquivo depois de salvar | Só a planilha abre sozinha; o JSON só é salvo | O JSON é para o sistema de cálculo importar; no Windows `.json` sem programa associado abre o diálogo "Como deseja abrir?" | n |
| Nome digitado sem extensão | Acrescentar a extensão do formato do resultado | Mantém o comportamento atual da planilha para os dois formatos | n |
| Onde o teste roda | e2e, no Python-alvo (no CI: o `python.exe` da pasta) | O job de unitários do CI só tem `pytest`; `app_desktop` importa `pywebview` e `flask` | n |
| Diálogo nativo no teste | Janela falsa que devolve o caminho escolhido e confere o filtro com `webview.util.parse_file_type` | Diálogo real exige interação; o filtro inválido quebraria em tempo de execução (`ValueError`) | n |
| Versão | `server.VERSAO = "1.2"`; o teste `test_versao_app_le_o_server_py` acompanha o número | Release existente nunca é sobrescrita (AD-001) | n |

**Open questions:** none - all resolved or logged above.

---

## User Stories

### P1: Salvar o resultado JSON no desktop ⭐ MVP

**User Story**: Como usuário do app de desktop, quero escolher JSON, converter e salvar um arquivo `.json` que o sistema de cálculo importe, sem que ele vire uma "planilha corrompida".

**Why P1**: É o defeito relatado; hoje o JSON no desktop é inutilizável.

**Acceptance Criteria**:

1. WHEN o resultado da conversão é JSON e o usuário confirma o "Salvar como" com um nome terminado em `.json` THEN o app SHALL gravar exatamente nesse caminho, sem acrescentar `.xlsx`.
2. WHEN o resultado é JSON e o usuário digita um nome sem extensão THEN o app SHALL gravar em `<nome>.json`.
3. WHEN o resultado é JSON THEN o "Salvar como" SHALL sugerir o nome `.json` recebido do servidor e oferecer só o filtro `JSON (*.json)`.
4. WHEN o resultado JSON é salvo THEN o arquivo SHALL ser um JSON válido cujo `proventos` traz uma linha por mês do ano da ficha com os mesmos valores de cada rubrica impressos na ficha.
5. WHEN o resultado JSON é salvo THEN o app SHALL NOT abrir o arquivo automaticamente.

**Independent Test**: converter a ficha fictícia em JSON pelo servidor local, chamar `Api.salvar` com uma janela falsa e ler o arquivo gravado.

---

### P1: A planilha continua igual ⭐ MVP

**User Story**: Como usuário do app de desktop, quero que salvar em Excel continue funcionando como na v1.1.

**Why P1**: A correção não pode quebrar o formato padrão.

**Acceptance Criteria**:

1. WHEN o resultado é `.xlsx` THEN o "Salvar como" SHALL oferecer o filtro `Planilha Excel (*.xlsx)` e o app SHALL gravar com extensão `.xlsx` (acrescentando-a a nome sem extensão).
2. WHEN a planilha é salva THEN o app SHALL abri-la em seguida e o arquivo SHALL ser uma planilha válida com a aba `Proventos`.

**Independent Test**: mesmo roteiro da história anterior com formato `xlsx`.

---

### P1: Build pega a regressão e sai como 1.2 ⭐ MVP

**User Story**: Como desenvolvedor, quero que o build Windows teste o salvamento do desktop com o Python da pasta e que a correção vá numa versão nova.

**Why P1**: A falta desse teste deixou o erro chegar à v1.1.

**Acceptance Criteria**:

1. The suíte e2e (`pytest -m e2e`) SHALL exercitar os critérios das duas histórias acima no Python-alvo.
2. The `server.VERSAO` SHALL ser `1.2`.

**Independent Test**: `pytest tests -m e2e` no Mac (alvo = `.venv`) e no workflow Windows.

---

## Edge Cases

- IF o usuário cancela o "Salvar como" THEN o app SHALL devolver `{"cancelado": True}` sem gravar nada (comportamento atual, não muda).
- IF o nome digitado termina em `.JSON` (maiúsculas) THEN o app SHALL gravar sem acrescentar outra extensão.

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| JSONDESK-01 | P1: Salvar JSON — AC 1, 2, edge `.JSON` | Execute | Implementing |
| JSONDESK-02 | P1: Salvar JSON — AC 3 | Execute | Implementing |
| JSONDESK-03 | P1: Salvar JSON — AC 4 | Execute | Implementing |
| JSONDESK-04 | P1: Salvar JSON — AC 5 | Execute | Implementing |
| JSONDESK-05 | P1: Planilha — AC 1, 2 | Execute | Implementing |
| JSONDESK-06 | P1: Build — AC 1 | Execute | Implementing |
| JSONDESK-07 | P1: Build — AC 2 | Execute | Pending |

**Coverage:** 7 total, 7 mapped to steps, 0 unmapped

---

## Success Criteria

- [ ] `pytest tests -m e2e` passa no Mac e no workflow Windows com os novos testes.
- [ ] Arquivo JSON salvo pelo desktop abre com `json.load` e bate valor a valor com a ficha fictícia.
