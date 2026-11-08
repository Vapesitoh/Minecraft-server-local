"""Non-blocking server subprocess management using QProcess."""
from __future__ import annotations
import codecs
import datetime as dt
import os
import re

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

try:
    import psutil
except ImportError:
    psutil = None

ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
JOIN_RE = re.compile(r"(?:\]:\s*|\s)([A-Za-z0-9_]{3,16}) joined the game", re.I)
LEAVE_RE = re.compile(r"(?:\]:\s*|\s)([A-Za-z0-9_]{3,16}) left the game", re.I)
READY_RE = re.compile(r"Done\s*\([^)]*\)!\s*For help", re.I)
EULA_RE = re.compile(r"(agree to the EULA|agree to the eula|eula\.txt|EULA agreement)", re.I)


class ServerEngine(QObject):
    line = Signal(str, str)         # type: 'system', 'info', 'warn', 'error', 'success'
    status = Signal(str)           # off, starting, running, stopping, eula
    stats = Signal(float, float)   # ram GB, cpu percent
    players = Signal(int)
    ended = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process: QProcess | None = None
        self.state = "off"
        self.player_names: set[str] = set()
        self.ready = False
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._buffer = ""
        self._ps = None
        self._restart_request = False
        self._restart_args = None
        self._poll = QTimer(self)
        self._poll.setInterval(1500)
        self._poll.timeout.connect(self._measure)
        self._poll.start()

    @property
    def active(self) -> bool:
        return self.process is not None and self.process.state() != QProcess.ProcessState.NotRunning

    def start(self, executable: str, arguments: list[str], cwd: str):
        if self.active:
            raise RuntimeError("El servidor ya está encendido")
        self._restart_request = False
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self._buffer = ""
        self.player_names.clear()
        self.players.emit(0)
        self.ready = False
        self._ps = None
        if self.process is not None:
            self.process.deleteLater()
        self.process = QProcess(self)
        self.process.setWorkingDirectory(cwd)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_data)
        self.process.started.connect(self._started)
        self.process.finished.connect(self._finished)
        self.process.errorOccurred.connect(self._error)
        self._set_state("starting")
        self.line.emit(f"Iniciando en: {cwd}", "system")
        self.line.emit(f"Comando: {executable} {' '.join(arguments)}", "system")
        self.process.start(executable, arguments)

    def _started(self):
        self.line.emit(f"Proceso iniciado (PID {self.process.processId()}).", "success")
        self._set_state("starting")
        if psutil:
            try:
                self._ps = psutil.Process(int(self.process.processId()))
                self._ps.cpu_percent(None)
            except (psutil.Error, ValueError):
                self._ps = None

    def _set_state(self, value: str):
        self.state = value
        self.status.emit(value)

    def _read_data(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput())
        self._buffer += self._decoder.decode(data)
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self._consume(line.rstrip("\r"))
        if len(self._buffer) > 200_000:
            self._consume(self._buffer[:100_000])
            self._buffer = self._buffer[100_000:]

    def _consume(self, raw: str):
        clean = ANSI_RE.sub("", raw).strip()
        if not clean:
            return
        low = clean.lower()
        if "error" in low or "exception" in low or "failed" in low:
            level = "error"
        elif "warn" in low:
            level = "warn"
        elif "done (" in low or "success" in low:
            level = "success"
        else:
            level = "info"
        self.line.emit(clean, level)
        match = JOIN_RE.search(clean)
        if match:
            self.player_names.add(match.group(1))
            self.players.emit(len(self.player_names))
        match = LEAVE_RE.search(clean)
        if match:
            self.player_names.discard(match.group(1))
            self.players.emit(len(self.player_names))
        if not self.ready and READY_RE.search(clean):
            self.ready = True
            self._set_state("running")
        if EULA_RE.search(clean) and not self.ready:
            self._set_state("eula")

    def send(self, command: str):
        if not self.active:
            raise RuntimeError("El servidor no está en ejecución")
        command = command.strip()
        if command:
            self.process.write((command + "\n").encode("utf-8"))
            self.line.emit(f"> {command}", "command")

    def stop(self):
        if not self.active:
            return
        self._set_state("stopping")
        self.line.emit("Solicitando cierre seguro ('stop')...", "system")
        try:
            self.send("stop")
        except RuntimeError:
            pass
        QTimer.singleShot(16000, self._stop_timeout)

    def _stop_timeout(self):
        if self.active and self.state == "stopping":
            self.line.emit("El servidor no respondió a 'stop'; cerrando el proceso.", "warn")
            self.process.terminate()
            QTimer.singleShot(3000, self._kill_timeout)

    def _kill_timeout(self):
        if self.active and self.state == "stopping":
            self.line.emit("El proceso sigue activo. Forzando cierre.", "error")
            self.process.kill()

    def restart(self, executable: str, arguments: list[str], cwd: str):
        if not self.active:
            self.start(executable, arguments, cwd)
            return
        self._restart_request = True
        self._restart_args = (executable, arguments, cwd)
        self.stop()

    def _finished(self, code: int, exit_status):
        if self.process:
            self._read_data()
        if self._buffer:
            self._consume(self._buffer)
        self._buffer = ""
        self._ps = None
        self.stats.emit(0, 0)
        self.players.emit(0)
        self.player_names.clear()
        self._set_state("off")
        self.line.emit(f"Proceso finalizado. Código de salida: {code}", "system" if code == 0 else "error")
        self.ended.emit(code)
        if self._restart_request and self._restart_args:
            args = self._restart_args
            self._restart_request = False
            self._restart_args = None
            QTimer.singleShot(650, lambda: self.start(*args))

    def _error(self, error):
        if self.process:
            self.line.emit("Error del proceso: " + self.process.errorString(), "error")
        if not self.active:
            self._set_state("off")

    def _measure(self):
        if not self.active or not psutil:
            self.stats.emit(0, 0)
            return
        if self._ps is None:
            try:
                self._ps = psutil.Process(int(self.process.processId()))
                self._ps.cpu_percent(None)
            except (psutil.Error, ValueError):
                self.stats.emit(0, 0)
                return
        try:
            all_p = [self._ps] + self._ps.children(recursive=True)
            rss = 0
            cpu = 0
            for proc in all_p:
                try:
                    rss += proc.memory_info().rss
                    cpu += proc.cpu_percent(None)
                except psutil.Error:
                    continue
            cpu = min(100.0, cpu / max(1, psutil.cpu_count() or 1))
            self.stats.emit(rss / 1024 ** 3, cpu)
        except (psutil.Error, ValueError):
            self.stats.emit(0, 0)

    def shutdown_blocking(self):
        if not self.active:
            return
        try:
            self.send("stop")
            if not self.process.waitForFinished(9000):
                self.process.terminate()
                if not self.process.waitForFinished(2000):
                    self.process.kill()
                    self.process.waitForFinished(2000)
        except Exception:
            if self.active:
                self.process.kill()
                self.process.waitForFinished(2000)
