from compile_commands import *
import pytest


@pytest.fixture
def cdb():
    return [
        {
            "directory": "/path/to/build/directory",
            "command": "/usr/bin/gcc path/to/file1.c -o path/to/output.o -I..",
            "file": "path/to/file1.c",
        },
        {
            "directory": "/path/to/build/directory",
            "command": "/usr/bin/g++ path/to/file2.cpp -o path/to/output.o -iquote .",
            "file": "path/to/file2.cpp",
        },
        {
            "directory": "/path/to/build/directory",
            "command": "/usr/bin/clang++ path/to/file3.cpp -o path/to/output.o -Isomething",
            "file": "path/to/file3.cpp",
        },
        {
            "directory": "/path/to/build/directory",
            "command": "/usr/bin/clang path/to/file4.c -o path/to/output.o -isystem /path/to/build/directory/include",
            "file": "path/to/file4.c",
        },
    ]


def test_remove_files(cdb):
    assert len(remove_files(cdb, "path/to/file2.cpp")) == 3
    assert (
        len(remove_files(cdb, str("path/to/file1.c,path/to/file2.cpp").split(","))) == 2
    )
    assert len(remove_files(cdb, "path/to/doesnotexist.c")) == 4


def test_include_files(cdb):
    assert len(include_files(cdb, "path/to/file2.cpp")) == 1
    assert (
        len(include_files(cdb, str("path/to/file1.c,path/to/file2.cpp").split(",")))
        == 2
    )
    assert len(include_files(cdb, "path/to/doesnotexist.c")) == 0


def test_absolute_include_paths(cdb):
    data = absolute_include_paths(cdb)

    print(data[0]["command"])
    assert data[0]["command"].endswith("-I/path/to/build/directory/..")
    assert data[1]["command"].endswith("-iquote /path/to/build/directory/.")
    assert data[2]["command"].endswith("-I/path/to/build/directory/something")
    assert data[3]["command"].endswith("-isystem /path/to/build/directory/include")


def test_add_flags(cdb):
    data = add_flags(cdb, "-flag")
    for entry in data:
        assert "-flag" in entry["command"]


def test_to_gcc(cdb):
    data = to_gcc(cdb)
    assert data[0]["command"].startswith("/usr/bin/gcc")
    assert data[1]["command"].startswith("/usr/bin/g++")
    assert data[2]["command"].startswith("/usr/bin/g++")
    assert data[3]["command"].startswith("/usr/bin/gcc")


def test_to_clang(cdb):
    data = to_clang(cdb)
    assert data[0]["command"].startswith("/usr/bin/clang")
    assert data[1]["command"].startswith("/usr/bin/clang++")
    assert data[2]["command"].startswith("/usr/bin/clang++")
    assert data[3]["command"].startswith("/usr/bin/clang")


def test_change_compiler_path(cdb):
    data = change_compiler_path(cdb, "/usr/local/bin/")
    for entry in data:
        assert entry["command"].startswith("/usr/local/bin/")


def test_filter_files(cdb):
    assert len(filter_files(cdb, "file")) == 0
    assert len(filter_files(cdb, "\\.cpp$")) == 2
    assert len(filter_files(cdb, "\\.c$")) == 2


def test_get_compile_dbs():
    assert len(get_compile_dbs("src/tests/compile_commands_tests/")) == 3


def test_merge_json_files():
    assert (
        len(merge_json_files(get_compile_dbs("src/tests/compile_commands_tests/"))) == 6
    )


def test_filter_commands(cdb):
    data = filter_commands(cdb, "-o .*\\.o", "")

    for entry in data:
        assert "-o" not in entry["command"] and "output" not in entry["command"]
        assert "-o" not in entry["command"] and "output" not in entry["command"]
        assert "-o" not in entry["command"] and "output" not in entry["command"]


def test_normalize_cdb():

    data = [
        {"file": "somefile.cpp", "command": "command", "dir": "somedir"},
        {
            "file": "somefile.cpp",
            "arguments": ["gcc", "somefile", "-Iinclude", "-o", "someoutput"],
        },
        {
            "file": "somefile.cpp",
            "arguments": ["command", "with spaces!"],
        },
    ]

    data = normalize_cdb(data)
    for entry in data:
        assert entry.get("command") is not None
        assert entry.get("arguments", 0) == 0

    assert data[1]["command"] == "gcc somefile -Iinclude -o someoutput"
    assert data[2]["command"] == "command 'with spaces!'"
