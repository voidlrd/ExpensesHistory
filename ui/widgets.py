from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt


def format_amount(value):
    """Render a quantity without trailing zeros: 2.0 -> '2', 1.500 -> '1.5'."""
    amount = float(value)
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.3f}".rstrip('0').rstrip('.')


def repopulate_combo(combo, entries, placeholder=None, block_signals=False):
    """Refill a combo box from (label, data) pairs, keeping the current selection."""
    previous = combo.currentData()

    if block_signals:
        combo.blockSignals(True)

    combo.clear()
    if placeholder is not None:
        combo.addItem(placeholder[0], userData=placeholder[1])
    for label, data in entries:
        combo.addItem(label, userData=data)

    if previous is not None:
        index = combo.findData(previous)
        if index >= 0:
            combo.setCurrentIndex(index)

    if block_signals:
        combo.blockSignals(False)


def make_stat_card(parent_layout, title_text, color, value_text="0.00",
                   value_size=28, padding=20, radius=10, subtitle=False):
    """Coloured card with a title and a big value; returns (value_label, subtitle_label)."""
    frame = QFrame()
    frame.setStyleSheet(f"background-color: {color}; border-radius: {radius}px; padding: {padding}px;")
    layout = QVBoxLayout(frame)

    title_size = 16 if subtitle is False else 14
    title = QLabel(title_text)
    title.setStyleSheet(f"color: white; font-size: {title_size}px;")
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)

    value = QLabel(value_text)
    value.setStyleSheet(f"color: white; font-size: {value_size}px; font-weight: bold;")
    value.setAlignment(Qt.AlignmentFlag.AlignCenter)

    layout.addWidget(title)
    layout.addWidget(value)

    sub = None
    if subtitle:
        sub = QLabel("")
        sub.setStyleSheet("color: #E0E0E0; font-size: 11px;")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

    parent_layout.addWidget(frame)
    return value, sub
