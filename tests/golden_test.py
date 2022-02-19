#!/usr/bin/env python3

from pathlib import Path

import src.compile_commands as cc
import pytest
import json
import os


@pytest.fixture
def current_path() -> Path:
    return Path(__file__).parent.resolve()


def test_golden(current_path):
    d = str(current_path / "data/compile_commands_tests")
    o = str(current_path / "data/golden_output.json")
    i = str(current_path / "data/golden.json")
    cc.main(["--dir", d, "--merge", "--output", o])

    with open(o, "r") as after:
        with open(i, "r") as before:
            assert json.load(after) == json.load(before)

    os.remove(o)
