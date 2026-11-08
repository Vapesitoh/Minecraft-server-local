"""Background functions: network and backup work never freeze the Qt UI."""
from __future__ import annotations
from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class TaskSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int)
    finished = Signal()


class Task(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()
        self.setAutoDelete(False)

    @Slot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        except Exception as ex:
            self.signals.error.emit(f"{type(ex).__name__}: {ex}")
        finally:
            self.signals.finished.emit()
