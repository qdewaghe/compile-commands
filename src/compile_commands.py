#!/usr/bin/env python3

from pathlib import Path
from subprocess import Popen
from argparse import ArgumentParser, RawTextHelpFormatter
from glob2 import glob
import shlex
import concurrent.futures
import re
import time
import json
import os


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
        default=os.getcwd(),
        type=dir_path,
        help="path to target directory",
    )

    parser.add_argument(
        "--file",
        type=str,
        help="path to compilation database",
    )

    parser.add_argument(
        "--files",
        nargs="+",
        type=str,
        help="path to compilations databases, implies --merge.",
    )

    parser.add_argument(
        "-m",
        "--merge",
        action="store_true",
        help=(
            "find all compile-commands.json files in --dir recursively and merges them,"
            "\nif not set only the CDB in the root directory will be considered"
            "\nNote that it may be relatively slow for big hierarchies. In which case you should use --files"
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
        print("compile-commands: 1.1.7")
        exit(0)

    if args.clang and args.gcc:
        print("error: --clang and --gcc are incompatible, aborting.")
        exit(2)

    if args.threads != 1 and not args.run:
        print("warning: --threads (-j) will be ignored since --run was not passed.")

    return args


def dir_path(path):
    if os.path.isdir(path):
        return path
    raise NotADirectoryError(path)


def get_compile_dbs(directory):
    paths = list(glob(f"{os.path.abspath(directory)}/**/compile_commands.json"))

    # Since we take into account symlinks we have to make sure the symlinks
    # doesn't resolve to a file that we already take into account
    paths = list(set([os.path.realpath(p) for p in paths]))

    # Making sure to ignore a compile_commands.json in the root directory
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

        new_path = os.path.normpath(new_path + "/")

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
        print(f"[{index + 1}/{total}]")
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


def filter_files(data, regex: str):
    return [d for d in data if not re.search(regex, d["file"], re.IGNORECASE)]


def filter_commands(data, regex, replacement):
    for entry in data:
        entry["command"] = re.sub(
            regex, replacement, entry["command"], flags=re.IGNORECASE
        )
    return data


def normalize_cdb(data):
    if len(data) == 0:
        return

    # We don't assume that if one entry has no "argument"
    # then none of them have, because in the case that
    # CDB are merged, they might have different origins
    for entry in data:
        if (args := entry.get("arguments")) is not None:
            entry["command"] = shlex.join(args)
            del entry["arguments"]

    return data


def process_cdb(args, data):
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

    return data


def main():
    args = parse_arguments()
    start = time.time()

    if args.file:
        args.dir = str(Path(os.path.abspath(args.file)).parent)

    args.dir = os.path.normpath(os.path.abspath(args.dir))

    data = []
    if args.merge or args.files:
        if not args.files:
            args.files = get_compile_dbs(args.dir)
        data = merge_json_files(args.files)
    else:
        # if --merge is not set we use existing data inside the specified directory
        filepath = f"{args.dir}/compile_commands.json"
        try:
            with open(filepath, "r") as json_file:
                data = json.load(json_file)
        except:
            print(f"{filepath} not found. Did you forget --merge?")
            exit(2)

    output_cdb = f"{args.dir}/{args.output}"
    overwrote = os.path.isfile(output_cdb)

    data = normalize_cdb(data)
    data = process_cdb(args, data)

    if len(data) > 0 or args.force_write:
        with open(str(output_cdb), "w") as json_file:
            json.dump(data, json_file, indent=4, sort_keys=False)
    else:
        print("The output compilation database has no commands.")
        print("Use --force-write to generate it anyway.")
        exit(1)

    if not args.quiet:
        end = time.time()

        print(
            "{} {} with {} command(s) in {}s.".format(
                output_cdb,
                "updated" if overwrote else "created",
                len(data),
                round(end - start, 4),
            )
        )

    if args.run:
        print("Executing all commands, this may take a while...")
        execute(data, args.threads, args.quiet)


if __name__ == "__main__":
    main()
