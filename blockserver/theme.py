"""BlockServer desktop theme and tiny procedural block-landscape art."""
from __future__ import annotations
import random
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, Signal, QSize
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from .icons import icon

ASSETS = Path(__file__).resolve().parents[1] / "assets"
GREEN = "#40f59b"
TEXT = "#eaf0fb"
MUTED = "#aab8cb"

STYLE = """
QMainWindow, QWidget#root { background: #0b121e; color: #eaf0fb; }
QWidget { color: #eaf0fb; font-family: 'Segoe UI', 'Inter', 'Arial'; font-size: 12px; }
QFrame#header { background: #0e1825; border-bottom: 1px solid #273748; }
QFrame#sidebar { background: #111b2a; border-right: 1px solid #2a394b; }
QFrame#statusPane { background: #141f2d; border: 1px solid #283a4e; border-radius: 14px; }
QFrame#panel, QFrame#statCard { background: #182533; border: 1px solid #334556; border-radius: 12px; }
QFrame#glassPanel { background: #142231; border: 1px solid #2a4051; border-radius: 11px; }
QLabel#titleLabel { font-size: 22px; font-weight: 750; color: #f4f7fc; }
QLabel#sectionTitle { font-size: 19px; font-weight: 700; color: #eff4fb; }
QLabel#smallTitle { font-size: 14px; font-weight: 650; color: #e8f2fa; }
QLabel#muted, QLabel#hint { color: #9dadbf; font-size: 11px; }
QLabel#green { color: #48f6a4; }
QLabel#value { font-size: 16px; font-weight: 600; }
QPushButton { background: #223143; color: #ecf3fe; border: 1px solid #41566b; border-radius: 9px; padding: 9px 14px; font-weight: 600; }
QPushButton:hover { border-color: #65fbb9; background: #2a4453; }
QPushButton:pressed { background: #1e574c; }
QPushButton:disabled { background: #1d2a39; color: #697788; border-color: #2b394a; }
QPushButton#primary { color: #09241b; font-size: 15px; font-weight: 750; border: 1px solid #8affc6; background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #33d74c,stop:1 #20dba0); }
QPushButton#primary:hover { background: #62fba4; }
QPushButton#danger { background: #342b38; border-color: #6b4451; }
QPushButton#danger:hover { background: #653044; }
QPushButton#nav { background: transparent; color: #d4ddeb; border: 1px solid transparent; text-align: left; font-size: 13px; padding: 12px 15px; border-radius: 9px; }
QPushButton#nav:hover { background: #1a3a3c; }
QPushButton#nav[active="true"] { background: #164738; color: #f2fff9; border: 1px solid #285b4a; font-weight: 700; }
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit { background: #192634; border: 1px solid #354b5e; border-radius: 8px; padding: 8px 10px; selection-background-color: #147d66; color: #ebf1fa; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus { border: 1px solid #49e7a5; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox QAbstractItemView { background: #192634; color: #e8f0fb; selection-background-color: #157455; border: 1px solid #436075; }
QCheckBox { spacing: 10px; }
QCheckBox::indicator { width: 17px; height: 17px; }
QProgressBar { border: 0; border-radius: 5px; background: #304051; max-height: 9px; text-align: center; }
QProgressBar::chunk { background: #43f69e; border-radius: 5px; }
QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: #101c2a; width: 11px; }
QScrollBar::handle:vertical { background: #415468; min-height: 25px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QTreeView, QTableWidget, QListWidget { background: #101b29; alternate-background-color: #182635; border: 1px solid #304252; border-radius: 9px; selection-background-color: #215d50; outline: none; padding: 5px; }
QTreeView::item, QListWidget::item { padding: 4px; }
QHeaderView::section { background: #223344; border: none; border-bottom: 1px solid #405263; padding: 9px; color: #b9cbdc; font-weight: 650; }
QSplitter::handle { background: #213140; width: 3px; }
QStatusBar { background: #132131; color: #b6c8db; border-top: 1px solid #2b3e50; }
QToolTip { background: #1d3442; border: 1px solid #52f5ae; color: white; padding: 6px; }
QMessageBox { background: #152231; }
"""


class DropZone(QWidget):
    filesDropped = Signal(list)
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumHeight(155)
        self.setMaximumHeight(215)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.hovered = False
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(8)
        self.icon = QLabel()
        self.icon.setFixedSize(70, 58)
        self.icon.setPixmap(icon("upload", "#45ffa8").pixmap(QSize(54, 54)))
        self.icon.setStyleSheet("background: transparent;")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.headline = QLabel("Arrastra aquí los archivos de tu servidor")
        self.headline.setStyleSheet("font-size: 18px; font-weight: 750; background: transparent;")
        self.headline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = QLabel("Admite .jar, paquetes .zip, carpetas y mundos")
        self.hint.setStyleSheet("font-size: 12px; color: #b9cede; background: transparent;")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.icon, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.headline)
        layout.addWidget(self.hint)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()
            self.hovered = True
            self.update()

    def dragLeaveEvent(self, event):
        self.hovered = False
        self.update()

    def dropEvent(self, event):
        self.hovered = False
        self.update()
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.filesDropped.emit(paths)
            event.acceptProposedAction()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor("#082f2a" if not self.hovered else "#125c41"))
        gradient.setColorAt(0.55, QColor("#0d2733"))
        gradient.setColorAt(1, QColor("#0d352f"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawRoundedRect(rect, 17, 17)
        rng = random.Random(19)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Decorative pixelated columns recede toward the center of the drop target.
        for side in (0, 1):
            edge = 8 if side == 0 else self.width() - 8
            sign = 1 if side == 0 else -1
            for k in range(13):
                step = 12
                colheight = rng.randrange(2, 7) * 12
                px = edge + sign * k * step
                py = self.height() - colheight - rng.randrange(0, 20)
                base = QColor("#126343" if k % 3 == 0 else "#0b513d")
                painter.fillRect(int(px), int(py), 13, int(colheight + 30), base)
                painter.fillRect(int(px - 6), int(py - 12), 25, 12, QColor("#0f7652"))
                painter.fillRect(int(px - 17), int(py), 40, 14, QColor("#0d6649"))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#46ff9f"), 2, Qt.PenStyle.DashLine)
        pen.setDashPattern([5, 3])
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 16, 16)
        painter.end()
