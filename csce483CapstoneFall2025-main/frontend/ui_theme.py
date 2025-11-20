import tkinter as tk
from tkinter import ttk
from typing import Optional


# Shared color palette inspired by the optimization summary window
COLORS = {
    "bg_primary": "#ffffff",
    "bg_secondary": "#f8fafc",
    "bg_tertiary": "#f1f5f9",
    "sidebar_bg": "#f1f5f9",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "success": "#10b981",
    "warning": "#f59e0b",
    "error": "#ef4444",
    "text_primary": "#1e293b",
    "text_secondary": "#64748b",
    "border": "#e2e8f0",
    "log_bg": "#ffffff",
}

FONTS = {
    "title": ("Segoe UI", 22, "bold"),
    "heading": ("Segoe UI", 16, "bold"),
    "subheading": ("Segoe UI", 13, "bold"),
    "body": ("Segoe UI", 11),
    "button": ("Segoe UI", 11, "bold"),
    "small": ("Segoe UI", 10),
}


def apply_modern_theme(root: tk.Misc) -> ttk.Style:
    """
    Configure a light, modern theme on the provided root widget.
    Returns the ttk.Style instance so callers can further tweak if needed.
    """
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        # Fallback silently if clam is unavailable
        pass

    # Set base colors on the root
    root.configure(bg=COLORS["bg_primary"])
    try:
        root.option_add("*Font", FONTS["body"])
        root.option_add("*Label.Font", FONTS["body"])
        root.option_add("*Entry.Font", FONTS["body"])
        root.option_add("*Button.Font", FONTS["button"])
        root.option_add("*TCombobox*Listbox.Font", FONTS["body"])
        root.option_add("*Foreground", COLORS["text_primary"])
    except tk.TclError:
        # option_add can fail for transient toplevels; ignore quietly.
        pass

    # Frames and containers
    style.configure("TFrame", background=COLORS["bg_primary"], borderwidth=0)
    style.configure("Card.TFrame", background=COLORS["bg_secondary"], borderwidth=0)
    style.configure("Sidebar.TFrame", background=COLORS["sidebar_bg"], borderwidth=0)
    style.configure("TLabelframe", background=COLORS["bg_secondary"], borderwidth=0)
    style.configure(
        "TLabelframe.Label",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_secondary"],
        font=FONTS["subheading"],
    )

    # Text styles
    style.configure(
        "TLabel",
        background=COLORS["bg_primary"],
        foreground=COLORS["text_primary"],
        font=FONTS["body"],
    )
    style.configure(
        "Secondary.TLabel",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_secondary"],
        font=FONTS["body"],
    )
    style.configure(
        "Heading.TLabel",
        background=COLORS["bg_primary"],
        foreground=COLORS["text_primary"],
        font=FONTS["heading"],
    )
    style.configure(
        "CardHeading.TLabel",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_primary"],
        font=FONTS["heading"],
    )
    style.configure(
        "Hint.TLabel",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_secondary"],
        font=FONTS["small"],
    )

    # Buttons
    style.configure(
        "Accent.TButton",
        background=COLORS["accent"],
        foreground="#ffffff",
        borderwidth=0,
        focusthickness=0,
        padding=(18, 10),
        font=FONTS["button"],
    )
    style.map(
        "Accent.TButton",
        background=[("active", COLORS["accent_hover"]), ("disabled", COLORS["border"])],
        foreground=[("disabled", COLORS["text_secondary"])],
    )

    style.configure(
        "Secondary.TButton",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_primary"],
        borderwidth=1,
        focusthickness=0,
        padding=(18, 10),
        font=FONTS["button"],
    )
    style.map(
        "Secondary.TButton",
        background=[
            ("active", COLORS["bg_tertiary"]),
            ("disabled", COLORS["bg_tertiary"]),
        ],
        foreground=[("disabled", COLORS["text_secondary"])],
    )

    # Inputs
    style.configure(
        "TEntry",
        fieldbackground="#ffffff",
        background="#ffffff",
        foreground=COLORS["text_primary"],
        bordercolor=COLORS["border"],
        lightcolor=COLORS["border"],
        darkcolor=COLORS["border"],
        padding=6,
    )
    style.map(
        "TEntry",
        fieldbackground=[("disabled", COLORS["bg_tertiary"])],
        foreground=[("disabled", COLORS["text_secondary"])],
    )

    style.configure(
        "TCombobox",
        fieldbackground="#ffffff",
        background="#ffffff",
        foreground=COLORS["text_primary"],
        bordercolor=COLORS["border"],
        padding=6,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", "#ffffff")],
        selectbackground=[("readonly", COLORS["accent"])],
        selectforeground=[("readonly", "#ffffff")],
    )

    # Treeview styling
    style.configure(
        "Treeview",
        background=COLORS["bg_secondary"],
        fieldbackground=COLORS["bg_secondary"],
        foreground=COLORS["text_primary"],
        bordercolor=COLORS["border"],
        rowheight=26,
    )
    style.map(
        "Treeview",
        background=[("selected", COLORS["accent"])],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Treeview.Heading",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_secondary"],
        bordercolor=COLORS["border"],
        font=FONTS["subheading"],
    )

    # Scrollbar tweaks
    style.configure(
        "Vertical.TScrollbar",
        background=COLORS["bg_secondary"],
        troughcolor=COLORS["bg_tertiary"],
        bordercolor=COLORS["bg_secondary"],
    )
    style.configure(
        "Horizontal.TScrollbar",
        background=COLORS["bg_secondary"],
        troughcolor=COLORS["bg_tertiary"],
        bordercolor=COLORS["bg_secondary"],
    )

    # Toggle controls
    style.configure(
        "TCheckbutton",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_primary"],
        focuscolor=COLORS["bg_secondary"],
        bordercolor=COLORS["border"],
        indicatordiameter=12,
        indicatorbackground="#ffffff",
        indicatorcolor=COLORS["accent"],
    )
    style.map(
        "TCheckbutton",
        background=[("active", COLORS["bg_tertiary"]), ("disabled", COLORS["bg_secondary"])],
        foreground=[("disabled", COLORS["text_secondary"])],
        indicatorcolor=[("selected", COLORS["accent"]), ("!selected", COLORS["border"])],
    )
    style.configure(
        "TRadiobutton",
        background=COLORS["bg_secondary"],
        foreground=COLORS["text_primary"],
        focuscolor=COLORS["bg_secondary"],
        bordercolor=COLORS["border"],
        indicatordiameter=11,
        indicatorbackground="#ffffff",
        indicatorcolor=COLORS["accent"],
    )
    style.map(
        "TRadiobutton",
        background=[("active", COLORS["bg_tertiary"]), ("disabled", COLORS["bg_secondary"])],
        foreground=[("disabled", COLORS["text_secondary"])],
        indicatorcolor=[("selected", COLORS["accent"]), ("!selected", COLORS["border"])],
    )

    return style


def create_card(parent: tk.Widget, *, padding: Optional[int] = 20) -> tk.Frame:
    """
    Create a rounded looking card container using a Frame with border/highlight.
    The returned frame has an `inner` attribute pointing at the padded interior.
    """
    card = tk.Frame(
        parent,
        bg=COLORS["bg_secondary"],
        bd=0,
        highlightbackground=COLORS["border"],
        highlightthickness=1,
        relief=tk.FLAT,
    )
    inner = card
    if padding:
        inner = tk.Frame(card, bg=COLORS["bg_secondary"], bd=0, relief=tk.FLAT)
        inner.pack(fill=tk.BOTH, expand=True, padx=padding, pady=padding)
    card.inner = inner
    return card


def style_listbox(listbox: tk.Listbox) -> None:
    """Apply the shared theme colors to a standard Tk listbox."""
    listbox.configure(
        bg=COLORS["bg_secondary"],
        fg=COLORS["text_primary"],
        highlightthickness=0,
        borderwidth=0,
        selectbackground=COLORS["accent"],
        selectforeground="#ffffff",
        relief=tk.FLAT,
    )


def create_primary_button(parent: tk.Widget, text: str, command=None, **kwargs) -> tk.Button:
    """Create a primary action button matching the shared theme."""
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=COLORS["accent"],
        fg="#ffffff",
        activebackground=COLORS["accent_hover"],
        activeforeground="#ffffff",
        font=FONTS["button"],
        relief=tk.FLAT,
        bd=0,
        cursor="hand2",
        padx=18,
        pady=10,
    )
    if kwargs:
        btn.configure(**kwargs)
    return btn


def create_secondary_button(parent: tk.Widget, text: str, command=None, **kwargs) -> tk.Button:
    """Create a secondary action button in the shared theme."""
    btn = tk.Button(
        parent,
        text=text,
        command=command,
        bg=COLORS["bg_secondary"],
        fg=COLORS["text_primary"],
        activebackground=COLORS["bg_tertiary"],
        activeforeground=COLORS["text_primary"],
        font=FONTS["button"],
        relief=tk.FLAT,
        bd=1,
        highlightthickness=1,
        highlightbackground=COLORS["border"],
        highlightcolor=COLORS["border"],
        cursor="hand2",
        padx=18,
        pady=10,
    )
    if kwargs:
        btn.configure(**kwargs)
    return btn

