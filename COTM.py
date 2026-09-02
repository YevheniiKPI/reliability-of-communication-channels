

import importlib.util
import math
import os
import queue
import random
import sys
import threading
import time
import traceback
from datetime import datetime
from itertools import combinations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "COTM"
MAX_N = 100                 # максимум вузлів у редакторі
SLOW_N = 5                  # починаючи з цього n попереджаємо про час роботи

CLR_BG = "#f4f6f8"
CLR_NODE = "#2d6cdf"
CLR_NODE_BAD = "#d63b3b"
CLR_EDGE = "#2d6cdf"
CLR_EDGE_OFF = "#c9ced4"
CLR_TEXT = "#1b2430"



#  Завантаження модуля логіки

def load_start_function(func_name="", path=None):
    """
    Повертає (функція start, шлях до файлу) або (None, повідомлення про помилку).
    """
    here = os.path.dirname(os.path.abspath(__file__))

    if path:
        candidates = [path]
    else:
        default = os.path.join(here, "logic_module.py")
        candidates = [default] if os.path.exists(default) else []
        for name in sorted(os.listdir(here)):
            full = os.path.join(here, name)
            if (name.endswith(".py")
                    and full not in candidates
                    and os.path.abspath(full) != os.path.abspath(__file__)):
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        if f"def {func_name}(" in f.read():
                            candidates.append(full)
                except OSError:
                    pass

    for full in candidates:
        try:
            spec = importlib.util.spec_from_file_location("logic_module", full)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, func_name):
                # *Функція за назвою
                if func_name == "brute_force":
                    return module.brute_force, full
                elif func_name == "optimal_algorithm":
                    return module.optimal_algorithm, full
        except Exception as err:                       # noqa: BLE001
            return None, f"Не вдалося завантажити «{full}»:\n{err}"

    return None, ("Файл логіки не знайдено. Покладіть модуль із функцією "
                  f"{func_name}() поруч із цим файлом (наприклад, logic.py).")



#  Допоміжні обчислення для відображення (не дублюють логіку)

def matrix_to_list(m):
    """Приводить numpy-масив або список списків до звичайного списку."""
    try:
        return m.tolist()
    except AttributeError:
        return [list(row) for row in m]


def analyse_result(n, adj, rel, prob, cost, budget):
    """Готує зведення по результату, який повернула логіка."""
    edges = [(i, j) for i, j in combinations(range(n), 2) if adj[i][j]]
    pairs = [(i, j, rel[i][j]) for i, j in combinations(range(n), 2)]
    nonzero = [(i, j, v) for i, j, v in pairs if v > 1e-12]

    if nonzero:
        worst = min(nonzero, key=lambda x: x[2])
        min_r, worst_pair = worst[2], (worst[0], worst[1])
        avg_r = sum(v for _, _, v in nonzero) / len(nonzero)
    else:
        min_r, worst_pair, avg_r = 0.0, None, 0.0

    return {
        "edges": edges,
        "matrix": rel,
        "min_r": min_r,
        "worst_pair": worst_pair,
        "avg_r": avg_r,
        "connected_pairs": len(nonzero),
        "total_pairs": len(pairs),
        "all_connected": len(nonzero) == len(pairs),
        "cost": sum(cost[a][b] for a, b in edges),
        "found": bool(edges),
    }


def build_report(n, prob, cost, budget, res, elapsed, logic_path):
    """Формує текстовий звіт для вкладки «Звіт» і збереження у файл."""
    L = []
    w = 10

    def matrix_block(m, title, digits):
        L.append(title)
        L.append("-" * (len(title) + 2))
        L.append(" " * 5 + "".join(f"{j + 1:>{w}}" for j in range(n)))
        for i in range(n):
            L.append(f"{i + 1:>3} |" +
                     "".join(f"{m[i][j]:>{w}.{digits}f}" for j in range(n)))
        L.append("")

    L.append("ЗВІТ ПРО СИНТЕЗ ТОПОЛОГІЇ МЕРЕЖІ")
    L.append(f"Дата й час: {datetime.now():%Y-%m-%d %H:%M:%S}")
    L.append(f"Модуль логіки: {logic_path}")
    L.append("")
    L.append("=" * 72)
    L.append("ВХІДНІ ДАНІ")
    L.append("=" * 72)
    L.append(f"Кількість комп'ютерів: {n}")
    L.append(f"Бюджет S: {budget:.2f}")
    L.append("")
    matrix_block(prob, "Імовірності справності каналів:", 4)
    matrix_block(cost, "Вартість прокладення каналів:", 2)

    L.append("=" * 72)
    L.append("РЕЗУЛЬТАТ")
    L.append("=" * 72)
    L.append(f"Час обчислення: {elapsed:.3f} с")
    L.append("")

    if not res["found"]:
        L.append("Жодної придатної топології в межах бюджету не знайдено.")
        return "\n".join(L)

    L.append(f"Прокладені канали ({len(res['edges'])} шт.):")
    for a, b in res["edges"]:
        L.append(f"  {a + 1:>2} --- {b + 1:<2}  p = {prob[a][b]:.3f}, "
                 f"вартість = {cost[a][b]:>8.2f}")
    L.append("")
    L.append(f"Сумарна вартість: {res['cost']:.2f} із бюджету {budget:.2f} "
             f"(залишок {budget - res['cost']:.2f})")
    L.append("")

    L.append("Списки суміжності:")
    adjacency = {v: [] for v in range(n)}
    for a, b in res["edges"]:
        adjacency[a].append(b)
        adjacency[b].append(a)
    for v in range(n):
        nbrs = ", ".join(str(u + 1) for u in sorted(adjacency[v])) or "—"
        L.append(f"  комп'ютер {v + 1:>2}: {nbrs}   (степінь {len(adjacency[v])})")
    L.append("")

    matrix_block(res["matrix"], "МАТРИЦЯ НАДІЙНОСТІ (зв'язності) R:", 6)

    L.append("Ймовірності зв'язності за парами:")
    for i, j in combinations(range(n), 2):
        mark = "  <-- мінімум" if res["worst_pair"] == (i, j) else ""
        L.append(f"  R({i + 1:>2},{j + 1:>2}) = {res['matrix'][i][j]:.6f}{mark}")
    L.append("")

    L.append("-" * 72)
    L.append("ПОКАЗНИКИ ЯКОСТІ")
    L.append("-" * 72)
    wp = res["worst_pair"]
    L.append(f"МІНІМАЛЬНЕ R: {res['min_r']:.6f}"
             + (f"  (пара {wp[0] + 1}, {wp[1] + 1})" if wp else ""))
    L.append(f"Середнє R: {res['avg_r']:.6f}")
    L.append(f"Зв'язаних пар: {res['connected_pairs']} із {res['total_pairs']}")
    return "\n".join(L)



#  Головне вікно

class TopologyApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x820")
        self.root.minsize(1040, 660)
        self.root.configure(bg=CLR_BG)

        #self.start_func, self.logic_path = load_start_function()
        # *Початкові дані
        self.start_func, self.logic_path = load_start_function("brute_force")
        self.mthds_var = tk.StringVar(value="auto")

        self.n_var = tk.IntVar(value=5)
        self.budget_var = tk.StringVar(value="150")
        self.status_var = tk.StringVar(value="")

        self.prob_vars = {}
        self.cost_vars = {}
        self.result = None
        self.result_data = None
        self.report_text = ""
        self.queue = queue.Queue()
        self.busy = False

        self._build_style()
        self._build_layout()
        self.rebuild_matrices()
        self.load_example(silent=True)

    """
        if self.start_func is None:
            self.set_status("Модуль логіки не завантажено")
            self.root.after(300, self._logic_missing_dialog)
        else:
            self.set_status(f"Логіку завантажено з: {self.logic_path}")
    """
    # ------------------------------------------------------------------
    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        for name in ("TLabel", "TFrame", "TLabelframe", "TRadiobutton",
                     "TCheckbutton"):
            style.configure(name, background=CLR_BG)
        style.configure("TLabelframe.Label", background=CLR_BG,
                        foreground=CLR_TEXT, font=("Segoe UI", 10, "bold"))
        style.configure("Run.TButton", font=("Segoe UI", 11, "bold"), padding=8)
        style.configure("Warn.TLabel", background=CLR_BG, foreground="#b45309")

    def _build_layout(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        paned = ttk.PanedWindow(main, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, width=520)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        self._build_left(left)
        self._build_right(right)

        bar = ttk.Frame(main)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Label(bar, textvariable=self.status_var,
                  foreground="#39424e").pack(side="left")

    # ---------------------------- ліва панель --------------------------
    def _build_left(self, parent):
        src = ttk.LabelFrame(parent, text="Вхідні дані", padding=8)
        src.pack(fill="x", pady=(0, 6))

        row = ttk.Frame(src)
        row.pack(fill="x")
        ttk.Label(row, text="Кількість комп'ютерів n:").pack(side="left")
        ttk.Spinbox(row, from_=2, to=MAX_N, width=5, textvariable=self.n_var,
                    command=self.rebuild_matrices).pack(side="left", padx=6)
        ttk.Button(row, text="Застосувати",
                   command=self.rebuild_matrices).pack(side="left")

        btns = ttk.Frame(src)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Згенерувати випадкові",
                   command=self.generate_random).pack(side="left", padx=(0, 4))
        ttk.Button(btns, text="Завантажити з файлу",
                   command=self.load_file).pack(side="left", padx=4)
        ttk.Button(btns, text="Зберегти дані",
                   command=self.save_input).pack(side="left", padx=4)
        ttk.Button(btns, text="Приклад",
                   command=self.load_example).pack(side="left", padx=4)

        # *Вибір методу
        mthds = ttk.Frame(src)
        mthds.pack(fill="x", pady=(8, 0))
        ttk.Label(mthds, text="Метод").pack(side="left", padx=(0, 4))
        ttk.Radiobutton(mthds, text="Авто", variable=self.mthds_var, 
                    value="auto").pack(side="left", padx=4)
        ttk.Radiobutton(mthds, text="Повний перебір", variable=self.mthds_var, 
                    value="brute").pack(side="left", padx=4)
        ttk.Radiobutton(mthds, text="Евристика", variable=self.mthds_var, 
                    value="optimal").pack(side="left", padx=4)
        

        editor = ttk.LabelFrame(parent, text="Параметри каналів зв'язку", padding=6)
        editor.pack(fill="both", expand=True, pady=6)

        ttk.Label(editor, wraplength=470, foreground="#5a6572",
                  text="Редагується верхній трикутник; нижній заповнюється "
                       "автоматично. Щоб канал вважався неможливим, обнуліть "
                       "І ймовірність, І вартість.").pack(fill="x", pady=(0, 6))

        self.matrix_nb = ttk.Notebook(editor)
        self.matrix_nb.pack(fill="both", expand=True)
        self.prob_tab = self._scrollable_tab(self.matrix_nb,
                                             "Імовірності справності p")
        self.cost_tab = self._scrollable_tab(self.matrix_nb,
                                             "Вартість прокладення c")

        par = ttk.LabelFrame(parent, text="Параметри задачі", padding=8)
        par.pack(fill="x")

        r1 = ttk.Frame(par)
        r1.pack(fill="x")
        ttk.Label(r1, text="Бюджет S:").pack(side="left")
        ttk.Entry(r1, textvariable=self.budget_var, width=12).pack(side="left", padx=6)
        self.budget_hint = ttk.Label(r1, text="", foreground="#5a6572")
        self.budget_hint.pack(side="left", padx=4)

        self.warn_lbl = ttk.Label(par, style="Warn.TLabel", wraplength=470, text="")
        self.warn_lbl.pack(fill="x", pady=(6, 0))

        run = ttk.Frame(parent)
        run.pack(fill="x", pady=(8, 0))
        self.run_btn = ttk.Button(run, text="РОЗРАХУВАТИ ТОПОЛОГІЮ",
                                  style="Run.TButton", command=self.compute)
        self.run_btn.pack(fill="x")
        self.progress = ttk.Progressbar(run, mode="indeterminate")
        self.progress.pack(fill="x", pady=(6, 0))

    def _scrollable_tab(self, notebook, title):
        outer = ttk.Frame(notebook)
        notebook.add(outer, text=title)
        canvas = tk.Canvas(outer, background=CLR_BG, highlightthickness=0, height=220)
        vbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        hbar = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)
        return inner

    # права панель
    def _build_right(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)
        self.result_nb = nb

        topo = ttk.Frame(nb)
        nb.add(topo, text="Топологія мережі")
        self.canvas = tk.Canvas(topo, background="white", highlightthickness=1,
                                highlightbackground="#d7dce2")
        self.canvas.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas.bind("<Configure>", lambda e: self.draw_topology())

        legend = ttk.Frame(topo)
        legend.pack(fill="x", padx=6, pady=(0, 6))
        self.legend_lbl = ttk.Label(
            legend, foreground="#5a6572", justify="left",
            text="Синя лінія — прокладений канал (товщина відповідає "
                 "надійності).    Сіра пунктирна — можливий, але не "
                 "прокладений.    Червоні вузли — найслабша пара.")
        self.legend_lbl.pack(side="left", fill="x", expand=True)
        legend.bind("<Configure>", lambda e: self.legend_lbl.configure(
            wraplength=max(200, e.width - 20)))

        mat = ttk.Frame(nb)
        nb.add(mat, text="Матриця надійності R")
        self.matrix_tree = ttk.Treeview(mat, show="headings", height=14)
        vs = ttk.Scrollbar(mat, orient="vertical", command=self.matrix_tree.yview)
        self.matrix_tree.configure(yscrollcommand=vs.set)
        self.matrix_tree.pack(side="left", fill="both", expand=True,
                              padx=(4, 0), pady=4)
        vs.pack(side="right", fill="y", pady=4)

        rep = ttk.Frame(nb)
        nb.add(rep, text="Звіт")
        self.report_box = tk.Text(rep, wrap="none", font=("Consolas", 9))
        rv = ttk.Scrollbar(rep, orient="vertical", command=self.report_box.yview)
        rh = ttk.Scrollbar(rep, orient="horizontal", command=self.report_box.xview)
        self.report_box.configure(yscrollcommand=rv.set, xscrollcommand=rh.set)
        self.report_box.grid(row=0, column=0, sticky="nsew")
        rv.grid(row=0, column=1, sticky="ns")
        rh.grid(row=1, column=0, sticky="ew")
        rep.rowconfigure(0, weight=1)
        rep.columnconfigure(0, weight=1)
        bar = ttk.Frame(rep)
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)
        ttk.Button(bar, text="Зберегти звіт у файл",
                   command=self.save_report).pack(side="left")

        summ = ttk.Frame(nb)
        nb.add(summ, text="Підсумок")
        self.summary_box = tk.Text(summ, wrap="word", font=("Segoe UI", 11),
                                   background=CLR_BG, relief="flat", padx=14, pady=12)
        self.summary_box.pack(fill="both", expand=True)
        self.summary_box.insert("1.0", "Задайте вхідні дані та натисніть "
                                       "«РОЗРАХУВАТИ ТОПОЛОГІЮ».")
        self.summary_box.configure(state="disabled")


    #  Матриці
    def rebuild_matrices(self):
        try:
            n = int(self.n_var.get())
        except (tk.TclError, ValueError):
            return
        n = max(2, min(MAX_N, n))
        self.n_var.set(n)

        old_p = {k: v.get() for k, v in self.prob_vars.items()}
        old_c = {k: v.get() for k, v in self.cost_vars.items()}
        for tab in (self.prob_tab, self.cost_tab):
            for w in tab.winfo_children():
                w.destroy()

        self.prob_vars, self.cost_vars = {}, {}
        self._build_grid(self.prob_tab, self.prob_vars, n, old_p, "0.0")
        self._build_grid(self.cost_tab, self.cost_vars, n, old_c, "0")
        self.update_hints()

    def _build_grid(self, parent, store, n, old, default):
        ttk.Label(parent, text="").grid(row=0, column=0, padx=2, pady=2)
        for j in range(n):
            ttk.Label(parent, text=str(j + 1), width=7, anchor="center",
                      font=("Segoe UI", 9, "bold")).grid(row=0, column=j + 1, padx=1)

        for i in range(n):
            ttk.Label(parent, text=str(i + 1), width=3, anchor="e",
                      font=("Segoe UI", 9, "bold")).grid(row=i + 1, column=0, padx=2)
            for j in range(n):
                if i == j:
                    ttk.Label(parent, text="—", width=7, anchor="center").grid(
                        row=i + 1, column=j + 1, padx=1, pady=1)
                    continue
                key = (min(i, j), max(i, j))
                if key not in store:
                    store[key] = tk.StringVar(value=old.get(key, default))
                    store[key].trace_add("write", lambda *a: self.update_hints())
                ent = ttk.Entry(parent, textvariable=store[key], width=7,
                                justify="center")
                if i > j:
                    ent.configure(state="readonly")
                ent.grid(row=i + 1, column=j + 1, padx=1, pady=1)

    def read_matrices(self):
        """Зчитує поля; кидає ValueError з поясненням, якщо дані некоректні."""
        n = int(self.n_var.get())
        prob = [[0.0] * n for _ in range(n)]
        cost = [[0.0] * n for _ in range(n)]

        for store, target, name, hi in ((self.prob_vars, prob, "Імовірність", 1.0),
                                        (self.cost_vars, cost, "Вартість", None)):
            for (i, j), var in store.items():
                if i >= n or j >= n:
                    continue
                raw = var.get().strip().replace(",", ".") or "0"
                try:
                    val = float(raw)
                except ValueError:
                    raise ValueError(f"{name} у комірці ({i + 1},{j + 1}) — "
                                     f"не число: «{var.get()}»")
                if val < 0 or (hi is not None and val > hi):
                    limit = "[0, 1]" if hi else "невід'ємною"
                    raise ValueError(f"{name} у комірці ({i + 1},{j + 1}) "
                                     f"має бути {limit}.")
                target[i][j] = target[j][i] = val

        return n, prob, cost

    def fill_matrices(self, n, prob, cost):
        self.n_var.set(n)
        self.rebuild_matrices()
        for (i, j) in list(self.prob_vars):
            self.prob_vars[(i, j)].set(f"{prob[i][j]:g}")
            self.cost_vars[(i, j)].set(f"{cost[i][j]:g}")
        self.update_hints()

    def update_hints(self):
        """Оновлює підказку біля бюджету та попередження про час роботи."""
        try:
            n, prob, cost = self.read_matrices()
        except (ValueError, tk.TclError):
            self.budget_hint.configure(text="")
            return

        # канали, які логіка вважатиме наявними
        edges = [(i, j) for i, j in combinations(range(n), 2)
                 if prob[i][j] != 0.0 or cost[i][j] != 0.0]
        total = sum(cost[a][b] for a, b in edges)
        self.budget_hint.configure(text=f"можливих каналів: {len(edges)}, "
                                        f"усі разом коштують {total:g}")

        warns = []
        if n > SLOW_N and self.mthds_var.get() == "brute_force":
            warns.append(f"Увага: при n = {n} перебір 2^{len(edges)} варіантів "
                         f"може тривати десятки хвилин.")
        zero_p = [(i, j) for i, j in edges if prob[i][j] == 0.0]
        if zero_p:
            pairs = ", ".join(f"({a + 1},{b + 1})" for a, b in zero_p[:5])
            warns.append(f"Канали з нульовою ймовірністю, але ненульовою "
                         f"вартістю: {pairs} — логіка вважатиме їх наявними "
                         f"з надійністю 0.")
        self.warn_lbl.configure(text="  ".join(warns))

    #  Кнопки роботи з даними
    def load_example(self, silent=False):
        prob = [[0.00, 0.90, 0.75, 0.60, 0.85],
                [0.90, 0.00, 0.80, 0.70, 0.65],
                [0.75, 0.80, 0.00, 0.95, 0.55],
                [0.60, 0.70, 0.95, 0.00, 0.90],
                [0.85, 0.65, 0.55, 0.90, 0.00]]
        cost = [[0, 40, 25, 30, 55],
                [40, 0, 35, 20, 45],
                [25, 35, 0, 50, 30],
                [30, 20, 50, 0, 35],
                [55, 45, 30, 35, 0]]
        self.fill_matrices(5, prob, cost)
        self.budget_var.set("150")
        if not silent:
            self.set_status("Завантажено демонстраційний приклад")

    def generate_random(self):
        try:
            n = int(self.n_var.get())
        except (tk.TclError, ValueError):
            return
        prob = [[0.0] * n for _ in range(n)]
        cost = [[0.0] * n for _ in range(n)]
        for i, j in combinations(range(n), 2):
            prob[i][j] = prob[j][i] = round(random.uniform(0.5, 0.95), 2)
            cost[i][j] = cost[j][i] = round(random.uniform(10, 100), 1)
        self.fill_matrices(n, prob, cost)
        total = sum(cost[i][j] for i, j in combinations(range(n), 2))
        self.budget_var.set(f"{total * 0.45:.1f}")
        self.set_status(f"Згенеровано випадкові дані для {n} комп'ютерів")

    def load_file(self):
        """
        Формат: спочатку n, далі n*n чисел матриці ймовірностей,
        далі n*n чисел матриці вартостей, далі (необов'язково) бюджет.
        Рядки, що починаються з '#', ігноруються.
        """
        path = filedialog.askopenfilename(
            title="Виберіть файл з вхідними даними",
            filetypes=[("Текстові файли", "*.txt"), ("Усі файли", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = "".join(ln.split("#")[0] + " " for ln in f)
            nums = [float(x) for x in text.split()]
            n = int(nums[0])
            need = 1 + 2 * n * n
            if n > MAX_N:
                raise ValueError(f"Редактор підтримує щонайбільше {MAX_N} вузлів.")
            if len(nums) < need:
                raise ValueError(f"Замало чисел: потрібно {need}, є {len(nums)}.")
            prob = [nums[1 + i * n: 1 + (i + 1) * n] for i in range(n)]
            off = 1 + n * n
            cost = [nums[off + i * n: off + (i + 1) * n] for i in range(n)]
            budget = nums[need] if len(nums) > need else None
        except (OSError, ValueError, IndexError) as err:
            messagebox.showerror("Помилка читання файлу", str(err))
            return

        self.fill_matrices(n, prob, cost)
        if budget is not None:
            self.budget_var.set(f"{budget:g}")
        self.set_status(f"Завантажено з файлу: {path}")

    def save_input(self):
        try:
            n, prob, cost = self.read_matrices()
        except ValueError as err:
            messagebox.showerror("Помилка у вхідних даних", str(err))
            return
        path = filedialog.asksaveasfilename(
            title="Зберегти вхідні дані", defaultextension=".txt",
            filetypes=[("Текстові файли", "*.txt")])
        if not path:
            return
        lines = ["# кількість комп'ютерів", str(n), "# матриця ймовірностей"]
        lines += [" ".join(f"{prob[i][j]:.3f}" for j in range(n)) for i in range(n)]
        lines.append("# матриця вартостей")
        lines += [" ".join(f"{cost[i][j]:.2f}" for j in range(n)) for i in range(n)]
        lines += ["# бюджет", self.budget_var.get().strip() or "0"]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        self.set_status(f"Вхідні дані збережено: {path}")

    def save_report(self):
        if not self.report_text:
            messagebox.showinfo("Немає звіту", "Спочатку виконайте розрахунок.")
            return
        path = filedialog.asksaveasfilename(
            title="Зберегти звіт", defaultextension=".txt",
            initialfile="topology_report.txt",
            filetypes=[("Текстові файли", "*.txt")])
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.report_text)
        self.set_status(f"Звіт збережено: {path}")

    def _logic_missing_dialog(self):
        """Пропонує вказати файл логіки вручну, якщо його не знайдено."""
        if messagebox.askyesno(
                "Модуль логіки не знайдено",
                f"{self.logic_path}\n\nВказати файл із функцією start() вручну?"):
            path = filedialog.askopenfilename(
                title="Виберіть файл модуля логіки",
                filetypes=[("Файли Python", "*.py")])
            if path:
                func, info = load_start_function(path)
                if func is None:
                    messagebox.showerror("Не вдалося завантажити", info)
                else:
                    self.start_func, self.logic_path = func, info
                    self.set_status(f"Логіку завантажено з: {info}")

    # *Функція зміни методу
    def change_method(self):
        n = int(self.n_var.get())
        match self.mthds_var.get():
            case "auto":
                if n <= SLOW_N:
                    self.start_func, self.logic_path = load_start_function("brute_force")
                elif n > SLOW_N:
                    self.start_func, self.logic_path = load_start_function("optimal_algorithm")
            case "brute":
                if n <= SLOW_N:
                    self.start_func, self.logic_path = load_start_function("brute_force")
                else:
                    self.start_func, self.logic_path = load_start_function("brute_force")
                    if n > SLOW_N and not messagebox.askyesno(
                            "Це може бути довго",
                            f"Кількість комп'ютерів {n}, можливих каналів {len(str(n*(n - 1) / 2))}, "
                            f"тобто до 2^{len(str(n*(n - 1) / 2))} варіантів топології.\n\n"
                            f"Розрахунок може тривати десятки хвилин, і перервати його "
                            f"кнопкою не вийде.\n\nПродовжити?"):
                        return
            case "optimal":
                self.start_func, self.logic_path = load_start_function("optimal_algorithm")


    #  Розрахунок у фоновому потоці
    def compute(self):
        if self.busy:
            return
        if self.start_func is None:
            self._logic_missing_dialog()
            return

        try:
            n, prob, cost = self.read_matrices()
            budget = float(self.budget_var.get().strip().replace(",", "."))
            if budget < 0:
                raise ValueError("Бюджет не може бути від'ємним.")
        except ValueError as err:
            messagebox.showerror("Помилка у вхідних даних", str(err))
            return

        edges = [(i, j) for i, j in combinations(range(n), 2)
                 if prob[i][j] != 0.0 or cost[i][j] != 0.0]
        if not edges:
            messagebox.showerror("Немає каналів",
                                 "Не задано жодного можливого каналу.")
            return

        self.busy = True
        self.run_btn.configure(state="disabled")
        self.progress.start(12)
        self.set_status("Обчислення... вікно лишається активним")

        threading.Thread(target=self._worker,
                         args=(n, prob, cost, budget), daemon=True).start()
        self.root.after(120, self._poll_queue)

    def _worker(self, n, prob, cost, budget):
        """Виконується в окремому потоці; інтерфейс тут не чіпається."""
        try:
            t0 = time.time()
            self.change_method()
            adj, rel = self.start_func(n, budget, prob, cost)   # виклик логіки
            elapsed = time.time() - t0

            adj = matrix_to_list(adj)
            rel = matrix_to_list(rel)
            res = analyse_result(n, adj, rel, prob, cost, budget)
            text = build_report(n, prob, cost, budget, res, elapsed,
                                self.logic_path)
            self.queue.put(("ok", res, text, elapsed, (n, prob, cost, budget)))
        except Exception:                                    # noqa: BLE001
            self.queue.put(("err", traceback.format_exc()))

    def _poll_queue(self):
        try:
            item = self.queue.get_nowait()
        except queue.Empty:
            self.root.after(120, self._poll_queue)
            return

        self.busy = False
        self.progress.stop()
        self.run_btn.configure(state="normal")

        if item[0] == "err":
            messagebox.showerror("Помилка у модулі логіки", item[1])
            self.set_status("Розрахунок завершився помилкою")
            return

        # *Логіка нестачі бюджету (зробити пізніше)
        """if item[0] == "budget_err":
            self.set_status("Придатної топології в межах бюджету не знайдено")
            messagebox.showinfo(
                "Нічого не знайдено",
                "Логіка не знайшла жодної топології, яка вміщується в бюджет "
                "і з'єднує всі комп'ютери.\nСпробуйте збільшити бюджет.")
            return"""

        _, res, text, elapsed, data = item
        self.result, self.report_text, self.result_data = res, text, data

        self.report_box.delete("1.0", "end")
        self.report_box.insert("1.0", text)
        self.fill_matrix_table()
        self.fill_summary(elapsed)
        self.draw_topology()
        self.result_nb.select(0)

        if not res["found"]:
            self.set_status("Придатної топології в межах бюджету не знайдено")
            messagebox.showinfo(
                "Нічого не знайдено",
                "Логіка не знайшла жодної топології, яка вміщується в бюджет "
                "і з'єднує всі комп'ютери.\nСпробуйте збільшити бюджет.")
        else:
            self.set_status(f"Готово за {elapsed:.3f} с — мінімальне "
                            f"R = {res['min_r']:.6f}, вартість {res['cost']:.2f}")


    #  Відображення результату
    def fill_matrix_table(self):
        tree = self.matrix_tree
        tree.delete(*tree.get_children())
        if not self.result or not self.result["found"]:
            tree["columns"] = ()
            return

        n = self.result_data[0]
        cols = ["вузол"] + [str(j + 1) for j in range(n)]
        tree["columns"] = cols
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=90 if c == "вузол" else 80, anchor="center")
        for i in range(n):
            tree.insert("", "end",
                        values=[str(i + 1)] +
                               [f"{self.result['matrix'][i][j]:.6f}"
                                for j in range(n)])

    def fill_summary(self, elapsed):
        box = self.summary_box
        box.configure(state="normal")
        box.delete("1.0", "end")

        if not self.result or not self.result["found"]:
            box.insert("1.0", "Придатної топології в межах бюджету не знайдено.\n\n"
                              "Логіка перебирає лише ті варіанти, що з'єднують "
                              "усі комп'ютери й уміщуються в бюджет. "
                              "Спробуйте збільшити бюджет.")
            box.configure(state="disabled")
            return

        res = self.result
        n, prob, cost, budget = self.result_data
        wp = res["worst_pair"]

        lines = ["РЕЗУЛЬТАТ ОПТИМІЗАЦІЇ", "",
                 f"Мінімальне R:  {res['min_r']:.6f}"
                 + (f"   (найслабша пара: {wp[0] + 1} — {wp[1] + 1})" if wp else ""),
                 f"Середнє R:  {res['avg_r']:.6f}",
                 f"Зв'язаних пар:  {res['connected_pairs']} із {res['total_pairs']}",
                 "",
                 f"Прокладено каналів:  {len(res['edges'])}",
                 f"Витрачено:  {res['cost']:.2f} із бюджету {budget:.2f} "
                 f"(залишок {budget - res['cost']:.2f})",
                 f"Час обчислення:  {elapsed:.3f} с",
                 "", "Перелік прокладених каналів:"]
        for a, b in res["edges"]:
            lines.append(f"    {a + 1} — {b + 1}    p = {prob[a][b]:.3f}, "
                         f"вартість = {cost[a][b]:.2f}")

        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")

    def draw_topology(self):
        cv = self.canvas
        cv.delete("all")
        w = max(cv.winfo_width(), 200)
        h = max(cv.winfo_height(), 200)

        if not self.result or not self.result["found"]:
            cv.create_text(w // 2, h // 2, fill="#9aa4b0", font=("Segoe UI", 12),
                           text="Тут з'явиться схема мережі після розрахунку")
            return

        n, prob, cost, budget = self.result_data
        res = self.result
        chosen = set(res["edges"])
        possible = [(i, j) for i, j in combinations(range(n), 2)
                    if prob[i][j] != 0.0 or cost[i][j] != 0.0]

        cx, cy = w / 2, h / 2 + 10
        radius = max(60, min(w, h) / 2 - 70)
        node_r = 20
        pos = {}
        for v in range(n):
            angle = -math.pi / 2 + 2 * math.pi * v / n
            pos[v] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))

        for a, b in possible:                        # не прокладені — пунктиром
            if (a, b) in chosen:
                continue
            cv.create_line(*pos[a], *pos[b], fill=CLR_EDGE_OFF, width=1, dash=(4, 4))

        for a, b in sorted(chosen):                  # прокладені — суцільні
            x1, y1 = pos[a]
            x2, y2 = pos[b]
            cv.create_line(x1, y1, x2, y2, fill=CLR_EDGE,
                           width=1 + 4 * prob[a][b], capstyle="round")

        worst = set(res["worst_pair"]) if res["worst_pair"] else set()
        for v in range(n):
            x, y = pos[v]
            cv.create_oval(x - node_r, y - node_r, x + node_r, y + node_r,
                           fill=CLR_NODE_BAD if v in worst else CLR_NODE,
                           outline="white", width=2)
            cv.create_text(x, y, text=str(v + 1), fill="white",
                           font=("Segoe UI", 11, "bold"))

        cv.create_text(w / 2, 20, font=("Segoe UI", 11, "bold"), fill=CLR_TEXT,
                       text=f"min R = {res['min_r']:.6f}    |    "
                            f"каналів: {len(chosen)}    |    "
                            f"вартість: {res['cost']:.2f} / {budget:.2f}")

    def set_status(self, text):
        self.status_var.set(text)


def main():
    root = tk.Tk()
    TopologyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()