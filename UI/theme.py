#some of the themes lol might add some more vibrant colors
THEMES = {
    "Dark": dict(bg="#08090a", panel="#141516", card="#141516", hover="#1c1d21",
                 selected="#2b2d31", text="#f7f8f8", sub="#8a8f98", border="#23252a"),
    "Midnight": dict(bg="#000000", panel="#0b0b0c", card="#0f0f10", hover="#161618",
                     selected="#202024", text="#f7f8f8", sub="#8a8f98", border="#1c1c1f"),
    "Light": dict(bg="#f4f5f7", panel="#ffffff", card="#ffffff", hover="#eceef2",
                  selected="#e2e5eb", text="#16181d", sub="#5f6672", border="#d9dce3"),
}

ACCENTS = {
    "Purple": "#5e6ad2",
    "Blue": "#3b82f6",
    "Green": "#22c55e",
    "Orange": "#f59e0b",
    "Pink": "#ec4899",
    "Red": "#ef4444",
}

P = {}


def apply(theme="Dark", accent="Purple"):
    P.clear()
    P.update(THEMES.get(theme, THEMES["Dark"]))
    P["accent"] = ACCENTS.get(accent, ACCENTS["Purple"])
    P["mode"] = "light" if theme == "Light" else "dark"


apply()