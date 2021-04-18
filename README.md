# Compilation Database Manipulation Utility

This utility facilitates the use and modifications of compilation databases (CDB). \
Modifying compilation databases can be useful especially when you don't have control over how a project is built.

## Install

```bash
pip install compile-commands
```

## Requirements

Requires at least python 3.4. 

## Usage

This tool has many possible uses, I'll go through some of them to showcase how it can be used.

In a project composed of subproject with their own build folder, you can use `--merge` and indicate the root `--dir` and it will merge them in the specified directory.\
This is particularly useful for LSP servers that don't handle these projects well.

```bash
compile-commands --dir /path/to/project --merge
```

You can also indicate to the LSP server that you prefer using libc++ instead of libstdc++ even if your buildsystem doesn't use it.

```bash
compile-commands --file /path/to/project/compile-commands.json \
                 --add_flags='-stdlib=libc++'
```

`--add_flags` takes in a string so you can add multiple flags

```bash
compile-commands --file /path/to/project/compile-commands.json \
                 --add_flags='-stdlib=libc++ -O0'
```

You can combine `--add_flags` with `--run` to monitor warnings as example:

```bash
compile-commands --file /path/to/project/compile-commands.json \
                 --add_flags='-Wall -Wextra -pedantic -fsyntax' \
                 --run --threads=12
```

You can decide to treat only a subset of your project by using `--filter-files` or `--remove-files`.\
`--filter-files` takes in a regular expression whereas `--remove-files` takes in a comma-separated list of absolute paths.

You can as example filter out .c files from the database:

```bash 
compile-commands --file /path/to/project/compile-commands.json \
                 --filter-files='.*\.c$' \
                 --remove-files='path/to/file1,path/to/file2'
```

You can decide to treat only a subset of your project by using `--include_files` which takes in a comma-separated list of absolute paths. You can also prefix each paths passed to `--include_files` and `--remove_files` by using `--path-prefix`.

```bash 
compile-commands --file /path/to/project/compile-commands.json \
                 --include-files='path/to/file1,path/to/file2'
```

You can use the `-o` flag to specify the name of the output file in case you don't want to overwrite

```bash
compile-commands --file /path/to/project/compile-commands.json \
                 --filter-files='.*\.c$' \
                 --remove-files='path/to/file1,path/to/file2' \
                 -o 'my-db-without-c-files.json'
```

You can also filter out parts of the commands based on a regular expression using `--filter`. \
This is particularly useful when you need to modify the `-o` from the command. 
A good example of that is using [ClangBuildAnalyzer](https://github.com/aras-p/ClangBuildAnalyzer). 

```bash
mkdir ftime
cd ftime
./compile-commands --file=/path/to/project/compile-commands.json \
                   --add_flags='-ftime-trace' \
                   --filter='-o .*\\.o' \
                   --run -j 12

# .json and .o files are created in-place!
ClangBuildAnalyzer --all . capture_file
ClangBuildAnalyzer --analyze capture_file
```

We add the clang's `-ftime-trace` as required by ClangBuildAnalyzer and remove every occurences of -o path/to/object/file.o and run each commands to produces the json tracings.\
What if g++ was used during the creation of compilation database ? In this case we can use `--clang` and `--gcc` to switch between the two compilers and even change the path of the compiler with `--compiler_path` if let's say gcc is in `/usr/bin` and the clang we want to use is in `/usr/bin/local`.

```bash
./compile-commands.py --file=/path/to/project/compile-commands.json \
                      --clang --compiler_path='/usr/bin/local' \
                      --add_flags='-ftime-trace' \
                      --filter='-o .*\\.o' \
                      --run -j 12 
```

`--filter` also accepts a replacement through the `--replacement` flag, it accepts reference to groups within the regular expression as per `re.sub()`. `--filter` is also useful to remove flags that are not compatible with both compilers.

If you are a user of the Ninja buildsystem you might notice that the above example does not work. That is because generating a CDB through Cmake using Ninja as the generator will result in having relative include paths within the CDB (relative to "directory" that is). This is inconvenient because the above effectively moves the build directory but does not move dependencies. To fix that you can use `--absolute_include_paths` which will try to modify relative includes paths into absolute include paths. 
