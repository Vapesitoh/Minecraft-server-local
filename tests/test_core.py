from pathlib import Path
import hashlib
import io
import json
import zipfile

import pytest

from blockserver import core


def test_profile_store_persists(tmp_path):
    store = core.Store(tmp_path / "config" / "config.json", tmp_path / "servers")
    assert len(store.profiles) == 1
    second = store.create("Prueba: Paper")
    assert second["name"] == "Prueba_ Paper"
    assert Path(second["path"]).is_dir()
    again = core.Store(tmp_path / "config" / "config.json", tmp_path / "servers")
    assert again.selected["id"] == second["id"]
    again.remove(second["id"])
    assert len(again.profiles) == 1


def test_eula_requires_explicit_true(tmp_path):
    assert not core.eula_accepted(tmp_path)
    with pytest.raises(ValueError):
        core.accept_eula(tmp_path, "yes")
    core.accept_eula(tmp_path, "true")
    assert core.eula_accepted(tmp_path)
    assert "eula=true" in (tmp_path / "eula.txt").read_text()
    core.accept_eula(tmp_path, "true")
    assert (tmp_path / "eula.txt").read_text().count("eula=true") == 1


def test_eula_false_is_not_accepted(tmp_path):
    (tmp_path / "eula.txt").write_text("# EULA=true comment\neula=false\n")
    assert not core.eula_accepted(tmp_path)


def test_jar_auto_detect_skips_installers(tmp_path):
    for name in ("forge-installer.jar", "custom.jar", "paper-1.21.jar", "server.jar", "neoforge-installer.jar"):
        (tmp_path / name).touch()
    jars = core.jar_candidates(tmp_path)
    assert [p.name for p in jars] == ["server.jar", "paper-1.21.jar", "custom.jar"]


def test_launch_jar_arguments(tmp_path):
    jar = tmp_path / "paper.jar"
    jar.write_bytes(b"demo")
    p = core.profile_default("Test", tmp_path)
    p.update({"jar": "paper.jar", "java": "/custom/java", "xms": 2048, "xmx": 8192})
    exe, args, description = core.build_launch(p)
    assert exe == "/custom/java"
    assert args == ["-Xms2048M", "-Xmx8192M", "-jar", "paper.jar", "nogui"]


def test_launch_blocks_parent_traversal(tmp_path):
    (tmp_path.parent / "external.jar").touch()
    p = core.profile_default("Test", tmp_path)
    p.update({"jar": "../external.jar"})
    with pytest.raises(ValueError):
        core.build_launch(p)


def test_launch_script_linux(tmp_path):
    (tmp_path / "run.sh").write_text("#!/bin/sh\nexit 0")
    p = core.profile_default("Test", tmp_path)
    exe, args, description = core.build_launch(p)
    assert exe == "/bin/bash"
    assert args == [str(tmp_path / "run.sh")]


def test_zip_rejects_traversal(tmp_path):
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("../../bad.txt", "evil")
    with pytest.raises(ValueError):
        core.extract_archive(archive, tmp_path / "server")
    assert not (tmp_path / "bad.txt").exists()


def test_zip_rejects_symlinks(tmp_path):
    archive = tmp_path / "links.zip"
    with zipfile.ZipFile(archive, "w") as z:
        info = zipfile.ZipInfo("evil")
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        z.writestr(info, "../../outside")
    with pytest.raises(ValueError):
        core.extract_archive(archive, tmp_path / "server")


def test_zip_pack_flattens_wrapper(tmp_path):
    archive = tmp_path / "pack.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("MyPack/server.jar", "abc")
        z.writestr("MyPack/plugins/config.yml", "test")
    dest = tmp_path / "server"
    core.extract_archive(archive, dest)
    assert (dest / "server.jar").read_text() == "abc"
    assert (dest / "plugins" / "config.yml").is_file()


def test_zip_preserves_world_wrapper(tmp_path):
    archive = tmp_path / "world.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("MyWorld/level.dat", "demo")
        z.writestr("MyWorld/region/r.0.0.mca", "data")
    dest = tmp_path / "server"
    core.extract_archive(archive, dest)
    assert (dest / "MyWorld" / "level.dat").is_file()


def test_zip_conflict_does_not_overwrite(tmp_path):
    dest = tmp_path / "server"
    dest.mkdir()
    (dest / "server.jar").write_text("before")
    archive = tmp_path / "file.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("server.jar", "after")
    with pytest.raises(FileExistsError):
        core.extract_archive(archive, dest, overwrite=False)
    assert (dest / "server.jar").read_text() == "before"
    core.extract_archive(archive, dest, overwrite=True)
    assert (dest / "server.jar").read_text() == "after"


def test_properties_update_preserves_comments(tmp_path):
    (tmp_path / "server.properties").write_text("# keep\nserver-port=25565\nmax-players=10\n")
    core.update_properties(tmp_path, {"server-port": "25566", "online-mode": "true"})
    text = (tmp_path / "server.properties").read_text()
    assert "# keep" in text
    assert text.count("server-port=") == 1
    assert core.read_properties(tmp_path)["server-port"] == "25566"
    assert core.read_properties(tmp_path)["online-mode"] == "true"


def test_backup_restore(tmp_path):
    folder = tmp_path / "server"
    folder.mkdir()
    (folder / "world").mkdir()
    (folder / "world" / "level.dat").write_bytes(b"original")
    archive = core.make_backup(folder, tmp_path / "backups")
    assert archive.is_file()
    (folder / "world" / "level.dat").write_bytes(b"modified")
    core.restore_backup(archive, folder)
    assert (folder / "world" / "level.dat").read_bytes() == b"original"


def test_source_secure_urls(monkeypatch, tmp_path):
    with pytest.raises(ValueError):
        core.request_json("http://host.invalid")
    with pytest.raises(ValueError):
        core.vanilla_metadata({"url": "https://evil.test/data.json"})


def test_download_vanilla_verifies_hash(monkeypatch, tmp_path):
    data = b"fake jar bytes"
    sha1 = hashlib.sha1(data).hexdigest()
    metadata = {"downloads": {"server": {"url": "https://piston-data.mojang.com/example/server.jar", "sha1": sha1, "size": len(data)}},
                "javaVersion": {"majorVersion": 25}}
    monkeypatch.setattr(core, "vanilla_metadata", lambda ver: metadata)
    class FakeResponse(io.BytesIO):
        headers = {"Content-Length": str(len(data))}
        def __enter__(self): return self
        def __exit__(self, *args): self.close()
    monkeypatch.setattr(core.urllib.request, "urlopen", lambda req, timeout: FakeResponse(data))
    result, java_major = core.download_vanilla({"id": "26.3"}, tmp_path)
    assert result.read_bytes() == data
    assert java_major == 25
    with pytest.raises(FileExistsError):
        core.download_vanilla({"id": "26.3"}, tmp_path)


def test_reject_folder_with_symlink(tmp_path):
    folder = tmp_path / "source"
    folder.mkdir()
    (folder / "external").symlink_to(tmp_path / "outside")
    with pytest.raises(ValueError):
        core.import_paths([folder], tmp_path / "destination")


def test_auto_forge_prefers_existing_run_script(tmp_path):
    (tmp_path / "libraries").mkdir()
    (tmp_path / "forge-1.21.1.jar").touch()
    (tmp_path / "run.sh").write_text("#!/bin/sh\nexit 0")
    profile = core.profile_default("Forge", tmp_path)
    executable, args, text = core.build_launch(profile)
    assert executable == "/bin/bash"
    assert text == "Script: run.sh"


def test_java_candidates_find_java_home_even_if_not_in_path(tmp_path, monkeypatch):
    java = tmp_path / "my-jdk" / "bin" / ("java.exe" if core.os.name == "nt" else "java")
    java.parent.mkdir(parents=True)
    java.touch()
    monkeypatch.setenv("JAVA_HOME", str(java.parent.parent))
    monkeypatch.setenv("PATH", "")
    assert str(java.resolve()) in core.java_candidates()


def test_scan_java_reports_multiple_installations_sorted(monkeypatch):
    java8 = core.JavaInfo("/jdk8/java", 8, "Java 8", 32)
    java21 = core.JavaInfo("/jdk21/java", 21, "Java 21", 64)
    java17 = core.JavaInfo("/jdk17/java", 17, "Java 17", 64)
    monkeypatch.setattr(core, "java_candidates", lambda: [java8.path, java21.path, java17.path, "/bad/java"])
    monkeypatch.setattr(core, "java_info", lambda p: {
        java8.path: java8, java21.path: java21, java17.path: java17,
        "/bad/java": core.JavaInfo("/bad/java", None, "Not found", None),
    }[p])
    assert [j.version for j in core.scan_java()] == [21, 17, 8]
    assert core.preferred_java(core.scan_java(), 17).path == java21.path
    assert core.preferred_java(core.scan_java(), 22) is None


def test_preferred_java_prioritizes_64_bit():
    variants = [core.JavaInfo("/32/java", 25, "Java 25", 32),
                core.JavaInfo("/64/java", 21, "Java 21", 64)]
    assert core.preferred_java(variants).path == "/64/java"
    assert core.preferred_java(variants, 25).path == "/32/java"


def test_launch_auto_chooses_compatible_java(monkeypatch, tmp_path):
    (tmp_path / "server.jar").touch()
    monkeypatch.setattr(core, "scan_java", lambda: [
        core.JavaInfo("/jdk8/java", 8, "8", 64),
        core.JavaInfo("/jdk21/java", 21, "21", 64)])
    p = core.profile_default("Test", tmp_path)
    p["required_java"] = 21
    assert core.build_launch(p)[0] == "/jdk21/java"
    p["required_java"] = 25
    with pytest.raises(ValueError, match="Java 25"):
        core.build_launch(p)
    p["java"] = "/user/java"
    assert core.build_launch(p)[0] == "/user/java"


def test_java_info_parses_32bit_legacy_and_modern(monkeypatch):
    from subprocess import CompletedProcess
    monkeypatch.setattr(core.subprocess, "run", lambda *a, **k: CompletedProcess(
        args=a, returncode=0, stdout="", stderr='java version "1.8.0_511"\\nJava HotSpot(TM) Client VM'))
    old = core.java_info("java8")
    assert old.version == 8
    assert old.bits == 32
    monkeypatch.setattr(core.subprocess, "run", lambda *a, **k: CompletedProcess(
        args=a, returncode=0, stdout='openjdk version "21.0.5"\\nOpenJDK 64-Bit Server VM', stderr=""))
    modern = core.java_info("java21")
    assert modern.version == 21
    assert modern.bits == 64
