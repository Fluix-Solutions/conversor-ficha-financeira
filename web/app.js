"use strict";

const $ = (id) => document.getElementById(id);
const state = { origem: null, file: null, origens: [], ultimo: null };

/* ---------- tema ---------- */
function aplicarTema(dark) {
  document.documentElement.classList.toggle("dark", dark);
  const txt = dark ? "Modo claro" : "Modo escuro";
  const span = $("toggle-tema").querySelector("span");
  if (span) span.textContent = txt;
  try { localStorage.setItem("tema", dark ? "dark" : "light"); } catch (e) {}
}
const alternarTema = () =>
  aplicarTema(!document.documentElement.classList.contains("dark"));
$("toggle-tema").addEventListener("click", alternarTema);
$("toggle-tema-m").addEventListener("click", alternarTema);

/* ---------- ajuda ---------- */
$("nav-ajuda").addEventListener("click", (e) => {
  e.preventDefault();
  const p = $("painel-ajuda");
  p.hidden = !p.hidden;
  if (!p.hidden) p.scrollIntoView({ behavior: "smooth", block: "nearest" });
});
$("nav-converter").addEventListener("click", (e) => {
  e.preventDefault();
  $("painel-ajuda").hidden = true;
  window.scrollTo({ top: 0, behavior: "smooth" });
});

/* ---------- passos / estado visual ---------- */
function atualizarPassos() {
  const temOrigem = !!state.origem;
  const temArquivo = !!state.file;

  marcar($("card-origem"), temOrigem ? "done" : "active");
  marcar($("card-arquivo"), temArquivo ? "done" : temOrigem ? "active" : "");

  passo("origem", temOrigem ? "done" : "active");
  passo("arquivo", temArquivo ? "done" : temOrigem ? "active" : "");
  passo("baixar", state.ultimo ? "done" : temOrigem && temArquivo ? "active" : "");

  $("btn-converter").disabled = !(temOrigem && temArquivo);
}
function marcar(card, estado) {
  card.classList.toggle("is-active", estado === "active");
  card.classList.toggle("is-done", estado === "done");
}
function passo(nome, estado) {
  const li = document.querySelector(`.steps li[data-step="${nome}"]`);
  li.classList.toggle("active", estado === "active");
  li.classList.toggle("done", estado === "done");
}

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
  atualizarPassos();
}
function abrirLista() { cInput.select(); renderLista(""); }
cInput.addEventListener("focus", abrirLista);
cInput.addEventListener("mousedown", () => {
  if (document.activeElement === cInput) setTimeout(abrirLista, 0);
});
cInput.addEventListener("input", () => {
  state.origem = null; renderLista(cInput.value); atualizarPassos();
});
cInput.addEventListener("blur", () => setTimeout(() => (cList.hidden = true), 150));
cInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const first = cList.querySelector("li");
    if (first && !cList.hidden)
      escolherOrigem(state.origens.find((o) => o.chave === first.dataset.chave));
  } else if (e.key === "Escape") cList.hidden = true;
});

/* ---------- arquivo (clique + arrastar) ---------- */
const dz = $("dropzone");
const fileInput = $("pdf-input");

function setFile(f) {
  if (!f) return;
  if (!/\.pdf$/i.test(f.name)) { mostrarErro("Envie um arquivo PDF.", "aviso"); return; }
  state.file = f;
  dz.classList.add("tem-arquivo");
  $("dz-text").innerHTML = 'PDF escolhido: <span class="file-chosen"></span>';
  $("dz-text").querySelector(".file-chosen").textContent = f.name;
  atualizarPassos();
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
      state.ultimo = { nome: data.arquivo_nome, b64: data.arquivo_b64 };
      baixar(data.arquivo_nome, data.arquivo_b64);
      mostrarSucesso(data.resumo, data.arquivo_nome);
    }
  } catch (e) {
    mostrarErro("Não consegui falar com o servidor. Tente de novo.", "erro");
  }

  btn.textContent = "Converter para Excel";
  atualizarPassos();
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
$("btn-baixar-de-novo").addEventListener("click", () => {
  if (state.ultimo) baixar(state.ultimo.nome, state.ultimo.b64);
});

function mostrarSucesso(r, nome) {
  const box = $("result");
  $("result-card").hidden = false;
  $("btn-baixar-de-novo").hidden = false;
  box.className = "result ok";
  const anos = r.anos && r.anos.length
    ? r.anos[0] + (r.anos.length > 1 ? "–" + r.anos[r.anos.length - 1] : "")
    : "—";
  let html =
    "<b>✓ Conversão concluída — o download começou.</b>\n\n" +
    "Arquivo: " + nome + "\n" +
    "Origem: " + r.origem + "\n" +
    "Período: " + anos + "     Contratos: " + r.blocos + "     Colunas: " + r.rubricas;
  if (r.multiplos_blocos)
    html +=
      "\n\nA pessoa tem mais de um contrato (" + (r.contratos || []).join(", ") +
      "). Nos meses em que dois contratos pagaram, os valores da mesma verba foram somados.";
  if (r.avisos && r.avisos.length)
    html += '<div class="avisos"><b>Conferir na planilha:</b>\n- ' + r.avisos.join("\n- ") + "</div>";
  box.innerHTML = html;
  $("result-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
}
function mostrarErro(msg, tipo) {
  const box = $("result");
  $("result-card").hidden = false;
  $("btn-baixar-de-novo").hidden = true;
  box.className = "result " + (tipo === "aviso" ? "warn" : "err");
  box.textContent = msg;
  $("result-card").scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ---------- init ---------- */
(async () => {
  try { if (localStorage.getItem("tema") === "dark") aplicarTema(true); } catch (e) {}
  try {
    state.origens = await fetch("api/origens").then((r) => r.json());
  } catch (e) { state.origens = []; }
  try {
    const v = await fetch("api/versao").then((r) => r.json());
    if (v && v.versao) $("versao").textContent = "v" + v.versao;
  } catch (e) {}
  atualizarPassos();
})();
