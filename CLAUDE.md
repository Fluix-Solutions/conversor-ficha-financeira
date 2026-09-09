# Projeto: Conversor de Ficha Financeira (PDF → Excel)

Contexto para retomar o trabalho em outra sessão.

## Objetivo

Converter "Ficha Financeira" (PDF) em `.xlsx` no formato que o **sistema de
cálculo de processos judiciais** do usuário importa: aba **Proventos**, formato
largo — uma linha por `Ano + Mês`, uma coluna por rubrica (só o nome da verba, sem o código).

- Só exporta **Proventos** (Vantagens). Não exporta Descontos/Outros.
- Valores como **número puro** (ex: `2779.09`).
- **Uma linha por Ano+Mês** — nunca anos repetidos empilhados.
- **Múltiplos contratos (matrículas)**: os valores da mesma verba são **SOMADOS**
  (decisão do usuário, 2026-09-08 — antes tinha tentado colunas separadas por
  matrícula, revertido). Resumo retorna `contratos` (lista de matrículas) e
  `multiplos_blocos` (= há mais de um contrato).
- **Seletor de origem obrigatório** (sem modo automático): `converter(pdf, out,
  origem)` com `origem` ∈ chaves de `ORIGENS` (`serra` / `estado`); CLI
  `-t serra|estado`. Rótulos em `converter.ORIGENS` ("Município da Serra",
  "Estado do Espírito Santo") — o app importa esse dict e monta um
  `ttk.Combobox` editável com filtro por texto (`_filtrar_origem`); o botão
  Converter só habilita quando o texto casa com um rótulo (`_origem_chave`).
  Mismatch origem×PDF → `ConversaoError`. Dentro de `serra`, `_detectar_formato`
  distingue A vs B sozinho.

## Arquivos

| Arquivo | Papel |
|---|---|
| `converter.py` | Motor. Detecta o layout e converte. Roda sozinho: `python converter.py "FF X.pdf"` |
| `app.py` + `Conversor.bat` | App de janela (Tkinter). Duplo clique no `.bat`. |
| `requirements.txt` | `pdfplumber`, `openpyxl`, `pymupdf` |
| `ficha_financeira.xlsx` | Modelo de saída validado (formato A) |
| `FF *.pdf` | Fichas de teste |

## Versão web (`server.py` + `web/`)

Flask. Rotas: `/` e assets da pasta `web/`; `GET /api/origens`, `GET /api/versao`,
`POST /api/converter` (multipart `pdf` + `origem` → JSON com `resumo` +
`arquivo_b64`). Converte via arquivo temporário apagado no `finally` (nada
persiste, nada em log). Login opcional por env: `CONVERSOR_SENHA` /
`CONVERSOR_USUARIO`. Deploy: `Procfile` (`gunicorn server:app`), `runtime.txt`
(py 3.12), `requirements.txt` (engine + flask + gunicorn). Front em `web/` é o
mesmo visual do `ui/` adaptado para `fetch` + `<input type=file>` + drag-drop.
Alvo: Railway (site separado por ora; migrar pro Valorizei depois é possível).

## Empacotamento (.exe)

`Conversor.spec` + `construir_exe.bat` → `dist/Conversor de Ficha Financeira.exe`
(PyInstaller onefile, windowed, ícone `icone.ico`). `dist/` também tem
`Instalar.bat` / `Desinstalar.bat` / `LEIA-ME.txt`.
`app.py --selftest <serra|estado> <pdf>` converte sem abrir janela (testa o exe).

## Os 3 layouts (`_detectar_formato` distingue A/B/C)

- **A — FPFF902** (Prefeitura da Serra, recente): texto normal, linhas
  `NNN Nome`. `_pagina_formato_a`. Cabeçalho de meses achado por
  `_centros_meses` (linha com mais meses, qualquer y) → aceita **ano parcial**
  (ficha que cobre só alguns meses). Separa **blocos por matrícula**
  (`Servidor: NNNNN`): mesmo ano com matrículas diferentes → coluna `Bloco`.
- **B — FPFF102** (Serra, antigo): linhas `Evento: NNN Nome` + `Valor` + `Ref.`.
  Duas sub-variantes: **(1)** fonte sem ToUnicode → `chr(cid+29)` (`decode_cid`);
  **(2)** fonte normal, mas com espaços dentro dos números ("1.50 9 , 8 9").
  `_tokens_numericos` reconstrói os números por **vão horizontal** entre
  caracteres (ignora espaços). Meses pela coordenada X. `_converter_formato_b`.
- **C — SIARHES / PRODEST** (Governo do Estado do ES): seções `Vantagens` /
  `Descontos`. Fonte Type3; **cada página tem uma cifra de substituição
  diferente**. `_converter_formato_c`:
  1. letras: da linha de cabeçalho dos meses — por extenso (`Janeiro`) **ou
     abreviado** (`Jan Fev Mar ...`, `MESES_ABREV`);
  2. dígitos: resolve as somas dos totais (`_resolver_digitos`) + compara o
     hash do desenho de cada glifo entre páginas (`_hashes_glifos`, via pymupdf);
     `_resolver_digitos` descarta restrições sem informação, confere cada uma
     só quando fica completa e escolhe a ordem dos glifos p/ podar cedo — ficha
     do Estado caiu de ~400 s para ~5 s (mesmo resultado da versão antiga);
  3. prefixo/decimal/milhar: `_glifos_por_frequencia` (token de valor mais
     comum = o zero, `<pref>0<dec>00`); cai para `_glifos_numericos`+CPF só se
     falhar. O `.` **pode ser um glifo-dígito** nessas fichas → o separador
     interno inteiro/centavos é `_SEP_INT` (`\x00`), nunca `.`.

  **Duas variantes de layout C** (ver `PDF/Estado/`):
  - `Estado Seguido 1.pdf`: meses por extenso, seção lida pelo nome
    (`Vantagens`), código e nome da rubrica separados por espaço.
  - `FICHA 01/02/03.pdf`: meses abreviados; o título da seção usa **outra
    cifra** (ilegível) → seção detectada pela **posição** (1º bloco de meses =
    Proventos, `_eh_cabecalho_meses`); código **colado** no nome →
    `_split_cod` corta o prefixo de glifos-dígito; `_converter_formato_c`
    escolhe o tamanho (2-4) preferindo um código que exista em `RUBRICAS_C`.
    A **descrição da rubrica não é legível** no PDF (fonte da descrição sem
    ToUnicode) → o nome vem de `RUBRICAS_C` pelo código. Código novo →
    aviso "Rubrica NNN: nome não disponível" e coluna `Rubrica NNN`: ler o
    nome na ficha impressa (`pymupdf` render p/ PNG) e acrescentar em
    `RUBRICAS_C`. Os **valores** batem com os totais impressos.
    Códigos já mapeados (proventos): 20,21,24,26,28,119,192,231,248,339,348,
    494,1010,1025,1040,1110. **339 e 348** = "Bônus Desempenho SEDU" com
    valores iguais e 348 também espelhado em Descontos (provável estorno) →
    ficam em colunas separadas (348 rotulado "(cód. 348)"); usuário decide se
    conta.

## Nomes de rubrica

Dicionários no topo do `converter.py`: `RUBRICAS_CANONICAS` (A/B),
`RUBRICAS_C` (C), `_ACENTOS` (recupera acentos perdidos no layout B).
Aviso `Nome incompleto (acento)` ou `nome não decifrado` → adicionar no dict.

A coluna da planilha é **só o nome da verba** (`_coluna()`), sem o código.
Consequência: códigos diferentes com o mesmo nome viram UMA coluna e somam
(ex.: `212` e `937` → ambos "13º Salário" — são o mesmo 13º de sistemas de
folha diferentes; não se sobrepõem no mesmo ano).

## Pendências / próximos passos

- **FF 3** é PDF **escaneado** (imagem) → precisa OCR (Tesseract não instalado).
  Plano: render + OCR + conferir contra a coluna Total.
- Gerar `.exe` único (PyInstaller) para rodar sem Python.
- Conversão em lote (pasta inteira).
- Incluir Descontos/Outros, se o sistema precisar.
- Testar com mais fichas reais.

## Como validar uma conversão

Comparar a soma dos 12 meses de cada rubrica com a coluna **Total** do PDF
(o layout C já faz isso e emite aviso quando não fecha).
