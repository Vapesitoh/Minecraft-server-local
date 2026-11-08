"""Native PySide6 interface for BlockServer GUI."""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
import os
import re
import sys
import traceback

from PySide6.QtCore import Qt, QDir, QSize, QThreadPool, QTimer, QUrl
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices, QIcon, QKeySequence, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFileSystemModel, QFormLayout, QFrame, QGridLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QStackedWidget, QTableWidget, QTableWidgetItem, QTextEdit, QTreeView,
    QVBoxLayout, QWidget, QHeaderView, QAbstractItemView, QMenu,
)

from .controls import WheelSafeSpinBox
from .core import (
    Store, accept_eula, build_launch, download_vanilla, eula_accepted,
    fetch_versions, scan_java, preferred_java, import_paths, jar_candidates, java_info,
    launch_scripts, make_backup, read_properties, readable_size, restore_backup,
    update_properties,
)
from .engine import ServerEngine
from .icons import icon, icon_label
from .theme import ASSETS, DropZone, STYLE
from .workers import Task


PAGES = [("Dashboard", "dashboard"), ("Archivos", "files"), ("Consola", "console"),
         ("Versiones", "versions"), ("Copias", "backups"), ("Ajustes", "settings")]


def hbox(spacing=10) -> QHBoxLayout:
    box = QHBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(spacing)
    return box


def vbox(spacing=10) -> QVBoxLayout:
    box = QVBoxLayout()
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(spacing)
    return box


def txt(value: str, style="") -> QLabel:
    result = QLabel(value)
    if style:
        result.setObjectName(style)
    return result


def btn(value: str, onclick=None, style="", icon_name: str | None = None) -> QPushButton:
    result = QPushButton(value)
    if style:
        result.setObjectName(style)
    if icon_name:
        result.setIcon(icon(icon_name, "#103529" if style == "primary" else "#65efad"))
        result.setIconSize(QSize(17, 17))
    if onclick:
        result.clicked.connect(onclick)
    return result


def caption_icon(title: str, icon_name: str) -> QWidget:
    widget = QWidget()
    row = hbox(8)
    row.addWidget(icon_label(icon_name, 19))
    row.addWidget(txt(title, "smallTitle"))
    row.addStretch(1)
    widget.setLayout(row)
    return widget


def panel() -> QFrame:
    p = QFrame()
    p.setObjectName("panel")
    return p


def make_page(title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(16)
    h = txt(title, "sectionTitle")
    layout.addWidget(h)
    sub = txt(subtitle, "muted")
    sub.setWordWrap(True)
    layout.addWidget(sub)
    return widget, layout


class EulaDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Minecraft EULA — aceptación requerida")
        self.setMinimumWidth(480)
        self.setModal(True)
        self.setStyleSheet(STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(15)
        image = QLabel()
        iconpath = ASSETS / "block_icon.png"
        if iconpath.is_file():
            image.setPixmap(QPixmap(str(iconpath)).scaled(60, 60, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image)
        header = txt("Se requiere aceptar la EULA", "sectionTitle")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        text = QLabel("Para continuar, debes aceptar personalmente el Acuerdo de licencia de usuario final de Minecraft (EULA). Esta aplicación no lo acepta automáticamente.")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)
        link = QLabel('<a style="color:#55e9f8;" href="https://www.minecraft.net/eula">Leer la EULA oficial (minecraft.net/eula) ↗</a>')
        link.setTextFormat(Qt.TextFormat.RichText)
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(link)
        layout.addWidget(txt("Escribe exactamente true para aceptar:", "smallTitle"))
        self.answer = QLineEdit()
        self.answer.setPlaceholderText("true")
        self.answer.textChanged.connect(self.validate)
        layout.addWidget(self.answer)
        controls = hbox()
        self.cancel = btn("Cancelar", self.reject)
        self.continue_btn = btn("Aceptar y continuar", self.accept, "primary", "check")
        self.continue_btn.setEnabled(False)
        controls.addStretch(1)
        controls.addWidget(self.cancel)
        controls.addWidget(self.continue_btn)
        layout.addLayout(controls)
        self.answer.setFocus()

    def validate(self, text):
        self.continue_btn.setEnabled(text.strip() == "true")


class ServerStatus(QWidget):
    """Right-hand live status panel."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(304)
        base = QFrame(self)
        base.setObjectName("statusPane")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(base)
        self.contents = QVBoxLayout(base)
        self.contents.setContentsMargins(14, 17, 14, 17)
        self.contents.setSpacing(13)
        heading = hbox(8)
        heading.addWidget(icon_label("server", 22))
        heading.addWidget(txt("Estado del servidor", "smallTitle"))
        heading.addStretch()
        self.state = QLabel("Detenido")
        self.state.setStyleSheet("background:#283b4a; color:#b9c8d5; border-radius:8px; padding:6px 7px; font-size:10px; font-weight:700;")
        heading.addWidget(self.state)
        self.contents.addLayout(heading)
        self.mem_value, self.ram_bar = self.progress_card("RAM utilizada", "0.0 / 4.0 GB", "ram")
        self.cpu_value, self.cpu_bar = self.progress_card("CPU", "0%", "cpu")
        split = hbox(10)
        a = panel()
        la = QVBoxLayout(a)
        la.setContentsMargins(13, 12, 12, 12)
        la.addWidget(caption_icon("Jugadores", "players"))
        self.people = txt("0 / 20", "value")
        la.addWidget(self.people)
        b = panel()
        lb = QVBoxLayout(b)
        lb.setContentsMargins(13, 12, 12, 12)
        lb.addWidget(caption_icon("Puerto", "port"))
        self.port = txt("25565", "value")
        lb.addWidget(self.port)
        split.addWidget(a)
        split.addWidget(b)
        self.contents.addLayout(split)
        self.world = self.text_card("Mundo", "world", "world")
        self.java = self.text_card("Java", "Detectando...", "java")
        self.jar = self.text_card("Archivo de inicio", "No seleccionado", "jar")
        self.contents.addStretch(1)

    def progress_card(self, title, initial, symbol):
        frame = panel()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(9)
        top = hbox()
        top.addWidget(caption_icon(title, symbol))
        top.addStretch()
        value = txt(initial, "green")
        top.addWidget(value)
        lay.addLayout(top)
        bar = QProgressBar()
        bar.setTextVisible(False)
        bar.setRange(0, 100)
        bar.setValue(0)
        lay.addWidget(bar)
        self.contents.addWidget(frame)
        return value, bar

    def text_card(self, title, val, icon_name):
        frame = panel()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(6)
        lay.addWidget(caption_icon(title, icon_name))
        value = txt(val, "muted")
        value.setWordWrap(True)
        lay.addWidget(value)
        self.contents.addWidget(frame)
        return value

    def update_profile(self, profile: dict, root: Path):
        props = read_properties(root)
        max_players = props.get("max-players", str(profile.get("max_players", 20)))
        self.people.setText(f"0 / {max_players}")
        self.port.setText(props.get("server-port", str(profile.get("port", 25565))))
        self.world.setText(props.get("level-name", "world"))
        jars = jar_candidates(root)
        selected = profile.get("jar") or (jars[0].name if jars else "Sin JAR")
        if profile.get("mode") == "script":
            selected = profile.get("script") or "Script de inicio"
        self.jar.setText(selected)
        self.mem_value.setText(f"0.0 / {int(profile.get('xmx',4096))/1024:.1f} GB")
        self.ram_bar.setValue(0)
        self.cpu_value.setText("0%")
        self.cpu_bar.setValue(0)

    def update_stats(self, mem, cpu, profile):
        maxram = max(0.01, int(profile.get("xmx", 4096)) / 1024)
        self.mem_value.setText(f"{mem:.2f} / {maxram:.1f} GB")
        self.ram_bar.setValue(max(0, min(100, round(mem / maxram * 100))))
        self.cpu_value.setText(f"{cpu:.1f}%")
        self.cpu_bar.setValue(max(0, min(100, round(cpu))))

    def update_state(self, state):
        labels = {"off": "Detenido", "starting": "Iniciando", "running": "En línea",
                  "stopping": "Deteniendo", "eula": "EULA pendiente"}
        self.state.setText(labels.get(state, state))
        colors = {"off": "#b7c7d5", "starting": "#ffd56d", "running": "#4ff9a1", "stopping": "#ffd56d", "eula": "#ffd56d"}
        self.state.setStyleSheet(f"background:#253542;color:{colors.get(state,'#fff')};border:1px solid #415363;border-radius:8px;padding:6px 8px;font-weight:700;font-size:10px;")


class ConsoleArea(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = vbox(6)
        self.setLayout(layout)
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.document().setMaximumBlockCount(3500)
        self.output.setAcceptRichText(False)
        self.output.setStyleSheet("font-family:Consolas,'Cascadia Mono',monospace;font-size:11px;background:#07121d;border:1px solid #2b4153;border-radius:8px;padding:9px;")
        layout.addWidget(self.output, 1)
        command_row = hbox(5)
        self.command = QLineEdit()
        self.command.setPlaceholderText("Escribe un comando: say Hola, list, save-all, stop...")
        self.command.returnPressed.connect(self.send)
        command_row.addWidget(self.command, 1)
        self.go = btn("", self.send, "primary", "send")
        self.go.setFixedWidth(46)
        command_row.addWidget(self.go)
        layout.addLayout(command_row)
        self.on_send = None
        self.command.setEnabled(False)
        self.go.setEnabled(False)

    def send(self):
        if self.on_send:
            self.on_send(self.command.text())
            self.command.clear()

    def append_line(self, line: str, level: str):
        colors = {"warn": "#ffcb6c", "error": "#ff767d", "success": "#4efa9f",
                  "system": "#86a9ff", "command": "#71e7ec", "info": "#d6e3ed"}
        safe = escape(line)
        safe = safe.replace(" ", "&nbsp;")
        timestamp = datetime.now().strftime("%H:%M:%S")
        vertical = self.output.verticalScrollBar()
        follow = vertical.value() >= vertical.maximum() - 18
        self.output.append(f'<span style="color:#72869b">[{timestamp}]</span>&nbsp;<span style="color:{colors.get(level,"#d6e3ed")}">{safe}</span>')
        if follow:
            vertical.setValue(vertical.maximum())

    def clear(self):
        self.output.clear()

    def running(self, enabled: bool):
        self.command.setEnabled(enabled)
        self.go.setEnabled(enabled)


class MainWindow(QMainWindow):
    def __init__(self, config_root: Path | None = None, workspace: Path | None = None):
        super().__init__()
        config_root = config_root or (Path(os.environ.get("APPDATA", "")) / "BlockServerGUI" if os.name == "nt" else Path.home() / ".config" / "blockserver-gui")
        workspace = workspace or (Path.home() / "Documents" / "BlockServerGUI")
        self.store = Store(config_root / "config.json", workspace)
        self.engine = ServerEngine(self)
        self.engine.line.connect(self.append_log)
        self.engine.status.connect(self.on_status)
        self.engine.stats.connect(self.on_stats)
        self.engine.players.connect(self.on_players)
        self.engine.ended.connect(self.on_finished)
        self.versions: list[dict] = []
        self._jobs: set[Task] = set()
        self._busy = 0
        self._eula_retry = False
        self._last_error = ""
        self._java_installs = []
        self._java_scan_active = False
        self._java_scan_task = None
        self.setWindowTitle("BlockServer GUI • Universal Minecraft Server Manager")
        self.setMinimumSize(1120, 740)
        self.resize(1530, 865)
        icon = ASSETS / "block_icon.png"
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))
        self.setStyleSheet(STYLE)
        self._create_ui()
        self.load_profile()
        self.append_log("BlockServer GUI listo. Importa un .jar o descarga una versión Vanilla.", "success")
        self.append_log("Los servidores requieren Java instalado. EULA: aceptación manual obligatoria.", "system")
        QTimer.singleShot(0, self.scan_java_on_startup)

    @property
    def profile(self) -> dict:
        return self.store.selected

    @property
    def folder(self) -> Path:
        return Path(self.profile["path"])

    @property
    def backup_folder(self) -> Path:
        return self.store.workspace / "_backups" / self.profile["id"]

    def _create_ui(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setObjectName("header")
        header.setFixedHeight(73)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(25, 9, 20, 8)
        hl.setSpacing(15)
        icon = QLabel()
        if (ASSETS / "block_icon.png").is_file():
            icon.setPixmap(QPixmap(str(ASSETS / "block_icon.png")).scaled(46, 46, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        hl.addWidget(icon)
        brand = QLabel('BlockServer <span style="color:#46ee86">GUI</span>')
        brand.setStyleSheet("font-size:24px;font-weight:850;")
        hl.addWidget(brand)
        sep = QLabel("│")
        sep.setStyleSheet("color:#506477;font-size:25px;")
        hl.addWidget(sep)
        tagline = txt("Universal Minecraft Server Manager")
        tagline.setStyleSheet("font-size:14px;color:#bfcada;")
        hl.addWidget(tagline)
        hl.addStretch(1)
        scene = QLabel()
        scene.setFixedSize(400, 61)
        scene.setScaledContents(True)
        if (ASSETS / "header_scene.png").is_file():
            scene.setPixmap(QPixmap(str(ASSETS / "header_scene.png")))
        hl.addWidget(scene)
        layout.addWidget(header)

        main = QWidget()
        ml = QHBoxLayout(main)
        ml.setContentsMargins(0, 0, 0, 0)
        ml.setSpacing(0)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(216)
        sl = QVBoxLayout(self.sidebar)
        sl.setContentsMargins(12, 15, 12, 0)
        sl.setSpacing(9)
        sl.addWidget(txt("SERVIDOR ACTIVO", "muted"))
        select_row = hbox(5)
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(80)
        self.profile_combo.currentIndexChanged.connect(self.switch_profile)
        select_row.addWidget(self.profile_combo, 1)
        plus = btn("", self.create_profile, icon_name="plus")
        plus.setFixedWidth(34)
        plus.setToolTip("Crear otro servidor")
        select_row.addWidget(plus)
        sl.addLayout(select_row)
        link_btn = btn("Vincular carpeta existente", self.link_existing_server, "nav", "link")
        link_btn.setToolTip("Administrar un servidor que ya tienes en otra carpeta")
        sl.addWidget(link_btn)
        sl.addSpacing(5)
        self.nav_buttons = []
        for idx, (title, symbol) in enumerate(PAGES):
            button = btn(title, lambda checked=False, page=idx: self.goto_page(page), "nav", symbol)
            button.setFixedHeight(49)
            sl.addWidget(button)
            self.nav_buttons.append(button)
        sl.addStretch(1)
        decorative = QLabel()
        decorative.setFixedSize(192, 274)
        decorative.setScaledContents(True)
        if (ASSETS / "sidebar_scene.png").is_file():
            decorative.setPixmap(QPixmap(str(ASSETS / "sidebar_scene.png")))
        sl.addWidget(decorative)
        ml.addWidget(self.sidebar)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._dashboard_page())
        self.pages.addWidget(self._files_page())
        self.pages.addWidget(self._console_page())
        self.pages.addWidget(self._versions_page())
        self.pages.addWidget(self._backups_page())
        self.pages.addWidget(self._settings_page())
        ml.addWidget(self.pages, 1)
        layout.addWidget(main, 1)

        footer = QFrame()
        footer.setStyleSheet("background:#142132;border-top:1px solid #2f3f51;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(17, 8, 16, 8)
        self.footer_text = QLabel("Preparado")
        self.footer_text.setStyleSheet("color:#53f8a4;")
        fl.addWidget(self.footer_text)
        fl.addStretch()
        self.footer_profile = QLabel("Mi servidor")
        fl.addWidget(self.footer_profile)
        fl.addWidget(QLabel("    │    "))
        self.footer_eula = QLabel("EULA pendiente")
        self.footer_eula.setStyleSheet("color:#ffd267;")
        fl.addWidget(self.footer_eula)
        fl.addWidget(QLabel("    │    "))
        fl.addWidget(QLabel("v1.1.1"))
        layout.addWidget(footer)
        self.goto_page(0)

    def _dashboard_page(self):
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(18, 19, 13, 16)
        outer.setSpacing(15)
        left = QWidget()
        col = QVBoxLayout(left)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(14)
        options = hbox(12)
        options.addWidget(txt("Versión:"))
        self.auto_version = QComboBox()
        self.auto_version.setMinimumWidth(170)
        self.auto_version.setMaximumWidth(270)
        self.auto_version.addItem("Auto-detectar .jar")
        self.auto_version.currentIndexChanged.connect(self.jar_combo_changed)
        options.addWidget(self.auto_version, 1)
        options.addWidget(txt("│"))
        options.addWidget(txt("Java:"))
        self.java_display = QComboBox()
        self.java_display.setEditable(True)
        self.java_display.setMinimumWidth(190)
        self.java_display.addItem("Auto · buscando Java...", "")
        self.java_display.setToolTip("Elige un Java encontrado o escribe una ruta personalizada. Auto selecciona uno compatible.")
        self.java_display.currentIndexChanged.connect(self.save_java_inline)
        self.java_display.lineEdit().editingFinished.connect(self.save_java_inline)
        options.addWidget(self.java_display, 2)
        rescan_java = btn("", self.scan_java_on_startup, icon_name="reload")
        rescan_java.setFixedWidth(42)
        rescan_java.setToolTip("Volver a buscar todas las instalaciones de Java")
        options.addWidget(rescan_java)
        browse_java = btn("", self.browse_java, icon_name="folder")
        browse_java.setFixedWidth(46)
        browse_java.setToolTip("Buscar java.exe")
        options.addWidget(browse_java)
        col.addLayout(options)
        self.drop = DropZone()
        self.drop.filesDropped.connect(self.import_files)
        self.drop.clicked.connect(self.choose_import)
        col.addWidget(self.drop)
        actions = hbox(11)
        self.import_btn = btn("Importar archivos", self.choose_import, icon_name="upload")
        self.run_btn = btn("Ejecutar servidor", self.start_server, "primary", "play")
        self.stop_btn = btn("Detener", self.stop_server, icon_name="stop")
        self.restart_btn = btn("Reiniciar", self.restart_server, icon_name="restart")
        for b in (self.import_btn, self.run_btn, self.stop_btn, self.restart_btn):
            b.setMinimumHeight(48)
            actions.addWidget(b, 1)
        self.stop_btn.setEnabled(False)
        self.restart_btn.setEnabled(False)
        col.addLayout(actions)
        con_frame = panel()
        conlay = QVBoxLayout(con_frame)
        conlay.setContentsMargins(10, 10, 10, 10)
        conlay.setSpacing(8)
        line = hbox()
        line.addWidget(caption_icon("Consola", "console"))
        line.addStretch()
        line.addWidget(btn("Limpiar", self.clear_console))
        line.addWidget(btn("Expandir", lambda: self.goto_page(2), icon_name="external"))
        conlay.addLayout(line)
        self.dashboard_console = ConsoleArea()
        self.dashboard_console.on_send = self.send_command
        conlay.addWidget(self.dashboard_console, 1)
        col.addWidget(con_frame, 1)
        outer.addWidget(left, 1)
        self.status_panel = ServerStatus()
        outer.addWidget(self.status_panel)
        return page

    def _files_page(self):
        page, layout = make_page("Administrador de archivos", "Explora, importa y organiza el contenido del servidor. Haz doble clic para abrir archivos con tu sistema operativo.")
        tools = hbox()
        tools.addWidget(btn("Importar", self.choose_import, icon_name="upload"))
        tools.addWidget(btn("Importar carpeta", self.choose_import_folder, icon_name="folder"))
        tools.addWidget(btn("Nueva carpeta", self.new_folder, icon_name="folder-add"))
        tools.addWidget(btn("Abrir en el sistema", self.open_selected_file, icon_name="external"))
        tools.addWidget(btn("Usar como servidor", self.use_selected_jar, icon_name="check"))
        tools.addWidget(btn("Actualizar", self.refresh_files, icon_name="reload"))
        tools.addStretch()
        tools.addWidget(btn("Eliminar", self.delete_selected_file, "danger", "trash"))
        layout.addLayout(tools)
        self.files_path = txt("", "hint")
        layout.addWidget(self.files_path)
        self.file_model = QFileSystemModel(self)
        self.file_model.setFilter(QDir.Filter.AllEntries | QDir.Filter.NoDotAndDotDot | QDir.Filter.AllDirs)
        self.file_tree = QTreeView()
        self.file_tree.setModel(self.file_model)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setSortingEnabled(True)
        self.file_tree.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        self.file_tree.doubleClicked.connect(self.open_selected_file)
        self.file_tree.setColumnWidth(0, 360)
        self.file_tree.setColumnWidth(1, 120)
        self.file_tree.setColumnWidth(2, 140)
        layout.addWidget(self.file_tree, 1)
        return page

    def _console_page(self):
        page, layout = make_page("Consola en vivo", "Registros del proceso Java y ejecución directa de comandos en la consola del servidor.")
        toolbar = hbox()
        toolbar.addWidget(btn("Ejecutar", self.start_server, "primary", "play"))
        toolbar.addWidget(btn("Detener", self.stop_server, icon_name="stop"))
        toolbar.addStretch()
        toolbar.addWidget(btn("Vaciar registros", self.clear_console))
        layout.addLayout(toolbar)
        self.full_console = ConsoleArea()
        self.full_console.on_send = self.send_command
        layout.addWidget(self.full_console, 1)
        return page

    def _versions_page(self):
        page, layout = make_page("Catálogo de versiones", "Descarga e instala servidores Vanilla oficiales de Mojang; para Paper, Fabric, Forge, Mohist o modpacks importa sus archivos directamente.")
        tools = hbox()
        self.search_version = QLineEdit()
        self.search_version.setPlaceholderText("Buscar versión (p. ej. 1.20.1, 26.3...)")
        self.search_version.textChanged.connect(self.fill_versions)
        tools.addWidget(self.search_version, 1)
        self.snapshots = QCheckBox("Incluir snapshots")
        self.snapshots.toggled.connect(self.fill_versions)
        tools.addWidget(self.snapshots)
        tools.addWidget(btn("Actualizar catálogo", self.get_versions, icon_name="reload"))
        layout.addLayout(tools)
        self.version_table = QTableWidget(0, 3)
        self.version_table.setHorizontalHeaderLabels(["Versión", "Canal", "Fecha de publicación"])
        self.version_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.version_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.version_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.version_table.verticalHeader().setVisible(False)
        self.version_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.version_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.version_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.version_table.doubleClicked.connect(self.install_version)
        layout.addWidget(self.version_table, 1)
        bottom = hbox()
        self.version_info = txt("Pulsa «Actualizar catálogo» para consultar las versiones disponibles.", "muted")
        bottom.addWidget(self.version_info, 1)
        self.install_btn = btn("Instalar Vanilla seleccionada", self.install_version, "primary", "download")
        bottom.addWidget(self.install_btn)
        layout.addLayout(bottom)
        return page

    def _backups_page(self):
        page, layout = make_page("Copias de seguridad", "Crea respaldos comprimidos del servidor y restaura uno cuando lo necesites. Para evitar mundos corruptos, el servidor debe estar apagado.")
        actions = hbox()
        actions.addWidget(btn("Crear respaldo", self.make_backup, icon_name="plus"))
        actions.addWidget(btn("Restaurar seleccionado", self.restore_backup, icon_name="undo"))
        actions.addWidget(btn("Abrir carpeta", self.open_backups, icon_name="folder"))
        actions.addStretch()
        actions.addWidget(btn("Actualizar", self.refresh_backups, icon_name="reload"))
        layout.addLayout(actions)
        self.backup_list = QListWidget()
        layout.addWidget(self.backup_list, 1)
        self.backup_hint = txt("Sin copias de seguridad.", "muted")
        layout.addWidget(self.backup_hint)
        return page

    def _settings_page(self):
        page, outer = make_page("Configuración del servidor", "Ajusta Java, memoria, archivo de inicio y propiedades del juego. Guarda los cambios con el servidor detenido.")
        scroller = QScrollArea()
        scroller.setWidgetResizable(True)
        interior = QWidget()
        interior_layout = QVBoxLayout(interior)
        interior_layout.setContentsMargins(4, 3, 16, 8)
        interior_layout.setSpacing(17)

        server_section = panel()
        server_form = QFormLayout(server_section)
        server_form.setContentsMargins(20, 20, 20, 20)
        server_form.setSpacing(13)
        self.server_name = QLineEdit()
        server_form.addRow("Nombre del perfil", self.server_name)
        location = hbox(7)
        self.server_directory = QLineEdit()
        self.server_directory.setReadOnly(True)
        location.addWidget(self.server_directory, 1)
        location.addWidget(btn("Abrir", self.open_folder))
        server_form.addRow("Carpeta del servidor", location)
        self.mode = QComboBox()
        self.mode.addItem("Automático (JAR o script)", "auto")
        self.mode.addItem("Archivo JAR", "jar")
        self.mode.addItem("Script (Forge / NeoForge)", "script")
        self.mode.addItem("Argumentos Java personalizados", "custom")
        server_form.addRow("Modo de inicio", self.mode)
        self.jar_choice = QComboBox()
        self.jar_choice.setEditable(True)
        server_form.addRow("JAR seleccionado", self.jar_choice)
        self.script_choice = QComboBox()
        self.script_choice.setEditable(True)
        server_form.addRow("Script seleccionado", self.script_choice)
        self.custom_args = QLineEdit()
        self.custom_args.setPlaceholderText("-Xmx{xmx}M -Xms{xms}M -jar {jar} nogui")
        self.custom_args.setToolTip("Argumentos, sin intérprete shell; variables: {jar}, {xms}, {xmx}")
        server_form.addRow("Argumentos personalizados", self.custom_args)
        self.java_path = QLineEdit()
        self.java_path.setPlaceholderText("Automático si está vacío")
        self.java_catalog = QComboBox()
        self.java_catalog.addItem("Auto · buscando Java...", "")
        self.java_catalog.currentIndexChanged.connect(self.select_java_in_settings)
        server_form.addRow("Java instalado", self.java_catalog)
        java_row = hbox(7)
        java_row.addWidget(self.java_path, 1)
        java_row.addWidget(btn("Examinar", self.browse_java, icon_name="folder"))
        java_row.addWidget(btn("Verificar", self.check_java, icon_name="verify"))
        java_row.addWidget(btn("Buscar Java", self.scan_java_on_startup, icon_name="reload"))
        server_form.addRow("Ruta de Java", java_row)
        self.java_result = txt("Java sin comprobar", "muted")
        server_form.addRow("Versión de Java", self.java_result)
        memory = hbox(12)
        self.xms = WheelSafeSpinBox()
        self.xms.setRange(256, 131072)
        self.xms.setSuffix(" MB mínimo")
        self.xms.setSingleStep(512)
        self.xms.setToolTip("Modifica con las flechas o escribiendo. La rueda y el touchpad no cambian el valor.")
        self.xmx = WheelSafeSpinBox()
        self.xmx.setRange(512, 131072)
        self.xmx.setSuffix(" MB máximo")
        self.xmx.setSingleStep(512)
        self.xmx.setToolTip("Modifica con las flechas o escribiendo. La rueda y el touchpad no cambian el valor.")
        memory.addWidget(self.xms)
        memory.addWidget(self.xmx)
        memory.addStretch()
        server_form.addRow("Memoria RAM", memory)
        interior_layout.addWidget(server_section)

        game_section = panel()
        form = QFormLayout(game_section)
        form.setContentsMargins(20, 20, 20, 20)
        form.setSpacing(13)
        self.port_spin = WheelSafeSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setToolTip("Modifica con las flechas o escribiendo. La rueda y el touchpad no cambian el valor.")
        form.addRow("Puerto TCP", self.port_spin)
        self.max_players_spin = WheelSafeSpinBox()
        self.max_players_spin.setRange(1, 1000)
        self.max_players_spin.setToolTip("Modifica con las flechas o escribiendo. La rueda y el touchpad no cambian el valor.")
        form.addRow("Máximo de jugadores", self.max_players_spin)
        self.motd = QLineEdit()
        form.addRow("Mensaje MOTD", self.motd)
        self.online_mode = QCheckBox("Verificar cuentas oficiales (recomendado)")
        form.addRow("Online mode", self.online_mode)
        self.pvp = QCheckBox("Permitir PvP")
        form.addRow("PvP", self.pvp)
        self.gamemode = QComboBox()
        self.gamemode.addItems(["survival", "creative", "adventure", "spectator"])
        form.addRow("Modo de juego", self.gamemode)
        self.difficulty = QComboBox()
        self.difficulty.addItems(["peaceful", "easy", "normal", "hard"])
        form.addRow("Dificultad", self.difficulty)
        self.world_name = QLineEdit()
        form.addRow("Nombre del mundo", self.world_name)
        interior_layout.addWidget(game_section)
        interior_layout.addStretch()
        scroller.setWidget(interior)
        outer.addWidget(scroller, 1)
        actions = hbox()
        actions.addWidget(btn("Eliminar perfil (sin borrar archivos)", self.delete_profile, "danger"))
        actions.addStretch()
        actions.addWidget(btn("Descartar cambios", self.populate_settings, icon_name="undo"))
        actions.addWidget(btn("Guardar configuración", self.save_settings, "primary", "check"))
        outer.addLayout(actions)
        return page

    # -------- Navigation and profiles --------
    def goto_page(self, index: int):
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            active = i == index
            button.setProperty("active", "true" if active else "false")
            button.style().unpolish(button)
            button.style().polish(button)
        if index == 1:
            self.refresh_files()
        elif index == 3 and not self.versions:
            self.get_versions()
        elif index == 4:
            self.refresh_backups()
        elif index == 5:
            self.populate_settings()

    def load_profile(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for p in self.store.profiles:
            self.profile_combo.addItem(p["name"], p["id"])
            if p["id"] == self.profile["id"]:
                self.profile_combo.setCurrentIndex(self.profile_combo.count() - 1)
        self.profile_combo.blockSignals(False)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.footer_profile.setText(self.profile["name"])
        self.footer_eula.setText("EULA aceptada" if eula_accepted(self.folder) else "EULA pendiente")
        self.footer_eula.setStyleSheet("color:#48f69e;" if eula_accepted(self.folder) else "color:#ffd267;")
        self.update_jar_choices()
        self.refresh_java_choices()
        self.status_panel.update_profile(self.profile, self.folder)
        self.update_java_status()
        self.populate_settings()
        self.refresh_files()
        self.refresh_backups()

    def create_profile(self):
        if self.engine.active or self._busy:
            self.warn("Detén el servidor y termina las operaciones activas antes de cambiar de perfil.")
            return
        name, ok = QInputDialog.getText(self, "Nuevo servidor", "Nombre del nuevo servidor:", text="Nuevo servidor")
        if not ok or not name.strip():
            return
        try:
            self.store.create(name)
            self.load_profile()
            self.append_log(f"Perfil creado: {self.profile['name']}", "success")
        except Exception as ex:
            self.fail(str(ex))

    def link_existing_server(self):
        if self.engine.active or self._busy:
            self.warn("Detén el servidor antes de vincular una carpeta.")
            return
        path = QFileDialog.getExistingDirectory(self, "Seleccionar servidor ya existente", str(Path.home()))
        if not path:
            return
        name, ok = QInputDialog.getText(self, "Vincular servidor", "Nombre del perfil:", text=Path(path).name)
        if not ok or not name.strip():
            return
        try:
            self.store.create(name, Path(path))
            self.load_profile()
            self.append_log(f"Carpeta existente vinculada: {path}", "success")
        except Exception as ex:
            self.fail(str(ex))

    def switch_profile(self, index: int):
        if index < 0:
            return
        selected_id = self.profile_combo.itemData(index)
        if selected_id == self.profile["id"]:
            return
        if self.engine.active or self._busy:
            self.warn("Primero detén el servidor y termina las operaciones pendientes.")
            self.load_profile()
            return
        self.store.select(selected_id)
        self.load_profile()
        self.append_log(f"Perfil activo: {self.profile['name']}", "system")

    def delete_profile(self):
        if self.engine.active or self._busy:
            self.warn("Primero detén el servidor.")
            return
        if not self.confirm("Eliminar perfil", f"Se quitará el perfil «{self.profile['name']}» de la lista.\n\nLos archivos y respaldos NO se eliminarán."):
            return
        try:
            self.store.remove(self.profile["id"])
            self.load_profile()
        except ValueError as ex:
            self.warn(str(ex))

    def update_jar_choices(self):
        self.auto_version.blockSignals(True)
        self.auto_version.clear()
        self.auto_version.addItem("Auto-detectar .jar", "")
        for jar in jar_candidates(self.folder):
            self.auto_version.addItem(jar.name, jar.name)
        desired = self.profile.get("jar", "")
        index = self.auto_version.findData(desired)
        self.auto_version.setCurrentIndex(max(index, 0))
        self.auto_version.blockSignals(False)

    def jar_combo_changed(self, index):
        if index < 0:
            return
        if self.engine.active:
            self.warn("No puedes cambiar el archivo JAR mientras el servidor está encendido.")
            self.update_jar_choices()
            return
        self.profile["jar"] = self.auto_version.itemData(index) or ""
        self.store.save()
        self.status_panel.update_profile(self.profile, self.folder)
        self.update_java_status()

    def open_folder(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.folder)))

    # -------- Java discovery, automatic selection, manual override --------
    def scan_java_on_startup(self):
        """Detect all Java installations in a worker; never freeze the window."""
        if self._java_scan_active:
            return
        self._java_scan_active = True
        self.java_result.setText("Buscando versiones de Java instaladas...")
        self.append_log("Buscando Java (registro, PATH, JAVA_HOME y carpetas habituales)...", "system")
        task = Task(scan_java)
        self._java_scan_task = task
        task.signals.result.connect(self.java_scan_finished)
        task.signals.error.connect(self.java_scan_failed)
        task.signals.finished.connect(self.java_scan_cleanup)
        QThreadPool.globalInstance().start(task)

    def java_scan_finished(self, infos):
        self._java_installs = infos
        self.refresh_java_choices()
        self.update_java_status()
        if infos:
            versions = ", ".join(f"Java {j.version} ({j.bits or '?'} bits)" for j in infos)
            self.append_log(f"Java detectado: {versions}", "success")
        else:
            self.append_log("No se encontró Java. Instala un JDK y pulsa Buscar Java.", "warn")
        if self.profile.get("required_java") and not preferred_java(infos, self.profile["required_java"]):
            self.append_log(f"No hay un Java compatible con el mínimo {self.profile['required_java']} requerido por el servidor.", "warn")

    def java_scan_failed(self, error):
        self.append_log(f"Error al buscar Java: {error}", "error")
        self.java_result.setText("No se pudo completar la detección")

    def java_scan_cleanup(self):
        self._java_scan_active = False
        self._java_scan_task = None

    def _java_auto_label(self) -> str:
        info = preferred_java(self._java_installs, self.profile.get("required_java"))
        if info:
            return f"Auto: Java {info.version} ({info.bits or '?'} bits)"
        if self._java_installs and self.profile.get("required_java"):
            return "Auto: sin Java compatible"
        return "Auto: Java no detectado" if not self._java_scan_active else "Auto: buscando Java..."

    def refresh_java_choices(self):
        """Keep the configured Java selected even when a custom path is used."""
        desired = self.profile.get("java", "")
        for combo in (self.java_display, self.java_catalog):
            combo.blockSignals(True)
            combo.clear()
            combo.addItem(self._java_auto_label(), "")
            for info in self._java_installs:
                label = f"Java {info.version} · {info.bits or '?'} bits — {Path(info.path).parent.parent.name}"
                combo.addItem(label, info.path)
                combo.setItemData(combo.count() - 1, info.path, Qt.ItemDataRole.ToolTipRole)
            idx = combo.findData(desired)
            if desired and idx < 0:
                combo.addItem(f"Personalizado: {desired}", desired)
                idx = combo.count() - 1
            combo.setCurrentIndex(max(idx, 0))
            combo.blockSignals(False)

    def select_java_in_settings(self, index: int):
        if index < 0:
            return
        self.java_path.setText(self.java_catalog.itemData(index) or "")
        self.check_java()

    def save_java_inline(self, *unused):
        if self.engine.active:
            self.refresh_java_choices()
            return
        index = self.java_display.currentIndex()
        typed = self.java_display.currentText().strip().strip('"')
        value = (self.java_display.itemData(index) if index >= 0 and
                 typed == self.java_display.itemText(index)
                 else typed) or ""
        # Editable combo: its displayed version description is never mistaken
        # for an executable path.
        if value and not Path(value).is_file():
            self.warn("La ruta de Java seleccionada no existe. Elige un ejecutable java.exe válido.")
            self.refresh_java_choices()
            return
        if value != self.profile.get("java", ""):
            self.profile["java"] = value
            self.store.save()
            self.java_path.setText(value)
            self.refresh_java_choices()
            self.update_java_status()
            self.append_log(f"Java seleccionado: {value or 'Automático'}", "system")

    def browse_java(self):
        initial = self.java_path.text() or self.profile.get("java") or str(Path.home())
        path, _ = QFileDialog.getOpenFileName(self, "Selecciona Java", initial,
                                               "Ejecutable Java (java.exe java);;Todos los archivos (*)")
        if path:
            if self.engine.active:
                self.warn("Detén el servidor antes de cambiar Java.")
                return
            self.profile["java"] = path
            self.java_path.setText(path)
            self.store.save()
            self.refresh_java_choices()
            self.check_java()
            self.update_java_status()

    def selected_java_info(self):
        java_path = self.profile.get("java", "")
        if java_path:
            return next((j for j in self._java_installs if j.path == java_path), None)
        return preferred_java(self._java_installs, self.profile.get("required_java"))

    def update_java_status(self):
        info = self.selected_java_info()
        if info:
            label = f"Java {info.version} · {info.bits or '?'} bits"
            self.status_panel.java.setText(label)
            self.java_result.setText(f"{label} — {info.path}")
        elif self.profile.get("java"):
            self.status_panel.java.setText("Java personalizado")
            self.java_result.setText("Ruta personalizada; pulsa Verificar")
        else:
            self.status_panel.java.setText("Sin Java compatible detectado")
            self.java_result.setText("No hay Java compatible. Pulsa Buscar Java.")

    def check_java(self):
        path = self.java_path.text().strip().strip('"')
        info = preferred_java(self._java_installs, self.profile.get("required_java")) if not path else None
        j = info if info else java_info(path or "java")
        if j.version:
            self.java_result.setText(f"Java {j.version} ({j.bits or '?'} bits) · {j.display} · {j.path}")
        else:
            self.java_result.setText("Java no encontrado. Instálalo o selecciona java.exe")
        return j

    def start_server(self):
        if self.engine.active:
            self.warn("El servidor ya está en ejecución.")
            return
        if self._busy:
            self.warn("Hay una operación en curso. Termínala antes de iniciar el servidor.")
            return
        try:
            executable, args, description = build_launch(self.profile)
        except Exception as ex:
            self.warn(str(ex))
            return
        # Script launchers (Forge/NeoForge) can select Java themselves.
        if not description.startswith("Script:"):
            info = java_info(executable)
            if info.version is None:
                self.warn("No se encontró Java. Instala el JDK compatible con tu versión de Minecraft, o selecciónalo en Ajustes → Ruta de Java.")
                self.goto_page(5)
                return
            need = self.profile.get("required_java")
            if need and info.version < int(need):
                self.warn(f"Este servidor exige Java {need} o superior y seleccionaste Java {info.version}.\n\nSelecciona un JDK compatible en Ajustes.")
                self.goto_page(5)
                return
            if info.bits == 32 and self.profile.get("xmx", 4096) > 1400:
                self.warn("Seleccionaste Java de 32 bits y mucha RAM. Instala Java de 64 bits para este servidor.")
                return
        if not eula_accepted(self.folder):
            dialog = EulaDialog(self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self.append_log("La EULA no se aceptó. Inicio cancelado.", "warn")
                return
            try:
                accept_eula(self.folder, dialog.answer.text())
            except Exception as ex:
                self.fail(str(ex))
                return
            self.footer_eula.setText("EULA aceptada")
            self.footer_eula.setStyleSheet("color:#48f69e;")
            self.append_log("EULA aceptada expresamente por el usuario y guardada en eula.txt.", "success")
        if description.startswith("Script:") and not self.confirm(
                "Ejecutar script de servidor",
                f"Se ejecutará {description} con los permisos de tu usuario.\n\nLos scripts importados pueden incluir comandos de terceros. Ejecuta únicamente modpacks de fuentes confiables. ¿Continuar?"):
            return
        self.status_panel.jar.setText(description)
        try:
            self.engine.start(executable, args, str(self.folder))
        except Exception as ex:
            self.fail(str(ex))

    def stop_server(self):
        if self.engine.active:
            self.engine.stop()

    def restart_server(self):
        if not self.engine.active:
            self.start_server()
            return
        try:
            executable, args, _ = build_launch(self.profile)
            self.engine.restart(executable, args, str(self.folder))
        except Exception as ex:
            self.fail(str(ex))

    def send_command(self, command: str):
        command = command.strip()
        if not command:
            return
        try:
            self.engine.send(command)
        except Exception as ex:
            self.warn(str(ex))

    def clear_console(self):
        self.dashboard_console.clear()
        self.full_console.clear()

    def append_log(self, message: str, level: str = "info"):
        self.dashboard_console.append_line(message, level)
        self.full_console.append_line(message, level)

    def on_status(self, value):
        self.status_panel.update_state(value)
        online = self.engine.active
        self.run_btn.setEnabled(value == "off" and not self._busy)
        self.stop_btn.setEnabled(online and value != "stopping")
        self.restart_btn.setEnabled(online and value != "stopping")
        for console in (self.dashboard_console, self.full_console):
            console.running(online and value != "stopping")
        labels = {"off": "Apagado", "starting": "Iniciando...", "running": "Servidor en línea",
                  "stopping": "Deteniendo...", "eula": "EULA pendiente"}
        self.footer_text.setText(labels.get(value, value))
        self.footer_text.setStyleSheet("color:#48f69e;" if value == "running" else "color:#ffcf70;" if value != "off" else "color:#becddd;")
        if value == "eula" and not eula_accepted(self.folder):
            self._eula_retry = True

    def on_stats(self, mem, cpu):
        self.status_panel.update_stats(mem, cpu, self.profile)

    def on_players(self, amount):
        maximum = read_properties(self.folder).get("max-players", str(self.profile.get("max_players", 20)))
        self.status_panel.people.setText(f"{amount} / {maximum}")

    def on_finished(self, code):
        self.run_btn.setEnabled(not self._busy)
        if self._eula_retry and not self.engine.active:
            self._eula_retry = False
            QTimer.singleShot(300, self.prompt_eula_and_restart)

    def prompt_eula_and_restart(self):
        if not eula_accepted(self.folder):
            self.append_log("Minecraft solicitó la EULA. Puedes aceptarla y reintentar.", "warn")
            self.start_server()

    # -------- Safe import & file explorer --------
    def choose_import(self):
        if self.engine.active or self._busy:
            self.warn("Detén el servidor antes de importar para evitar conflictos con archivos abiertos.")
            return
        dialog = QFileDialog(self, "Importar JAR, ZIP o archivos del servidor")
        dialog.setFileMode(QFileDialog.FileMode.ExistingFiles)
        dialog.setNameFilters(["Servidores y mundos (*.jar *.zip *.json *.dat *.properties *.yml *.yaml *.toml *.txt *.bat *.cmd *.sh)", "Todos los archivos (*)"])
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.import_files(dialog.selectedFiles())

    def choose_import_folder(self):
        if self.engine.active or self._busy:
            self.warn("Detén el servidor antes de importar una carpeta.")
            return
        directory = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta del servidor o mundo", str(Path.home()))
        if directory:
            self.import_files([directory])

    def import_files(self, paths: list[str]):
        if self.engine.active or self._busy:
            self.warn("El servidor debe estar apagado antes de importar.")
            return
        paths = [Path(p) for p in paths]
        if not paths:
            return
        folder = self.folder

        def imported(result):
            names = ", ".join(p.name for p in result[:6]) or "No se copiaron archivos"
            # Dragging a new server JAR should make it the active one immediately.
            direct_jars = [p for p in result if p.is_file() and p.parent.resolve() == folder.resolve()
                           and p.suffix.lower() == ".jar" and "installer" not in p.name.lower()]
            if direct_jars:
                self.profile["jar"] = direct_jars[0].name
                self.profile["mode"] = "jar"
                self.profile["required_java"] = None
                self.profile["version"] = "Auto-detect"
                self.store.save()
            self.append_log(f"Importación completada: {names}", "success")
            self.refresh_files()
            self.update_jar_choices()
            self.populate_settings()
            self.status_panel.update_profile(self.profile, self.folder)
            self.update_java_status()
            QMessageBox.information(self, "Importación terminada", f"Archivos incorporados en:\n{folder}\n\n{names}")

        def fail_with_overwrite(error):
            if error.startswith("FileExistsError:"):
                if self.confirm("Archivo existente", f"{error}\n\n¿Quieres sobrescribir archivos existentes? (Los archivos anteriores podrían perderse)"):
                    self.run_job("Importar sobrescribiendo", import_paths, paths, folder, True, on_result=imported)
            else:
                self.fail(error)
        self.run_job("Importando archivos", import_paths, paths, folder, False,
                     on_result=imported, on_error=fail_with_overwrite)

    def refresh_files(self):
        folder = self.folder
        folder.mkdir(parents=True, exist_ok=True)
        self.files_path.setText(str(folder))
        root = self.file_model.setRootPath(str(folder))
        self.file_tree.setRootIndex(root)
        self.file_tree.setColumnHidden(2, False)

    def selected_file_path(self) -> Path | None:
        index = self.file_tree.currentIndex()
        if not index.isValid():
            return None
        path = Path(self.file_model.filePath(index))
        if not path.exists() or not path.resolve().is_relative_to(self.folder.resolve()):
            return None
        return path

    def open_selected_file(self, *unused):
        item = self.selected_file_path() or self.folder
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(item)))

    def new_folder(self):
        if self.engine.active or self._busy:
            self.warn("Detén el servidor antes de modificar archivos.")
            return
        parent = self.selected_file_path()
        if parent is None or not parent.is_dir():
            parent = self.folder
        name, ok = QInputDialog.getText(self, "Nueva carpeta", "Nombre:")
        if ok and name.strip():
            # A single folder name, not a user-controlled relative path.
            name = name.strip()
            if name in (".", "..") or Path(name).name != name or "/" in name or "\\" in name:
                self.warn("Escribe un nombre de carpeta, no una ruta.")
                return
            try:
                (parent / name).mkdir(exist_ok=False)
                self.refresh_files()
            except OSError as ex:
                self.fail(str(ex))

    def delete_selected_file(self):
        if self.engine.active or self._busy:
            self.warn("El servidor debe estar apagado antes de borrar archivos.")
            return
        path = self.selected_file_path()
        if not path or path.resolve() == self.folder.resolve():
            self.warn("Selecciona un archivo o subcarpeta del servidor.")
            return
        if not self.confirm("Enviar a la papelera", f"¿Mover «{path.name}» a la papelera del sistema?"):
            return
        try:
            from send2trash import send2trash
            send2trash(str(path))
            self.append_log(f"Enviado a la papelera: {path.name}", "warn")
            self.refresh_files()
            self.update_jar_choices()
        except Exception as ex:
            self.fail(f"No se pudo mover a la papelera: {ex}")

    def use_selected_jar(self):
        if self.engine.active:
            self.warn("Detén el servidor para cambiar el archivo de inicio.")
            return
        path = self.selected_file_path()
        if not path or path.suffix.lower() != ".jar" or path.parent.resolve() != self.folder.resolve():
            self.warn("Selecciona un archivo .jar ubicado directamente en la carpeta del servidor.")
            return
        if "installer" in path.name.lower():
            self.warn("Este archivo parece ser un instalador, no un servidor ejecutable.")
            return
        self.profile["jar"] = path.name
        self.profile["mode"] = "jar"
        self.profile["required_java"] = None
        self.store.save()
        self.update_jar_choices()
        self.populate_settings()
        self.status_panel.update_profile(self.profile, self.folder)
        self.update_java_status()
        self.append_log(f"Archivo de inicio seleccionado: {path.name}", "success")

    # -------- Versions: official Mojang metadata, SHA-1 verification --------
    def get_versions(self):
        if self._busy:
            return
        self.version_info.setText("Consultando el manifiesto oficial de Mojang...")
        def received(versions):
            self.versions = versions
            self.fill_versions()
            self.version_info.setText(f"{len(versions)} versiones del manifiesto oficial. Elige una versión e instálala.")
        self.run_job("Consultando versiones", fetch_versions, on_result=received)

    def fill_versions(self, *unused):
        search = self.search_version.text().strip().lower()
        include_snapshots = self.snapshots.isChecked()
        filtered = [v for v in self.versions
                    if (include_snapshots or v.get("type") == "release") and search in v.get("id", "").lower()]
        self.version_table.setRowCount(min(350, len(filtered)))
        for row, version in enumerate(filtered[:350]):
            id_item = QTableWidgetItem(version.get("id", ""))
            id_item.setData(Qt.ItemDataRole.UserRole, version)
            typ = QTableWidgetItem("Estable" if version.get("type") == "release" else "Snapshot")
            published = version.get("releaseTime", "")[:10]
            date_item = QTableWidgetItem(published)
            for i, item in enumerate((id_item, typ, date_item)):
                self.version_table.setItem(row, i, item)
        if filtered:
            self.version_table.selectRow(0)

    def install_version(self, *unused):
        if self.engine.active or self._busy:
            self.warn("Para instalar una versión, primero apaga el servidor.")
            return
        selected = self.version_table.currentRow()
        if selected < 0 or self.version_table.item(selected, 0) is None:
            self.warn("Selecciona una versión de la tabla.")
            return
        version = self.version_table.item(selected, 0).data(Qt.ItemDataRole.UserRole)
        if not version:
            return
        if not self.confirm("Descargar servidor Vanilla", f"Versión: {version['id']}\nDestino: {self.folder}\n\nSe descargará el archivo oficial del servidor y se verificará su SHA-1. No incluye Java. ¿Continuar?"):
            return
        folder = self.folder
        self.version_info.setText(f"Descargando Vanilla {version['id']}...")
        task = Task(lambda: download_vanilla(version, folder, callback=lambda done, total: task.signals.progress.emit(round(done / total * 100) if total else 0)))
        task.signals.progress.connect(lambda percent: self.version_info.setText(f"Descargando {version['id']}: {percent}%"))
        def finished(result):
            jar, required_java = result
            if self.folder.resolve() != folder.resolve():
                return
            self.profile["jar"] = jar.name
            self.profile["mode"] = "jar"
            self.profile["version"] = version["id"]
            self.profile["required_java"] = required_java
            self.store.save()
            self.update_jar_choices()
            self.populate_settings()
            self.refresh_files()
            self.status_panel.update_profile(self.profile, self.folder)
            self.update_java_status()
            self.version_info.setText(f"Instalado: {jar.name}  •  Java requerido: {required_java or 'no especificado'}")
            self.append_log(f"Vanilla {version['id']} instalado y SHA-1 verificado. Requiere Java {required_java or '?'}.", "success")
            QMessageBox.information(self, "Instalación lista", f"Servidor instalado:\n{jar}\n\nJava mínimo: {required_java or 'Consulta la documentación'}\n\nPulsa «Ejecutar servidor» en Dashboard.")
        self.start_task("Descargando Vanilla", task, finished)

    # -------- Backups --------
    def refresh_backups(self):
        self.backup_list.clear()
        backups = sorted(self.backup_folder.glob("backup_*.zip"), reverse=True) if self.backup_folder.exists() else []
        for path in backups:
            item_text = f"{path.name}    ·    {readable_size(path.stat().st_size)}"
            self.backup_list.addItem(item_text)
            self.backup_list.item(self.backup_list.count() - 1).setData(Qt.ItemDataRole.UserRole, str(path))
        self.backup_hint.setText(f"{len(backups)} respaldo(s) en {self.backup_folder}")

    def make_backup(self):
        if self.engine.active or self._busy:
            self.warn("Apaga el servidor antes de crear una copia consistente.")
            return
        if not self.folder.exists():
            self.warn("La carpeta del servidor no existe.")
            return
        def done(path):
            self.refresh_backups()
            self.append_log(f"Respaldo creado: {path.name} ({readable_size(path.stat().st_size)})", "success")
            QMessageBox.information(self, "Respaldo completado", f"Copia guardada en:\n{path}")
        self.run_job("Creando respaldo", make_backup, self.folder, self.backup_folder, on_result=done)

    def restore_backup(self):
        if self.engine.active or self._busy:
            self.warn("El servidor debe estar apagado antes de restaurar.")
            return
        selected = self.backup_list.currentItem()
        if not selected:
            self.warn("Selecciona un archivo de respaldo.")
            return
        zip_path = Path(selected.data(Qt.ItemDataRole.UserRole))
        if not zip_path.is_file():
            self.warn("No existe la copia seleccionada.")
            return
        if not self.confirm("Restaurar copia de seguridad", f"Se copiarán archivos desde:\n{zip_path.name}\n\na:\n{self.folder}\n\nSe sobrescribirán archivos con el mismo nombre. Se creará antes una copia de seguridad automática del estado actual. ¿Continuar?"):
            return
        def restore_with_snapshot():
            safety_copy = make_backup(self.folder, self.backup_folder)
            changes = restore_backup(zip_path, self.folder)
            return safety_copy, changes
        def done(result):
            safety_copy, changes = result
            self.refresh_files()
            self.refresh_backups()
            self.update_jar_choices()
            self.status_panel.update_profile(self.profile, self.folder)
            self.update_java_status()
            self.append_log(f"Restauración terminada ({len(changes)} elementos). Respaldo previo: {safety_copy.name}", "success")
            QMessageBox.information(self, "Restauración terminada", f"Archivos restaurados: {len(changes)}\n\nCopia de protección previa:\n{safety_copy.name}")
        self.run_job("Restaurando servidor", restore_with_snapshot, on_result=done)

    def open_backups(self):
        self.backup_folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.backup_folder)))

    # -------- Settings & server.properties --------
    def populate_settings(self):
        p = self.profile
        props = read_properties(self.folder)
        self.server_name.setText(p.get("name", "Servidor"))
        self.server_directory.setText(p["path"])
        self.mode.setCurrentIndex(max(self.mode.findData(p.get("mode", "auto")), 0))
        self.jar_choice.clear()
        self.jar_choice.addItem("")
        for jar in jar_candidates(self.folder):
            self.jar_choice.addItem(jar.name)
        if p.get("jar"):
            self.jar_choice.setCurrentText(p["jar"])
        self.script_choice.clear()
        self.script_choice.addItem("")
        for script in launch_scripts(self.folder):
            self.script_choice.addItem(script.name)
        if p.get("script"):
            self.script_choice.setCurrentText(p["script"])
        self.custom_args.setText(p.get("custom_args", ""))
        self.java_path.setText(p.get("java", ""))
        self.refresh_java_choices()
        self.update_java_status()
        self.xms.setValue(int(p.get("xms", 1024)))
        self.xmx.setValue(int(p.get("xmx", 4096)))
        self.port_spin.setValue(int(props.get("server-port", p.get("port", 25565))))
        self.max_players_spin.setValue(int(props.get("max-players", p.get("max_players", 20))))
        self.motd.setText(props.get("motd", "Un servidor de Minecraft"))
        self.online_mode.setChecked(props.get("online-mode", "true").lower() == "true")
        self.pvp.setChecked(props.get("pvp", "true").lower() == "true")
        self.gamemode.setCurrentText(props.get("gamemode", "survival"))
        self.difficulty.setCurrentText(props.get("difficulty", "easy"))
        self.world_name.setText(props.get("level-name", "world"))

    def save_settings(self):
        if self.engine.active or self._busy:
            self.warn("Detén el servidor antes de guardar la configuración.")
            return
        if self.xms.value() > self.xmx.value():
            self.warn("La RAM mínima no puede ser mayor que la RAM máxima.")
            return
        if not self.server_name.text().strip():
            self.warn("Escribe un nombre para el perfil.")
            return
        world = self.world_name.text().strip()
        if not world or world in (".", "..") or "/" in world or "\\" in world:
            self.warn("El nombre del mundo debe ser un nombre de carpeta válido.")
            return
        p = self.profile
        old_jar = p.get("jar", "")
        p.update({"name": self.server_name.text().strip(),
                  "mode": self.mode.currentData(), "jar": self.jar_choice.currentText().strip(),
                  "script": self.script_choice.currentText().strip(),
                  "custom_args": self.custom_args.text().strip(),
                  "java": self.java_path.text().strip().strip('"'),
                  "xms": self.xms.value(), "xmx": self.xmx.value(),
                  "port": self.port_spin.value(), "max_players": self.max_players_spin.value()})
        if old_jar != p["jar"]:
            p["required_java"] = None
            p["version"] = "Auto-detect"
        updates = {"server-port": str(self.port_spin.value()),
                   "max-players": str(self.max_players_spin.value()),
                   "motd": self.motd.text().replace("\n", " ").replace("\r", " "),
                   "online-mode": str(self.online_mode.isChecked()).lower(),
                   "pvp": str(self.pvp.isChecked()).lower(),
                   "gamemode": self.gamemode.currentText(),
                   "difficulty": self.difficulty.currentText(),
                   "level-name": world}
        try:
            update_properties(self.folder, updates)
            self.store.save()
            self.load_profile()
            self.append_log("Configuración guardada en config.json y server.properties.", "success")
            QMessageBox.information(self, "Configuración guardada", "Se guardó la configuración. Los cambios se aplican al iniciar el servidor.")
        except Exception as ex:
            self.fail(f"No se pudo guardar: {ex}")

    # -------- Background jobs --------
    def run_job(self, label: str, fn, *args, on_result=None, on_error=None):
        task = Task(fn, *args)
        self.start_task(label, task, on_result, on_error)

    def start_task(self, label: str, task: Task, on_result=None, on_error=None):
        self._jobs.add(task)
        self._busy += 1
        self.run_btn.setEnabled(False)
        self.profile_combo.setEnabled(False)
        self.append_log(f"{label}...", "system")
        if on_result:
            task.signals.result.connect(on_result)
        if on_error:
            task.signals.error.connect(on_error)
        else:
            task.signals.error.connect(self.fail)
        task.signals.finished.connect(lambda: self._job_finished(task))
        QThreadPool.globalInstance().start(task)

    def _job_finished(self, task):
        self._jobs.discard(task)
        self._busy = max(0, self._busy - 1)
        if not self._busy:
            self.profile_combo.setEnabled(True)
            self.run_btn.setEnabled(not self.engine.active)

    # -------- Dialogs, errors, shutdown --------
    def warn(self, message: str):
        QMessageBox.warning(self, "BlockServer GUI", message)

    def fail(self, message: str):
        self.append_log(message, "error")
        QMessageBox.critical(self, "Error — BlockServer GUI", message)

    def confirm(self, title: str, message: str) -> bool:
        return QMessageBox.question(self, title, message, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                    QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes

    def closeEvent(self, event: QCloseEvent):
        if self._busy:
            self.warn("Hay una copia, importación o descarga en curso. Finaliza esa operación antes de cerrar.")
            event.ignore()
            return
        if self.engine.active:
            if not self.confirm("Cerrar aplicación", "El servidor está encendido. ¿Deseas apagarlo de forma segura y salir?"):
                event.ignore()
                return
            self.engine.shutdown_blocking()
        event.accept()
