from compile_commands import *

DATA = [
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


def test_remove_files():
    assert len(remove_files(DATA, "path/to/file2.cpp")) == 3
    assert (
        len(remove_files(DATA, str("path/to/file1.c,path/to/file2.cpp").split(",")))
        == 2
    )
    assert len(remove_files(DATA, "path/to/doesnotexist.c")) == 4


def test_include_files():
    assert len(include_files(DATA, "path/to/file2.cpp")) == 1
    assert (
        len(include_files(DATA, str("path/to/file1.c,path/to/file2.cpp").split(",")))
        == 2
    )
    assert len(include_files(DATA, "path/to/doesnotexist.c")) == 0


def test_absolute_include_paths():
    data = absolute_include_paths(DATA)

    print(data[0]["command"])
    assert data[0]["command"].endswith("-I/path/to/build/directory/..")
    assert data[1]["command"].endswith("-iquote /path/to/build/directory/.")
    assert data[2]["command"].endswith("-I/path/to/build/directory/something")
    assert data[3]["command"].endswith("-isystem /path/to/build/directory/include")


def test_add_flags():
    data = add_flags(DATA, "-flag")
    for entry in data:
        assert "-flag" in entry["command"]


def test_remove_trailing():
    assert remove_trailing("/usr/bin/", "/") == "/usr/bin"
    assert remove_trailing("/usr/bin", "/") == "/usr/bin"


def test_to_gcc():
    data = to_gcc(DATA)
    assert data[0]["command"].startswith("/usr/bin/gcc")
    assert data[1]["command"].startswith("/usr/bin/g++")
    assert data[2]["command"].startswith("/usr/bin/g++")
    assert data[3]["command"].startswith("/usr/bin/gcc")


def test_to_clang():
    data = to_clang(DATA)
    assert data[0]["command"].startswith("/usr/bin/clang")
    assert data[1]["command"].startswith("/usr/bin/clang++")
    assert data[2]["command"].startswith("/usr/bin/clang++")
    assert data[3]["command"].startswith("/usr/bin/clang")


def test_change_compiler_path():
    data = change_compiler_path(DATA, "/usr/local/bin/")
    for entry in data:
        assert entry["command"].startswith("/usr/local/bin/")


def test_filter_files():
    assert len(filter_files(DATA, "file")) == 0
    assert len(filter_files(DATA, "\\.cpp$")) == 2
    assert len(filter_files(DATA, "\\.c$")) == 2


def test_get_compile_dbs():
    assert len(get_compile_dbs("src/tests/compile_commands_tests/")) == 3


def test_merge_json_files():
    assert (
        len(merge_json_files(get_compile_dbs("src/tests/compile_commands_tests/"))) == 6
    )


def test_filter_commands():
    data = filter_commands(DATA, "-o .*\\.o", "")

    for entry in data:
        assert "-o" not in entry["command"] and "output" not in entry["command"]
        assert "-o" not in entry["command"] and "output" not in entry["command"]
        assert "-o" not in entry["command"] and "output" not in entry["command"]
