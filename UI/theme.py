import flet as ft

# Typography System (Matching Linear Desktop)
FONT_FAMILY = "Inter"
FONT_REGULAR = "Inter"
FONT_MEDIUM = "Inter-Medium"
FONT_SEMIBOLD = "Inter-SemiBold"
FONT_BOLD = "Inter-Bold"

# Linear Dark Color System
BG_APP = "#090a0d"           # Main app canvas
BG_SIDEBAR = "#0d0e12"       # Navigation sidebar
BG_SURFACE = "#12141a"       # Secondary surface
BG_CARD = "#171922"          # Issue card / container
BG_CARD_HOVER = "#202330"    # Hover card state
BG_CARD_ACTIVE = "#282c3c"   # Selected item state

BORDER_SUBTLE = "#1f222e"    # Hairline divider
BORDER_ACTIVE = "#5e6ad2"    # Active focus border

TEXT_PRIMARY = "#f4f5f8"     # Bright white
TEXT_SECONDARY = "#9da3ae"   # Muted silver
TEXT_MUTED = "#606675"       # Dim gray

BRAND_ACCENT = "#5e6ad2"     # Linear Violet
BRAND_ACCENT_HOVER = "#6e7bf0"

# Priority System
PRIORITIES = {
    0: {"name": "No priority", "color": "#606675", "icon": ft.Icons.REMOVE},
    1: {"name": "Urgent",      "color": "#eb5757", "icon": ft.Icons.PRIORITY_HIGH},
    2: {"name": "High",        "color": "#f2994a", "icon": ft.Icons.SIGNAL_CELLULAR_ALT},
    3: {"name": "Medium",      "color": "#f2c94c", "icon": ft.Icons.SIGNAL_CELLULAR_ALT_2_BAR},
    4: {"name": "Low",         "color": "#56ccf2", "icon": ft.Icons.SIGNAL_CELLULAR_ALT_1_BAR},
}

# State System
STATE_COLORS = {
    "backlog":   "#8a8f98",
    "unstarted": "#e2e8f0",
    "started":   "#f2c94c",
    "completed": "#5e6ad2",
    "canceled":  "#606675",
}

STATE_ICONS = {
    "backlog":   ft.Icons.RADIO_BUTTON_OFF,
    "unstarted": ft.Icons.RADIO_BUTTON_UNCHECKED,
    "started":   ft.Icons.CHANGE_CIRCLE_OUTLINED,
    "completed": ft.Icons.CHECK_CIRCLE,
    "canceled":  ft.Icons.CANCEL_OUTLINED,
}
