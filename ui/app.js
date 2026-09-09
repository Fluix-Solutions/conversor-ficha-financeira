"use strict";

const $ = (id) => document.getElementById(id);
const state = { origem: null, pdf: null, origens: [] };

/* ---------- API bridge (pywebview) ---------- */
function api() {
  return (window.pywebview && window.pywebview.api) || null;
}
async function ready() {
  if (api()) return;
  await new Promise((res) => window.addEventListener("pywebviewready", res, { once: true }));
}

/* ---------- tema ---------- */
function aplicarTema(dark) {
  document.documentElement.classList.toggle("dark", dark);
  $("toggle-tema").querySelector("span").textContent = dark ? "Modo claro" : "Modo escuro";
  try { localStorage.setItem("tema", dark ? "dark" : "light"); } catch (e) {}
}
$("toggle-tema").addEventListener("click", () =>
  aplicarTema(!document.documentElement.classList.contains("dark"))
);

/* ---------- combobox pesquisável ---------- */
const cInput = $("combo-input");
const cList = $("combo-list");

function renderLista(filtro) {
  const t = (filtro || "").trim().toLowerCase();
  const hits = state.origens.filter((o) => o.rotulo.toLowerCase().includes(t));
  const arr = hits.length ? hits : state.origens;
  cList.innerHTML = "";
  for (const o of arr) {
    const li = document.createElement("li");
    li.textContent = o.rotulo;
    li.dataset.chave = o.chave;
    li.addEventListener("mousedown", (e) => {
      e.preventDefault();
      escolherOrigem(o);
    });
    cList.appendChild(li);
  }
  cList.hidden = false;
}
function escolherOrigem(o) {
  state.origem = o.chave;
  cInput.value = o.rotulo;
  cList.hidden = true;
  atualizarBotao();
}
function abrirLista() {
  cInput.select();
  renderLista("");
}
cInput.addEventListener("focus", abrirLista);
cInput.addEventListener("mousedown", () => {
  if (document.activeElement === cInput) setTimeout(abrirLista, 0);
});
cInput.addEventListener("input", () => {
  state.origem = null;
  renderLista(cInput.value);
  atualizarBotao();
});
cInput.addEventListener("blur", () => setTimeout(() => (cList.hidden = true), 150));
cInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const first = cList.querySelector("li");
    if (first && !cList.hidden) {
      escolherOrigem(state.origens.find((o) => o.chave === first.dataset.chave));
    }
  } else if (e.key === "Escape") {
    cList.hidden = true;
  }
});

/* ---------- escolher PDF ---------- */
$("btn-pdf").addEventListener("click", async () => {
  const p = await api().escolher_pdf();
  if (!p) return;
  state.pdf = p;
  $("pdf-nome").textContent = p.split(/[\\/]/).pop();
  atualizarBotao();
});

/* ---------- converter ---------- */
function atualizarBotao() {
  $("btn-converter").disabled = !(state.origem && state.pdf);
}

$("btn-converter").addEventListener("click", async () => {
  const btn = $("btn-converter");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Convertendo…';
  $("result-card").hidden = true;

  const r = await api().converter(state.pdf, state.origem);

  btn.textContent = "Converter para Excel";
  atualizarBotao();
  mostrarResultado(r);
});

function mostrarResultado(r) {
  const box = $("result");
  $("result-card").hidden = false;
  if (r.erro) {
    box.className = "result " + (r.tipo === "aviso" ? "warn" : "err");
    box.textContent = r.erro;
    return;
  }
  box.className = "result ok";
  const anos = r.anos && r.anos.length ? r.anos[0] + "–" + r.anos[r.anos.length - 1] : "—";
  let html =
    "<b>✓ Conversão concluída</b>\n" +
    "Arquivo: " + r.arquivo + "\n" +
    "Origem: " + r.origem + "\n" +
    "Período: " + anos + "     Contratos: " + r.blocos + "     Colunas: " + r.rubricas;
  if (r.multiplos_blocos)
    html +=
      "\nA pessoa tem mais de um contrato (" + (r.contratos || []).join(", ") +
      "). Nos meses em que dois contratos pagaram, os valores da mesma verba foram somados.";
  if (r.avisos && r.avisos.length)
    html +=
      '<div class="avisos">Conferir na planilha:\n- ' + r.avisos.join("\n- ") + "</div>";
  box.innerHTML = html;

  const abrir = document.createElement("button");
  abrir.className = "btn";
  abrir.style.cssText = "display:block;margin-top:14px";
  abrir.textContent = "Abrir planilha";
  abrir.addEventListener("click", () => api().abrir(r.arquivo));
  box.appendChild(abrir);
}

/* ---------- ajuda ---------- */
$("nav-ajuda").addEventListener("click", (e) => {
  e.preventDefault();
  $("result-card").hidden = false;
  $("result").className = "result warn";
  $("result").textContent =
    "Como usar:\n" +
    "1. Escolha a origem da ficha (Município da Serra ou Estado do Espírito Santo).\n" +
    "2. Clique em “Escolher PDF…” e selecione a ficha financeira.\n" +
    "3. Clique em “Converter para Excel” e escolha onde salvar.\n\n" +
    "PDFs escaneados (imagem, sem texto) ainda não são suportados.";
});

/* ---------- init ---------- */
(async () => {
  try {
    const t = localStorage.getItem("tema");
    if (t === "dark") aplicarTema(true);
  } catch (e) {}
  await ready();
  state.origens = await api().origens();
  $("versao").textContent = "v" + (await api().versao());
})();
