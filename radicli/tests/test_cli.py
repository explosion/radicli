from typing import List, Iterator, Optional, Dict, Any, Literal
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from radicli import Radicli, Arg
from radicli.util import SimpleFrozenDict


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
