#!/usr/bin/env python3

from pathlib import Path
from subprocess import Popen
from argparse import ArgumentParser, RawTextHelpFormatter
import concurrent.futures
import subprocess
import time
import json
import sys
import os
import re


def parse_arguments():
    parser = ArgumentParser(
        description="Utility to manipulate compilation databases.",
        usage="./compile-commands.py --dir=DIR",
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
        help="path to compilation database"
    )

    parser.add_argument(
        "-m",
        "--merge",
        action="store_true",
        help="find all compile-commands.json files in --dir recursively, if not only the root directory will be considered",
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
        help="comma-seperated list of files to be removed",
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
        default='',
        help='replacement for matches of --filter, can reference groups matched.'
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

    args = parser.parse_args()

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


def dir_path(path: str):
    if os.path.isdir(path):
        return path
    else:
        raise NotADirectoryError(path)


def get_compile_dbs(dir: str):
    paths = []
    for path in Path(dir).rglob("compile_commands.json"):
        paths.append(Path(os.path.abspath(str(path))))

    # We don't want the compilationDBs of the root dir if any
    # because we assume that they're user generated
    paths = [p for p in paths if Path(
        p).parent.parts[-1] != Path(dir).parts[-1]]
    return paths


def remove_files(data, files):
    return [d for d in data if d["file"] not in files]


def merge_json_files(paths):
    data = []
    for path in paths:
        with open(str(path), "r") as json_file:
            data.extend(json.load(json_file))
    return data


def add_flags(data, flags: str):
    for entry in data:
        entry["command"] = entry["command"] + ' ' + flags
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
            entry["command"].replace(
                "/gcc", "/clang").replace("/g++", "/clang++")
        )
    return data


def to_gcc(data):
    for entry in data:
        entry["command"] = (entry["command"].replace(
            "/clang++", "/g++").replace("/clang", "/gcc"))
    return data


def run(args, index, total, quiet):
    print("[{}/{}]".format(index + 1, total))
    if quiet:
        args += " --quiet"
    Popen(args, shell=True).wait()


def execute(data, threads, quiet):
    total = len(data)

    with concurrent.futures.ProcessPoolExecutor(max_workers=threads) as executor:
        for index, entry in enumerate(data):
            executor.submit(run, entry["command"], index, total, quiet)


def remove_trailing(string: str, to_remove: str):
    if string.endswith(to_remove):
        return string[: -len(to_remove)]
    return string


def filter_files(data, regex: str):
    return [d for d in data if not re.search(regex, d["file"], re.IGNORECASE)]


def filter_commands(data, regex, replacement):
    for entry in data:
        entry["command"] = re.sub(
            regex, replacement, entry["command"], flags=re.IGNORECASE)
    return data


def main():
    args = parse_arguments()

    if not args.quiet:
        start = time.time()

    if args.file:
        args.dir = str(Path(args.file).parent)
        with open(str(args.file), "r") as json_file:
            data = json.load(json_file)
    elif not args.merge:
        with open(str('{}/compile_commands.json'.format(args.dir)), "r") as json_file:
            data = json.load(json_file)
    else:
        data = merge_json_files(get_compile_dbs(args.dir))

    compile_db = "{}/{}".format(remove_trailing(
        args.dir, "/"), args.output)

    if args.add_flags:
        data = add_flags(data, args.add_flags)

    if args.remove_files:
        data = remove_files(data, [x.strip()
                                   for x in args.remove_files.split(",")])

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

    if args.run:
        execute(data, args.threads, args.quiet)

    with open(str(compile_db), "w") as json_file:
        json.dump(data, json_file, indent=4, sort_keys=False)

    if not args.quiet:
        end = time.time()
        print(
            "{} created with {} commands in {}s.".format(
                compile_db, len(data), end - start
            )
        )


if __name__ == "__main__":
    main()
