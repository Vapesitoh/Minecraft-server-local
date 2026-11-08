"""Verifica que los campos numéricos no cambien accidentalmente con scroll."""
from __future__ import annotations

import ast
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_four_numeric_fields_are_wheel_safe():
    """Revisión del código, también cuando Qt no está instalado en CI."""
    module = ast.parse((ROOT / "blockserver" / "ui.py").read_text(encoding="utf-8"))
    desired = {"xms", "xmx", "port_spin", "max_players_spin"}
    found = set()
    for node in ast.walk(module):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        for target in node.targets:
            if isinstance(target, ast.Attribute) and target.attr in desired:
                assert isinstance(node.value.func, ast.Name)
                assert node.value.func.id == "WheelSafeSpinBox"
                found.add(target.attr)
    assert found == desired


def test_wheel_safe_spinbox_ignores_wheel_event():
    module = ast.parse((ROOT / "blockserver" / "controls.py").read_text(encoding="utf-8"))
    classes = {node.name: node for node in module.body if isinstance(node, ast.ClassDef)}
    for cls in ("WheelSafeSpinBox", "WheelSafeDoubleSpinBox"):
        methods = {node.name: node for node in classes[cls].body if isinstance(node, ast.FunctionDef)}
        wheel = methods["wheelEvent"]
        calls = [node for node in ast.walk(wheel) if isinstance(node, ast.Call)]
        assert any(isinstance(c.func, ast.Attribute) and isinstance(c.func.value, ast.Name)
                   and c.func.value.id == "event" and c.func.attr == "ignore" for c in calls)


def test_real_qt_wheel_keyboard_and_typing():
    """Prueba funcional cuando PySide6 está disponible, en modo sin pantalla."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6.QtWidgets", reason="PySide6 no disponible para prueba Qt")
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QKeyEvent, QWheelEvent
    from PySide6.QtWidgets import QApplication
    from blockserver.controls import WheelSafeSpinBox, WheelSafeDoubleSpinBox

    app = QApplication.instance() or QApplication([])
    for cls in (WheelSafeSpinBox, WheelSafeDoubleSpinBox):
        spin = cls()
        spin.setRange(0, 10000)
        spin.setSingleStep(1)
        spin.setValue(512)
        for angle in (120, -120, 240, -240):
            event = QWheelEvent(QPointF(4, 4), QPointF(4, 4), QPoint(0, 0),
                                QPoint(0, angle), Qt.MouseButton.NoButton,
                                Qt.KeyboardModifier.NoModifier,
                                Qt.ScrollPhase.ScrollUpdate, False)
            QApplication.sendEvent(spin, event)
            assert spin.value() == 512
        up = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(spin, up)
        assert spin.value() == 513
        spin.lineEdit().setText("4096")
        spin.interpretText()
        assert spin.value() == 4096
        spin.deleteLater()
