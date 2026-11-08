"""Consistent Font Awesome 6 vector icons for the whole interface.

QtAwesome bundles the icon resources through its pip package; no external
icon files, emoji fonts or online requests are necessary at runtime.
"""
from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QLabel, QStyle

try:
    import qtawesome as qta
except ImportError:
    qta = None

ICONS = {
    "dashboard": "house", "files": "folder-open", "console": "terminal",
    "versions": "layer-group", "backups": "box-archive", "settings": "gear",
    "upload": "cloud-arrow-up", "download": "download", "play": "play",
    "stop": "stop", "restart": "rotate", "folder": "folder-open",
    "folder-add": "folder-plus", "plus": "plus", "check": "check",
    "trash": "trash-can", "external": "arrow-up-right-from-square",
    "reload": "arrows-rotate", "ram": "memory", "cpu": "microchip",
    "players": "users", "port": "network-wired", "world": "cube",
    "java": "mug-hot", "jar": "file-code", "terminal": "terminal",
    "send": "paper-plane", "link": "link", "server": "server",
    "search": "magnifying-glass", "verify": "circle-check", "undo": "rotate-left",
    "edit": "pen", "info": "circle-info", "copy": "copy",
    "database": "database", "warning": "triangle-exclamation",
    "archive": "file-zipper",
}


def icon(name: str, color: str = "#65efad") -> QIcon:
    glyph = ICONS.get(name, name)
    if qta is not None:
        try:
            return qta.icon(f"fa6s.{glyph}", color=color, color_disabled="#627486")
        except Exception:
            pass
    style = QApplication.style() if QApplication.instance() is not None else None
    return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon) if style else QIcon()


def icon_label(name: str, size: int = 20, color: str = "#5deda9") -> QLabel:
    label = QLabel()
    label.setFixedSize(size + 2, size + 2)
    label.setPixmap(icon(name, color).pixmap(QSize(size, size)))
    label.setStyleSheet("background: transparent; border: none; padding: 0;")
    return label
