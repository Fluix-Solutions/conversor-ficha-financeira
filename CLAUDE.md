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

## Empacotamento (.exe) — ABANDONADO (2026-09-09)

Caminho do `.exe` descartado: a máquina do usuário tem **Smart App Control em
modo ENFORCE**, que bloqueia qualquer `.exe` não assinado (PyInstaller/Nuitka/
Electron não resolvem — é falta de assinatura de código). Os arquivos de build
(`ConversorWeb.spec`, `construir_exe.bat`, `icone.ico`, `version_info.txt`,
`dist/`) foram removidos. Distribuição = **versão web** (Railway) ou rodar
`python app_web.py` / `python server.py` localmente.
`app.py --selftest <serra|estado> <pdf>` ainda converte sem abrir janela.

## Os layouts (`_detectar_formato` distingue A/B/C/D; "OCR" p/ scan)

**PDF escaneado (imagem, sem texto)** — Estado e Serra. Detectado em
`converter()`: o texto do carimbo do PJe (assinatura/URL/"Num.") é descartado
antes de medir, senão um scan parece "ter texto". OCR = rapidocr,
`requirements-desktop.txt` (não vai pro web → lá o scan é recusado).
**Cada linha é validada** (soma dos 12 meses == total impresso); o que não
fecha vira aviso "CONFERIR". Sempre acrescenta o aviso "lida por OCR - confira".

- **Estado** → `_converter_ocr`: remonta igual ao layout D (código+nome + 13
  nº estilo US, rótulo pode vir no meio da linha).
- **Serra** → `_converter_ocr_serra`: remonta a grade de 12 meses do layout
  A/B. Pontos não óbvios:
  - **Orientação**: `_ocr_linhas_serra` tenta 0°/90°/270°/180° e escolhe pelo
    `_ocr_orient_score` — exige os meses em **ordem crescente de x**, senão a
    página de cabeça para baixo casa os 12 meses e ganha do ângulo certo.
  - **Grade dos meses**: NÃO usar o x do cabeçalho (rótulo alinhado à esquerda,
    número à direita → desloca o mês). Espaçamento vem do cabeçalho, a âncora é
    a coluna TOTAL, e o deslocamento fino é o que melhor encaixa os números
    lidos na página.
  - **Marcadores de seção** ("Proventos"/"TOTAL:") são procurados **célula a
    célula**, não na linha concatenada: o carimbo do PJe cai no mesmo y e
    colava lixo no rótulo.
  - Linha cujo nome não tem letras reconhecíveis é **descartada** (ruído de
    OCR viraria coluna sem sentido). Se a ficha inteira render < 2 colunas,
    `ConversaoError` em vez de planilha duvidosa.


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
    A **descrição da rubrica não é legível** como texto (fonte sem ToUnicode).
    Nome vem: (1) de `RUBRICAS_C` pelo código; (2) senão, por **OCR** da
    imagem da página (`_ocr_rubricas`, rapidocr) - roda só quando falta nome,
    ~2-12 s/ficha; o OCR também corrige códigos ambíguos de linhas coladas
    (`_resolver_cod` 2ª passada). `_nome_canonico` casa o texto do OCR com a
    grafia canônica de `RUBRICAS_C` e separa palavras grudadas (`_quebrar`,
    vocabulário em `_VOCAB_EXTRA`). Só sobra `Rubrica NNN` se OCR indisponível
    e código desconhecido. Os **valores** sempre batem com os totais impressos
    (OCR não toca em número).
    Códigos já mapeados (proventos): 20,21,24,26,28,101,107,114,119,127,128,
    142,146,148,150,161,192,231,248,339,348,494,1010,1025,1040,1110.
    **339 e 348** = "Bônus Desempenho SEDU" com valores iguais e 348 também
    espelhado em Descontos (provável estorno) → colunas separadas (348 =
    "(cód. 348)"); usuário decide se conta.

- **D — Estado do ES, texto limpo (sem cifra)** — `_converter_formato_d`.
  Detecção: `"GOVERNO DO ESTADO"` + `"Ano Ref:"` no texto. Cobre 2 sub-modelos
  (ver `PDF/Estado/FF 01.pdf`, que junta os dois):
  - "FICHA FINANCEIRA" antigo: `Ano Ref:AAAA`, servidor na linha
    `<matrícula> <NOME> <dd/mm/aaaa>`, fim de seção `Total de Vantagens:`.
  - "FICHA FINANCEIRA POR FUNCIONÁRIO" texto: `ANO: AAAA`,
    `FUNCIONÁRIO:<NOME> CPF:`, meses abreviados, fim de seção linha `TOTAL ...`.
  Linha de rubrica: `<cód 1-4díg> <nome> <12 valores> <total>`, número **estilo
  americano** (`1,234.56` → `_US_NUM_RE`). Nome pode continuar na linha
  seguinte (`AP.AT.SAUDE`). Nome vem direto do PDF (NÃO usa `RUBRICAS_C` —
  1101 etc. têm significado diferente aqui). Valida soma×total impresso.
  **Múltiplos servidores no mesmo PDF**: `_converter_formato_d` soma tudo por
  ano/mês e emite aviso "ATENÇÃO: N servidores diferentes". Decisão pendente
  com o usuário: `FF 01.pdf` tem 6 pessoas (arquivo de teste montado à mão?).

## Nomes de rubrica

Dicionários no topo do `converter.py`: `RUBRICAS_CANONICAS` (A/B),
`RUBRICAS_C` (C), `_ACENTOS` (recupera acentos perdidos no layout B).
Aviso `Nome incompleto (acento)` ou `nome não decifrado` → adicionar no dict.

A coluna da planilha é **só o nome da verba** (`_coluna()`), sem o código.
Consequência: códigos diferentes com o mesmo nome viram UMA coluna e somam
(ex.: `212` e `937` → ambos "13º Salário" — são o mesmo 13º de sistemas de
folha diferentes; não se sobrepõem no mesmo ano).

## Pendências / próximos passos

- **Deploy no Railway** (em andamento — usuário criou a conta; falta ligar o
  repo `WilkersonPenido/conversor-ficha-financeira` e gerar o domínio).
- Scan da Serra de **qualidade muito baixa** (ex.: `Serra Alternado 1.pdf`) é
  recusado pelo filtro de qualidade. Melhorar exigiria pré-processar a imagem
  (deskew/contraste) antes do OCR.
- OCR no **web/Railway**: hoje fica de fora (~150 MB). Se ativar, subir o
  `--timeout` do Procfile — OCR de ficha com várias páginas leva minutos.
- Conversão em lote (pasta inteira).
- Incluir Descontos/Outros, se o sistema precisar.
- Testar com mais fichas reais.

## Como validar uma conversão

Comparar a soma dos 12 meses de cada rubrica com a coluna **Total** do PDF
(o layout C já faz isso e emite aviso quando não fecha).
