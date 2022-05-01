#!/usr/bin/env bash

python3 -m cProfile -s cumtime -o output.cprof ../compile_commands/main.py --file compile_commands.json --output tmp.json
gprof2dot -f pstats output.cprof > graph.dot
dot -Tsvg graph.dot -o graph.svg
