#!/usr/bin/env python3

from pathlib import Path
from .main import main
import pytest
import json


@pytest.fixture
def current_path() -> Path:
    return Path(__file__).parent.resolve()


@pytest.mark.parametrize(
    "arg1,arg2",
    [
        ("--files", "--dir"),
        ("--file", "--files"),
        ("--files", "--dir"),
        ("--gcc", "--clang"),
    ],
)
def test_exclusive_commands(capsys, arg1, arg2):
    try:
        main([arg1, ".", arg2, "."])
    except:
        pass

    out, err = capsys.readouterr()
    assert not out
    assert err.endswith(
        f"pytest: error: argument {arg2}: not allowed with argument {arg1}\n"
    )


def test_no_files(capsys, current_path):
    f = current_path / "does_not_exist.json"
    main(["--file", str(f)])
    out, err = capsys.readouterr()
    assert not out
    assert err == f"error: {f} not found.\n"

    main(["--files", str(f), str(current_path / "data/data.json"), "--merge"])
    out, err = capsys.readouterr()
    assert not out
    assert "error: one of the file passed to --files couldn't be opened.\n" in err
    assert "[Errno 2] No such file or directory:" in err


def test_execution(capfd, current_path):
    file = str(current_path / "data/execution.json")
    main(["--file", file, "--run", "-v"])

    out, err = capfd.readouterr()

    assert not err

    # Execution order isn't guaranteed
    assert "hello" in out
    assert "hello1" in out


def test_warnings(capsys, current_path):
    f1 = str(current_path / "data/data.json")
    f2 = f1

    main(["--files", f1, f2, "-o", "none"])
    out, err = capsys.readouterr()
    assert not out
    assert (
        err
        == "warning: more than one file passed to --files, it implies --merge which was not specified.\n"
    )

    main(["--file", f1, "-j", "1", "-o", "/dev/null"])
    out, err = capsys.readouterr()
    assert not out
    assert (
        err == "warning: --threads (-j) will be ignored since --run was not passed.\n"
    )

    main(["--file", f1, "--replacement='\\1'", "-o=None"])
    out, err = capsys.readouterr()
    assert not out
    assert err == "warning: --replacement requires --filter\n"


def test_invalid_dir(current_path):
    invalid_path = str(current_path / "does_not_exist/")

    try:
        main(["--dir", invalid_path])
    except Exception as e:
        assert type(e).__name__ == "NotADirectoryError"
    else:
        assert False


def test_add_test(capsys, current_path):
    cdb_path = str(current_path / "data/data.json")
    main(["--file", cdb_path, "--add_flags=-O3 -g", "-o=stderr"])

    _, err = capsys.readouterr()

    data = json.loads(err)

    for entry in data:
        assert "-O3" in entry["arguments"]
        assert "-g" in entry["arguments"]
