from pathlib import Path
from .main import *

import pytest
import json


@pytest.fixture
def current_path() -> Path:
    return Path(__file__).parent.resolve()


@pytest.fixture
def cdb(current_path: Path):
    with open(current_path / "data/data.json", "r") as f:
        return json.load(f)


@pytest.fixture
def arguments_cdb(current_path: Path):
    with open(current_path / "data/arguments_cdb.json", "r") as f:
        return json.load(f)


@pytest.fixture
def normalized_cdb(cdb):
    return normalize(cdb)


@pytest.mark.parametrize(
    "file,count",
    [
        (["path/to/file2.cpp"], 4),
        (["path/to/file1.c", "path/to/file2.cpp"], 3),
        (["path/to/doesnotexist.c"], 5),
    ],
)
def test_remove_files(cdb, file, count):
    assert len(remove_files(cdb, file)) == count


@pytest.mark.parametrize(
    "file,count",
    [
        (["path/to/file2.cpp"], 1),
        (["path/to/file1.c", "path/to/file2.cpp"], 2),
        (["path/to/doesnotexist.c"], 0),
    ],
)
def test_include_files(cdb, file, count):
    assert len(include_files(cdb, file)) == count


@pytest.mark.parametrize(
    "regex,index,expected_args_len",
    [
        ("\\.", 0, 4),
        ("\\.", 1, 4),
        ("something", 2, 4),
        ("\\.", 2, 6),
        ("path/to/", 3, 4),
    ],
)
def test_filter_include_directories(normalized_cdb, regex, index, expected_args_len):
    data = filter_include_directories(normalized_cdb, regex)
    assert len(data[index]["arguments"]) == expected_args_len


@pytest.mark.parametrize(
    "index,flag,dir",
    [
        (0, "-I", "/path/to/build"),
        (1, "-iquote", "/path/to/build/directory"),
        (2, "-I", "/path/to/build/directory/something"),
        (3, "-isystem", "/path/to/build/directory/include"),
    ],
)
def test_absolute_include_directories(normalized_cdb, index, flag, dir):
    data = absolute_include_directories(normalized_cdb)
    assert data[index]["arguments"][-1] == dir
    assert data[index]["arguments"][-2] == flag


def test_normalize_include_directories(normalized_cdb):
    data = normalize_include_directories(normalized_cdb)
    assert data[4]["arguments"] == [
        "/usr/bin/clang",
        "-isystem",
        "/path/to/build/directory",
        "-I",
        "..",
        "-I",
        ".",
        "-isystem",
        "/home",
    ]


@pytest.mark.parametrize(
    "index,clang,gcc",
    [
        (0, "/usr/bin/clang", "/usr/bin/gcc"),
        (1, "/usr/bin/clang++", "/usr/bin/g++"),
        (2, "/usr/bin/clang++", "/usr/bin/g++"),
        (3, "/usr/bin/clang", "/usr/bin/gcc"),
    ],
)
def test_compiler(normalized_cdb, index, clang, gcc):
    data = to_clang(normalized_cdb)
    assert data[index]["arguments"][0] == clang
    data = to_gcc(normalized_cdb)
    assert data[index]["arguments"][0] == gcc


@pytest.mark.parametrize(
    "regex,length",
    [
        ("file", 0),
        ("\\.cpp$", 3),
        ("\\.c$", 2),
    ],
)
def test_filter_files(cdb, regex, length):
    assert len(filter_files(cdb, regex)) == length


def test_get_compile_dbs(current_path: Path):
    p = str(current_path / "data/compile_commands_tests")
    assert set(get_compile_dbs(p)) == set(
        [
            os.path.join(p, "component1/compile_commands.json"),
            os.path.join(p, "component2/compile_commands.json"),
            os.path.normpath(
                os.path.join(p, "../external_component/compile_commands.json")
            ),
        ]
    )


def test_merge_json_files(current_path: Path):
    p = str(current_path / "data/compile_commands_tests")
    assert len(merge_json_files(get_compile_dbs(p))) == 6


def test_filter_commands(cdb):
    data = filter_commands(cdb, "-o .*\\.o", "")

    for entry in data:
        assert "-o" not in entry["command"] and "output" not in entry["command"]
        assert "-o" not in entry["command"] and "output" not in entry["command"]
        assert "-o" not in entry["command"] and "output" not in entry["command"]


@pytest.mark.parametrize(
    "index,result",
    [
        (1, "gcc somefile -Iinclude -o someoutput"),
        (2, "command 'with spaces!'"),
    ],
)
def test_command_cdb(arguments_cdb, index, result):
    data = to_command_cdb(arguments_cdb)

    assert "arguments" not in data[index].keys()
    assert data[index]["command"] == result


@pytest.mark.parametrize(
    "index,result",
    [
        (0, ["/usr/bin/gcc", "path/to/file1.c", "-o", "path/to/output.o", "-I.."]),
        (
            1,
            [
                "/usr/bin/g++",
                "path/to/file2.cpp",
                "-o",
                "path/to/output.o",
                "-iquote",
                ".",
            ],
        ),
        (
            2,
            [
                "/usr/bin/clang++",
                "path/to/file3.cpp",
                "-o",
                "path/to/output.o",
                "-Isomething",
            ],
        ),
        (
            3,
            [
                "/usr/bin/clang",
                "path/to/file4.c",
                "-o",
                "path/to/output.o",
                "-isystem",
                "/path/to/build/directory/include",
            ],
        ),
    ],
)
def test_arguments_cdb(cdb, index, result):
    data = to_arguments_cdb(cdb)

    assert "command" not in data[index].keys()
    assert data[index]["arguments"] == result


def test_change_compiler_path(normalized_cdb):
    data = change_compiler_path(normalized_cdb, "/usr/local/bin/")
    for entry in data:
        assert entry["arguments"][0].startswith("/usr/local/bin/")


def test_add_flags(normalized_cdb):
    data = add_flags(normalized_cdb, "-flag -O3")
    for entry in data:
        assert "-flag" in entry["arguments"]
        assert "-O3" in entry["arguments"]
