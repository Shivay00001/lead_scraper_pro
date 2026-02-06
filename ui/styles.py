"""
Lead Scraper Pro - Modern UI Styles
Cyber/Dark theme definitions.
"""

THEME_COLORS = {
    "background": "#1a1b26",    # Deep Navy
    "surface": "#24283b",       # Lighter Navy
    "surface_hover": "#2f334d",
    "primary": "#7aa2f7",       # Neon Blue
    "primary_hover": "#89b4fa",
    "secondary": "#bb9af7",     # Soft Purple
    "success": "#9ece6a",       # Neon Green
    "warning": "#e0af68",       # Orange
    "error": "#f7768e",         # Red
    "text": "#c0caf5",          # White-ish
    "text_dim": "#a9b1d6",      # Grey-ish
    "border": "#414868",
    "scrollbar": "#565f89"
}

STYLESHEET = f"""
/* Global Reset */
* {{
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    font-size: 14px;
    color: {THEME_COLORS['text']};
    outline: none;
}}

QMainWindow, QWidget {{
    background-color: {THEME_COLORS['background']};
}}

/* Cards & Containers */
.Card {{
    background-color: {THEME_COLORS['surface']};
    border-radius: 12px;
    border: 1px solid {THEME_COLORS['border']};
}}

/* Buttons */
QPushButton {{
    background-color: {THEME_COLORS['surface']};
    border: 1px solid {THEME_COLORS['primary']};
    color: {THEME_COLORS['primary']};
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: 600;
}}

QPushButton:hover {{
    background-color: {THEME_COLORS['primary']};
    color: {THEME_COLORS['background']};
}}

QPushButton:pressed {{
    background-color: {THEME_COLORS['primary_hover']};
    border-color: {THEME_COLORS['primary_hover']};
}}

QPushButton:disabled {{
    border-color: {THEME_COLORS['text_dim']};
    color: {THEME_COLORS['text_dim']};
    background-color: transparent;
}}

/* Primary Action Button */
QPushButton.Primary {{
    background-color: {THEME_COLORS['primary']};
    color: {THEME_COLORS['background']};
    border: none;
}}

QPushButton.Primary:hover {{
    background-color: {THEME_COLORS['primary_hover']};
}}

/* Destructive Button */
QPushButton.Destructive {{
    border-color: {THEME_COLORS['error']};
    color: {THEME_COLORS['error']};
}}

QPushButton.Destructive:hover {{
    background-color: {THEME_COLORS['error']};
    color: {THEME_COLORS['background']};
}}

/* Inputs */
QLineEdit, QComboBox, QPlainTextEdit {{
    background-color: {THEME_COLORS['background']};
    border: 1px solid {THEME_COLORS['border']};
    border-radius: 6px;
    padding: 8px;
    color: {THEME_COLORS['text']};
}}

QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {THEME_COLORS['primary']};
    background-color: {THEME_COLORS['background']};
}}

/* Tables */
QTableWidget {{
    background-color: {THEME_COLORS['surface']};
    border: 1px solid {THEME_COLORS['border']};
    border-radius: 8px;
    gridline-color: {THEME_COLORS['border']};
}}

QTableWidget::item {{
    padding: 6px;
}}

QHeaderView::section {{
    background-color: {THEME_COLORS['surface_hover']};
    color: {THEME_COLORS['text']};
    padding: 8px;
    border: none;
    border-bottom: 2px solid {THEME_COLORS['border']};
    font-weight: 600;
}}

/* Scrollbars */
QScrollBar:vertical {{
    border: none;
    background: {THEME_COLORS['background']};
    width: 8px;
    margin: 0px 0px 0px 0px;
}}

QScrollBar::handle:vertical {{
    background: {THEME_COLORS['scrollbar']};
    min-height: 20px;
    border-radius: 4px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* Progress Bar */
QProgressBar {{
    border: none;
    background-color: {THEME_COLORS['surface']};
    border-radius: 4px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {THEME_COLORS['primary']};
    border-radius: 4px;
}}

/* Labels */
QLabel.Title {{
    font-size: 24px;
    font-weight: 700;
    color: {THEME_COLORS['text']};
}}

QLabel.Subtitle {{
    font-size: 16px;
    font-weight: 600;
    color: {THEME_COLORS['text_dim']};
}}

QLabel.StatValue {{
    font-size: 28px;
    font-weight: 800;
    color: {THEME_COLORS['primary']};
}}

QLabel.StatLabel {{
    font-size: 12px;
    color: {THEME_COLORS['text_dim']};
    text-transform: uppercase;
    letter-spacing: 1px;
}}
"""
