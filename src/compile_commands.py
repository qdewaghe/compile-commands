#!/usr/bin/env python3


from src.arguments import parse_arguments

from concurrent.futures import ProcessPoolExecutor
from typing import Optional, Sequence, List, Any
from subprocess import check_output, STDOUT, CalledProcessError
from pprint import pprint
from pathlib import Path
from glob2 import glob

import json

import shlex
import re
import time
import os
import sys


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
