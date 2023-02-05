from typing import List, Iterable, Optional, Union
import pytest
from radicli import Radicli
from radicli.util import get_arg

TEST_CASES = [
    (
        ["--a", "1", "--b", "2", "--c", "2"],
        [
            get_arg("a", str, name="--a"),
            get_arg("b", int, name="--b"),
            get_arg("c", float, name="--c"),
        ],
        {"a": "1", "b": 2, "c": 2.0},
    ),
    # Positional arguments
    (
        ["1", "2", "--c", "2"],
        [
            get_arg("a", str),
            get_arg("b", int),
            get_arg("c", float, name="--c"),
        ],
        {"a": "1", "b": 2, "c": 2.0},
    ),
    # Booleans
    (["--a"], [get_arg("a", bool, name="--a")], {"a": True}),
    (
        ["--a", "1", "--b", "--c", "3"],
        [
            get_arg("a", str, name="--a"),
            get_arg("b", bool, name="--b"),
            get_arg("c", int, name="--c"),
            get_arg("d", bool, name="--d"),
        ],
        {"a": "1", "b": True, "c": 3, "d": False},
    ),
    # List types and iterables
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", List[str], name="--a")],
        {"a": ["1", "2", "3"]},
    ),
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", List[int], name="--a")],
        {"a": [1, 2, 3]},
    ),
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", List[float], name="--a")],
        {"a": [1.0, 2.0, 3.0]},
    ),
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", Iterable[str], name="--a")],
        {"a": ["1", "2", "3"]},
    ),
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", Optional[List[str]], name="--a")],
        {"a": ["1", "2", "3"]},
    ),
    # Optional arguments
    (
        ["--a", "1", "--c", "3"],
        [
            get_arg("a", Optional[str], name="--a"),
            get_arg("b", Optional[int], name="--b"),
            get_arg("c", Union[str, int], name="--c"),
        ],
        {"a": "1", "b": None, "c": "3"},
    ),
    # Shorthand format
    (
        ["-A", "1", "--b", "2", "-C", "2"],
        [
            get_arg("a", str, name="--a", shorthand="-A"),
            get_arg("b", int, name="--b", shorthand="-B"),
            get_arg("c", float, name="--c", shorthand="-C"),
        ],
        {"a": "1", "b": 2, "c": 2.0},
    ),
    # Custom converter
    (
        ["--a", "hello world"],
        [get_arg("a", lambda x: x.upper(), name="--a", skip_resolve=True)],
        {"a": "HELLO WORLD"},
    ),
]


@pytest.mark.parametrize(
    "args,arg_info,expected",
    TEST_CASES,
)
def test_options(args, arg_info, expected):
    cli = Radicli("test")
    assert cli.parse(args, arg_info) == expected
