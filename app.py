"""
Conversor de Ficha Financeira - aplicativo de janela.

Abra com um duplo clique em "Conversor.bat" (ou rode: python app.py).
"""
from __future__ import annotations

import queue
import threading
import traceback
from pathlib import Path
from tkinter import Tk, StringVar, filedialog, messagebox, scrolledtext
from tkinter import ttk

from converter import ORIGENS, ConversaoError, converter

APP_TITULO = "Conversor de Ficha Financeira"


class App:
    def __init__(self, root: Tk):
        self.root = root
        self.pdf_path: Path | None = None
        self.fila: queue.Queue = queue.Queue()

        root.title(APP_TITULO)
        root.geometry("640x460")
        root.minsize(560, 400)

        moldura = ttk.Frame(root, padding=16)
        moldura.pack(fill="both", expand=True)

        ttk.Label(
            moldura, text=APP_TITULO, font=("Segoe UI", 15, "bold")
        ).pack(anchor="w")
        ttk.Label(
            moldura,
            text="Converte a 'Relação Ficha Financeira' (PDF) em uma planilha Excel "
            "com os Proventos por mês.",
            wraplength=580,
            foreground="#555",
        ).pack(anchor="w", pady=(2, 14))

        # -- 1) origem da ficha -------------------------------------------
        grupo = ttk.LabelFrame(moldura, text="1. Origem da ficha", padding=10)
        grupo.pack(fill="x")
        ttk.Label(
            grupo, text="Digite para pesquisar e escolha na lista:",
            foreground="#555",
        ).pack(anchor="w")
        # rótulo exibido -> chave interna ("serra" / "estado" / ...)
        self._origens = {rotulo: chave for chave, rotulo in ORIGENS.items()}
        self._origens_labels = sorted(self._origens)
        self.var_origem = StringVar(value="")
        self.cbo_origem = ttk.Combobox(
            grupo, textvariable=self.var_origem, values=self._origens_labels,
            state="normal",
        )
        self.cbo_origem.pack(fill="x", pady=(4, 0))
        self.cbo_origem.bind("<KeyRelease>", self._filtrar_origem)
        self.cbo_origem.bind(
            "<<ComboboxSelected>>", lambda e: self._atualizar_botao()
        )

        # -- 2) arquivo PDF ---------------------------------------------
        linha_pdf = ttk.Frame(moldura)
        linha_pdf.pack(fill="x", pady=(12, 0))
        self.var_pdf = StringVar(value="Nenhum PDF selecionado")
        ttk.Button(linha_pdf, text="2. Abrir PDF...", command=self.escolher_pdf).pack(
            side="left"
        )
        ttk.Label(linha_pdf, textvariable=self.var_pdf, foreground="#333").pack(
            side="left", padx=10
        )

        self.btn_converter = ttk.Button(
            moldura, text="3. Converter para Excel", command=self.converter, state="disabled"
        )
        self.btn_converter.pack(anchor="w", pady=14)

        self.barra = ttk.Progressbar(moldura, mode="indeterminate")

        ttk.Label(moldura, text="Resultado:", font=("Segoe UI", 10, "bold")).pack(
            anchor="w"
        )
        self.log = scrolledtext.ScrolledText(
            moldura, height=12, wrap="word", font=("Consolas", 9), state="disabled"
        )
        self.log.pack(fill="both", expand=True, pady=(4, 0))

        self._escrever(
            "1. Escolha a origem da ficha (Serra ou Estado).\n"
            "2. Clique em 'Abrir PDF...' e escolha a ficha financeira.\n"
            "3. Clique em 'Converter para Excel' e escolha onde salvar.\n"
        )

    # -- ações -------------------------------------------------------------
    def _origem_chave(self):
        """Chave interna da origem escolhida, ou None se o texto não for válido."""
        return self._origens.get(self.var_origem.get().strip())

    def _filtrar_origem(self, event):
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        txt = self.var_origem.get().strip().lower()
        achados = [o for o in self._origens_labels if txt in o.lower()]
        self.cbo_origem["values"] = achados or self._origens_labels
        self._atualizar_botao()

    def _atualizar_botao(self):
        pronto = bool(self.pdf_path) and self._origem_chave() is not None
        self.btn_converter.config(state="normal" if pronto else "disabled")

    def escolher_pdf(self):
        caminho = filedialog.askopenfilename(
            title="Escolha a ficha financeira (PDF)",
            filetypes=[("Arquivos PDF", "*.pdf")],
        )
        if not caminho:
            return
        self.pdf_path = Path(caminho)
        self.var_pdf.set(self.pdf_path.name)
        self._atualizar_botao()
        self._escrever(f"\nPDF selecionado: {self.pdf_path}\n")

    def converter(self):
        if not self.pdf_path:
            return
        sugestao = self.pdf_path.with_suffix(".xlsx").name
        destino = filedialog.asksaveasfilename(
            title="Salvar planilha como",
            defaultextension=".xlsx",
            initialfile=sugestao,
            initialdir=str(self.pdf_path.parent),
            filetypes=[("Planilha Excel", "*.xlsx")],
        )
        if not destino:
            return

        self.btn_converter.config(state="disabled")
        self.barra.pack(fill="x", pady=(0, 12))
        self.barra.start(12)
        self._escrever("\nConvertendo... aguarde.\n")

        t = threading.Thread(
            target=self._trabalho,
            args=(self.pdf_path, Path(destino), self._origem_chave()),
            daemon=True,
        )
        t.start()
        self.root.after(100, self._checar_fila)

    # -- bastidores ------------------------------------------------------
    def _trabalho(self, pdf: Path, saida: Path, origem: str):
        try:
            resumo = converter(pdf, saida, origem)
            self.fila.put(("ok", resumo))
        except ConversaoError as e:
            self.fila.put(("erro_conhecido", str(e)))
        except Exception:
            self.fila.put(("erro", traceback.format_exc()))

    def _checar_fila(self):
        try:
            tipo, dado = self.fila.get_nowait()
        except queue.Empty:
            self.root.after(100, self._checar_fila)
            return

        self.barra.stop()
        self.barra.pack_forget()
        self._atualizar_botao()

        if tipo == "ok":
            self._mostrar_sucesso(dado)
        elif tipo == "erro_conhecido":
            self._escrever(f"\n❌ {dado}\n")
            messagebox.showwarning(APP_TITULO, dado)
        else:
            self._escrever(f"\n❌ Erro inesperado:\n{dado}\n")
            messagebox.showerror(
                APP_TITULO, "Ocorreu um erro inesperado. Veja os detalhes na janela."
            )

    def _mostrar_sucesso(self, r: dict):
        anos = r["anos"]
        periodo = f"{anos[0]}–{anos[-1]}" if anos else "-"
        linhas = [
            "",
            "✅ Conversão concluída!",
            f"   Arquivo:  {r['arquivo']}",
            f"   Origem:   {r['origem']}",
            f"   Período:  {periodo}",
            f"   Contratos: {r['blocos']}     Colunas: {r['rubricas']}",
        ]
        if r["multiplos_blocos"]:
            linhas.append(
                f"   Mais de um contrato ({', '.join(r['contratos'])}). Nos meses "
                "com dois contratos, os valores da mesma verba foram somados."
            )
        if r["avisos"]:
            linhas.append("")
            linhas.append("   Avisos (conferir na planilha):")
            linhas += [f"     - {a}" for a in r["avisos"]]
        self._escrever("\n".join(linhas) + "\n")

        if messagebox.askyesno(
            APP_TITULO, "Conversão concluída!\n\nQuer abrir a planilha agora?"
        ):
            try:
                import os

                os.startfile(r["arquivo"])  # Windows
            except Exception:
                pass

    def _escrever(self, texto: str):
        self.log.config(state="normal")
        self.log.insert("end", texto)
        self.log.see("end")
        self.log.config(state="disabled")


def _selftest(tipo: str, pdf: str):
    """Converte um PDF sem abrir janela. Usado para testar o .exe empacotado."""
    import tempfile

    saida = Path(tempfile.gettempdir()) / "selftest_ficha.xlsx"
    try:
        r = converter(Path(pdf), saida, tipo)
    except Exception as e:  # noqa: BLE001
        print(f"FALHOU: {e}")
        return 1
    print(f"OK  origem={r['origem']}  anos={r['anos']}  rubricas={r['rubricas']}")
    return 0


def main():
    import sys

    if len(sys.argv) >= 4 and sys.argv[1] == "--selftest":
        sys.exit(_selftest(sys.argv[2], sys.argv[3]))

    root = Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
