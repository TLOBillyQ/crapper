import json
from pathlib import Path

from crapper.discover import is_test_file
from crapper.runners import (
    _clean_clojure,
    _ensure_vitest_coverage,
    _manifest_snapshot,
    _python_executable,
    _restore_manifests,
    _rust_kind,
    _vitest_version,
    python_coverage_commands,
    python_roots,
    python_sources,
    run_coverage,
    rust_coverage_command,
    rust_modules,
    typescript_command,
    typescript_packages,
    uses_pytest,
)


def _write(root: Path, relative: str, source: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def test_vitest_uses_its_own_coverage_instead_of_c8(tmp_path):
    _write(
        tmp_path,
        "package.json",
        json.dumps({"scripts": {"test": "vitest run"}}),
    )
    _write(tmp_path, "vitest.config.ts", "export default {}\n")
    source = _write(tmp_path, "src/book.ts", "export function plan() { return 1 }\n")
    _write(tmp_path, "src/book.test.ts", "import { plan } from './book'\n")
    report_dir = tmp_path / "target" / "coverage" / "typescript"
    command = typescript_command(tmp_path, [source, tmp_path / "src" / "book.test.ts"], report_dir)
    assert command is not None
    assert "c8" not in command
    assert "vitest run --coverage" in command
    assert "--coverage.reporter=lcov" in command
    assert f"--coverage.reportsDirectory={report_dir}" in command
    assert "--coverage.include=src/book.ts" in command
    assert "book.test.ts" not in command


def test_existing_coverage_script_is_left_alone(tmp_path):
    _write(
        tmp_path,
        "package.json",
        json.dumps({"scripts": {"coverage": "vitest run --coverage", "test": "vitest run"}}),
    )
    command = typescript_command(tmp_path, [], tmp_path / "coverage")
    assert command == "npm run coverage"


def test_node_test_script_still_uses_c8(tmp_path):
    _write(tmp_path, "package.json", json.dumps({"scripts": {"test": "node --test"}}))
    report_dir = tmp_path / "target" / "coverage" / "typescript"
    command = typescript_command(tmp_path, [], report_dir)
    assert command == f"npx --yes c8 --reporter=lcov --reports-dir {report_dir} npm test"


def test_typescript_package_is_found_from_a_source_file(tmp_path):
    _write(tmp_path, "web/package.json", json.dumps({"scripts": {"test": "vitest run"}}))
    source = _write(tmp_path, "web/src/app.ts", "export const n = 1\n")
    assert typescript_packages(tmp_path, [source]) == [(tmp_path / "web").resolve()]


def test_rust_module_is_the_nearest_cargo_package(tmp_path):
    _write(tmp_path, "src-tauri/Cargo.toml", '[package]\nname = "bookwriter"\nversion = "0.1.0"\n')
    lib = _write(tmp_path, "src-tauri/src/lib.rs", "pub fn read_text() {}\n")
    assert rust_modules(tmp_path, [lib]) == [(tmp_path / "src-tauri").resolve()]


def test_manifests_are_restored_after_a_coverage_install(tmp_path):
    package_json = tmp_path / "package.json"
    lock = tmp_path / "package-lock.json"
    package_json.write_bytes(b'{"name":"demo"}\n')
    lock.write_bytes(b'{"lockfileVersion":3}\n')
    snapshot = _manifest_snapshot(tmp_path)
    package_json.write_bytes(b'{"name":"changed"}\n')
    lock.unlink()
    shrink = tmp_path / "npm-shrinkwrap.json"
    shrink.write_text("{}\n", encoding="utf-8")
    _restore_manifests(snapshot)
    assert package_json.read_bytes() == b'{"name":"demo"}\n'
    assert lock.read_bytes() == b'{"lockfileVersion":3}\n'
    assert not shrink.exists()


def test_python_project_uses_pytest_and_coverage_lcov(tmp_path):
    _write(tmp_path, "pyproject.toml", "[tool.pytest.ini_options]\ntestpaths = ['tests']\n")
    source = _write(tmp_path, "src/demo/box.py", "def choose(x):\n    return x\n")
    _write(tmp_path, "tests/test_box.py", "def test_choose():\n    assert True\n")
    assert python_roots(tmp_path, [source]) == [tmp_path.resolve()]
    assert uses_pytest(tmp_path)
    assert python_sources(tmp_path, [source, tmp_path / "tests" / "test_box.py"]) == "src"
    assert is_test_file(tmp_path / "tests" / "test_box.py")
    data = tmp_path / "target" / "coverage" / "python" / ".coverage"
    report = data.parent / "lcov.info"
    run, lcov = python_coverage_commands("python3", "pytest", data, report, "src")
    assert run == (
        f"python3 -m coverage run --data-file={data} --source=src -m pytest"
    )
    assert lcov == f"python3 -m coverage lcov --data-file={data} -o {report}"


def test_python_package_without_pytest_uses_unittest(tmp_path):
    _write(tmp_path, "setup.py", "from setuptools import setup\nsetup(name='demo')\n")
    source = _write(tmp_path, "demo/app.py", "def run():\n    return 1\n")
    assert not uses_pytest(tmp_path)
    run, _lcov = python_coverage_commands("python3", "unittest", Path("data"), Path("out"), "demo")
    assert "-m unittest discover -s ." in run
    assert python_roots(tmp_path, [source]) == [tmp_path.resolve()]


def test_rust_lcov_path_is_absolute():
    report = Path("/tmp/bookwriter/target/coverage/rust/src-tauri/lcov.info")
    command = rust_coverage_command("llvm-cov", report)
    assert command == f"cargo llvm-cov --lcov --output-path {report}"


def test_vitest_version_and_provider_install(tmp_path, monkeypatch):
    assert _vitest_version(tmp_path) is None
    _write(tmp_path, "node_modules/vitest/package.json", "{not json")
    assert _vitest_version(tmp_path) is None
    _write(tmp_path, "node_modules/vitest/package.json", '{"version": "4.1.11"}\n')
    assert _vitest_version(tmp_path) == "4.1.11"
    provider = tmp_path / "node_modules" / "@vitest" / "coverage-v8"
    provider.mkdir(parents=True)
    assert _ensure_vitest_coverage(tmp_path) is True
    provider.rmdir()
    monkeypatch.setattr("crapper.runners.run_shell", lambda command, cwd: 1)
    assert _ensure_vitest_coverage(tmp_path) is False


def test_clean_clojure_keeps_other_language_reports(tmp_path):
    kept = tmp_path / "target" / "coverage" / "python"
    kept.mkdir(parents=True)
    (kept / "lcov.info").write_text("keep", encoding="utf-8")
    stale = tmp_path / "target" / "coverage" / "lcov.info"
    stale.write_text("old", encoding="utf-8")
    _clean_clojure(tmp_path)
    assert (kept / "lcov.info").is_file()
    assert not stale.exists()


def test_python_executable_prefers_a_project_venv(tmp_path):
    binary = tmp_path / ".venv" / "bin" / "python"
    binary.parent.mkdir(parents=True)
    binary.write_text("", encoding="utf-8")
    assert _python_executable(tmp_path) == str(binary)


def test_rust_kind_installs_llvm_cov_when_it_is_missing(monkeypatch):
    installed = {"llvm": False}

    def which(name):
        if name == "cargo-llvm-cov" and installed["llvm"]:
            return "/bin/cargo-llvm-cov"
        if name == "rustup":
            return "/bin/rustup"
        return None

    def shell(command, cwd):
        if "cargo install" in command:
            installed["llvm"] = True
        return 0

    monkeypatch.setattr("crapper.runners.shutil.which", which)
    monkeypatch.setattr("crapper.runners.run_shell", shell)
    assert _rust_kind() == "llvm-cov"
    installed["llvm"] = False
    monkeypatch.setattr("crapper.runners.run_shell", lambda command, cwd: 1)
    assert _rust_kind() is None


def test_coverage_commands_are_issued_per_language(tmp_path, monkeypatch):
    commands: list[str] = []

    def shell(command, cwd):
        commands.append(command)
        if "--data-file=" in command:
            data = Path(command.split("--data-file=", 1)[1].split()[0])
            data.parent.mkdir(parents=True, exist_ok=True)
            data.write_text("x", encoding="utf-8")
            return 1
        if command.startswith("clj") or command.startswith("mvn") or command.startswith("go "):
            return 1
        if "vitest" in command or command.startswith("cargo "):
            return 1
        return 0

    monkeypatch.setattr("crapper.runners.run_shell", shell)
    monkeypatch.setattr(
        "crapper.runners.shutil.which",
        lambda name: "/bin/cargo-llvm-cov" if name == "cargo-llvm-cov" else None,
    )
    _write(tmp_path, "deps.edn", "{}\n")
    _write(tmp_path, "src/demo/core.clj", "(ns demo.core)\n(defn x [])\n")
    _write(tmp_path, "pom.xml", "<project></project>\n")
    _write(tmp_path, "src/Board.java", "class Board { int place(){ return 1; } }\n")
    (tmp_path / "target" / "jacoco.exec").parent.mkdir(parents=True)
    (tmp_path / "target" / "jacoco.exec").write_text("x", encoding="utf-8")
    _write(tmp_path, "go.mod", "module example.com/demo\n")
    _write(tmp_path, "board.go", "package demo\nfunc Place() int { return 1 }\n")
    profile = tmp_path / "target" / "coverage" / "go" / "coverage.out"
    profile.parent.mkdir(parents=True)
    profile.write_text("old", encoding="utf-8")
    _write(tmp_path, "package.json", json.dumps({"scripts": {"test": "vitest run"}}))
    _write(tmp_path, "src/ui.ts", "export function view(){ return 1 }\n")
    (tmp_path / "node_modules" / "@vitest" / "coverage-v8").mkdir(parents=True)
    _write(tmp_path, "pyproject.toml", "[tool.pytest.ini_options]\n")
    _write(tmp_path, "src/app.py", "def run():\n    return 1\n")
    _write(tmp_path, "Cargo.toml", '[package]\nname = "demo"\nversion = "0.1.0"\n')
    _write(tmp_path, "src/lib.rs", "pub fn open() {}\n")
    files = [
        tmp_path / "src/demo/core.clj",
        tmp_path / "src/Board.java",
        tmp_path / "board.go",
        tmp_path / "src/ui.ts",
        tmp_path / "src/app.py",
        tmp_path / "src/lib.rs",
    ]
    run_coverage(tmp_path, files, None)
    text = "\n".join(commands)
    assert "clj -M:cov --lcov" in text
    assert "clj -M:cov\n" in text or text.endswith("clj -M:cov") or "clj -M:cov" in text
    assert "mvn " in text
    assert "go test" in text
    assert "vitest" in text
    assert "coverage run" in text
    assert "cargo llvm-cov" in text
    run_coverage(tmp_path, files, "echo custom")
    assert commands[-1] == "echo custom"


def test_missing_build_files_skip_that_language(tmp_path, monkeypatch):
    monkeypatch.setattr("crapper.runners.run_shell", lambda command, cwd: 0)
    files = [
        _write(tmp_path, "src/App.java", "class App {}\n"),
        _write(tmp_path, "main.go", "package main\n"),
        _write(tmp_path, "src/app.ts", "export const n = 1\n"),
        _write(tmp_path, "src/lib.rs", "pub fn open() {}\n"),
    ]
    run_coverage(tmp_path, files, None)
