# Build Windows (pasta portátil via GitHub Actions) Specification

## Problem Statement

A versão Windows do conversor é a pasta portátil gerada por `construir_portatil.py`, e esse script só roda num Windows: ele executa o `python.exe` embutido para instalar o pip, as dependências e o teste final (passo 6/6). O desenvolvimento agora acontece num Mac, onde o build não roda — e o `pip` do Mac não resolve dependências do Windows (avalia os marcadores do host e puxa `pyobjc`). Além disso, as dependências não têm versão fixa, então dois builds em dias diferentes podem sair diferentes (hoje viria `opencv-python 5`, nunca testado com `rapidocr-onnxruntime 1.4.4`).

## Goals

- [ ] Gerar a pasta portátil Windows a partir do Mac com um `git push` de tag, sem precisar de uma máquina Windows.
- [ ] Todo zip publicado passou pela verificação com o Python DA PASTA num Windows real (importações, OCR, conversão de uma ficha fictícia de texto e escaneada).
- [ ] Dois builds do mesmo commit instalam exatamente as mesmas versões de dependência.

## Out of Scope

| Feature | Reason |
| ------- | ------ |
| Instalador `.exe`/`.msi` ou assinatura de código | Decisão do usuário: entrega continua sendo o zip da pasta portátil (sem assinatura, o Smart App Control bloqueia instalador) |
| Log de erro visível quando o app não abre | Usuário escolheu não incluir agora (fica em Deferred Ideas) |
| Aviso de WebView2 ausente | Usuário escolheu não incluir agora (fica em Deferred Ideas) |
| Build local no Mac com `uv` (cross-build) | Decisão do usuário: build oficial só no GitHub Actions; o cross-build não roda o teste com o Python da pasta |
| Migrar para `rapidocr` novo / Python 3.13+ | `rapidocr-onnxruntime` exige Python < 3.13; migração muda o motor de OCR e é outro trabalho |
| Mudanças no deploy web (Railway, `Dockerfile`, `requirements.txt`) | Não fazem parte da entrega Windows |
| Alterar a lógica de `converter.py`, `server.py`, `app_desktop.py` ou `web/` | O build empacota o app como está; só se lê `server.VERSAO` |

---

## Assumptions & Open Questions

| Assumption / decision | Chosen default | Rationale | Confirmed? |
| --------------------- | -------------- | --------- | ---------- |
| Onde o build roda | GitHub Actions, runner `windows-latest` | Único jeito de rodar o `python.exe` da pasta a partir do Mac; gratuito em repo público | y |
| Formato de entrega | Zip da pasta portátil | Caminho que já passou pelo Smart App Control | y |
| Onde publicar | GitHub Release por tag (repo público: download aberto) | Link permanente por versão | y |
| Travar versões | Lock com versão exata + hash por pacote, para win_amd64/cp312 | Build reproduzível; escolha do usuário | y |
| Disparo | Tag `vX.Y` ou `vX.Y.Z` publica Release; o botão manual (`workflow_dispatch`) também publica, criando a tag `v<server.VERSAO>` no commit escolhido | Decisão do usuário (2026-09-11): o disparo manual também cria a Release | y |
| Versão do Python embutido | Manter 3.12.9 (a validada hoje); não subir para 3.12.10 aqui | Não misturar troca de runtime com mudança de pipeline | y |
| Versões iniciais do lock | O que o `uv` resolve hoje para Windows; se o teste de OCR falhar com `opencv-python 5`, travar `opencv-python < 5` | O teste com a ficha fictícia escaneada decide, não suposição. Spike no Mac (2026-09-11) com opencv 5.0.0 + numpy 2.5.3: texto e OCR com valores exatos | y |
| Ficha fictícia de teste | Layout D (Estado, texto limpo) gerado com pymupdf dentro do teste, valores em colunas espaçadas como numa ficha real; a versão escaneada é a mesma ficha rasterizada em 300 DPI, sem camada de texto | É o único layout fabricável sem cifra/grade; o OCR do Estado remonta a mesma tabela. Com valores separados por um espaço só, o OCR lê a linha inteira como uma caixa e não remonta | y |
| Nome das colunas no caminho OCR | Comparar nomes de rubrica sem diferenciar maiúsculas | O OCR passa o nome por `_nome_canonico`, que devolve `Vencimento` onde o texto dá `VENCIMENTO`; o que se verifica é o valor | n |
| Integridade do Python embutido | SHA-256 do zip fixado no script, conferido após o download (`615861fb…5865`; o MD5 bate com o publicado pelo python.org) | Repo público distribui binário a terceiros | n |
| `get-pip.py` | Continua baixando do `bootstrap.pypa.io` sem versão fixa | O pip só instala; tudo o que o app usa vem do lock com hash | n |
| Release já existente para a tag | Falhar sem sobrescrever | Um zip publicado não muda por baixo de quem já baixou | n |
| Retenção do artefato do workflow | 14 dias | O zip permanente é o da Release; o artefato só leva o zip do build para o job de publicação | n |
| Script de build | O mesmo `construir_portatil.py` roda no CI e num Windows local | Um caminho só de build, sem duplicar lógica | n |
| Smart App Control com zip baixado da internet | Não é verificável no CI; vira UAT manual numa máquina com SAC ligado antes de divulgar a 1ª Release | O Mark-of-the-Web do download pode mudar a avaliação do SAC — incerto | n |

**Open questions:** none - all resolved or logged above (required before the spec is confirmed).

---

## User Stories

### P1: Build verificado num Windows real ⭐ MVP

**User Story**: Como desenvolvedor no Mac, quero disparar o build da pasta portátil num Windows real e só receber o zip se ele funcionar com o Python da própria pasta, para não descobrir erro na máquina do usuário final.

**Why P1**: Sem isso não existe build Windows a partir do Mac, e o teste do passo 6/6 é o que pegou os dois bugs anteriores.

**Acceptance Criteria**:

1. WHEN o workflow é disparado manualmente THEN the pipeline SHALL rodar o build num runner `windows-latest` e publicar a Release com a tag `v<server.VERSAO>` no commit escolhido.  <!-- WIN-01 -->
2. The pipeline SHALL montar a pasta com o Python embutido 3.12.9 amd64 e os itens `converter.py`, `server.py`, `app_desktop.py`, `web/`, `Conversor.bat` e `LEIA-ME.txt`.  <!-- WIN-02 -->
3. IF o SHA-256 do zip do Python embutido baixado diferir do valor fixado no script THEN the build SHALL falhar antes de instalar qualquer dependência.  <!-- WIN-03 -->
4. WHEN a pasta é montada THEN the pipeline SHALL importar, com o `python.exe` da pasta, `pdfplumber`, `openpyxl`, `pymupdf`, `flask`, `webview`, `cv2`, `onnxruntime`, `rapidocr_onnxruntime`, `clr`, `converter` e `server`, e falhar se qualquer importação falhar.  <!-- WIN-04 -->
5. WHEN a pasta é montada THEN the pipeline SHALL converter, com o Python da pasta e origem `estado`, a ficha fictícia de texto e conferir que o `.xlsx` tem, na aba Proventos, exatamente os valores esperados por Ano+Mês e rubrica.  <!-- WIN-05 -->
6. WHEN a pasta é montada THEN the pipeline SHALL converter por OCR, com o Python da pasta e origem `estado`, a versão escaneada (só imagem) da mesma ficha fictícia e conferir que o layout é `OCR`, que os 12 valores de cada rubrica batem com os esperados e que não há aviso `CONFERIR`.  <!-- WIN-06 -->
7. WHEN a pasta é montada THEN the pipeline SHALL subir o `server.py` com o Python da pasta e receber `"ocr": true` em `GET /api/versao`.  <!-- WIN-07 -->
8. IF qualquer passo do build ou da verificação falhar THEN the pipeline SHALL terminar com falha e não publicar zip nenhum (nem artefato nem Release).  <!-- WIN-08 -->
9. The pipeline SHALL usar só fichas fictícias geradas no próprio teste; nenhum PDF real entra no repositório nem nos logs.  <!-- WIN-09 -->
10. WHEN o build termina com sucesso THEN the pipeline SHALL registrar no log os pacotes instalados na pasta com versão, o tamanho do zip e o SHA-256 do zip.  <!-- WIN-10 -->

**Independent Test**: Disparar o workflow pelo botão "Run workflow" (ou `gh workflow run`); o job de build fica verde só se WIN-04..07 passarem, e só então a Release `v<server.VERSAO>` aparece.

---

### P1: Publicação da versão por tag ⭐ MVP

**User Story**: Como desenvolvedor, quero que um `git push` de tag `vX.Y` gere uma Release com o zip pronto, para mandar ao usuário final um link permanente por versão.

**Why P1**: É a entrega escolhida pelo usuário; sem ela o zip fica preso numa execução do Actions que expira.

**Acceptance Criteria**:

1. WHEN uma tag no formato `vX.Y` ou `vX.Y.Z` é enviada ao GitHub THEN the pipeline SHALL criar uma Release com essa tag e anexar o arquivo `Conversor-de-Ficha-Financeira-<tag>-windows-x64.zip`.  <!-- WIN-11 -->
2. The zip SHALL conter uma única pasta raiz `Conversor de Ficha Financeira/` com `Conversor.bat` e `LEIA-ME.txt` no primeiro nível dela.  <!-- WIN-12 -->
3. WHEN a Release é criada THEN the pipeline SHALL escrever nas notas o SHA-256 do zip e os requisitos: Windows 10/11 64 bits, .NET Framework 4.7.2+ e WebView2 Runtime.  <!-- WIN-13 -->
4. IF já existir uma Release para a tag THEN the pipeline SHALL falhar sem alterar a Release nem o zip existentes.  <!-- WIN-14 -->
5. The pipeline SHALL dar permissão `contents: write` só ao job que publica a Release; os demais jobs rodam com `contents: read`.  <!-- WIN-15 -->

**Independent Test**: Enviar a tag `v1.1` (igual a `server.VERSAO`) e ver a Release com o zip e o SHA-256; reenviar o workflow para a mesma tag e ver a falha sem alteração da Release.

---

### P1: Dependências travadas

**User Story**: Como desenvolvedor, quero que o build instale versões exatas e conferidas por hash, para que dois builds do mesmo commit sejam iguais e nenhuma versão nova de dependência entre de surpresa.

**Why P1**: Pedido explícito do usuário; sem lock, `opencv-python 5` entraria no próximo build sem ninguém ter testado.

**Acceptance Criteria**:

1. The build SHALL instalar as dependências da pasta a partir de um lock com versão exata e hash de cada pacote para win_amd64/cp312, usando `pip install --require-hashes`.  <!-- WIN-16 -->
2. The lock SHALL conter todo pacote listado em `requirements-desktop.txt` e em `requirements-base.txt`.  <!-- WIN-17 -->
3. WHEN o lock precisa ser atualizado THEN the project SHALL oferecer um único comando, rodável no Mac, que o regenera para Windows a partir de `requirements-desktop.txt`.  <!-- WIN-18 -->

**Independent Test**: Rodar o teste unitário que compara o lock com os requirements; rodar o comando de regeneração no Mac e ver o lock regenerado idêntico quando nada mudou no PyPI.

---

### P2: Versão coerente e documentação

**User Story**: Como desenvolvedor que retoma o projeto, quero que a versão da Release bata com a que o app mostra e que o processo esteja escrito, para não depender de memória.

**Why P2**: Evita Release `v1.2` com o app dizendo `1.1`, e registra as pegadinhas descobertas nesta análise.

**Acceptance Criteria**:

1. IF a versão da tag enviada, sem o `v`, diferir de `server.VERSAO` THEN the pipeline SHALL falhar antes do build com uma mensagem que mostra os dois valores.  <!-- WIN-19 -->
2. The README SHALL descrever como gerar uma versão Windows a partir do Mac (tag → Release), como testar o build sem publicar e como atualizar o lock.  <!-- WIN-20 -->
3. The CLAUDE.md SHALL registrar o novo fluxo de build, o repositório `Fluix-Solutions/conversor-ficha-financeira` e as pegadinhas: `pip --platform` no Mac não resolve Windows, e o Python está preso na 3.12 por causa do `rapidocr-onnxruntime`.  <!-- WIN-21 -->

**Independent Test**: Enviar uma tag diferente de `server.VERSAO` e ver o job falhar com os dois valores na mensagem; ler o README e seguir o passo a passo.

---

## Edge Cases

- IF `python.org`, `bootstrap.pypa.io` ou o PyPI estiverem fora do ar THEN the pipeline SHALL falhar mostrando a URL ou o pacote que falhou (coberto por WIN-08).
- IF a tag não seguir `vX.Y` ou `vX.Y.Z` (ex.: `teste`) THEN the workflow SHALL NOT rodar.
- WHEN duas tags são enviadas ao mesmo tempo THEN the pipeline SHALL gerar cada Release de forma independente, sem uma cancelar a outra.
- IF a ficha fictícia escaneada gerar aviso `CONFERIR` (soma dos meses ≠ total) THEN the verification SHALL falhar (coberto por WIN-06).

---

## Implicit-Requirement Dimensions

| Dimension | Coverage |
| --------- | -------- |
| Input validation & bounds | Formato da tag (Edge Cases), versão da tag × `server.VERSAO` (WIN-19) |
| Failure / partial-failure states | Nenhum zip sai de build com falha (WIN-08); Release é o último passo |
| Idempotency / retry / duplicate handling | Release existente não é sobrescrita (WIN-14) |
| Auth boundaries & rate limits | `contents: write` só no job de publicação (WIN-15); download público aceito pelo usuário |
| Concurrency / ordering | Tags simultâneas independentes (Edge Cases) |
| Data lifecycle / expiry | Artefato manual 14 dias; Release permanente; só fichas fictícias (WIN-09) |
| Observability | Versões instaladas, tamanho e SHA-256 no log (WIN-10) e nas notas (WIN-13) |
| External-dependency failure | Downloads com falha derrubam o build (Edge Cases); SHA-256 do Python (WIN-03); hash do lock (WIN-16) |
| State-transition integrity | N/A because o pipeline não mantém estado além da existência da Release, coberta em WIN-14 |

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----- | ----- | ------ |
| WIN-01 | P1: Build verificado | Design | Pending |
| WIN-02 | P1: Build verificado | Design | Pending |
| WIN-03 | P1: Build verificado | T3 | Implementing |
| WIN-04 | P1: Build verificado | Design | Pending |
| WIN-05 | P1: Build verificado | T5 | Implementing |
| WIN-06 | P1: Build verificado | Design | Pending |
| WIN-07 | P1: Build verificado | Design | Pending |
| WIN-08 | P1: Build verificado | Design | Pending |
| WIN-09 | P1: Build verificado | T5 | Implementing |
| WIN-10 | P1: Build verificado | T4 | Implementing |
| WIN-11 | P1: Publicação por tag | T2 | Implementing |
| WIN-12 | P1: Publicação por tag | T4 | Implementing |
| WIN-13 | P1: Publicação por tag | T2 | Implementing |
| WIN-14 | P1: Publicação por tag | Design | Pending |
| WIN-15 | P1: Publicação por tag | Design | Pending |
| WIN-16 | P1: Dependências travadas | T1, T3 | Implementing |
| WIN-17 | P1: Dependências travadas | T1 | Implementing |
| WIN-18 | P1: Dependências travadas | T1 | Implementing |
| WIN-19 | P2: Versão e docs | T2 | Implementing |
| WIN-20 | P2: Versão e docs | Design | Pending |
| WIN-21 | P2: Versão e docs | Design | Pending |

**Coverage:** 21 total, 0 mapped to tasks, 21 unmapped ⚠️ (tasks ainda não criadas)

---

## Success Criteria

- [ ] Uma tag `vX.Y` enviada do Mac produz uma Release com o zip em menos de 30 minutos, sem intervenção.
- [ ] O zip da Release abre o app e converte uma ficha escaneada real numa máquina Windows com Smart App Control ligado (UAT manual antes de divulgar a 1ª Release).
- [ ] Dois builds do mesmo commit registram a mesma lista de pacotes e versões no log.
