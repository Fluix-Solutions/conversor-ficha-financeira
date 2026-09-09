"use strict";

const $ = (id) => document.getElementById(id);
const state = { origem: null, file: null, origens: [] };

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
    li.addEventListener("mousedown", (e) => { e.preventDefault(); escolherOrigem(o); });
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
  // ao (re)abrir, mostra todas as opções e seleciona o texto para digitar por cima
  cInput.select();
  renderLista("");
}
cInput.addEventListener("focus", abrirLista);
cInput.addEventListener("mousedown", () => {
  if (document.activeElement === cInput) setTimeout(abrirLista, 0);
});
cInput.addEventListener("input", () => { state.origem = null; renderLista(cInput.value); atualizarBotao(); });
cInput.addEventListener("blur", () => setTimeout(() => (cList.hidden = true), 150));
cInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const first = cList.querySelector("li");
    if (first && !cList.hidden) escolherOrigem(state.origens.find((o) => o.chave === first.dataset.chave));
  } else if (e.key === "Escape") cList.hidden = true;
});

/* ---------- arquivo (clique + arrastar) ---------- */
const dz = $("dropzone");
const fileInput = $("pdf-input");

function setFile(f) {
  if (!f) return;
  if (!/\.pdf$/i.test(f.name)) { alerta("Envie um arquivo PDF."); return; }
  state.file = f;
  $("dz-text").innerHTML = 'PDF escolhido: <span class="file-chosen"></span>';
  $("dz-text").querySelector(".file-chosen").textContent = f.name;
  atualizarBotao();
}
fileInput.addEventListener("change", () => setFile(fileInput.files[0]));
["dragover", "dragenter"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("drag"); })
);
["dragleave", "drop"].forEach((ev) =>
  dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("drag"); })
);
dz.addEventListener("drop", (e) => setFile(e.dataTransfer.files[0]));

/* ---------- converter ---------- */
function atualizarBotao() {
  $("btn-converter").disabled = !(state.origem && state.file);
}

$("btn-converter").addEventListener("click", async () => {
  const btn = $("btn-converter");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span>Convertendo…';
  $("result-card").hidden = true;

  const fd = new FormData();
  fd.append("pdf", state.file);
  fd.append("origem", state.origem);

  try {
    const resp = await fetch("api/converter", { method: "POST", body: fd });
    const data = await resp.json();
    if (!resp.ok || data.erro) {
      mostrarErro(data.erro || "Erro na conversão.", data.tipo);
    } else {
      baixar(data.arquivo_nome, data.arquivo_b64);
      mostrarSucesso(data.resumo, data.arquivo_nome);
    }
  } catch (e) {
    mostrarErro("Não consegui falar com o servidor. Tente de novo.", "erro");
  }

  btn.textContent = "Converter para Excel";
  atualizarBotao();
});

function baixar(nome, b64) {
  const bin = atob(b64);
  const buf = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) buf[i] = bin.charCodeAt(i);
  const blob = new Blob([buf], {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

function mostrarSucesso(r, nome) {
  const box = $("result");
  $("result-card").hidden = false;
  box.className = "result ok";
  const anos = r.anos && r.anos.length ? r.anos[0] + "–" + r.anos[r.anos.length - 1] : "—";
  let html =
    "<b>✓ Conversão concluída — o download começou.</b>\n" +
    "Arquivo: " + nome + "\n" +
    "Origem: " + r.origem + "\n" +
    "Período: " + anos + "     Contratos: " + r.blocos + "     Colunas: " + r.rubricas;
  if (r.multiplos_blocos)
    html +=
      "\nA pessoa tem mais de um contrato (" + (r.contratos || []).join(", ") +
      "). Nos meses em que dois contratos pagaram, os valores da mesma verba foram somados.";
  if (r.avisos && r.avisos.length)
    html += '<div class="avisos">Conferir na planilha:\n- ' + r.avisos.join("\n- ") + "</div>";
  box.innerHTML = html;
}
function mostrarErro(msg, tipo) {
  const box = $("result");
  $("result-card").hidden = false;
  box.className = "result " + (tipo === "aviso" ? "warn" : "err");
  box.textContent = msg;
}
function alerta(msg) { mostrarErro(msg, "aviso"); }

/* ---------- ajuda ---------- */
$("nav-ajuda").addEventListener("click", (e) => {
  e.preventDefault();
  mostrarErro(
    "Como usar:\n" +
    "1. Escolha a origem da ficha (Município da Serra ou Estado do Espírito Santo).\n" +
    "2. Escolha ou arraste o PDF da ficha financeira.\n" +
    "3. Clique em “Converter para Excel” — o download começa sozinho.\n\n" +
    "O PDF é processado na hora e descartado; nada fica salvo no servidor.\n" +
    "PDFs escaneados (imagem, sem texto) ainda não são suportados.",
    "aviso"
  );
});

/* ---------- init ---------- */
(async () => {
  try { if (localStorage.getItem("tema") === "dark") aplicarTema(true); } catch (e) {}
  try {
    state.origens = await fetch("api/origens").then((r) => r.json());
  } catch (e) { state.origens = []; }
})();
