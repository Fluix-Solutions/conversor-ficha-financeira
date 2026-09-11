# Conversor de Ficha Financeira (PDF → Excel)

Converte a Ficha Financeira (Prefeitura da Serra, Governo do Estado do ES
**ou** Prefeitura de Vitória) em uma planilha `.xlsx` com os **Proventos** por
mês: uma linha por `Ano + Mês`, uma coluna por rubrica (só o nome da verba,
sem o código).

## Instalação (uma vez)

1. Instale o [Python](https://www.python.org/downloads/) (marque
   *"Add Python to PATH"* durante a instalação).
2. Nesta pasta, instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

## Usar o programa (janela)

Dê um **duplo clique em `Conversor.bat`**. Abre a **mesma tela do site**, com
os 3 passos guiados e a barra de progresso — só que rodando na sua máquina.

1. **Origem da ficha** → digite parte do nome (ex: `serra`) e escolha na lista.
2. **Arquivo PDF** → clique ou arraste a ficha.
3. **Converter para Excel** → ao terminar, abre um "Salvar como" e a planilha
   é aberta em seguida.

**Use o desktop para fichas escaneadas.** O OCR roda no seu computador:
medido em ~72 s, contra ~14 min na instância do Railway (3 vCPU). Para PDFs
de texto tanto faz — os dois são instantâneos.

Como funciona (`app_desktop.py`): em vez de manter duas interfaces, o app sobe
o próprio `server.py` numa porta local e abre uma janela apontando para ele.
`server.py` e a pasta `web/` são usados **sem alteração nenhuma**. A única
diferença é o download: o `web/app.js` usa um link de navegador, que não
funciona bem em janela pywebview, então o app substitui a função `baixar()`
depois que a página carrega — sem tocar no arquivo.

`app_web.py` + `ui/` são a janela antiga (interface anterior ao redesenho),
mantidos como reserva.

## Usar pela linha de comando (opcional)

```bash
python converter.py "FF 1.pdf" -t serra
```

`-t` / `--tipo` é obrigatório: `serra`, `estado` ou `vitoria`. Para escolher o
nome da saída: `python converter.py "FF 1.pdf" -t serra -o "saida.xlsx"`.

## Layouts

A origem é escolhida no seletor; dentro de **Serra** o programa ainda distingue
sozinho os dois modelos:

**A — Sistema FPFF902 (Serra, recente).** Linhas `001 Salário Base`, um ano por página.

**B — Sistema FPFF102 (Serra, antigo).** Linhas `Evento: 001 Salário Base` + linha
`Valor` + linha `Ref.` (horas). Um ano ocupa 2+ páginas e a fonte do PDF não
traz mapa de caracteres — o texto é decodificado por deslocamento fixo.
Só a linha **Valor** é usada; os meses são deduzidos pela posição de cada número.

**C — SIARHES / PRODEST (Governo do Estado do ES), com cifra.** Uma página por
ano, seções **Vantagens** e **Descontos**. A fonte é do tipo Type3 (glifos
desenhados) e cada página embaralha as letras e os números de um jeito
diferente. O programa descobre a cifra de cada página cruzando as linhas de
total (`soma dos 12 meses = coluna Total`, `Total Líquido = Vantagens −
Descontos`) e comparando o desenho de cada glifo entre as páginas. Todos os
valores conferem com os totais impressos no PDF.

**D — Governo do Estado do ES, texto limpo (sem cifra).** Modelos "FICHA
FINANCEIRA" e "FICHA FINANCEIRA POR FUNCIONÁRIO". Linhas
`código  nome  12 valores  total`, número no estilo `1.234,56` americano
(`1,234.56`). O nome da rubrica vem do próprio PDF. Se o arquivo tiver mais
de um servidor, o programa junta tudo e mostra um aviso.

**V — Prefeitura Municipal de Vitória.** Um ano por página, cabeçalho
`VALORES PARA O ANO`, rubricas com código de 4 dígitos
(`1002 - VENCIMENTO`). Entram na planilha as duas seções de vantagens do ano —
`MOVIMENTO NORMAL` e `MOVIMENTO DÉCIMO` (13º salário). A seção **`VALOR BASE`**
que aparece no meio da ficha é a base de cálculo do IRRF/IPAMV, **não** é
provento, e é ignorada. Se o arquivo tiver mais de um servidor, junta tudo e
avisa. Fichas de Vitória **escaneadas** ainda não são suportadas (só as
exportadas com texto).

A planilha tem sempre **uma linha por Ano + Mês**. Se a pessoa teve **mais de um
contrato (matrícula)** e dois deles pagaram no mesmo mês, os valores da mesma
verba são **somados**.

## Avisos que o programa pode mostrar

- **`Nome incompleto (acento): NNN '...'`** — o nome da rubrica ficou com `?`
  no lugar de um acento. Não afeta os valores. Para corrigir o nome, edite a
  tabela `RUBRICAS_CANONICAS` no início de `converter.py`:

  ```python
  "161": "Gratif. Direção 3108/2007",
  ```

## Limitações

- Extrai apenas **Proventos** (não Descontos nem Outros).
- **PDFs escaneados** (imagem, sem texto) são lidos por **OCR** da Serra e do
  Estado — inclusive quando a folha foi digitalizada deitada ou de cabeça para
  baixo (a orientação é detectada automaticamente). **Vitória escaneada ainda
  não é suportada** (dá erro explicando). Nesse modo:
  - cada rubrica é conferida contra a coluna **TOTAL** impressa na ficha, e o
    que não fecha vira aviso `CONFERIR`;
  - **sempre confira a planilha contra o PDF** antes de usar no cálculo;
  - scans de qualidade muito baixa são **recusados** com erro claro, em vez de
    gerar uma planilha duvidosa;
  - exige as dependências de OCR — presentes tanto no app de desktop
    (`requirements-desktop.txt`) quanto na versão web. Onde o OCR não estiver
    disponível, o PDF escaneado é recusado com mensagem clara, e
    `GET /api/versao` mostra `"ocr": false` com o motivo.
- No layout B, rubricas pagas em poucos meses são posicionadas pela coordenada
  do número no PDF; convém conferir os meses parciais nas primeiras fichas.

## Levar para outros computadores (pasta portátil)

```bash
python construir_portatil.py
```

Gera `portatil/Conversor de Ficha Financeira/` (~360 MB) com um **Python
embutido** e todas as dependências dentro. Copie a pasta para a outra máquina
(pendrive, rede, OneDrive) e dê **duplo clique em `Conversor.bat`** — não se
instala nada, e funciona sem internet, com OCR em velocidade plena (~73 s por
ficha escaneada).

Por que não um `.exe`: um executável do PyInstaller não é assinado, e o
Windows com **Smart App Control** o bloqueia — foi o que inviabilizou esse
caminho aqui. O `python.exe` embutido é assinado pela Python Software
Foundation e passa.

Requisitos na máquina de destino (já presentes num Windows 10/11 atualizado):
.NET Framework 4.7.2+ e o WebView2 Runtime (vem com o Edge).

> O build **confere a pasta gerada rodando o Python dela** e falha se algo não
> importar. Isso não é zelo excessivo: na primeira versão faltava o `flask`, e
> na segunda o Python embutido não enxergava `converter.py` — nenhum dos dois
> aparece se você testar com o Python do sistema.

## Versão web (rodar online)

`server.py` é um servidor Flask que serve a mesma interface (pasta `web/`).
O PDF enviado é gravado num temporário só durante a conversão e apagado logo
em seguida — nada fica salvo no servidor, e o conteúdo não vai para log.

A conversão roda em **fila**, não na requisição: converter uma ficha escaneada
leva de 1 a 2 minutos (OCR), tempo demais para uma requisição HTTP ficar
aberta — proxy, navegador ou uma queda de rede derrubariam o trabalho no meio.
O fluxo é:

| Rota | O que faz |
|---|---|
| `POST /api/converter` | enfileira e devolve `{"job": "<id>"}` (HTTP 202) |
| `GET /api/job/<id>` | estado e andamento (`Lendo a imagem da página 4 de 10`) |
| `GET /api/job/<id>/arquivo` | baixa o `.xlsx` |

O `.xlsx` gerado fica num temporário até o download e é apagado por uma faxina
automática em no máximo 20 minutos (`JOB_TTL`).

> **Os jobs vivem na memória do processo**, por isso o `Procfile` usa
> `--workers 1` (com `--threads`). Com mais de um worker, a consulta do
> andamento cairia num processo que não conhece o job.

### Rodar localmente

```bash
pip install -r requirements.txt
python server.py            # abre em http://127.0.0.1:8000
```

### Proteger com senha (recomendado)

Defina as variáveis de ambiente antes de subir:

| Variável | Efeito |
|---|---|
| `CONVERSOR_SENHA` | se definida, o site passa a exigir login |
| `CONVERSOR_USUARIO` | usuário do login (padrão `conversor`) |

### Deploy no Railway

1. Suba a pasta para um repositório GitHub.
2. No Railway: **New Project → Deploy from GitHub repo**.
3. O Railway detecta o **`Dockerfile`** e o usa (ignorando `Procfile` /
   `runtime.txt`). O Dockerfile existe por um motivo específico: o `rapidocr`
   puxa `opencv-python` com interface gráfica, que num container headless
   quebra no import (`libxcb.so.1`); ele troca pela build headless e confere
   o import ainda no build, de modo que uma imagem sem OCR **falha ali** em
   vez de subir quebrada.
4. Em **Variables**, defina `CONVERSOR_SENHA` (e opcionalmente `CONVERSOR_USUARIO`).
5. Pronto — a URL gerada pelo Railway é o conversor online.
6. Confira em `GET /api/versao`: deve vir `"ocr": true`. Se vier `false`, o
   `ocr_erro` diz o motivo e fichas escaneadas serão recusadas.

**Tamanho da instância.** O OCR pesa: as dependências somam ~210 MB
(opencv sozinho são ~118 MB) e o pico de RAM de uma conversão medido foi de
**~580 MB**. A instância precisa de folga — numa pequena demais o processo é
morto no meio da conversão.

Arquivos de deploy: `Dockerfile` (o que o Railway usa), `.dockerignore`,
`requirements.txt`. `Procfile` e `runtime.txt` ficam para outros builders.

## Arquivos do projeto

| Arquivo | Função |
|---|---|
| `converter.py` | Motor da conversão (`python converter.py PDF -t serra\|estado\|vitoria`) |
| `server.py` + `web/` | Versão web (Flask) |
| `app_web.py` + `ui/` | App de janela (pywebview, visual Valorizei) |
| `app.py` | App de janela antigo (Tkinter) — reserva |
| `Conversor.bat` | Abre o app de janela (duplo clique) |
| `requirements.txt` | Deploy web (engine + Flask) |
| `requirements-desktop.txt` | App de janela (engine + pywebview) |
| `requirements-base.txt` | Só o motor (`pdfplumber`, `openpyxl`, `pymupdf`) |
