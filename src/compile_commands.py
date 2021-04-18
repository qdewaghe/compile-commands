#!/usr/bin/env python3

from pathlib import Path
from subprocess import Popen
from argparse import ArgumentParser, RawTextHelpFormatter
import concurrent.futures
import re
import time
import json
import os
import glob2


def parse_arguments():
    parser = ArgumentParser(
        description="""
        Utility to manipulate compilation databases. (CDB)
        https://github.com/qdewaghe/compile-commands""",
        usage="compile-commands --file=FILE",
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        "--dir",
        type=dir_path,
        help="path to target directory",
    )

    parser.add_argument(
        "--file",
        type=str,
        help="path to compilation database",
    )

    parser.add_argument(
        "-m",
        "--merge",
        action="store_true",
        help=(
            "find all compile-commands.json files in --dir recursively and merges them,"
            "\nif not set only the CDB in the root directory will be considered"
        ),
    )

    parser.add_argument(
        "--filter_files",
        type=str,
        help="regular expression that will filter out matching files",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="compile_commands.json",
        help="name for the output file, defaults to compile_commands.json",
    )

    parser.add_argument(
        "--compiler_path",
        type=dir_path,
        help="change the compiler path (e.g. --compiler_path='/usr/local/bin')",
    )

    parser.add_argument(
        "--remove_files",
        default="",
        type=str,
        help="comma-separated list of files to be removed from the CDB",
    )

    parser.add_argument(
        "--include_files",
        default="",
        type=str,
        help="comma-separated list of files to keep in the CDB (every other files will be removed)",
    )

    parser.add_argument(
        "--path_prefix",
        default="",
        type=str,
        help="file path prefix of include_files and remove_files",
    )

    parser.add_argument(
        "--add_flags",
        type=str,
        help="add the argument to each commands as text",
    )

    parser.add_argument(
        "--filter",
        type=str,
        help="regular expression that will filter matches from each command",
    )

    parser.add_argument(
        "--replacement",
        type=str,
        default="",
        help="replacement for matches of --filter, can reference groups matched.",
    )

    parser.add_argument(
        "--run",
        default=False,
        action="store_true",
        help="execute each commands listed in the resulting file",
    )

    parser.add_argument(
        "--clang",
        default=False,
        action="store_true",
        help="replace 'gcc' and 'g++' by 'clang' and 'clang++' respectively in each commands.",
    )

    parser.add_argument(
        "--gcc",
        default=False,
        action="store_true",
        help="replace 'clang' and 'clang++' by 'gcc' and 'g++' respectively in each commands",
    )

    parser.add_argument(
        "-j",
        "--threads",
        help="number of threads for --run, defaults to 1",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--quiet",
        default=False,
        action="store_true",
        help="print stats at the end of the execution.",
    )

    parser.add_argument(
        "--allow_duplicates",
        default=False,
        action="store_true",
        help="by default duplicated files are deleted.",
    )

    parser.add_argument(
        "--force_write",
        default=False,
        help="force write compile commands even when compile commands list is empty",
    )

    parser.add_argument(
        "--absolute_include_paths",
        default=False,
        action="store_true",
        help="If the include paths inside the commands are relative, make them absolute.",
    )

    parser.add_argument("--version", action="store_true", help="prints the version")

    args = parser.parse_args()

    if args.version:
        print("compile-commands: 1.1.3")
        exit(0)

    if not args.dir and not args.file:
        print("error: must specified at least --file or --dir")
        exit(2)

    if args.merge and not args.dir:
        print("error: --merge requires --dir")
        exit(2)

    if args.clang and args.gcc:
        print("error: --clang and --gcc are incompatible, aborting.")
        exit(2)

    if args.file and args.dir:
        print("error: --file and --dir are incompatible, aborting.")
        exit(2)

    if args.threads != 1 and not args.run:
        print("warning: --threads (-j) will be ignored since --run was not passed.")

    return args


def dir_path(path):
    if os.path.isdir(path):
        return path
    raise NotADirectoryError(path)


def get_compile_dbs(directory):
    # TODO:
    # Replace this call by something that stop the recursion for a given directory
    # once the file has been found (BFS)
    # e.g:
    #    .
    #    ├── component1
    #    │   ├── build_Release
    #    │   │   └── compile_commands.json // TODO:
    #    │   ├── build_Debug               // Add logic to be able to choose in between two CDB
    #    │   │   └── compile_commands.json // that are on the same level
    #    │   └── some_directory //visit because it could be a build directory
    #    |       └── another_directory //do not visit
    #    ...
    paths = list(
        glob2.glob("{}/**/compile_commands.json".format(directory), recursive=True)
    )

    # Since we take into account symlinks we have to make sure the symlinks
    # doesn't resolve to a file that we already take into account
    paths = list(set([os.path.realpath(os.path.abspath(p)) for p in paths]))

    # Make sure we don't take into account a file in the root directory
    # if the file in the root directory is a symlink to a build directory
    # it will still be taken into account as long as the build directory
    # is inside the tree
    return [p for p in paths if Path(p).parent.parts[-1] != Path(directory).parts[-1]]


def remove_files(data, files):
    return [d for d in data if d["file"] not in files]


def include_files(data, files):
    return [d for d in data if d["file"] in files]


def merge_json_files(paths):
    data = []
    for path in paths:
        with open(str(path), "r") as json_file:
            data.extend(json.load(json_file))
    return data


def add_flags(data, flags: str):
    for entry in data:
        entry["command"] = entry["command"] + " " + flags
    return data


def change_compiler_path(data, new_path: str):
    for entry in data:
        compiler_path = entry["command"].split(" ")[0]
        compiler = Path(compiler_path).parts[-1]

        new_path = remove_trailing(new_path, "/")

        entry["command"] = entry["command"].replace(
            compiler_path, new_path + "/" + compiler
        )
    return data


def to_clang(data):
    for entry in data:
        entry["command"] = (
            entry["command"].replace("/gcc", "/clang").replace("/g++", "/clang++")
        )
    return data


def to_gcc(data):
    for entry in data:
        entry["command"] = (
            entry["command"].replace("/clang++", "/g++").replace("/clang", "/gcc")
        )
    return data


def run(args, index, total, quiet):
    if not quiet:
        print("[{}/{}]".format(index + 1, total))
    Popen(args, shell=True).wait()


def execute(data, threads, quiet):
    total = len(data)

    with concurrent.futures.ProcessPoolExecutor(max_workers=threads) as executor:
        for index, entry in enumerate(data):
            executor.submit(run, entry["command"], index, total, quiet)


def absolute_include_paths(data):
    for entry in data:
        directory = entry["directory"]
        command = entry["command"]

        # Include paths with spaces `-I include` and without spaces `-Iinclude`
        # are treated separately. The first regular expressions deals with the includes
        # with spaces, and conversely for the second.
        #
        # This won't work well if there are multiple spaces between the include flag
        # and the first char because it'll break the lookahead that checks that the path
        # is indeed relative by verifying that the first char is not a '/'.
        # There is probably a better way to do this.
        command = re.sub(
            r"(-I|-iquote|-isystem|-idirafter)(?=\s)(\s+)(?=[^\/])([^\/]\S*)",
            f"\\1\\2{directory}/\\3",
            command,
        )
        entry["command"] = re.sub(
            r"(-I|-iquote|-isystem|-idirafter)(?=\S)(?=[^\/])([^\/]\S*)",
            f"\\1{directory}/\\2",
            command,
        )
    return data


def remove_trailing(string: str, to_remove: str):
    if string.endswith(to_remove):
        return string[: -len(to_remove)]
    return string


def filter_files(data, regex: str):
    return [d for d in data if not re.search(regex, d["file"], re.IGNORECASE)]


def filter_commands(data, regex, replacement):
    for entry in data:
        entry["command"] = re.sub(
            regex, replacement, entry["command"], flags=re.IGNORECASE
        )
    return data


def main():
    args = parse_arguments()
    start = time.time()

    if args.dir:
        args.dir = os.path.abspath(args.dir)

    if args.file:
        args.dir = str(Path(os.path.abspath(args.file)).parent)

    data = []
    if args.merge:
        data = merge_json_files(get_compile_dbs(args.dir))
    else:
        # if --merge is not set we use existing data inside the specified directory
        filepath = "{}/compile_commands.json".format(args.dir)
        try:
            with open(filepath, "r") as json_file:
                data = json.load(json_file)
        except:
            print("{} not found. Did you forget --merge?".format(filepath))
            exit(2)

    compile_db = "{}/{}".format(remove_trailing(args.dir, "/"), args.output)

    if args.add_flags:
        data = add_flags(data, args.add_flags)

    if args.remove_files:
        data = remove_files(
            data, [args.path_prefix + x.strip() for x in args.remove_files.split(",")]
        )

    if args.include_files:
        data = include_files(
            data, [args.path_prefix + x.strip() for x in args.include_files.split(",")]
        )

    if args.filter_files:
        data = filter_files(data, args.filter_files)

    if args.filter:
        data = filter_commands(data, args.filter, args.replacement)

    if args.compiler_path:
        data = change_compiler_path(data, args.compiler_path)

    if args.clang:
        data = to_clang(data)
    elif args.gcc:
        data = to_gcc(data)

    if not args.allow_duplicates:
        data = [dict(t) for t in {tuple(d.items()) for d in data}]

    if args.absolute_include_paths:
        data = absolute_include_paths(data)

    overwrote = os.path.isfile(compile_db)

    if len(data) > 0:
        with open(str(compile_db), "w") as json_file:
            json.dump(data, json_file, indent=4, sort_keys=False)
    else:
        print("no commands found.")
        if args.force_write:
            with open(str(compile_db), "w") as json_file:
                json.dump(data, json_file, indent=4, sort_keys=False)
        else:
            exit(1)

    if not args.quiet:
        end = time.time()

        print(
            "{} {} with {} command(s) in {}s.".format(
                compile_db,
                "updated" if overwrote else "created",
                len(data),
                round(end - start, 4),
            )
        )

    if args.run:
        execute(data, args.threads, args.quiet)


if __name__ == "__main__":
    main()
