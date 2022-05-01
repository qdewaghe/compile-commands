#!/usr/bin/env python3

from argparse import ArgumentParser, RawTextHelpFormatter
from importlib.metadata import version
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Sequence, List, Any
from subprocess import check_output, STDOUT, CalledProcessError
from pprint import pprint
from pathlib import Path
from glob2 import glob

import os
import sys
import json
import shlex
import re
import time
import os
import sys


def dir_path(path):
    if os.path.isdir(path):
        return path
    raise NotADirectoryError(path)


def parse_arguments(argv: Optional[Sequence[str]] = None):
    parser = ArgumentParser(
        description=(
            "Utility to manipulate compilation databases. (CDB)\n"
            "https://github.com/qdewaghe/compile-commands\n"
            "https://pypi.org/project/compile-commands"
        ),
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {version('compile-commands')}",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increases verbosity (up to three times)",
    )

    location_group = parser.add_mutually_exclusive_group(required=True)
    location_group.add_argument(
        "--dir",
        default=os.getcwd(),
        type=dir_path,
        help="path to target directory containing a compilation database",
    )

    location_group.add_argument(
        "--file",
        type=str,
        help="path to a compilation database",
    )

    location_group.add_argument(
        "--files",
        nargs="+",
        type=str,
        help="paths to compilations databases, implies --merge.",
    )

    parser.add_argument(
        "-m",
        "--merge",
        action="store_true",
        help=(
            "find all compile-commands.json files in --dir recursively and merges them,"
            "\nif not set only the CDB in the root directory will be considered"
            "\nnote that it may be relatively slow for big hierarchies. In which case you should use --files"
        ),
    )

    compiler_group = parser.add_argument_group(title="compiler-related flags")
    compiler_group_exclusive = compiler_group.add_mutually_exclusive_group(
        required=False
    )

    compiler_group_exclusive.add_argument(
        "--clang",
        default=False,
        action="store_true",
        help="replace 'gcc' and 'g++' by 'clang' and 'clang++' respectively in each commands.",
    )

    compiler_group_exclusive.add_argument(
        "--gcc",
        default=False,
        action="store_true",
        help="replace 'clang' and 'clang++' by 'gcc' and 'g++' respectively in each commands",
    )

    compiler_group.add_argument(
        "--compiler_path",
        type=dir_path,
        help="change the compiler path (e.g. --compiler_path='/usr/local/bin')\n",
    )

    output_group = parser.add_argument_group(title="output options")
    output_group.add_argument(
        "-o",
        "--output",
        type=str,
        default=os.getcwd() + "/compile_commands.json",
        help=(
            "output path for the generated compilation database file.\n"
            "defaults to compile_commands.json within the current working directory\n"
            "--output=stdout to redirect to stdout\n"
            "--output=stderr to redirect to stderr\n"
            "--output=none is equivalent to --output=/dev/null\n"
        ),
    )

    output_group.add_argument(
        "--command",
        default=False,
        action="store_true",
        help=(
            "output a compilation database using the 'command' field rather than 'arguments'\n"
            "defaults to an arguments based CDB as it is recommended by the specification"
        ),
    )

    parser.add_argument(
        "--add_flags",
        type=str,
        help="add the argument to each commands as text",
    )

    file_handling_group = parser.add_argument_group(title="file handling flags")
    file_handling_group.add_argument(
        "--remove_files",
        nargs="+",
        type=str,
        help="files to be removed from the CDB",
    )

    file_handling_group.add_argument(
        "--include_files",
        nargs="+",
        type=str,
        help="files to keep in the CDB (every other files will be removed)",
    )

    file_handling_group.add_argument(
        "--path_prefix",
        default="",
        type=str,
        help="file path prefix of include_files and remove_files",
    )

    file_handling_group.add_argument(
        "--remove_duplicates",
        default=False,
        action="store_true",
        help="prevent the same translation unit from appearing twice in the CDB.",
    )

    regex_group = parser.add_argument_group(title="filtering flags")
    regex_group.add_argument(
        "--filter",
        type=str,
        help="regular expression that will filter out matches from each command",
    )

    regex_group.add_argument(
        "--replacement",
        type=str,
        default="",
        help="replacement for matches of --filter, can reference groups matched.",
    )

    regex_group.add_argument(
        "--filter_files",
        type=str,
        help="regular expression that will filter out matching files",
    )

    regex_group.add_argument(
        "--filter_include_directories",
        default="",
        type=str,
        help=(
            "regular expression that will filter out matching include directories\n"
            "This applies before AND after --absolute_include_directories"
        ),
    )

    execution_group = parser.add_argument_group(title="execution-related flags")
    execution_group.add_argument(
        "--run",
        default=False,
        action="store_true",
        help="execute each commands listed in the resulting file",
    )

    execution_group.add_argument(
        "-j",
        "--threads",
        help=f"number of threads for --run, defaults to multiprocessing.cpu_count() which is {cpu_count()}",
        type=int,
        default=cpu_count(),
    )

    path_group = parser.add_argument_group(
        title="Misc.",
    )
    path_group.add_argument(
        "--absolute_include_directories",
        default=False,
        action="store_true",
        help="make the paths contained in the command absolute",
    )

    path_group.add_argument(
        "--normalize_include_directories",
        default=False,
        action="store_true",
        help="normalize include directory paths in the command",
    )

    args = parser.parse_args(argv)

    if args.threads != cpu_count() and not args.run:
        print(
            "warning: --threads (-j) will be ignored since --run was not passed.",
            file=sys.stderr,
        )

    if args.files and len(args.files) > 1 and not args.merge:
        print(
            "warning: more than one file passed to --files, it implies --merge which was not specified.",
            file=sys.stderr,
        )
        args.merge = True

    if args.replacement and not args.filter:
        print("warning: --replacement requires --filter", file=sys.stderr)

    if args.verbose > 2:
        print("-- CLI arguments: ")
        print(args, end="\n\n")

    return args


def get_compile_dbs(directory) -> List[str]:
    paths: List[str] = list(
        str(p) for p in glob(f"{os.path.abspath(directory)}/**/compile_commands.json")
    )

    # Since we take into account symlinks we have to make sure the symlinks
    # doesn't resolve to a file that we already have
    paths = list(set([os.path.realpath(p) for p in paths]))

    # Making sure to ignore a compile_commands.json in the root directory
    return [p for p in paths if Path(p).parent.parts[-1] != Path(directory).parts[-1]]


def remove_files(data: List[Any], files: List[str]) -> List[Any]:
    return [d for d in data if d["file"] not in files]


def include_files(data: List[Any], files: List[str]) -> List[Any]:
    return [d for d in data if d["file"] in files]


def merge_json_files(paths: List[str]) -> List[Any]:
    data: List[Any] = []
    for path in paths:
        try:
            with open(str(path), "r") as json_file:
                data.extend(json.load(json_file))
        except ValueError as e:
            print(f"Couldn't parse json file: {path}", file=sys.stderr)
            print(e, file=sys.stderr)
            exit(1)
    return data


def add_flags(data: List[Any], flags: str) -> List[Any]:
    for entry in data:
        entry["arguments"].extend(flags.split())
    return data


def change_compiler_path(data: List[Any], new_path: str) -> List[Any]:
    for entry in data:
        compiler_path = entry["arguments"][0]
        compiler = os.path.basename(compiler_path)
        entry["arguments"][0] = os.path.normpath(new_path) + "/" + compiler
    return data


def to_clang(data: List[Any]) -> List[Any]:
    for entry in data:
        entry["arguments"][0] = (
            entry["arguments"][0].replace("/gcc", "/clang").replace("/g++", "/clang++")
        )
    return data


def to_gcc(data: List[Any]) -> List[Any]:
    for entry in data:
        entry["arguments"][0] = (
            entry["arguments"][0].replace("/clang++", "/g++").replace("/clang", "/gcc")
        )
    return data


def run(args: List[str], index: int, total: int, verbose: int) -> None:
    try:
        output = check_output(args, stderr=STDOUT, universal_newlines=True)
    except CalledProcessError as exc:
        print(
            f"command ({shlex.join(args)}) {index + 1} of {total} failed "
            f"with return code {exc.returncode}\n{exc.output}",
        )
    else:
        if verbose:
            print(f"[{index + 1}/{total}] '{shlex.join(args)}' {output}")


def execute(data: List[Any], threads: int, verbose: int) -> None:
    total = len(data)
    if verbose:
        print(f"Executing {total} commands, this may take a while...")

    with ProcessPoolExecutor(max_workers=threads) as executor:
        for index, entry in enumerate(data):
            executor.submit(run, entry["arguments"], index, total, verbose)


def normalize_include_directories(data: List[Any]) -> List[Any]:
    for entry in data:
        arguments = entry["arguments"]
        is_path = True
        for index, arg in enumerate(arguments):
            if arg in ("-I", "-isystem", "-iquote", "-idirafter"):
                is_path = True
            elif is_path:
                is_path = False
                arguments[index] = os.path.normpath(arg)

    return data


def absolute_include_directories(data: List[Any]) -> List[Any]:
    for entry in data:
        directory = entry["directory"]
        arguments = entry["arguments"]

        is_path = False
        for index, arg in enumerate(arguments):
            if arg in ("-I", "-isystem", "-iquote", "-idirafter"):
                is_path = True
            elif is_path:
                is_path = False
                if not os.path.isabs(arg):
                    arguments[index] = os.path.normpath(os.path.join(directory, arg))

    return data


def filter_files(data: List[Any], regex: str) -> List[Any]:
    return [d for d in data if not re.search(regex, d["file"], re.IGNORECASE)]


def filter_commands(data: List[Any], regex: str, replacement: str) -> List[Any]:
    for entry in data:
        entry["command"] = re.sub(
            regex, replacement, entry["command"], flags=re.IGNORECASE
        )
    return data


def filter_include_directories(data: List[Any], regex: str) -> List[Any]:
    for entry in data:
        is_path = False
        arguments = entry["arguments"]
        for index, arg in enumerate(arguments):
            if arg in ("-I", "-isystem", "-iquote", "-idirafter"):
                is_path = True
            elif is_path:
                is_path = False
                if re.search(regex, arg) is not None:
                    arguments[index] = ""
                    arguments[index - 1] = ""

        entry["arguments"] = list(filter(None, arguments))
    return data


def to_command_cdb(data: List[Any]) -> List[Any]:
    for entry in data:
        if args := entry.get("arguments"):
            entry["command"] = shlex.join(args)
            del entry["arguments"]
    return data


def to_arguments_cdb(data: List[Any]) -> List[Any]:
    for entry in data:
        if command := entry.get("command"):
            if "'" in command or '"' in command:
                entry["arguments"] = shlex.split(command)
            else:
                entry["arguments"] = command.split()

            del entry["command"]
    return data


def split_includes(s: str, regex) -> List[str]:
    if s.startswith(("-I", "-i")):
        return regex.split(s)
    return [s]


def normalize(data: List[Any]) -> List[Any]:
    data = to_arguments_cdb(data)
    regex = re.compile("(-I)|(-iquote)|(-isystem)|(-idirafter)")

    for entry in data:
        arguments = [
            x for arg in entry["arguments"] for x in split_includes(arg, regex)
        ]
        entry["arguments"] = list(filter(None, arguments))

    return data


def process_cdb(args, data: List[Any]) -> List[Any]:
    if args.remove_files:
        data = remove_files(
            data, [args.path_prefix + x.strip() for x in args.remove_files]
        )

    if args.include_files:
        data = include_files(
            data, [args.path_prefix + x.strip() for x in args.include_files]
        )

    if args.filter_files:
        data = filter_files(data, args.filter_files)

    if args.filter:
        data = to_command_cdb(data)
        data = filter_commands(data, args.filter, args.replacement)

    data = normalize(data)

    if args.add_flags:
        data = add_flags(data, args.add_flags)

    if args.compiler_path:
        data = change_compiler_path(data, args.compiler_path)

    if args.clang:
        data = to_clang(data)
    elif args.gcc:
        data = to_gcc(data)

    if args.remove_duplicates:
        s = {json.dumps(d, sort_keys=True) for d in data}
        data = [json.loads(t) for t in s]

    if args.filter_include_directories:
        data = filter_include_directories(data, args.filter_include_directories)

    if args.absolute_include_directories:
        data = absolute_include_directories(data)

        if args.filter_include_directories:
            data = filter_include_directories(data, args.filter_include_directories)

    if args.normalize_include_directories:
        data = normalize_include_directories(data)

    if args.command:
        data = to_command_cdb(data)

    return data


def main(argv: Optional[Sequence[str]] = None) -> int:
    start = time.time()
    args = parse_arguments(argv)

    if args.file:
        args.file = os.path.abspath(args.file)
        args.dir = os.path.dirname(args.file)
    else:
        args.dir = os.path.normpath(os.path.abspath(args.dir))

    data: List[Any] = []
    if args.merge or args.files:
        if not args.files:
            cdbs = get_compile_dbs(args.dir)
            if not cdbs:
                print(
                    f"error: no compilation databases found in {args.dir}",
                    file=sys.stderr,
                )
                return 1

            if args.verbose > 1:
                print("-- Found the following compilation databases: ")
                pprint(cdbs)
                print("")
            data = merge_json_files(cdbs)
        else:
            try:
                data = merge_json_files(args.files)
            except FileNotFoundError as e:
                print(
                    f"error: one of the file passed to --files couldn't be opened.",
                    file=sys.stderr,
                )
                print(e, file=sys.stderr)
                return 2
    else:
        filepath = args.file if args.file else f"{args.dir}/compile_commands.json"
        try:
            with open(filepath, "r") as json_file:
                data = json.load(json_file)
        except FileNotFoundError:
            print(f"error: {filepath} not found.", file=sys.stderr)
            return 2

    if not args.output:
        args.output = f"{args.dir}/compile_commands.json"

    data = process_cdb(args, data)

    if args.verbose:
        end = time.time()

        print(
            "-- {} commands processed in {}s.".format(
                len(data),
                round(end - start, 4),
            )
        )

    create_file = not any(
        [
            args.output.lower() == "stdout",
            args.output.lower() == "stderr",
            args.output.lower() == "none",
        ]
    )

    if create_file:
        if data:
            if args.verbose:
                print(f"-- writing to {args.output}")
            with open(str(args.output), "w") as json_file:
                json.dump(data, json_file, indent=4, sort_keys=True)
        else:
            print("error: The output compilation database has no commands.")
            return 1
    else:
        if args.output == "stdout":
            print(json.dumps(data, indent=4, sort_keys=False))
        elif args.output == "stderr":
            print(json.dumps(data, indent=4, sort_keys=False), file=sys.stderr)

    if args.run:
        data = normalize(data)
        execute(data, args.threads, args.verbose)

    return 0


if __name__ == "__main__":
    exit(main())
