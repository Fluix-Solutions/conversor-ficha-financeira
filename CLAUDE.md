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
  origem)` com `origem` ∈ chaves de `ORIGENS` (`serra` / `estado` / `vitoria`);
  CLI `-t serra|estado|vitoria`. Rótulos em `converter.ORIGENS` ("Município da
  Serra", "Estado do Espírito Santo", "Prefeitura de Vitória") — o app importa
  esse dict e monta um `ttk.Combobox` editável com filtro por texto
  (`_filtrar_origem`); o botão Converter só habilita quando o texto casa com um
  rótulo (`_origem_chave`). **Nada mais precisa ser tocado para acrescentar uma
  origem**: a tela web busca a lista em `GET /api/origens`, que devolve o dict.
  Mismatch origem×PDF → `ConversaoError` montada por `_FMT_ORIGEM` (layout →
  origem esperada) + `_ARTIGO_ORIGEM` (só para "ficha **do** Município" vs
  "ficha **da** Prefeitura"). Dentro de `serra`, `_detectar_formato` distingue
  A vs B sozinho.

## Arquivos

| Arquivo | Papel |
|---|---|
| `converter.py` | Motor. Detecta o layout e converte. Roda sozinho: `python converter.py "FF X.pdf"` |
| `app.py` + `Conversor.bat` | App de janela (Tkinter). Duplo clique no `.bat`. |
| `requirements.txt` | `pdfplumber`, `openpyxl`, `pymupdf` |
| `ficha_financeira.xlsx` | Modelo de saída validado (formato A) |
| `FF *.pdf` | Fichas de teste |

## Versão web (`server.py` + `web/`)

Flask. Rotas: `/` e assets de `web/`; `GET /api/origens`, `GET /api/versao`.

**Conversão em FILA** (2026-09-11), porque OCR leva 1-2 min e não cabe numa
requisição HTTP aberta (proxy/navegador/queda de rede matariam o trabalho):
- `POST /api/converter` (multipart `pdf` + `origem`) → **202** `{"job": id}`,
  dispara uma `threading.Thread` e retorna na hora;
- `GET /api/job/<id>` → `processando` (+ `etapa`/`atual`/`total`), `pronto`
  (+ `resumo`) ou `erro`;
- `GET /api/job/<id>/arquivo` → o `.xlsx` via `send_file`.

O andamento vem do callback `progresso(etapa, atual, total)` de
`converter()` — ligado nos 3 laços lentos (`_converter_ocr`,
`_converter_ocr_serra`, `_converter_formato_c`).

**Pegadinhas:**
- Os jobs vivem num dict na memória do processo → o `Procfile` **precisa** de
  `--workers 1` (usa `--threads 8`). Com 2 workers a consulta cai num processo
  que não conhece o job. Se um dia precisar escalar, os jobs têm que sair p/
  disco/Redis.
- O PDF de entrada é apagado no `finally` do job; o `.xlsx` fica num temporário
  até o download e some pela thread de faxina (`JOB_TTL` = 20 min). Sem essa
  faxina o resultado ficaria guardado, quebrando o "processa e descarta".
- `--timeout 900` no gunicorn: OCR de ficha grande passa fácil dos 120s antigos.
- **OCR satura CPU e, com 1 worker, deixa o site todo lento** enquanto
  converte — inclusive para quem só mandou um PDF de texto. Por isso
  `_ocr_engine()` fixa `OMP_NUM_THREADS = CPUs-1`, deixando um núcleo para
  atender requisições. Se a instância tiver 1 CPU só, não tem o que fazer:
  durante um OCR o site fica lento mesmo.
- O modelo de OCR é carregado numa thread no arranque (`_aquecer_ocr`). Sem
  isso a 1ª chamada pagava ~2,5 s — e quem pagava era o usuário, porque o
  front consulta `/api/versao` ao abrir a página.
- **Baixar o DPI do OCR NÃO acelera — já foi testado (2026-09-11).** Medido em
  300/250/200/150 DPI: o tempo praticamente não muda (em 150 chegou a ser
  *maior*), porque o rapidocr redimensiona a imagem para o tamanho fixo do
  modelo de detecção — o gargalo é a inferência, não os pixels. Pior: na Serra,
  DPI menor **muda os valores de lugar** na grade de meses (em 250 DPI
  apareceram 3 linhas falhando a conferência contra o TOTAL). Não repetir.
- **O `Dockerfile` é o que o Railway usa** (não o Procfile). Ele troca o
  `opencv-python` (com GUI, quebra com `libxcb.so.1` em container headless)
  pelo `opencv-python-headless`, e confere o import no build — imagem sem OCR
  falha no build em vez de subir quebrada.

Login opcional por env: `CONVERSOR_SENHA` / `CONVERSOR_USUARIO`. `runtime.txt`
= py 3.12. Front em `web/` é o visual do `ui/` adaptado, com barra de progresso.
Alvo: Railway (instância precisa de folga: pico medido ~580 MB de RAM).

## App de desktop (`app_desktop.py`) — 2026-09-11

Reaproveita a interface da web em vez de duplicá-la: sobe `server.py` numa
porta local (`_porta_livre`, bind em :0) numa thread e abre uma janela
pywebview apontando para `http://127.0.0.1:<porta>`. **`server.py` e `web/`
ficam intocados** — fila, progresso e mensagens são os mesmos.

Motivo de existir: OCR local leva ~72 s; no Railway (3 vCPU) leva ~14 min.

**Pegadinhas (as duas custaram tempo):**
- O download do `web/app.js` é um link de navegador e não funciona em
  pywebview. O app injeta `SHIM_JS` no evento `loaded`, substituindo o global
  `window.baixar` por uma chamada ao `js_api` que abre "Salvar como" nativo.
  Assim `web/app.js` não precisa saber que está no desktop.
- **Atributo que guarda a janela TEM que ser privado** (`self._window`). O
  pywebview inspeciona os atributos públicos do `js_api` para expor à página;
  com `self.window` ele entra em recursão infinita no objeto nativo e despeja
  ~137 KB de erro (`window.native.AccessibilityObject.Bounds.Empty.Empty...`).
- O handler de `loaded` aceita `*args` e **não retorna nada** — devolver o
  resultado do `evaluate_js` causa o mesmo despejo de erro.
- `CONVERSOR_SENHA` é removida do ambiente ANTES de importar o `server`
  (o módulo lê a senha no import), senão o app pediria login local.

`Conversor.bat` aponta para cá. `app_web.py` + `ui/` = janela antiga, reserva.

## Pasta portátil (`construir_portatil.py`) — 2026-09-11

Distribuição para outras máquinas. Baixa o **Python embeddable** (assinado
pela PSF → passa pelo Smart App Control, que barra .exe do PyInstaller),
instala `requirements-desktop.txt` dentro, copia `converter.py`/`server.py`/
`app_desktop.py`/`web/` e gera `Conversor.bat` + `LEIA-ME.txt`. ~360 MB.

**Duas armadilhas do Python embeddable, ambas pegas só ao testar com o Python
DA PASTA (com o do sistema tudo passa):**
1. `requirements-desktop.txt` não tinha **flask** — o `app_desktop.py`
   reaproveita o `server.py`, então o desktop também precisa dele.
2. Com um `._pth` presente o Python entra em **modo isolado e não põe a pasta
   do script no `sys.path`** → `import converter` falhava. O build acrescenta
   `..` ao `._pth` (que é relativo ao diretório do `python.exe`).

Por isso o passo 6/6 roda o Python da pasta, importa tudo, confere
`ocr_status()` e **falha o build** se algo não carregar.

## Empacotamento (.exe) — ABANDONADO (2026-09-09)

Caminho do `.exe` descartado: a máquina do usuário tem **Smart App Control em
modo ENFORCE**, que bloqueia qualquer `.exe` não assinado (PyInstaller/Nuitka/
Electron não resolvem — é falta de assinatura de código). Os arquivos de build
(`ConversorWeb.spec`, `construir_exe.bat`, `icone.ico`, `version_info.txt`,
`dist/`) foram removidos. Distribuição = **versão web** (Railway) ou rodar
`python app_web.py` / `python server.py` localmente.
`app.py --selftest <serra|estado> <pdf>` ainda converte sem abrir janela.

## Os layouts (`_detectar_formato` distingue A/B/C/D/V; "OCR" p/ scan)

**PDF escaneado (imagem, sem texto)** — Estado e Serra. Detectado em
`converter()`: o texto do carimbo do PJe (assinatura/URL/"Num.") é descartado
antes de medir, senão um scan parece "ter texto". OCR = rapidocr, presente no
desktop **e no web** (ver as pegadinhas do Dockerfile acima).
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

- **V — Prefeitura Municipal de Vitória** (2026-09-11) —
  `_converter_formato_vitoria`. Detecção: `"PREFEITURA MUNICIPAL DE VIT"`.
  Texto limpo, acentos corretos (ao contrário de A/B), número BR, **código de
  4 dígitos**, ano em `VALORES PARA O ANO AAAA`, servidor em
  `SERVIDOR: <matrícula> - <NOME> LOCAL:`. Cabeçalho de meses em MAIÚSCULAS
  (`JAN FEV ...`) → `_centros_meses_vitoria` (o `_centros_meses` dos outros
  layouts compara em Title Case e não casaria).
  O que o layout tem de diferente e por que o parser é como é:
  - **Código + nome + os 12 valores estão na MESMA linha** (no layout A o
    código fica numa linha e os valores em outra) → não existe estado
    "codigo_atual" atravessando linhas: cada linha se resolve sozinha.
  - Por ano há **duas** seções de vantagens: `MOVIMENTO NORMAL` e
    `MOVIMENTO DÉCIMO` (13º). As duas entram (é o que soma o total impresso).
  - Entre elas vêm Descontos e uma seção **`VALOR BASE`** (base de cálculo do
    IRRF — repete os códigos 2500/2510 com valores MAIORES). Se ela entrasse,
    a planilha inflaria silenciosamente. Por isso a captura é uma **máquina de
    2 estados**: liga em qualquer linha `MOVIMENTO...`, desliga em
    `TOTAL DE VANTAGEM`. Tudo que está fora desse intervalo (Descontos, Valor
    Base, Totais, resumo do ano) é ignorado sem precisar reconhecer cada seção
    pelo nome.
  - Ano pode terminar numa 2ª página só com o resumo (`ANO: AAAA ...`): sem a
    grade de meses a página é pulada (`len(centros) < 2`).
  - Múltiplos servidores no mesmo PDF: soma e avisa, igual ao layout D.
  - **Não há OCR para esta origem**: ficha de Vitória escaneada dá
    `ConversaoError` explicando (antes caía no OCR da Serra e devolvia lixo ou
    erro falando de outro município).
  Conferido contra os totais impressos em `PDF/vitoria/FF 01/02 vitoria.pdf`:
  72 células ano×mês, 0 divergência (o total do ano sozinho não prova nada —
  valor no mês errado dá o mesmo total; ver `TOTAL DE VANTAGEM` linha a linha).

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
- OCR **já vai pro web** (2026-09-11): `requirements.txt` tem
  `opencv-python-headless` + `rapidocr-onnxruntime`. Falta validar no Railway
  com instância maior (o usuário vai aumentar).
- Conversão em lote (pasta inteira).
- Incluir Descontos/Outros, se o sistema precisar.
- Testar com mais fichas reais.

## Como validar uma conversão

Comparar a soma dos 12 meses de cada rubrica com a coluna **Total** do PDF
(o layout C já faz isso e emite aviso quando não fecha).
