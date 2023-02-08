from typing import List, Iterator, Optional, Literal
from enum import Enum
from dataclasses import dataclass
import pytest
import sys
from contextlib import contextmanager
import tempfile
import shutil
from pathlib import Path
from radicli import Radicli, Arg
from radicli.util import CommandNotFoundError, CliParserError
from radicli.util import ExistingPath, ExistingFilePath, ExistingDirPath
from radicli.util import ExistingFilePathOrDash


@contextmanager
def make_tempdir() -> Iterator[Path]:
    """Run a block in a temp directory and remove it afterwards."""
    d = Path(tempfile.mkdtemp())
    yield d
    shutil.rmtree(str(d))


def test_cli_sys_argv():
    cli = Radicli()
    ran = False

    @cli.command("test")
    def test(a: str, b: int, c: float):
        assert a == "hello"
        assert b == 1
        assert c == 2.0
        nonlocal ran
        ran = True

    sys.argv = ["", "test", "hello", "1", "2"]
    cli.run()
    assert ran


def test_cli_no_annots():
    cli = Radicli()
    ran = False

    @cli.command("test")
    def test(a: str, b: int, c: float):
        assert a == "hello"
        assert b == 1
        assert c == 2.0
        nonlocal ran
        ran = True

    cli.run(["", "test", "hello", "1", "2"])
    assert ran


def test_cli_mix():
    cli = Radicli()
    ran = False

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

    cli.run(["", "test", "hello", "--b", "2", "-C", "3", "--d", "-E"])
    assert ran


def test_cli_lists():
    cli = Radicli()
    ran = False

    @cli.command("test", a=Arg("--a"), b=Arg("--b"), c=Arg("--c"))
    def test(a: str, b: List[str], c: Optional[List[int]] = None):
        assert a == "hello"
        assert b == ["one", "two"]
        assert c is None
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "hello", "--b", "one", "--b", "two"])
    assert ran


def test_cli_different_dest():
    cli = Radicli()
    ran = False

    @cli.command("test", first=Arg("--a"), second=Arg("--b"))
    def test(first: str, second: str):
        assert first == "one"
        assert second == "two"
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "one", "--b", "two"])
    assert ran


def test_cli_defaults():
    cli = Radicli()
    ran = False

    @cli.command("test", a=Arg(), b=Arg(), c=Arg("--c"), d=Arg("--d"))
    def test(a: str, b: str = "hey", *, c: List[str], d: Optional[List[int]] = None):
        assert a == "yo"
        assert b == "hey"
        assert c == ["one"]
        assert d is None
        nonlocal ran
        ran = True

    cli.run(["", "test", "yo", "--c", "one"])
    assert ran


def test_cli_literals():
    cli = Radicli()
    ran = False

    @cli.command("test", a=Arg("--a"), b=Arg("--b"))
    def test(a: Literal["pizza", "pasta"], b: Literal["cola", "fanta"]):
        assert a == "pizza"
        assert b == "fanta"
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "pizza", "--b", "fanta"])
    assert ran


def test_cli_literals_list():
    cli = Radicli()
    ran = False

    @cli.command("test", a=Arg("--a"))
    def test(a: List[Literal["pizza", "pasta", "burger"]]):
        assert a == ["pasta", "pizza"]
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "pasta", "--a", "pizza"])
    assert ran

    with pytest.raises(CliParserError):
        cli.run(["", "test", "--a", "burger", "--a", "fries"])


def test_cli_enums():
    cli = Radicli()
    ran = False

    class FoodEnum(Enum):
        pizza = "🍕"
        pasta = "🍝"
        burger = "🍔"

    class DrinkEnum(Enum):
        soda = "🥤"
        juice = "🧃"
        beer = "🍺"

    @cli.command("test", a=Arg("--a"), b=Arg("--b"))
    def test(a: FoodEnum, b: DrinkEnum):
        assert a == FoodEnum.burger
        assert b == DrinkEnum.beer
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "burger", "--b", "beer"])
    assert ran


@pytest.mark.parametrize(
    "args,count",
    [(["--verbose", "--verbose"], 2), (["-VVVVV"], 5)],
)
def test_cli_count(args, count):
    cli = Radicli()
    ran = False

    @cli.command("test", verbose=Arg("--verbose", "-V", count=True))
    def test(verbose: int):
        assert verbose == count
        nonlocal ran
        ran = True

    cli.run(["", "test", *args])
    assert ran


def test_cli_converter():
    cli = Radicli()
    converter = lambda x: x.upper()
    ran = False

    @cli.command("test", a=Arg("--a"), b=Arg("--b", converter=converter))
    def test(a: str, b: str):
        assert a == "hello"
        assert b == "WORLD"
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "hello", "--b", "world"])
    assert ran


def test_cli_invalid_converter():
    """Test that errors in converters aren't masked by argparse."""
    # Previously: argument --a: invalid converter value: 'hello'
    cli = Radicli()
    error_msg = "This is an error!"

    def converter(value):
        raise TypeError(error_msg)

    @cli.command("test", a=Arg("--a", converter=converter))
    def test(a: str):
        ...

    with pytest.raises(CliParserError, match=error_msg):
        cli.run(["", "test", "--a", "hello"])


def test_cli_global_converters():
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

    cli = Radicli(converters=converters)
    ran = False

    @cli.command("test", a=Arg("--a"), b=Arg("--b"), c=Arg("--c"))
    def test(a: str, b: List[str], c: CustomType):
        assert a == "HELLO"
        assert b == ["FOO", "BAR"]
        assert isinstance(c, CustomType)
        assert c.id == 123
        assert c.name == "Person"
        nonlocal ran
        ran = True

    args = ["", "test", "--a", "hello", "--b", "foo", "--b", "bar", "--c", "123|Person"]
    cli.run(args)
    assert ran


def test_cli_with_extra():
    cli = Radicli()
    ran = False

    @cli.command_with_extra("test", a=Arg("--a"), b=Arg("--b"))
    def test(a: str, b: int, _extra: List[str]):
        assert a == "hello"
        assert b == 1
        assert _extra == ["--hello", "2", "--world"]
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "hello", "--b", "1", "--hello", "2", "--world"])
    assert ran


def test_cli_with_extra_custom_key():
    cli = Radicli(extra_key="additional")
    ran = False

    @cli.command_with_extra("test", a=Arg("--a"), b=Arg("--b"))
    def test(a: str, b: int, additional: List[str]):
        assert a == "hello"
        assert b == 1
        assert additional == ["--hello", "2", "--world"]
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "hello", "--b", "1", "--hello", "2", "--world"])
    assert ran


def test_cli_subcommands():
    cli = Radicli()
    ran_parent = False
    ran_child1 = False
    ran_child2 = False

    @cli.command("test", a=Arg("--a"), b=Arg("--b"))
    def test(a: int, b: str):
        # Base command to prevent triggering single-command use case
        ...

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

    args_parent = ["--a", "1", "--b", "hello"]
    args_child1 = ["--a", "hey", "--b", "2", "--c"]
    args_child2 = ["yo", "--y", "pasta"]

    cli.run(["", "parent", *args_parent])
    assert ran_parent
    cli.run(["", "parent", "child1", *args_child1])
    assert ran_child1
    cli.run(["", "parent", "child2", *args_child2])
    assert ran_child2
    with pytest.raises(CommandNotFoundError):
        cli.run(["", "child1", *args_child1])
    with pytest.raises(CliParserError):
        cli.run(["", "parent", "child3"])
    with pytest.raises(CliParserError):
        cli.run(["", "parent", "child2", *args_child1])


def test_cli_subcommands_parent_extra():
    # Known limitation: extra arguments on parents with subcommands need to
    # be prefixed by - or --, otherwise they'll be falsely interpreted as a
    # subcommand.
    cli = Radicli()
    ran_parent = False
    ran_child = False

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

    cli.run(["", "parent", "--a", "1", "--b", "hello", "--xyz"])
    assert ran_parent
    cli.run(["", "parent", "child", "--a", "hey", "--b", "2"])
    assert ran_child


def test_cli_subcommands_child_extra():
    cli = Radicli()
    ran_parent = False
    ran_child = False

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

    cli.run(["", "parent", "--a", "1", "--b", "hello"])
    assert ran_parent
    cli.run(["", "parent", "child", "--a", "hey", "--b", "2", "xyz"])
    assert ran_child


def test_cli_subcommands_no_parent():
    cli = Radicli()
    ran_child1 = False
    ran_child2 = False

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

    cli.run(["", "parent", "child1", "--a", "hey", "--b", "2", "--c"])
    assert ran_child1
    cli.run(["", "parent", "child2", "yo", "--y", "pasta"])
    assert ran_child2


def test_cli_path_converters():
    cli = Radicli()
    dir_name = "my_dir"
    file_name = "my_file.txt"
    ran = False

    @cli.command("test", a=Arg("--a"), b=Arg("--b"), c=Arg("--c"))
    def test(a: ExistingPath, b: ExistingFilePath, c: ExistingDirPath):
        assert str(a) == str(file_path)
        assert str(b) == str(file_path)
        assert str(c) == str(dir_path)
        nonlocal ran
        ran = True

    with make_tempdir() as d:
        dir_path = d / dir_name
        dir_path.mkdir()
        file_path = d / file_name
        file_path.touch()
        bad_path = Path(d / "x.txt")

        args1 = ["--a", str(file_path), "--b", str(file_path), "--c", str(dir_path)]
        args2 = ["--a", str(bad_path), "--b", str(file_path), "--c", str(dir_path)]
        args3 = ["--a", str(file_path), "--b", str(dir_path), "--c", str(dir_path)]
        args4 = ["--a", str(file_path), "--b", str(file_path), "--c", str(file_path)]

        cli.run(["", "test", *args1])
        assert ran
        with pytest.raises(CliParserError):
            cli.run(["", "test", *args2])
        with pytest.raises(CliParserError):
            cli.run(["", "test", *args3])
        with pytest.raises(CliParserError):
            cli.run(["", "test", *args4])


def test_cli_path_or_dash():
    cli = Radicli()
    file_name = "my_file.txt"
    ran1 = False
    ran2 = False

    @cli.command("test1", a=Arg())
    def test1(a: ExistingFilePathOrDash):
        assert str(a) == str(file_path)
        nonlocal ran1
        ran1 = True

    @cli.command("test2", a=Arg())
    def test2(a: ExistingFilePathOrDash):
        assert a == "-"
        nonlocal ran2
        ran2 = True

    with make_tempdir() as d:
        file_path = d / file_name
        file_path.touch()
        bad_path = Path(d / "x.txt")

        cli.run(["", "test1", str(file_path)])
        assert ran1
        cli.run(["", "test2", "-"])
        assert ran2
        with pytest.raises(CliParserError):
            cli.run(["", "test1", str(bad_path)])
        with pytest.raises(CliParserError):
            cli.run(["", "test2", "_"])


def test_cli_stack_decorators():
    cli = Radicli()
    ran = 0

    @cli.command("one", a=Arg("--a"), b=Arg("--b"))
    @cli.command("two", a=Arg("--a"), b=Arg("--b"))
    @cli.command("three", a=Arg("--a"), b=Arg("--b"))
    def test(a: str, b: int):
        assert a == "hello"
        assert b == 1
        nonlocal ran
        ran += 1

    args = ["--a", "hello", "--b", "1"]
    cli.run(["", "one", *args])
    assert ran == 1
    cli.run(["", "two", *args])
    assert ran == 2
    cli.run(["", "three", *args])
    assert ran == 3


def test_cli_custom_help_arg():
    cli = Radicli()
    ran = False

    @cli.command("test", a=Arg("--a"), show_help=Arg("--help"))
    def test(a: str, show_help: bool):
        assert a == "hello"
        assert show_help
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "hello", "--help"])
    assert ran


def test_single_command():
    """Test that the name can be left out for CLIs with only one command."""
    cli = Radicli()
    ran = False

    @cli.command("test", a=Arg("--a"))
    def test(a: str):
        assert a == "hello"
        nonlocal ran
        ran = True

    cli.run(["", "--a", "hello"])
    assert ran


def test_single_command_subcommands():
    """Test that the name can be left out for CLIs with only one command."""
    cli = Radicli()
    ran_parent = False
    ran_child = False

    @cli.command("parent", a=Arg("--a"))
    def parent(a: str):
        assert a == "hello"
        nonlocal ran_parent
        ran_parent = True

    @cli.subcommand("parent", "child", a=Arg("--a"))
    def child(a: str):
        assert a == "hello"
        nonlocal ran_child
        ran_child = True

    cli.run(["", "--a", "hello"])
    assert ran_parent
    cli.run(["", "child", "--a", "hello"])
    assert ran_child
