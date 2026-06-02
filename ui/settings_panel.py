import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
settings_panel.py  –  Design settings + AI provider/model selector.
Fixed: model Combobox now uses real fetched models.
New: provider switcher (OpenAI / Anthropic / Gemini), API key fields,
     Netlify token field.
"""

import tkinter as tk
from tkinter import ttk
from core.ai_engine import get_models_for_provider, DEFAULT_MODEL, DEFAULT_PROVIDER

# بناء AI_PROVIDERS ديناميكياً من ai_engine
AI_PROVIDERS = {
    "openai":    {"models": get_models_for_provider("openai")},
    "anthropic": {"models": get_models_for_provider("anthropic")},
    "gemini":    {"models": get_models_for_provider("gemini")},
}


def create_settings_panel(parent):

    # ── scrollable container ──
    canvas  = tk.Canvas(parent, bg="#0f0f1a", highlightthickness=0)
    scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    container = tk.Frame(canvas, bg="#0f0f1a")
    win = canvas.create_window((0, 0), window=container, anchor="nw")

    def resize(event):
        canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.itemconfig(win, width=event.width)
    container.bind("<Configure>", resize)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

    # ── section builder ──
    def section(title):
        f = tk.Frame(container, bg="#13131f", bd=0)
        f.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(f, text=title, fg="#6b6b8a", bg="#13131f",
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 4))
        inner = tk.Frame(f, bg="#13131f")
        inner.pack(fill="x", padx=8, pady=(0, 8))
        return inner

    def combo_row(parent, label, variable, values, row, col=0, colspan=1):
        tk.Label(parent, text=label, fg="#8888aa", bg="#13131f",
                 font=("Segoe UI", 9)).grid(row=row, column=col*2,
                                            sticky="w", padx=(0, 4), pady=3)
        cb = ttk.Combobox(parent, textvariable=variable, values=values,
                          state="readonly", width=16,
                          font=("Segoe UI", 9))
        cb.grid(row=row, column=col*2+1, padx=(0, 12), pady=3, sticky="we",
                columnspan=colspan)
        return cb

    def entry_row(parent, label, variable, row, show=None):
        tk.Label(parent, text=label, fg="#8888aa", bg="#13131f",
                 font=("Segoe UI", 9)).grid(row=row, column=0, sticky="w", pady=3)
        kw = {"show": show} if show else {}
        e = tk.Entry(parent, textvariable=variable,
                     bg="#1a1a2e", fg="#c8c8e0", insertbackground="white",
                     relief="flat", font=("Consolas", 9), width=28, **kw)
        e.grid(row=row, column=1, columnspan=3, sticky="we", padx=(4, 0), pady=3, ipady=4)
        return e

    # ─ ttk styles ─
    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TCombobox",
                    fieldbackground="#1a1a2e", background="#1a1a2e",
                    foreground="#c8c8e0", selectbackground="#1a1a2e",
                    selectforeground="#c8c8e0", arrowcolor="#6b6b8a")
    style.map("TCombobox",
              fieldbackground=[("readonly", "#1a1a2e")],
              selectbackground=[("readonly", "#1a1a2e")],
              selectforeground=[("readonly", "#c8c8e0")])

    # ══════════════════════════════════════════
    #  Section 1 – Design Options
    # ══════════════════════════════════════════
    des = section("🎨  Design Options")
    des.columnconfigure(1, weight=1)
    des.columnconfigure(3, weight=1)

    theme_var  = tk.StringVar(value="Dark")
    color_var  = tk.StringVar(value="Gold")
    layout_var = tk.StringVar(value="Modern")
    lang_var   = tk.StringVar(value="English")
    type_var   = tk.StringVar(value="Business")

    combo_row(des, "Theme",   theme_var,  ["Dark","Light","Luxury","Minimal","Glassmorphism"],  0, 0)
    combo_row(des, "Color",   color_var,  ["Gold","Blue","Black","Green","Red","Purple","Teal"], 0, 1)
    combo_row(des, "Layout",  layout_var, ["Modern","Classic","Minimal","Luxury","Brutalist"],   1, 0)
    combo_row(des, "Language",lang_var,   ["English","Arabic","Swedish","French","Spanish"],      1, 1)
    combo_row(des, "Type",    type_var,
              ["Business","Online Store","Portfolio","Blog","Landing Page","SaaS","Restaurant"],  2, 0, colspan=3)

    # ══════════════════════════════════════════
    #  Section 2 – AI Provider
    # ══════════════════════════════════════════
    ai_sec = section("🤖  AI Provider")
    ai_sec.columnconfigure(1, weight=1)
    ai_sec.columnconfigure(3, weight=1)

    provider_var = tk.StringVar(value=DEFAULT_PROVIDER)
    model_var    = tk.StringVar(value=DEFAULT_MODEL)

    provider_cb = combo_row(ai_sec, "Provider", provider_var,
                            list(AI_PROVIDERS.keys()), 0, 0)
    model_cb    = combo_row(ai_sec, "Model",    model_var,
                            AI_PROVIDERS[DEFAULT_PROVIDER]["models"], 0, 1)

    info_lbl = tk.Label(ai_sec, text="", fg="#5a8a7a", bg="#13131f",
                        font=("Segoe UI", 8), wraplength=280, justify="left")
    info_lbl.grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 0))

    MODEL_INFO = {
        # GPT-5 family (latest)
        "gpt-5-mini":           "Fast & cheap GPT-5 — ideal for most tasks ⭐ Default",
        "gpt-5-mini-2025-08-07":"GPT-5 mini (Aug 2025 snapshot)",
        "gpt-5":                "Previous GPT-5 frontier model",
        "gpt-5-2025-08-07":     "GPT-5 (Aug 2025 snapshot)",
        "gpt-5.1":              "GPT-5.1 flagship — coding & agentic tasks",
        "gpt-5.2":              "GPT-5.2 — complex professional work",
        "gpt-5.4":              "GPT-5.4 — latest frontier model (most powerful)",
        # GPT-4o family
        "gpt-4o":               "Best quality — great for complex sites",
        "gpt-5-mini":           "Fast & cheap GPT-5 — ideal for most tasks ⭐ Default",
        "gpt-5-mini-2025-08-07":"GPT-5 mini (Aug 2025 snapshot)",
        "gpt-4o-mini":          "Fast & cheap — ideal for most tasks",
        "gpt-4o-2024-11-20":    "GPT-4o (Nov 2024 snapshot)",
        "gpt-4o-2024-08-06":    "GPT-4o (Aug 2024 snapshot)",
        "gpt-4o-2024-05-13":    "GPT-4o (May 2024 snapshot)",
        # GPT-4.1 family
        "gpt-4.1":              "Latest GPT-4.1 — high quality & fast",
        "gpt-4.1-mini":         "GPT-4.1 mini — balanced speed and quality",
        "gpt-4.1-nano":         "GPT-4.1 nano — fastest, most affordable",
        # GPT-4 Turbo
        "gpt-4-turbo":          "High quality with large context window",
        "gpt-4-turbo-preview":  "GPT-4 Turbo preview snapshot",
        "gpt-4-turbo-2024-04-09": "GPT-4 Turbo (Apr 2024 snapshot)",
        # GPT-4 base
        "gpt-4":                "Original GPT-4 — stable and reliable",
        "gpt-4-32k":            "GPT-4 with 32k context window",
        # GPT-3.5
        "gpt-3.5-turbo":        "Fast and very cheap — simple tasks",
        "gpt-3.5-turbo-16k":    "GPT-3.5 with 16k context window",
        # o-series reasoning
        "o1":                   "Advanced reasoning — best for logic tasks",
        "o1-mini":              "Reasoning model — fast and affordable",
        "o1-preview":           "o1 preview snapshot",
        "o3":                   "Most powerful reasoning model",
        "o3-mini":              "Compact reasoning model — great value",
        "o4-mini":              "Latest compact reasoning model",
        # Anthropic
        "claude-opus-4-5":      "Anthropic's most powerful model",
        "claude-sonnet-4-5":    "Balanced Anthropic model",
        "claude-haiku-4-5":     "Fastest Anthropic model",
        # Gemini
        "gemini-2.0-flash":     "Google's latest fast model",
        "gemini-1.5-pro":       "Google's most capable model",
        "gemini-1.5-flash":     "Google's fast model",
    }

    def on_provider_change(*_):
        prov   = provider_var.get()
        models = AI_PROVIDERS.get(prov, {}).get("models", [])
        model_cb.config(values=models)
        # تعيين النموذج الافتراضي لكل مزود
        defaults = {
            "openai":    "gpt-5-mini",
            "anthropic": "claude-sonnet-4-5",
            "gemini":    "gemini-2.0-flash",
        }
        model_var.set(defaults.get(prov, models[0] if models else ""))
        on_model_change()

    def on_model_change(*_):
        info_lbl.config(text=MODEL_INFO.get(model_var.get(), ""))

    provider_var.trace_add("write", on_provider_change)
    model_var.trace_add("write",    on_model_change)
    on_model_change()

    # Load models button
    def fetch_models():
        from core.ai_engine import get_models_for_provider
        prov   = provider_var.get()
        models = get_models_for_provider(prov)
        model_cb.config(values=models)
        if models:
            model_var.set(models[0])
        info_lbl.config(text=f"✓ Loaded {len(models)} models")

    tk.Button(ai_sec, text="↻ Refresh Models",
              bg="#1a1a2e", fg="#6b6b8a",
              activebackground="#007acc", activeforeground="white",
              bd=0, padx=8, pady=2, font=("Segoe UI", 8),
              cursor="hand2", relief="flat",
              command=fetch_models
    ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

    # ══════════════════════════════════════════
    #  Section 3 – API Keys
    # ══════════════════════════════════════════
    keys = section("🔑  API Keys")
    keys.columnconfigure(1, weight=1)
    keys.columnconfigure(3, weight=1)

    openai_key_var    = tk.StringVar()
    anthropic_key_var = tk.StringVar()
    gemini_key_var    = tk.StringVar()
    netlify_key_var   = tk.StringVar()
    github_key_var    = tk.StringVar()

    entry_row(keys, "OpenAI",    openai_key_var,    0, show="*")
    entry_row(keys, "Anthropic", anthropic_key_var, 1, show="*")
    entry_row(keys, "Gemini",    gemini_key_var,    2, show="*")
    entry_row(keys, "Netlify",   netlify_key_var,   3, show="*")
    entry_row(keys, "GitHub",    github_key_var,    4, show="*")

    tk.Label(keys, text="Keys are saved in session only (not stored to disk)",
             fg="#3a3a5a", bg="#13131f",
             font=("Segoe UI", 8)).grid(row=5, column=0, columnspan=4,
                                         sticky="w", pady=(4, 0))

    return (
        theme_var,
        color_var,
        layout_var,
        lang_var,
        type_var,
        model_var,
        provider_var,
        netlify_key_var,
        openai_key_var,
        anthropic_key_var,
        gemini_key_var,
    )