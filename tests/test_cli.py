import subprocess
from pathlib import Path

from crapper.cli import run
from crapper.discover import language_of


def test_language_detection():
    assert language_of("src/app/core.clj") == "clojure"
    assert language_of("src/app/core.cljc") == "clojure"
    assert language_of("Widget.java") == "java"
    assert language_of("board.go") == "go"
    assert language_of("ui/view.tsx") == "typescript"
    assert language_of("src/lib.rs") == "rust"
    assert language_of("src/crapper/cli.py") == "python"
    assert language_of("types.d.ts") is None
    assert language_of("notes.md") is None


def _write(root: Path, relative: str, source: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def test_project_snapshot_is_readable_as_crap4clj_edn(tmp_path):
    _write(
        tmp_path,
        "src/demo/core.clj",
        "(ns demo.core)\n\n(defn choose [x]\n  (if x 1 0))\n",
    )
    _write(
        tmp_path,
        "src/demo/Board.java",
        "package demo;\npublic class Board {\n  public int place(int x) {\n    if (x > 0 && ready) return 1;\n    return 0;\n  }\n}\n",
    )
    _write(
        tmp_path,
        "board.go",
        "package demo\n\nfunc Place(x int) int {\n\tif x > 0 {\n\t\treturn x\n\t}\n\treturn 0\n}\n",
    )
    _write(
        tmp_path,
        "src/ui/view.ts",
        "export function view(ok: boolean): number {\n  return ok ? 1 : 0;\n}\n",
    )
    _write(tmp_path, "Cargo.toml", '[package]\nname = "demo"\nversion = "0.1.0"\n')
    _write(
        tmp_path,
        "src/lib.rs",
        "pub fn open(ok: bool) -> i32 { if ok { 1 } else { 0 } }\n",
    )
    _write(tmp_path, "src/demo/core_test.clj", "(ns demo.core-test)\n(defn should-skip [] 1)\n")
    _write(tmp_path, "board_test.go", "package demo\nfunc TestPlace(t *testing.T) {}\n")

    code = run(["--root", str(tmp_path), "--no-coverage"])
    assert code == 0
    text = (tmp_path / ".metrics" / "crap.edn").read_text(encoding="utf-8")
    assert ':namespace "demo.core"' in text
    assert ':name "choose"' in text
    assert ':namespace "demo.Board"' in text
    assert ':name "place"' in text
    assert ':namespace "demo"' in text and ':name "Place"' in text
    assert ':namespace "ui.view"' in text
    assert ':namespace "demo"' in text and ':name "open"' in text
    assert "should-skip" not in text
    assert "TestPlace" not in text

    reader = subprocess.run(
        [
            "bb",
            "-e",
            (
                "(require '[clojure.edn :as edn])"
                "(let [data (edn/read-string (slurp *in*))]"
                " (doseq [entry (:entries data)]"
                "   (println (:namespace entry) (:name entry)"
                "            (:complexity entry) (pr-str (:coverage entry)))))"
            ),
        ],
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )
    assert reader.returncode == 0, reader.stderr
    assert "demo.core choose 2 nil" in reader.stdout
    assert "demo.Board place 3 nil" in reader.stdout


def test_existing_coverage_feeds_the_snapshot(tmp_path):
    _write(
        tmp_path,
        "src/demo/core.clj",
        "(ns demo.core)\n\n(defn choose [x]\n  (if x 1 0))\n",
    )
    lcov = tmp_path / "target" / "coverage" / "lcov.info"
    lcov.parent.mkdir(parents=True)
    lcov.write_text(
        "SF:src/demo/core.clj\nDA:3,1\nDA:4,1\nend_of_record\n",
        encoding="utf-8",
    )
    code = run(
        ["--root", str(tmp_path), "--use-existing-coverage", "src/demo/core.clj"]
    )
    assert code == 0
    text = (tmp_path / ".metrics" / "crap.edn").read_text(encoding="utf-8")
    assert ":coverage 100.0" in text
    assert ":crap 2.0" in text


def test_threshold_exits_when_the_worst_score_is_too_high(tmp_path):
    _write(tmp_path, "src/demo/core.clj", "(ns demo.core)\n\n(defn choose [x]\n  (if x 1 0))\n")
    lcov = tmp_path / "target" / "coverage" / "lcov.info"
    lcov.parent.mkdir(parents=True)
    lcov.write_text("SF:src/demo/core.clj\nDA:3,0\nDA:4,0\nend_of_record\n", encoding="utf-8")
    code = run(
        [
            "--root",
            str(tmp_path),
            "--use-existing-coverage",
            "--threshold",
            "1",
        ]
    )
    assert code == 2


def test_help_and_unknown_option(capsys):
    assert run(["--help"]) == 0
    assert "uml-viewer" in capsys.readouterr().out
    assert run(["--not-an-option"]) == 1
    assert run(["--root"]) == 1
    assert run(["--threshold", "nope"]) == 1
    assert run(["--no-coverage", "--coverage-command", "true"]) == 1


def test_selects_directories_filters_and_changed_files(tmp_path, monkeypatch, capsys):
    _write(tmp_path, "src/demo/core.clj", "(ns demo.core)\n\n(defn choose [x]\n  (if x 1 0))\n")
    _write(tmp_path, "notes.md", "not source\n")
    assert run(["--root", str(tmp_path), "--no-coverage", "--source-root", "src"]) == 0
    assert run(["--root", str(tmp_path), "--no-coverage", "src"]) == 0
    assert run(["--root", str(tmp_path), "--no-coverage", "src/demo/core.clj", "core"]) == 0
    assert run(["--root", str(tmp_path), "--no-coverage", "notes.md"]) == 0
    assert "No source files" in capsys.readouterr().out

    class Result:
        returncode = 0
        stdout = ' M src/demo/core.clj\nR  old.clj -> src/demo/core.clj\n?? "src/demo/core.clj"\n'
        stderr = ""

    monkeypatch.setattr("crapper.cli.subprocess.run", lambda *args, **kwargs: Result())
    assert run(["--root", str(tmp_path), "--no-coverage", "--changed"]) == 0

    class Failed:
        returncode = 1
        stdout = ""
        stderr = "git failed"

    monkeypatch.setattr("crapper.cli.subprocess.run", lambda *args, **kwargs: Failed())
    assert run(["--root", str(tmp_path), "--no-coverage", "--changed"]) == 0


def test_run_asks_for_coverage_when_it_is_enabled(tmp_path, monkeypatch):
    _write(tmp_path, "src/demo/core.clj", "(ns demo.core)\n\n(defn choose [x]\n  x)\n")
    monkeypatch.setattr("crapper.cli.run_coverage", lambda *args: None)
    assert run(["--root", str(tmp_path), "--coverage-command", "true"]) == 0
