"""Controles numéricos seguros contra cambios por rueda o gestos de scroll.

Las flechas del teclado, los botones de flecha del QSpinBox y la edición directa
mantienen el comportamiento estándar de Qt. Los eventos de rueda se ignoran
para que el QScrollArea contenedor pueda desplazarse sin cambiar los valores.
"""
from __future__ import annotations

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox


class WheelSafeSpinBox(QSpinBox):
    """Campo entero editable por teclado/flechas, pero NO por scroll."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class WheelSafeDoubleSpinBox(QDoubleSpinBox):
    """Misma protección para futuros valores decimales."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()
