from typing import List, Iterator, Optional, Dict, Any, Literal
import pytest
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from radicli import Radicli, Arg
from radicli.util import SimpleFrozenDict, CommandNotFoundError


@contextmanager
def cli_context(
    command: str, args: List[str], settings: Dict[str, Any] = SimpleFrozenDict()
) -> Iterator[Radicli]:
    sys.argv = ["", command, *args]
    cli = Radicli("test", **settings)
    yield cli
    cli.run()


def test_cli_no_annots():
    args = ["hello", "1", "2"]
    ran = False

    with cli_context("test", args) as cli:

        @cli.command("test")
        def test(a: str, b: int, c: float):
            assert a == "hello"
            assert b == 1
            assert c == 2.0
            nonlocal ran
            ran = True

    assert ran


def test_cli_mix():
    args = ["hello", "--b", "2", "-C", "3", "--d", "-E"]
    ran = False
    with cli_context("test", args) as cli:

        @cli.command(
            "test",
            a=Arg(),
            b=Arg("--b", "-B"),
            c=Arg("--c", "-C"),
            d=Arg("--d", "-D"),
            e=Arg("--e", "-E"),
            f=Arg("--f", "-F"),
            g=Arg("--g", "-G"),
        )
        def test(a: str, b: int, c: float, d: bool, e: bool, f: bool, g: str = "yo"):
            assert a == "hello"
            assert b == 2
            assert c == 3.0
            assert d is True
            assert e is True
            assert f is False
            assert g == "yo"
            nonlocal ran
            ran = True

    assert ran


def test_cli_lists():
    args = ["--a", "hello", "--b", "one", "--b", "two"]
    ran = False

    with cli_context("test", args) as cli:

        @cli.command("test", a=Arg("--a"), b=Arg("--b"), c=Arg("--c"))
        def test(a: str, b: List[str], c: Optional[List[int]] = None):
            assert a == "hello"
            assert b == ["one", "two"]
            assert c is None
            nonlocal ran
            ran = True

    assert ran


def test_cli_defaults():
    args = ["yo", "--c", "one"]
    ran = False

    with cli_context("test", args) as cli:

        @cli.command("test", a=Arg(), b=Arg(), c=Arg("--c"), d=Arg("--d"))
        def test(
            a: str, b: str = "hey", *, c: List[str], d: Optional[List[int]] = None
        ):
            assert a == "yo"
            assert b == "hey"
            assert c == ["one"]
            assert d is None
            nonlocal ran
            ran = True

    assert ran


def test_cli_literals():
    args = ["--a", "pizza", "--b", "fanta"]
    ran = False

    with cli_context("test", args) as cli:

        @cli.command("test", a=Arg("--a"), b=Arg("--b"))
        def test(a: Literal["pizza", "pasta"], b: Literal["cola", "fanta"]):
            assert a == "pizza"
            assert b == "fanta"
            nonlocal ran
            ran = True

    assert ran


def test_cli_converter():
    args = ["--a", "hello", "--b", "world"]
    converter = lambda x: x.upper()
    ran = False

    with cli_context("test", args) as cli:

        @cli.command("test", a=Arg("--a"), b=Arg("--b", converter=converter))
        def test(a: str, b: str):
            assert a == "hello"
            assert b == "WORLD"
            nonlocal ran
            ran = True

    assert ran


def test_cli_global_converters():
    args = ["--a", "hello", "--b", "foo", "--b", "bar", "--c", "123|Person"]
    collected = []

    def convert_list(value: str):
        collected.append(value.upper())
        return collected

    @dataclass
    class CustomType:
        id: int
        name: str

    def convert_custom_type(value: str):
        c_id, name = value.split("|")
        return CustomType(id=int(c_id), name=name)

    converters = {
        str: lambda x: x.upper(),
        List[str]: convert_list,
        CustomType: convert_custom_type,
    }
    ran = False

    with cli_context("test", args, {"converters": converters}) as cli:

        @cli.command("test", a=Arg("--a"), b=Arg("--b"), c=Arg("--c"))
        def test(a: str, b: List[str], c: CustomType):
            assert a == "HELLO"
            assert b == ["FOO", "BAR"]
            assert isinstance(c, CustomType)
            assert c.id == 123
            assert c.name == "Person"
            nonlocal ran
            ran = True

    assert ran


def test_cli_with_extra():
    args = ["--a", "hello", "--b", "1", "--hello", "2", "--world"]
    ran = False

    with cli_context("test", args) as cli:

        @cli.command_with_extra("test", a=Arg("--a"), b=Arg("--b"))
        def test(a: str, b: int, _extra: List[str]):
            assert a == "hello"
            assert b == 1
            assert _extra == ["--hello", "2", "--world"]
            nonlocal ran
            ran = True

    assert ran


def test_cli_with_extra_custom_key():
    args = ["--a", "hello", "--b", "1", "--hello", "2", "--world"]
    ran = False

    with cli_context("test", args, {"extra_key": "additional"}) as cli:

        @cli.command_with_extra("test", a=Arg("--a"), b=Arg("--b"))
        def test(a: str, b: int, additional: List[str]):
            assert a == "hello"
            assert b == 1
            assert additional == ["--hello", "2", "--world"]
            nonlocal ran
            ran = True

    assert ran


def test_cli_subcommands():
    args_parent = ["--a", "1", "--b", "hello"]
    args_child1 = ["--a", "hey", "--b", "2", "--c"]
    args_child2 = ["yo", "--y", "pasta"]
    ran_parent = False
    ran_child1 = False
    ran_child2 = False

    cli = Radicli("test")

    @cli.command("parent", a=Arg("--a"), b=Arg("--b"))
    def parent(a: int, b: str):
        assert a == 1
        assert b == "hello"
        nonlocal ran_parent
        ran_parent = True

    @cli.subcommand("parent", "child1", a=Arg("--a"), b=Arg("--b"), c=Arg("--c"))
    def child1(a: str, b: int, c: bool):
        assert a == "hey"
        assert b == 2
        assert c
        nonlocal ran_child1
        ran_child1 = True

    @cli.subcommand("parent", "child2", x=Arg(), y=Arg("--y"))
    def child2(x: str, y: Literal["pizza", "pasta"]):
        assert x == "yo"
        assert y == "pasta"
        nonlocal ran_child2
        ran_child2 = True

    sys.argv = ["", "parent", *args_parent]
    cli.run()
    assert ran_parent

    sys.argv = ["", "parent", "child1", *args_child1]
    cli.run()
    assert ran_child1

    sys.argv = ["", "parent", "child2", *args_child2]
    cli.run()
    assert ran_child2

    sys.argv = ["", "child1", *args_child1]
    with pytest.raises(CommandNotFoundError):
        cli.run()

    sys.argv = ["", "parent", "child3"]
    with pytest.raises(SystemExit):
        cli.run()

    sys.argv = ["", "parent", "child2", *args_child1]
    with pytest.raises(SystemExit):
        cli.run()


def test_cli_subcommands_parent_extra():
    # Known limitation: extra arguments on parents with subcommands need to
    # be prefixed by - or --, otherwise they'll be falsely interpreted as a
    # subcommand.
    args_parent = ["--a", "1", "--b", "hello", "--xyz"]
    args_child = ["--a", "hey", "--b", "2"]
    ran_parent = False
    ran_child = False

    cli = Radicli("test")

    @cli.command_with_extra("parent", a=Arg("--a"), b=Arg("--b"))
    def parent(a: int, b: str, _extra: List[str]):
        assert a == 1
        assert b == "hello"
        assert _extra == ["--xyz"]
        nonlocal ran_parent
        ran_parent = True

    @cli.subcommand("parent", "child", a=Arg("--a"), b=Arg("--b"))
    def child(a: str, b: int):
        assert a == "hey"
        assert b == 2
        nonlocal ran_child
        ran_child = True

    sys.argv = ["", "parent", *args_parent]
    cli.run()
    assert ran_parent

    sys.argv = ["", "parent", "child", *args_child]
    cli.run()
    assert ran_child


def test_cli_subcommands_child_extra():
    args_parent = ["--a", "1", "--b", "hello"]
    args_child = ["--a", "hey", "--b", "2", "xyz"]
    ran_parent = False
    ran_child = False

    cli = Radicli("test")

    @cli.command("parent", a=Arg("--a"), b=Arg("--b"))
    def parent(a: int, b: str):
        assert a == 1
        assert b == "hello"
        nonlocal ran_parent
        ran_parent = True

    @cli.subcommand_with_extra("parent", "child", a=Arg("--a"), b=Arg("--b"))
    def child(a: str, b: int, _extra: List[str]):
        assert a == "hey"
        assert b == 2
        assert _extra == ["xyz"]
        nonlocal ran_child
        ran_child = True

    sys.argv = ["", "parent", *args_parent]
    cli.run()
    assert ran_parent

    sys.argv = ["", "parent", "child", *args_child]
    cli.run()
    assert ran_child
