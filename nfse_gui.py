#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NFSe XML -> TXT ISS Fortaleza | Interface Grafica v2.0
Ednaldo Rodrigues Vieira - CRC/CE 029501/O-8
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import sys
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nfse_xml_to_txt import parse_nfse, gerar_linha

# ── Paleta de cores ────────────────────────────────────────────────────────────
BG        = "#F0F2F5"
PAINEL    = "#FFFFFF"
AZUL      = "#1565C0"
AZUL_ESC  = "#0D47A1"
AZUL_CLR  = "#E3F2FD"
VERDE     = "#2E7D32"
VERMELHO  = "#C62828"
TEXTO     = "#212121"
SUBTEXTO  = "#757575"
BORDA     = "#CFD8DC"
LOG_BG    = "#1E272E"
LOG_FG    = "#D2DBE0"

# ── Fontes ─────────────────────────────────────────────────────────────────────
F_TITULO  = ("Segoe UI", 14, "bold")
F_SUBTIT  = ("Segoe UI",  9)
F_LABEL   = ("Segoe UI", 10)
F_BOLD    = ("Segoe UI", 10, "bold")
F_MONO    = ("Consolas",  9)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NFSe XML  →  TXT ISS Fortaleza")
        self.configure(bg=BG)
        self.minsize(720, 640)
        self.resizable(True, True)
        self._estilos()
        self._build()
        self._centralizar()

    # ── Estilos ttk ───────────────────────────────────────────────────────────

    def _estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure("TFrame",        background=BG)
        s.configure("P.TFrame",      background=PAINEL)
        s.configure("TLabel",        background=BG,    foreground=TEXTO, font=F_LABEL)
        s.configure("P.TLabel",      background=PAINEL, foreground=TEXTO, font=F_LABEL)
        s.configure("Sub.TLabel",    background=PAINEL, foreground=SUBTEXTO, font=F_SUBTIT)
        s.configure("TEntry",        fieldbackground=PAINEL, foreground=TEXTO,
                    font=F_LABEL, padding=4)
        s.configure("Azul.TButton",  background=AZUL,  foreground="white",
                    font=F_BOLD,  padding=(14, 8), relief="flat", borderwidth=0)
        s.map("Azul.TButton",
              background=[("active", AZUL_ESC), ("pressed", AZUL_ESC),
                          ("disabled", BORDA)],
              foreground=[("disabled", SUBTEXTO)])
        s.configure("Ghost.TButton", background=PAINEL, foreground=AZUL,
                    font=F_LABEL, padding=(8, 5), relief="flat", borderwidth=0)
        s.map("Ghost.TButton",
              background=[("active", AZUL_CLR)])

    # ── Centralizar na tela ───────────────────────────────────────────────────

    def _centralizar(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── Construção da interface ───────────────────────────────────────────────

    def _build(self):
        self._cabecalho()
        corpo = ttk.Frame(self, padding=(16, 12, 16, 8))
        corpo.pack(fill="both", expand=True)
        corpo.columnconfigure(0, weight=1)
        corpo.rowconfigure(2, weight=2)
        corpo.rowconfigure(4, weight=1)

        self._secao_empresa(corpo)
        self._secao_xml(corpo)
        self._secao_saida(corpo)
        self._botao_processar(corpo)
        self._secao_log(corpo)
        self._barra_status()

    def _cabecalho(self):
        cab = tk.Frame(self, bg=AZUL, pady=0)
        cab.pack(fill="x")

        inner = tk.Frame(cab, bg=AZUL, padx=18, pady=14)
        inner.pack(fill="x")

        tk.Label(inner, text="NFSe XML  →  TXT",
                 bg=AZUL, fg="white", font=F_TITULO,
                 anchor="w").pack(side="left")

        info = tk.Frame(inner, bg=AZUL)
        info.pack(side="right", anchor="e")
        tk.Label(info, text="ISS Fortaleza / CE",
                 bg=AZUL, fg="#90CAF9", font=("Segoe UI", 9, "bold")).pack(anchor="e")
        tk.Label(info, text="Ednaldo Rodrigues Vieira  ·  CRC/CE 029501/O-8",
                 bg=AZUL, fg="#BBDEFB", font=("Segoe UI", 8)).pack(anchor="e")

        # linha separadora
        tk.Frame(self, bg=AZUL_ESC, height=2).pack(fill="x")

    def _card(self, pai, titulo, row, pady=(0, 10), expand=False):
        """Cria um card branco com título colorido."""
        outer = tk.Frame(pai, bg=BORDA, bd=0)
        outer.grid(row=row, column=0, sticky="nsew" if expand else "ew",
                   pady=pady)

        tk.Label(outer, text=f"  {titulo}",
                 bg=AZUL, fg="white",
                 font=("Segoe UI", 9, "bold"),
                 anchor="w", pady=5).pack(fill="x")

        inner = tk.Frame(outer, bg=PAINEL, padx=12, pady=8)
        inner.pack(fill="both", expand=True, padx=1, pady=(0, 1))
        inner.columnconfigure(0, weight=1)
        return inner

    def _secao_empresa(self, pai):
        card = self._card(pai, "  Empresa", row=0)

        tk.Label(card, text="Inscrição Municipal:",
                 bg=PAINEL, fg=TEXTO, font=F_LABEL).grid(
            row=0, column=0, sticky="w", pady=4)

        self.im_var = tk.StringVar()
        entry = tk.Entry(card, textvariable=self.im_var, font=F_LABEL,
                         bg=BG, fg=TEXTO, relief="flat",
                         highlightthickness=1, highlightbackground=BORDA,
                         highlightcolor=AZUL, insertbackground=TEXTO, width=32)
        entry.grid(row=0, column=1, sticky="w", padx=(10, 0), pady=4)

    def _secao_xml(self, pai):
        card = self._card(pai, "  Arquivos XML", row=1, expand=True)
        card.rowconfigure(0, weight=1)
        pai.rowconfigure(1, weight=2)

        # Lista de arquivos
        frame_lb = tk.Frame(card, bg=PAINEL)
        frame_lb.grid(row=0, column=0, sticky="nsew")
        card.rowconfigure(0, weight=1)

        self.listbox = tk.Listbox(
            frame_lb, selectmode=tk.EXTENDED, height=7,
            bg=BG, fg=TEXTO, font=F_MONO,
            selectbackground=AZUL, selectforeground="white",
            borderwidth=0, relief="flat",
            highlightthickness=1, highlightbackground=BORDA,
            activestyle="none"
        )
        sb = ttk.Scrollbar(frame_lb, orient="vertical", command=self.listbox.yview)
        self.listbox.config(yscrollcommand=sb.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb.pack(side="left", fill="y")

        # Botões da lista
        frame_btns = tk.Frame(card, bg=PAINEL, pady=6)
        frame_btns.grid(row=1, column=0, sticky="w")

        ttk.Button(frame_btns, text="＋  Adicionar XMLs",
                   style="Azul.TButton",
                   command=self._adicionar).pack(side="left", padx=(0, 6))
        ttk.Button(frame_btns, text="Remover selecionados",
                   style="Ghost.TButton",
                   command=self._remover).pack(side="left", padx=4)
        ttk.Button(frame_btns, text="Limpar tudo",
                   style="Ghost.TButton",
                   command=self._limpar).pack(side="left", padx=4)

        # Contador
        self.lbl_count = tk.Label(card, text="0 arquivo(s)",
                                  bg=PAINEL, fg=SUBTEXTO, font=F_SUBTIT)
        self.lbl_count.grid(row=1, column=0, sticky="e")

    def _secao_saida(self, pai):
        card = self._card(pai, "  Arquivo de saída", row=2, pady=(0, 10))
        card.columnconfigure(0, weight=1)
        pai.rowconfigure(2, weight=0)

        self.out_var = tk.StringVar(
            value=f"notas_servicos_{datetime.now().strftime('%Y%m%d')}.txt")

        entry = tk.Entry(card, textvariable=self.out_var, font=F_LABEL,
                         bg=BG, fg=TEXTO, relief="flat",
                         highlightthickness=1, highlightbackground=BORDA,
                         highlightcolor=AZUL, insertbackground=TEXTO)
        entry.grid(row=0, column=0, sticky="ew", pady=4)

        ttk.Button(card, text="  …  ", style="Ghost.TButton",
                   command=self._escolher_saida).grid(
            row=0, column=1, padx=(6, 0), pady=4)

    def _botao_processar(self, pai):
        self.btn_proc = ttk.Button(
            pai, text="▶   PROCESSAR",
            style="Azul.TButton",
            command=self._processar)
        self.btn_proc.grid(row=3, column=0, sticky="ew",
                           ipady=7, pady=(0, 10))

    def _secao_log(self, pai):
        card = self._card(pai, "  Log", row=4, pady=(0, 0), expand=True)
        pai.rowconfigure(4, weight=1)

        self.log = scrolledtext.ScrolledText(
            card, font=F_MONO,
            bg=LOG_BG, fg=LOG_FG,
            insertbackground="white",
            relief="flat", bd=0,
            state="disabled",
            padx=10, pady=8, height=8
        )
        self.log.grid(row=0, column=0, sticky="nsew")
        card.rowconfigure(0, weight=1)

        self.log.tag_config("ok",    foreground="#4EC9B0")
        self.log.tag_config("erro",  foreground="#F48771")
        self.log.tag_config("info",  foreground="#9CDCFE")
        self.log.tag_config("dim",   foreground="#6A9955")
        self.log.tag_config("aviso", foreground="#CE9178")

    def _barra_status(self):
        barra = tk.Frame(self, bg=AZUL_ESC, pady=3)
        barra.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="  Pronto")
        tk.Label(barra, textvariable=self.status_var,
                 bg=AZUL_ESC, fg="#90CAF9",
                 font=("Segoe UI", 8), anchor="w").pack(side="left")
        tk.Label(barra, text="NFSe Converter v2.0  ",
                 bg=AZUL_ESC, fg="#546E7A",
                 font=("Segoe UI", 8), anchor="e").pack(side="right")

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _adicionar(self):
        arquivos = filedialog.askopenfilenames(
            title="Selecionar arquivos XML",
            filetypes=[("XML NFSe", "*.xml"), ("Todos os arquivos", "*.*")])
        existentes = set(self.listbox.get(0, tk.END))
        for f in arquivos:
            if f not in existentes:
                self.listbox.insert(tk.END, f)
        self._atualizar_contador()

    def _remover(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
        self._atualizar_contador()

    def _limpar(self):
        self.listbox.delete(0, tk.END)
        self._atualizar_contador()

    def _atualizar_contador(self):
        n = self.listbox.size()
        self.lbl_count.config(text=f"{n} arquivo(s)")

    def _escolher_saida(self):
        f = filedialog.asksaveasfilename(
            title="Salvar arquivo TXT como",
            defaultextension=".txt",
            filetypes=[("Arquivo de texto", "*.txt"),
                       ("Todos os arquivos", "*.*")],
            initialfile=self.out_var.get())
        if f:
            self.out_var.set(f)

    def _log(self, msg, tag=""):
        self.log.config(state="normal")
        self.log.insert(tk.END, msg + "\n", tag)
        self.log.see(tk.END)
        self.log.config(state="disabled")

    def _processar(self):
        arquivos = list(self.listbox.get(0, tk.END))
        saida    = self.out_var.get().strip()
        im       = self.im_var.get().strip()

        if not arquivos:
            messagebox.showwarning("Atenção", "Adicione ao menos um arquivo XML.")
            return
        if not saida:
            messagebox.showwarning("Atenção", "Informe o arquivo de saída.")
            return

        self.log.config(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.config(state="disabled")

        self.btn_proc.config(state="disabled", text="  Processando...  ")
        self.status_var.set("  Processando...")

        def run():
            linhas, erros = [], []
            total = len(arquivos)

            self._log(f"Iniciando — {total} arquivo(s)", "dim")
            self._log("─" * 55, "dim")

            for i, xml_path in enumerate(arquivos, 1):
                nome = os.path.basename(xml_path)
                self.status_var.set(f"  [{i}/{total}]  {nome}")
                try:
                    dados = parse_nfse(xml_path)
                    dados["im"] = im
                    linhas.append(gerar_linha(dados))
                    self._log(f"✔  {nome}", "ok")
                    self._log(
                        f"   NFSe {dados['nDFSe']}  ·  "
                        f"{dados['nome'][:38]}  ·  R$ {dados['vS']}", "info")
                except Exception as e:
                    erros.append((nome, str(e)))
                    self._log(f"✘  {nome}", "erro")
                    self._log(f"   {e}", "aviso")

            with open(saida, "w", encoding="utf-8") as fout:
                fout.write("\n".join(linhas))
                if linhas:
                    fout.write("\n")

            self._log("─" * 55, "dim")
            self._log(f"Processadas : {len(linhas)}", "ok")
            if erros:
                self._log(f"Com erro    : {len(erros)}", "erro")
            self._log(f"Arquivo     : {saida}", "info")

            resumo = (f"{len(linhas)} processada(s)" +
                      (f"  |  {len(erros)} erro(s)" if erros else ""))
            self.status_var.set(f"  Concluído  —  {resumo}")
            self.btn_proc.config(state="normal", text="▶   PROCESSAR")

            if not erros:
                messagebox.showinfo(
                    "Concluído com sucesso",
                    f"{len(linhas)} nota(s) processada(s).\n\nArquivo gerado:\n{saida}")
            else:
                messagebox.showwarning(
                    "Concluído com erros",
                    f"{len(linhas)} processada(s)  |  {len(erros)} com erro\n\n"
                    f"Arquivo gerado:\n{saida}")

        threading.Thread(target=run, daemon=True).start()


if __name__ == "__main__":
    App().mainloop()
