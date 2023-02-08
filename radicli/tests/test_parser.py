from typing import List, Iterable, Optional, Union, Literal, Dict, Any
from enum import Enum
import pytest
import argparse
from radicli import Radicli, Arg
from radicli.util import get_arg, UnsupportedTypeError, CliParserError


class FoodEnum(Enum):
    pizza = "🍕"
    pasta = "🍝"
    burger = "🍔"


GOOD_TEST_CASES = [
    (
        ["--a", "1", "--b", "2", "--c", "2"],
        [
            get_arg("a", Arg("--a"), str),
            get_arg("b", Arg("--b"), int),
            get_arg("c", Arg("--c"), float),
        ],
        {"a": "1", "b": 2, "c": 2.0},
    ),
    # Positional arguments
    (
        ["1", "2", "--c", "2"],
        [
            get_arg("a", Arg(), str),
            get_arg("b", Arg(), int),
            get_arg("c", Arg("--c"), float),
        ],
        {"a": "1", "b": 2, "c": 2.0},
    ),
    # Booleans
    (["--a"], [get_arg("a", Arg("--a"), bool)], {"a": True}),
    (
        ["--a", "1", "--b", "--c", "3"],
        [
            get_arg("a", Arg("--a"), str),
            get_arg("b", Arg("--b"), bool),
            get_arg("c", Arg("--c"), int),
            get_arg("d", Arg("--d"), bool),
        ],
        {"a": "1", "b": True, "c": 3, "d": False},
    ),
    # List types and iterables
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", Arg("--a"), List[str])],
        {"a": ["1", "2", "3"]},
    ),
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", Arg("--a"), List[int])],
        {"a": [1, 2, 3]},
    ),
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", Arg("--a"), List[float])],
        {"a": [1.0, 2.0, 3.0]},
    ),
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", Arg("--a"), Iterable[str])],
        {"a": ["1", "2", "3"]},
    ),
    (
        ["--a", "1", "--a", "2", "--a", "3"],
        [get_arg("a", Arg("--a"), Optional[List[str]])],
        {"a": ["1", "2", "3"]},
    ),
    # Optional arguments
    (
        ["--a", "1", "--c", "3"],
        [
            get_arg("a", Arg("--a"), Optional[str]),
            get_arg("b", Arg("--b"), Optional[int]),
            get_arg("c", Arg("--c"), Union[str, int]),
        ],
        {"a": "1", "b": None, "c": "3"},
    ),
    # Shorthand format
    (
        ["-A", "1", "--b", "2", "-C", "2"],
        [
            get_arg("a", Arg("--a", "-A"), str),
            get_arg("b", Arg("--b", "-B"), int),
            get_arg("c", Arg("--c", "-C"), float),
        ],
        {"a": "1", "b": 2, "c": 2.0},
    ),
    # Custom converter
    (
        ["--a", "hello world"],
        [get_arg("a", Arg("--a"), lambda x: x.upper(), skip_resolve=True)],
        {"a": "HELLO WORLD"},
    ),
    # Literals
    (
        ["--a", "pizza", "--b", "fanta"],
        [
            get_arg("a", Arg("--a"), Literal["pizza", "pasta", "burger"]),
            get_arg("b", Arg("--b"), Literal["cola", "fanta", "sprite"]),
        ],
        {"a": "pizza", "b": "fanta"},
    ),
    # Enums
    (
        ["--a", "pizza"],
        [get_arg("a", Arg("--a"), FoodEnum)],
        {"a": FoodEnum.pizza},
    ),
    # Counting
    (
        ["--verbose", "--verbose"],
        [get_arg("verbose", Arg("--verbose", "-v", count=True), int)],
        {"verbose": 2},
    ),
    (
        ["-vvv"],
        [get_arg("verbose", Arg("--verbose", "-v", count=True), int)],
        {"verbose": 3},
    ),
]

EXTRA_KEY = "__extra__"
GOOD_WITH_EXTRA_TEST_CASES = [
    (
        ["--a", "1", "--b", "2", "--hello", "3", "--world"],
        [get_arg("a", Arg("--a"), str), get_arg("b", Arg("--b"), int)],
        {"a": "1", "b": 2, EXTRA_KEY: ["--hello", "3", "--world"]},
    ),
]

BAD_TEST_CASES = [
    # Unsupported types
    (
        ["--a", "{'hello': 'world'}"],
        [("a", Arg("--a"), Dict[str, Any])],
        UnsupportedTypeError,
    ),
    # Bad values
    (
        ["--a", "hello"],
        [("a", Arg("--a"), int)],
        CliParserError,
    ),
    # Unrecognized, missing or duplicate arguments
    (["--a", "1", "--b", "2"], [("a", Arg("--a"), str)], CliParserError),
    (["--a", "1"], [("a", Arg(), str)], CliParserError),
    (["--b", "1"], [("a", Arg(), str), ("b", Arg("--b"), str)], CliParserError),
    (
        ["--a", "1"],
        [("a", Arg("--a"), str), ("a", Arg("--a"), str)],
        argparse.ArgumentError,
    ),
    (
        ["--a", "1", "--b", "2"],
        [("a", Arg("--a", "-A"), str), ("b", Arg("--b", "-A"), str)],
        argparse.ArgumentError,
    ),
    # Literals
    (
        ["--a", "fries"],
        [("a", Arg("--a"), Literal["pizza", "pasta", "burger"])],
        CliParserError,
    ),
    # Enums
    (["--a", "fries"], [("a", Arg("--a"), FoodEnum)], CliParserError),
]


@pytest.mark.parametrize(
    "args,arg_info,expected",
    GOOD_TEST_CASES,
)
def test_parser_good(args, arg_info, expected):
    cli = Radicli()
    assert cli.parse(args, arg_info) == expected


@pytest.mark.parametrize(
    "args,arg_info,expected",
    GOOD_WITH_EXTRA_TEST_CASES,
)
def test_parser_good_with_extra(args, arg_info, expected):
    cli = Radicli(extra_key=EXTRA_KEY)
    assert cli.parse(args, arg_info, allow_extra=True) == expected


@pytest.mark.parametrize(
    "args,get_arg_args,expected_error",
    BAD_TEST_CASES,
)
def test_parser_bad(args, get_arg_args, expected_error):
    cli = Radicli()
    with pytest.raises(expected_error):
        arg_info = [get_arg(*args) for args in get_arg_args]
        cli.parse(args, arg_info)
