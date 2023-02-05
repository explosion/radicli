from typing import List, Iterable, Optional, Union, Literal, Dict
import pytest
import argparse
from radicli import Radicli
from radicli.util import get_arg, UnsupportedTypeError

GOOD_TEST_CASES = [
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
    # Literals
    (
        ["--a", "pizza", "--b", "fanta"],
        [
            get_arg("a", Literal["pizza", "pasta", "burger"], name="--a"),
            get_arg("b", Literal["cola", "fanta", "sprite"], name="--b"),
        ],
        {"a": "pizza", "b": "fanta"},
    ),
]

BAD_TEST_CASES = [
    # Unsupported types
    (
        ["--a", "{'hello': 'world'}"],
        [(("a", Dict[str, any]), {"name": "--a"})],
        UnsupportedTypeError,
    ),
    # Bad values
    (
        ["--a", "hello"],
        [(("a", int), {"name": "--a"})],
        SystemExit,
    ),
    # Unrecognized, missing or duplicate arguments
    (["--a", "1", "--b", "2"], [(("a", str), {"name": "--a"})], SystemExit),
    (["--a", "1"], [(("a", str), {})], SystemExit),
    (["--b", "1"], [(("a", str), {}), (("b", str), {"name": "--b"})], SystemExit),
    (
        ["--a", "1"],
        [(("a", str), {"name": "--a"}), (("a", str), {"name": "--a"})],
        argparse.ArgumentError,
    ),
    (
        ["--a", "1", "--b", "2"],
        [
            (("a", str), {"name": "--a", "shorthand": "-A"}),
            (("b", str), {"name": "--b", "shorthand": "-A"}),
        ],
        argparse.ArgumentError,
    ),
    # Literals
    (
        ["--a", "fries"],
        [(("a", Literal["pizza", "pasta", "burger"]), {"name": "--a"})],
        SystemExit,
    ),
]


@pytest.mark.parametrize(
    "args,arg_info,expected",
    GOOD_TEST_CASES,
)
def test_parser_good(args, arg_info, expected):
    cli = Radicli("test")
    assert cli.parse(args, arg_info) == expected


@pytest.mark.parametrize(
    "args,arg_info_data,expected_error",
    BAD_TEST_CASES,
)
def test_parser_bad(args, arg_info_data, expected_error):
    cli = Radicli("test")
    with pytest.raises(expected_error):
        arg_info = [get_arg(*args, **kwargs) for args, kwargs in arg_info_data]
        cli.parse(args, arg_info)
