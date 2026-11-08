"""Pure Python server workspace, safe imports, Java discovery, configuration & backups.
No GUI import: the functions in this module can be tested independently.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass

APP_NAME = "BlockServer GUI"
MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
MAX_IMPORT_FILES = 100_000
MAX_IMPORT_UNCOMPRESSED = 40 * 1024**3


def readable_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} TB"


def safe_name(value: str) -> str:
    value = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", value).strip(" .")
    return value[:80] or "Servidor"


def profile_default(name: str, path: Path) -> dict:
    return {
        "id": str(uuid.uuid4()), "name": name, "path": str(path), "java": "",
        "jar": "", "mode": "auto", "script": "", "custom_args": "",
        "xms": 1024, "xmx": 4096, "port": 25565, "max_players": 20,
        "version": "Auto-detect", "required_java": None,
    }


class Store:
    def __init__(self, config_path: Path, workspace: Path):
        self.file = Path(config_path)
        self.workspace = Path(workspace)
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.data = {"selected": "", "profiles": [], "window": {}}
        if self.file.exists():
            try:
                data = json.loads(self.file.read_text(encoding="utf-8"))
                if isinstance(data, dict) and isinstance(data.get("profiles"), list):
                    self.data.update(data)
            except (OSError, ValueError):
                # Don't overwrite a broken configuration until a user saves changes.
                pass
        if not self.data["profiles"]:
            p = profile_default("Mi servidor", self.workspace / "Mi servidor")
            Path(p["path"]).mkdir(parents=True, exist_ok=True)
            self.data["profiles"] = [p]
            self.data["selected"] = p["id"]
            self.save()

    @property
    def profiles(self) -> list[dict]:
        return self.data["profiles"]

    @property
    def selected(self) -> dict:
        current = next((p for p in self.profiles if p["id"] == self.data["selected"]), None)
        if current is None:
            current = self.profiles[0]
            self.data["selected"] = current["id"]
        return current

    def select(self, profile_id: str) -> None:
        if not any(p["id"] == profile_id for p in self.profiles):
            raise ValueError("Perfil no encontrado")
        self.data["selected"] = profile_id
        self.save()

    def create(self, name: str, directory: Path | None = None) -> dict:
        name = safe_name(name)
        directory = Path(directory) if directory else self.workspace / name
        if any(Path(p["path"]).resolve() == directory.resolve() for p in self.profiles):
            raise ValueError("Ya existe un perfil para esa carpeta")
        directory.mkdir(parents=True, exist_ok=True)
        p = profile_default(name, directory)
        self.profiles.append(p)
        self.data["selected"] = p["id"]
        self.save()
        return p

    def remove(self, profile_id: str) -> None:
        if len(self.profiles) <= 1:
            raise ValueError("Debe existir al menos un perfil")
        self.data["profiles"] = [p for p in self.profiles if p["id"] != profile_id]
        self.data["selected"] = self.data["profiles"][0]["id"]
        self.save()

    def save(self) -> None:
        self.file.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.file.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        tmp.replace(self.file)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def zip_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    infos = zf.infolist()
    if len(infos) > MAX_IMPORT_FILES:
        raise ValueError(f"Archivo con demasiados elementos (máximo {MAX_IMPORT_FILES}).")
    if sum(i.file_size for i in infos) > MAX_IMPORT_UNCOMPRESSED:
        raise ValueError("El ZIP descomprimido supera el límite de 40 GB.")
    for i in infos:
        name = i.filename.replace("\\", "/")
        p = Path(name)
        if not name or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
            raise ValueError("ZIP con rutas absolutas no permitidas")
        if ".." in p.parts:
            raise ValueError("ZIP con intento de salir de la carpeta de destino")
        filetype = (i.external_attr >> 16) & 0o170000
        if filetype == 0o120000:
            raise ValueError("ZIP con enlaces simbólicos no permitidos")
    return infos


def extract_archive(zfile: Path, dest: Path, overwrite: bool = False) -> list[Path]:
    """Extract safely into a staging directory, then merge. No zip-slip/symlinks.
    A single wrapper directory is removed only for obvious server packs.
    """
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zfile) as zf:
        infos = zip_members(zf)
        with tempfile.TemporaryDirectory(prefix="blockserver-unzip-") as tempdir:
            temp = Path(tempdir)
            for info in infos:
                rel = Path(info.filename.replace("\\", "/"))
                target = temp / rel
                if not is_within(target, temp):
                    raise ValueError("Ruta no válida en ZIP")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as src, target.open("wb") as out:
                        shutil.copyfileobj(src, out, 1024 * 1024)
            entries = list(temp.iterdir())
            if len(entries) == 1 and entries[0].is_dir():
                inner = entries[0]
                if any(p.name in ("server.properties", "eula.txt", "run.bat", "run.sh") or
                       p.suffix.lower() == ".jar" for p in inner.iterdir()):
                    entries = list(inner.iterdir())
            # Resolve all file conflicts before beginning the merge.
            for source in entries:
                target = dest / source.name
                if target.exists() and not overwrite:
                    raise FileExistsError(f"Ya existe: {target.name}")
            created: list[Path] = []
            for source in entries:
                target = dest / source.name
                if target.exists():
                    if target.is_dir() and source.is_dir():
                        # Keep old files in the folder; copy recursively with overwrites.
                        shutil.copytree(source, target, dirs_exist_ok=True)
                    else:
                        if target.is_dir():
                            shutil.rmtree(target)
                        else:
                            target.unlink()
                        shutil.move(str(source), str(target))
                else:
                    shutil.move(str(source), str(target))
                created.append(target)
            return created


def import_paths(paths: list[Path], dest: Path, overwrite: bool = False) -> list[Path]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    imported = []
    for src in paths:
        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(str(src))
        if src.resolve() == dest.resolve():
            continue
        if src.is_file() and src.suffix.lower() == ".zip":
            imported.extend(extract_archive(src, dest, overwrite))
            continue
        target = dest / src.name
        if src.is_dir() and is_within(dest, src):
            raise ValueError("No puedes importar una carpeta dentro de sí misma")
        if target.resolve() == src.resolve():
            continue
        if target.exists() and not overwrite:
            raise FileExistsError(f"Ya existe: {target.name}")
        if src.is_symlink():
            raise ValueError("No se pueden importar enlaces simbólicos")
        if src.is_dir():
            # Refuse internal links: following one could copy unrelated host files.
            for root, folders, files in os.walk(src, followlinks=False):
                if any((Path(root) / item).is_symlink() for item in folders + files):
                    raise ValueError("La carpeta incluye enlaces simbólicos; retíralos antes de importarla.")
            shutil.copytree(src, target, dirs_exist_ok=overwrite, symlinks=False)
        else:
            shutil.copy2(src, target)
        imported.append(target)
    return imported


def jar_candidates(folder: Path) -> list[Path]:
    folder = Path(folder)
    jars = [p for p in folder.glob("*.jar") if p.is_file()]
    def score(path: Path):
        name = path.name.lower()
        if "installer" in name or "-sources" in name or "-javadoc" in name:
            return -100
        if name == "server.jar":
            return 120
        if name.startswith(("paper", "purpur", "mohist", "fabric-server", "quilt-server", "spigot", "velocity", "waterfall")):
            return 100
        if "server" in name or name.startswith(("forge-", "neoforge-", "craftbukkit")):
            return 70
        return 20
    return sorted([p for p in jars if score(p) >= 0], key=lambda p: (-score(p), p.name.lower()))


def launch_scripts(folder: Path) -> list[Path]:
    names = ("run.bat", "start.bat", "run.cmd", "start.cmd") if os.name == "nt" else ("run.sh", "start.sh")
    return [folder / name for name in names if (folder / name).is_file()]


def read_properties(folder: Path) -> dict[str, str]:
    file = folder / "server.properties"
    if not file.is_file():
        return {}
    values = {}
    for raw in file.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "!")):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip()
    return values


def update_properties(folder: Path, updates: dict[str, str]) -> None:
    file = folder / "server.properties"
    lines = file.read_text(encoding="utf-8-sig", errors="replace").splitlines() if file.exists() else ["# Minecraft server properties"]
    found = set()
    out = []
    for line in lines:
        if line and not line.lstrip().startswith(("#", "!")) and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in updates:
                if key not in found:
                    out.append(f"{key}={updates[key]}")
                    found.add(key)
                continue
        out.append(line)
    out.extend(f"{k}={v}" for k, v in updates.items() if k not in found)
    file.write_text("\n".join(out) + "\n", encoding="utf-8")


def eula_accepted(folder: Path) -> bool:
    file = folder / "eula.txt"
    if not file.exists():
        return False
    return any(re.fullmatch(r"\s*eula\s*=\s*true\s*", line, re.IGNORECASE)
               for line in file.read_text(encoding="utf-8", errors="replace").splitlines())


def accept_eula(folder: Path, answer: str) -> None:
    if answer.strip() != "true":
        raise ValueError("Debes escribir exactamente true para aceptar.")
    file = folder / "eula.txt"
    lines = file.read_text(encoding="utf-8", errors="replace").splitlines() if file.exists() else ["# Accepted through BlockServer GUI by the server owner."]
    lines = [line for line in lines if not re.match(r"\s*eula\s*=", line, re.I)]
    lines.append("eula=true")
    file.write_text("\n".join(lines) + "\n", encoding="utf-8")


@dataclass
class JavaInfo:
    path: str
    version: int | None
    display: str
    bits: int | None


def java_info(path: str) -> JavaInfo:
    if not path:
        path = "java"
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run([path, "-version"], capture_output=True, text=True,
                                errors="replace", timeout=5, creationflags=flags)
        output = (result.stderr or "") + (result.stdout or "")
        match = re.search(r'version\s+"(?:1\.)?(\d+)', output) or re.search(r'openjdk\s+(?:version\s+)?"?(?:1\.)?(\d+)', output, re.I)
        major = int(match.group(1)) if match else None
        bits = 64 if "64-Bit" in output or "64-bit" in output else (32 if "32-Bit" in output or "Client VM" in output else None)
        description = output.splitlines()[0] if output.strip() else "Java sin información"
        return JavaInfo(path, major, description[:100], bits)
    except (OSError, subprocess.TimeoutExpired):
        return JavaInfo(path, None, "Java no encontrado", None)


def java_candidates() -> list[str]:
    """Find likely installed JDK/JRE executables without scanning complete disks.

    Windows: PATH, JAVA_HOME, standard vendor folders, user JDKs, Registry and
    common package managers. Linux/macOS: JVM system folders and user SDKs.
    The candidates are just paths; use ``scan_java`` to validate them with -version.
    """
    executable = "java.exe" if os.name == "nt" else "java"
    collected: list[str] = []
    seen: set[str] = set()

    def add(candidate: Path | str | None):
        if not candidate:
            return
        path = Path(os.path.expandvars(os.path.expanduser(str(candidate))))
        if path.is_dir():
            path = path / "bin" / executable
        try:
            if not path.is_file():
                return
            resolved = str(path.resolve())
        except (OSError, ValueError):
            return
        key = os.path.normcase(resolved).casefold()
        if key not in seen:
            seen.add(key)
            collected.append(resolved)

    for env_var in ("JAVA_HOME", "JDK_HOME", "JRE_HOME", "GRAALVM_HOME"):
        add(os.environ.get(env_var))

    # All Java executables in PATH, not only shutil.which's first match.
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if directory.strip():
            add(Path(directory.strip('"')) / executable)
    add(shutil.which("java"))

    def scan_parents(*parents: Path):
        for parent in parents:
            if not parent.is_dir():
                continue
            add(parent)
            try:
                for child in parent.iterdir():
                    if child.is_dir():
                        add(child)
                        # e.g. Microsoft's openjdk-21.0.6, SDKMAN 'current'.
                        if child.name.lower() in ("jdk", "jre", "java"):
                            try:
                                for sub in child.iterdir():
                                    if sub.is_dir():
                                        add(sub)
                            except OSError:
                                pass
            except OSError:
                continue

    home = Path.home()
    if os.name == "nt":
        program_roots = [Path(x) for x in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")),
        ) if x]
        vendors = ("Java", "Eclipse Adoptium", "AdoptOpenJDK", "Microsoft",
                   "Amazon Corretto", "Azul Systems", "Zulu", "BellSoft", "GraalVM",
                   "RedHat", "Red Hat", "Semeru", "LibericaJDK", "OpenJDK", "jdk")
        scan_parents(*(root / vendor for root in program_roots[:2] for vendor in vendors))
        scan_parents(home / ".jdks", home / ".gradle" / "jdks",
                     home / "scoop" / "apps" / "openjdk", home / "scoop" / "apps" / "temurin-jdk",
                     Path(os.environ.get("ChocolateyInstall", r"C:\ProgramData\chocolatey")) / "lib",
                     program_roots[-1] / "Programs" / "Eclipse Adoptium",
                     program_roots[-1] / "Programs" / "Java")
        # Registry includes installs that never added Java to PATH.
        try:
            import winreg
            reg_roots = (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER)
            reg_keys = (r"SOFTWARE\JavaSoft\JDK", r"SOFTWARE\JavaSoft\Java Development Kit",
                        r"SOFTWARE\JavaSoft\JRE", r"SOFTWARE\JavaSoft\Java Runtime Environment",
                        r"SOFTWARE\Eclipse Adoptium", r"SOFTWARE\Microsoft\JDK")
            views = (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY)
            for hive in reg_roots:
                for view in views:
                    for key_name in reg_keys:
                        try:
                            with winreg.OpenKey(hive, key_name, 0, winreg.KEY_READ | view) as key:
                                keys = [key]
                                count, _, _ = winreg.QueryInfoKey(key)
                                for index in range(count):
                                    try:
                                        keys.append(winreg.OpenKey(key, winreg.EnumKey(key, index)))
                                    except OSError:
                                        continue
                                for sub in keys:
                                    for field in ("JavaHome", "Path", "InstallationPath"):
                                        try:
                                            value = winreg.QueryValueEx(sub, field)[0]
                                            add(value)
                                        except OSError:
                                            pass
                        except OSError:
                            continue
        except ImportError:
            pass
    elif sys.platform == "darwin":
        scan_parents(Path("/Library/Java/JavaVirtualMachines"),
                     Path("/opt/homebrew/opt"), Path("/usr/local/opt"),
                     home / ".sdkman" / "candidates" / "java", home / ".jdks")
        for base in (Path("/Library/Java/JavaVirtualMachines"), home / "Library/Java/JavaVirtualMachines"):
            if base.is_dir():
                for bundle in base.iterdir():
                    add(bundle / "Contents" / "Home")
    else:
        scan_parents(Path("/usr/lib/jvm"), Path("/usr/java"), Path("/opt/java"),
                     Path("/opt/jdk"), Path("/usr/local/java"), home / ".jdks",
                     home / ".gradle" / "jdks", home / ".sdkman" / "candidates" / "java")
    return collected


def scan_java() -> list[JavaInfo]:
    """Probe all candidates, returning runnable Javas sorted by 64-bit and version."""
    found: list[JavaInfo] = []
    for candidate in java_candidates():
        info = java_info(candidate)
        if info.version is not None:
            found.append(info)
    found.sort(key=lambda j: (j.bits == 64, j.version or 0), reverse=True)
    return found


def preferred_java(installs: list[JavaInfo], minimum: int | None = None) -> JavaInfo | None:
    """Choose a valid runtime, preferring 64-bit; respect Mojang's minimum Java."""
    valid = [j for j in installs if j.version is not None and
             (minimum is None or j.version >= int(minimum))]
    return max(valid, key=lambda j: (j.bits == 64, j.version or 0), default=None)


def find_java() -> list[str]:
    """Backward-compatible path list for existing calls."""
    return java_candidates()


def build_launch(profile: dict) -> tuple[str, list[str], str]:
    folder = Path(profile["path"])
    if not folder.is_dir():
        raise ValueError("No existe la carpeta del servidor")
    mode = profile.get("mode", "auto")
    # Forge / NeoForge modern servers are normally launched through run.bat/run.sh.
    # Prefer their bundled script when a libraries/ runtime directory exists.
    prefer_script = bool(launch_scripts(folder)) and (
        not jar_candidates(folder) or
        ((folder / "libraries").is_dir() and not any(
            p.name.lower().startswith(("paper", "purpur", "fabric", "mohist", "spigot", "vanilla"))
            for p in jar_candidates(folder)))
    )
    if mode == "script" or (mode == "auto" and prefer_script):
        script = folder / (profile.get("script") or launch_scripts(folder)[0].name)
        if not script.is_file() or not is_within(script, folder):
            raise ValueError("Selecciona un script válido dentro de la carpeta del servidor")
        if os.name == "nt":
            if script.suffix.lower() not in (".bat", ".cmd"):
                raise ValueError("En Windows usa scripts .bat o .cmd")
            return "cmd.exe", ["/d", "/c", str(script)], f"Script: {script.name}"
        if script.suffix.lower() != ".sh":
            raise ValueError("En Linux/macOS usa un script .sh")
        return "/bin/bash", [str(script)], f"Script: {script.name}"
    java = profile.get("java", "")
    if not java:
        candidates = scan_java()
        chosen = preferred_java(candidates, profile.get("required_java"))
        # If no suitable installed Java exists, start_server reports the
        # required version; do not silently select an incompatible runtime.
        if not chosen and profile.get("required_java"):
            raise ValueError(f"Este servidor necesita Java {profile['required_java']} o superior. "
                             "No se encontró una instalación compatible. Revisa Ajustes > Java.")
        java = chosen.path if chosen else "java"
    if mode == "custom":
        # Advanced arguments for the java executable. No shell interpretation.
        import shlex
        raw = profile.get("custom_args", "").strip()
        if not raw:
            raise ValueError("Escribe los argumentos personalizados de Java")
        args = shlex.split(raw, posix=(os.name != "nt"))
        jar = profile.get("jar", "") or (jar_candidates(folder)[0].name if jar_candidates(folder) else "")
        args = [a.replace("{jar}", jar).replace("{xms}", str(profile.get("xms", 1024)))
                .replace("{xmx}", str(profile.get("xmx", 4096))) for a in args]
        return java, args, "Java personalizado"
    jarname = profile.get("jar") or (jar_candidates(folder)[0].name if jar_candidates(folder) else "")
    jar = folder / jarname
    if not jar.is_file() or not is_within(jar, folder) or jar.suffix.lower() != ".jar":
        raise ValueError("No se encontró ningún .jar ejecutable. Importa un servidor o instala Vanilla.")
    xms = int(profile.get("xms", 1024))
    xmx = int(profile.get("xmx", 4096))
    if xms <= 0 or xmx < xms:
        raise ValueError("La RAM mínima no puede superar la RAM máxima")
    return java, [f"-Xms{xms}M", f"-Xmx{xmx}M", "-jar", jar.name, "nogui"], f"JAR: {jar.name}"


def make_backup(folder: Path, backup_dir: Path) -> Path:
    folder = folder.resolve()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    filename = backup_dir / f"backup_{stamp}.zip"
    with zipfile.ZipFile(filename, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=4, allowZip64=True) as zf:
        for root, directories, files in os.walk(folder, followlinks=False):
            base = Path(root)
            directories[:] = [d for d in directories if not (base / d).is_symlink()
                               and not is_within(base / d, backup_dir)]
            for filename_part in files:
                path = base / filename_part
                if path.is_symlink() or is_within(path, backup_dir):
                    continue
                zf.write(path, arcname=str(path.relative_to(folder)))
    return filename


def restore_backup(zip_path: Path, folder: Path) -> list[Path]:
    # Restore overlays existing files. Caller must explicitly confirm first.
    return extract_archive(zip_path, folder, overwrite=True)


def request_json(url: str, timeout: int = 20) -> dict:
    if not url.lower().startswith("https://"):
        raise ValueError("Solo se permiten descargas HTTPS")
    request = urllib.request.Request(url, headers={"User-Agent": "BlockServerGUI/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def fetch_versions() -> list[dict]:
    data = request_json(MANIFEST_URL)
    return [v for v in data.get("versions", []) if v.get("type") in ("release", "snapshot")]


def vanilla_metadata(version: dict) -> dict:
    url = version.get("url", "")
    if not url.startswith("https://piston-meta.mojang.com/"):
        raise ValueError("Origen de metadatos no autorizado")
    return request_json(url)


def download_vanilla(version: dict, folder: Path, callback=None) -> tuple[Path, int | None]:
    """Download official vanilla server JAR and verify Mojang SHA-1 before replacing."""
    metadata = vanilla_metadata(version)
    server = metadata.get("downloads", {}).get("server")
    if not server:
        raise ValueError("Esta versión no dispone de servidor oficial descargable.")
    url = server["url"]
    if not url.startswith("https://piston-data.mojang.com/"):
        raise ValueError("Origen de descarga no autorizado")
    folder.mkdir(parents=True, exist_ok=True)
    name = f"vanilla-{safe_name(version['id'])}.jar"
    dest = folder / name
    if dest.exists():
        raise FileExistsError(f"El archivo {name} ya existe; no se sobrescribirá")
    descriptor, temp_path = tempfile.mkstemp(prefix="blockserver-download-", suffix=".tmp", dir=str(folder))
    os.close(descriptor)
    digest = hashlib.sha1()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "BlockServerGUI/1.0"})
        with urllib.request.urlopen(request, timeout=45) as response, open(temp_path, "wb") as out:
            total = int(response.headers.get("Content-Length", "0")) or int(server.get("size", 0))
            received = 0
            while True:
                chunk = response.read(512 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                received += len(chunk)
                if callback:
                    callback(received, total)
        if digest.hexdigest().lower() != server["sha1"].lower():
            raise ValueError("La firma SHA-1 no coincide; se descartó la descarga")
        if server.get("size") is not None and int(server["size"]) != received:
            raise ValueError("Descarga incompleta; tamaño incorrecto")
        os.replace(temp_path, dest)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    required_java = metadata.get("javaVersion", {}).get("majorVersion")
    return dest, int(required_java) if required_java else None
