#!/usr/bin/env python3

from pathlib import Path
import src.compile_commands as cc
import pytest


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
        cc.main([arg1, ".", arg2, "."])
    except:
        pass

    out, err = capsys.readouterr()
    assert not out
    assert err == (
        "usage: compile-commands --file=FILE\n"
        f"pytest: error: argument {arg2}: not allowed with argument {arg1}\n"
    )


def test_no_files(capsys, current_path):
    f = current_path / "does_not_exist.json"
    cc.main(["--file", str(f)])
    out, err = capsys.readouterr()
    assert not out
    assert err == f"error: {f} not found.\n"

    cc.main(["--files", str(f), str(current_path / "data/data.json"), "--merge"])
    out, err = capsys.readouterr()
    assert not out
    assert err == (
        "error: one of the file passed to --files couldn't be opened.\n"
        "[Errno 2] No such file or directory: '/home/quentin/code/compile-commands/tests/does_not_exist.json'\n"
    )


def test_execution(capfd, current_path):
    file = str(current_path / "data/execution.json")
    cc.main(["--file", file, "--run", "-q"])

    out, err = capfd.readouterr()

    assert not err
    assert out.startswith("Executing all commands, this may take a while...\n")

    # Execution order isn't guaranteed
    assert "hello" in out
    assert "hello1" in out
