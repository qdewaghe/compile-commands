import copy
import shlex

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
    {
        "directory": "/path/to/build/gone_too_far/../directory/2.2.1.0-beta",
        "command": "/usr/bin/gcc path/to/gone_too_far/../file5.c -o path/to/output.o -Isomestuff/..",
        "file": "path/to/gone_too_far/../file5.c",
    }
]


def test_remove_files():
    data = copy.deepcopy(DATA)
    assert len(remove_files(data, "path/to/file2.cpp")) == 4
    assert (
        len(remove_files(data, str("path/to/file1.c,path/to/file2.cpp").split(",")))
        == 3
    )
    assert len(remove_files(data, "path/to/doesnotexist.c")) == 5


def test_include_files():
    data = copy.deepcopy(DATA)
    assert len(include_files(data, "path/to/file2.cpp")) == 1
    assert (
        len(include_files(data, str("path/to/file1.c,path/to/file2.cpp").split(",")))
        == 2
    )
    assert len(include_files(data, "path/to/doesnotexist.c")) == 0

def test_filter_includes():
    data = copy.deepcopy(DATA)
    data = filter_includes(data, '(build|something)')

    assert data[0]["command"].endswith("-I..")
    assert data[1]["command"].endswith("-iquote .")
    assert data[2]["command"].endswith("-o path/to/output.o")
    assert data[3]["command"].endswith("-o path/to/output.o")
    assert data[4]["command"].endswith("-Isomestuff/..")

def test_absolute_include_paths():
    data = copy.deepcopy(DATA)
    data = absolute_include_paths(data)

    assert data[0]["command"].endswith("-I/path/to/build/directory/..")
    assert data[1]["command"].endswith("-iquote /path/to/build/directory/.")
    assert data[2]["command"].endswith("-I/path/to/build/directory/something")
    assert data[3]["command"].endswith("-isystem /path/to/build/directory/include")
    assert data[4]["command"].endswith("-I/path/to/build/gone_too_far/../directory/2.2.1.0-beta/somestuff/..")


def test_normalize_paths():
    data = copy.deepcopy(DATA)
    data = normalize_paths(data)

    assert data[0]["directory"]=="/path/to/build/directory"
    assert data[0]["file"]=="path/to/file1.c"
    args = shlex.split(data[0]["command"])
    assert args[0] == "/usr/bin/gcc"
    assert args[1] == f"path/to/file1.c"
    assert args[2] == "-o"
    assert args[3] == f"path/to/output.o"
    assert args[4] == f"-I{os.sep}path{os.sep}to{os.sep}build"
    
    assert data[1]["directory"] == "/path/to/build/directory"
    assert data[1]["file"] == "path/to/file2.cpp"
    args = shlex.split(data[1]["command"])
    assert args[0] == "/usr/bin/g++"
    assert args[1] == "path/to/file2.cpp"
    assert args[2] == "-o"
    assert args[3] == "path/to/output.o"
    assert args[4] == "-iquote"
    assert args[5] == f"{os.sep}path{os.sep}to{os.sep}build{os.sep}directory"
    
    assert data[2]["directory"] == "/path/to/build/directory"
    assert data[2]["command"] == "/usr/bin/clang++ path/to/file3.cpp -o path/to/output.o -Isomething"
    assert data[2]["file"] == "path/to/file3.cpp"

    assert data[3]["directory"] == "/path/to/build/directory"
    assert data[3]["command"] == "/usr/bin/clang path/to/file4.c -o path/to/output.o -isystem /path/to/build/directory/include"
    assert data[3]["file"] == "path/to/file4.c"

    assert data[4]["directory"] == f"{os.sep}path{os.sep}to{os.sep}build{os.sep}directory{os.sep}2.2.1.0-beta"
    assert data[4]["file"] == f"{os.sep}path{os.sep}to{os.sep}build{os.sep}directory{os.sep}2.2.1.0-beta{os.sep}path{os.sep}to{os.sep}file5.c"
    args = shlex.split(data[4]["command"])
    assert args[0] == "/usr/bin/gcc"
    assert args[1] == f"{os.sep}path{os.sep}to{os.sep}build{os.sep}directory{os.sep}2.2.1.0-beta{os.sep}path{os.sep}to{os.sep}file5.c"
    assert args[2] == "-o"
    assert args[3] == "path/to/output.o"
    assert args[4] == f"-I{os.sep}path{os.sep}to{os.sep}build{os.sep}directory{os.sep}2.2.1.0-beta"

def test_add_flags():
    data = copy.deepcopy(DATA)
    data = add_flags(data, "-flag")
    for entry in data:
        assert "-flag" in entry["command"]


def test_to_gcc():
    data = copy.deepcopy(DATA)
    data = to_gcc(data)
    assert data[0]["command"].startswith("/usr/bin/gcc")
    assert data[1]["command"].startswith("/usr/bin/g++")
    assert data[2]["command"].startswith("/usr/bin/g++")
    assert data[3]["command"].startswith("/usr/bin/gcc")


def test_to_clang():
    data = copy.deepcopy(DATA)
    data = to_clang(data)
    assert data[0]["command"].startswith("/usr/bin/clang")
    assert data[1]["command"].startswith("/usr/bin/clang++")
    assert data[2]["command"].startswith("/usr/bin/clang++")
    assert data[3]["command"].startswith("/usr/bin/clang")


def test_change_compiler_path():
    data = copy.deepcopy(DATA)
    data = change_compiler_path(data, "/usr/local/bin/")
    for entry in data:
        assert entry["command"].startswith(f"{os.sep}{os.path.join('usr', 'local', 'bin')}")


def test_filter_files():
    data = copy.deepcopy(DATA)
    assert len(filter_files(data, "file")) == 0
    assert len(filter_files(data, "\\.cpp$")) == 3
    assert len(filter_files(data, "\\.c$")) == 2


def test_get_compile_dbs():
    assert len(get_compile_dbs("src/tests/compile_commands_tests/")) == 3


def test_merge_json_files():
    assert (
        len(merge_json_files(get_compile_dbs("src/tests/compile_commands_tests/"))) == 6
    )


def test_filter_commands():
    data = copy.deepcopy(DATA)
    data = filter_commands(data, "-o .*\\.o", "")

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
