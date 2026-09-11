# Imagem do conversor. O Railway detecta este Dockerfile e o usa no lugar do
# Railpack/Nixpacks — o que nos dá controle sobre as bibliotecas de sistema,
# que é justamente onde o OCR quebrava.
FROM python:3.12-slim

# libgomp1  -> onnxruntime (OpenMP), usado pelo rapidocr.
# libglib2.0-0 -> exigida por builds do opencv, inclusive o headless.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./

# O rapidocr declara dependência de `opencv-python` (a build COM interface
# gráfica, que precisa de libxcb/libGL). Num container headless o import
# morre com "libxcb.so.1: cannot open shared object file" — foi exatamente
# o que aconteceu no primeiro deploy. Listar `opencv-python-headless` no
# requirements NÃO resolve: são distribuições diferentes, e o pip instala a
# cheia porque o rapidocr a declara.
#
# Como as duas fornecem o mesmo módulo `cv2`, a saída é trocar depois da
# instalação: remove as duas (para não ficar meio-a-meio) e põe só a headless,
# que traz a mesma API sem exigir bibliotecas gráficas.
RUN pip install --no-cache-dir -r requirements.txt \
 && pip uninstall -y opencv-python opencv-python-headless \
 && pip install --no-cache-dir opencv-python-headless \
 && python -c "import cv2, rapidocr_onnxruntime; print('cv2', cv2.__version__, '- OCR ok')"

COPY . .

# Fica igual ao Procfile (que o Railway ignora quando há Dockerfile).
# --workers 1 é obrigatório: os jobs vivem na memória do processo.
CMD gunicorn server:app --bind 0.0.0.0:$PORT --workers 1 --threads 8 --timeout 900
