from compile_commands import remove_files

DATA = [{
    "directory": "path/to",
    "commands": "gcc path/to/file1.c -o path/to/output",
    "file": "path/to/file1.c",
},
    {
    "directory": "path/to",
    "commands": "gcc path/to/file2.c -o path/to/output",
    "file": "path/to/file2.c",
}, ]


def test_remove_files():
    assert len(remove_files(DATA, 'path/to/file2.c')) == 1
    assert len(remove_files(
        DATA, str('path/to/file1.c,path/to/file2.c').split(','))) == 0
    assert len(remove_files(DATA, 'path/to/doesnotexist.c')) == 2
