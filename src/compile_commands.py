#!/usr/bin/env python3

from typing import Any
from pathlib import Path
from subprocess import Popen
from glob2 import glob
from src.arguments import parse_arguments
from typing import Optional, Sequence, List, Any

import shlex
import concurrent.futures
import re
import time
import json
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
        entry["command"] = entry["command"] + " " + flags
    return data


def change_compiler_path(data: List[Any], new_path: str) -> List[Any]:
    for entry in data:
        compiler_path = entry["command"].split(" ")[0]
        compiler = Path(compiler_path).parts[-1]

        new_path = os.path.normpath(new_path + "/")

        entry["command"] = entry["command"].replace(
            compiler_path, new_path + "/" + compiler
        )
    return data


def to_clang(data: List[Any]) -> List[Any]:
    for entry in data:
        entry["command"] = (
            entry["command"].replace("/gcc", "/clang").replace("/g++", "/clang++")
        )
    return data


def to_gcc(data: List[Any]) -> List[Any]:
    for entry in data:
        entry["command"] = (
            entry["command"].replace("/clang++", "/g++").replace("/clang", "/gcc")
        )
    return data


def run(args, index: int, total: int, quiet: bool) -> None:
    if not quiet:
        print(f"[{index + 1}/{total}]")
    Popen(args, shell=True).wait()


def execute(data: List[Any], threads: int, quiet: bool) -> None:
    total = len(data)

    with concurrent.futures.ProcessPoolExecutor(max_workers=threads) as executor:
        for index, entry in enumerate(data):
            executor.submit(run, entry["command"], index, total, quiet)


def absolute_include_paths(data: List[Any]) -> List[Any]:
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


def filter_files(data: List[Any], regex: str) -> List[Any]:
    return [d for d in data if not re.search(regex, d["file"], re.IGNORECASE)]


def filter_commands(data: List[Any], regex: str, replacement: str) -> List[Any]:
    for entry in data:
        entry["command"] = re.sub(
            regex, replacement, entry["command"], flags=re.IGNORECASE
        )
    return data


def to_command_cdb(data: List[Any]) -> List[Any]:
    for entry in data:
        if (args := entry.get("arguments")) is not None:
            entry["command"] = shlex.join(args)
            del entry["arguments"]
    return data


def to_arguments_cdb(data: List[Any]) -> List[Any]:
    for entry in data:
        if (command := entry.get("command")) is not None:
            entry["arguments"] = shlex.split(command)
            del entry["command"]
    return data


def process_cdb(args, data: List[Any]) -> List[Any]:

    if args.add_flags:
        data = add_flags(data, args.add_flags)

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
        data = filter_commands(data, args.filter, args.replacement)

    if args.compiler_path:
        data = change_compiler_path(data, args.compiler_path)

    if args.clang:
        data = to_clang(data)
    elif args.gcc:
        data = to_gcc(data)

    if args.remove_duplicates:
        data = [dict(t) for t in {tuple(d.items()) for d in data}]

    if args.absolute_include_paths:
        data = absolute_include_paths(data)

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
            data = merge_json_files(get_compile_dbs(args.dir))
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

    create_file = not any(
        [
            args.output.lower() == "stdout",
            args.output.lower() == "stderr",
            args.output.lower() == "none",
        ]
    )

    data = to_command_cdb(data)
    data = process_cdb(args, data)

    if create_file:
        if data or args.force_write:
            with open(str(args.output), "w") as json_file:
                json.dump(data, json_file, indent=4, sort_keys=True)
        else:
            print("error: The output compilation database has no commands.")
            return 1
    else:
        if args.output == "stdout":
            print(json.dumps(data, indent=4, sort_keys=True))
        elif args.output == "stderr":
            print(json.dumps(data, indent=4, sort_keys=True), file=sys.stderr)

    if not args.quiet:
        end = time.time()

        print(
            "{} commands processed in {}s.".format(
                len(data),
                round(end - start, 4),
            )
        )

    if args.run:
        print("Executing all commands, this may take a while...")
        execute(data, args.threads, args.quiet)

    return 0


if __name__ == "__main__":
    exit(main())
