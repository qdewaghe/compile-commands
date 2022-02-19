from argparse import ArgumentParser, RawTextHelpFormatter
from importlib.metadata import version
from multiprocessing import cpu_count
from typing import Optional, Sequence, Any
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
        usage="compile-commands --file=FILE",
        formatter_class=RawTextHelpFormatter,
    )

    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {version('compile-commands')}",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        default=False,
        action="store_true",
        help="quiet mode",
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
        help="change the compiler path (e.g. --compiler_path='/usr/local/bin')",
    )

    output_group = parser.add_argument_group(title="output options")
    output_group.add_argument(
        "-o",
        "--output",
        type=str,
        default=os.getcwd() + "/compile_commands.json",
        help=(
            "output path for the generated compilation database file.\n"
            "defaults to compile_commands.json within the current working directory"
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

    regex_group = parser.add_argument_group(title="regex-related flags")
    regex_group.add_argument(
        "--filter_files",
        type=str,
        help="regular expression that will filter out matching files",
    )

    regex_group.add_argument(
        "--filter",
        type=str,
        help="regular expression that will filter matches from each command",
    )

    regex_group.add_argument(
        "--replacement",
        type=str,
        default="",
        help="replacement for matches of --filter, can reference groups matched.",
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
        title="path-related flags",
    )
    path_group.add_argument(
        "--absolute_include_paths",
        default=False,
        action="store_true",
        help="make the paths contained in the command absolute",
    )

    path_group.add_argument(
        "--normalize_paths",
        default=False,
        action="store_true",
        help="normalize paths contained in the command",
    )

    misc_group = parser.add_argument_group(title="misc.")
    misc_group.add_argument(
        "--disallow_duplicates",
        default=True,
        action="store_false",
        help="prevent a file appearing twice in the CDB,\n"
        "it can occur when two different translation units are based on the same source file.",
    )

    misc_group.add_argument(
        "--force_write",
        default=False,
        help="force write compile commands even when compile commands list is empty",
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

    return args
