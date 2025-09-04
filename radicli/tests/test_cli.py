from typing import List, Iterator, Optional, Literal, TypeVar, Generic, Type, Union, cast
from enum import Enum
from dataclasses import dataclass
import pytest
import sys
from contextlib import contextmanager
import tempfile
import shutil
from zipfile import ZipFile
from pathlib import Path
from radicli import Radicli, StaticRadicli, Arg, get_arg, ArgparseArg, Command
from radicli.util import CommandNotFoundError, CliParserError
from radicli.util import ExistingPath, ExistingFilePath, ExistingDirPath
from radicli.util import ExistingFilePathOrDash, DEFAULT_CONVERTERS, ConvertersType
from radicli.util import stringify_type, get_list_converter, format_type


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


def test_cli_required():
    cli = Radicli()

    @cli.command("test", a=Arg(), b=Arg("--b"), c=Arg("--c"), d=Arg("--d"))
    def test(a: str, b: str, c: int, d: int = 0):
        ...

    with pytest.raises(CliParserError) as err:
        cli.run(["", "test", "hello", "--c", "1"])
    assert str(err.value).endswith("required: --b")
    with pytest.raises(CliParserError) as err:
        cli.run(["", "test", "--b", "hello", "--c", "1"])
    assert str(err.value).endswith("required: a")
    with pytest.raises(CliParserError) as err:
        # Positional, so this is parsed in argparse before it hits custom logic
        cli.run(["", "test", "--c", "1"])
    assert str(err.value).endswith("required: a")
    with pytest.raises(CliParserError) as err:
        cli.run(["", "test", "hello", "--d", "1"])
    assert str(err.value).endswith("required: --b, --c")


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


_KindT = TypeVar("_KindT", bound=Union[str, int, float, Path])


class CustomGeneric(Generic[_KindT]):
    ...


def test_cli_converters_generics():
    converters = {CustomGeneric: lambda value: f"generic: {value}"}
    cli = Radicli(converters=cast(ConvertersType, converters))
    ran = False

    @cli.command("test", a=Arg("--a"))
    def test(a: CustomGeneric[str]):
        assert a == "generic: x"
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "x"])
    assert ran


def test_cli_converters_generics_multiple():
    _KindT = TypeVar("_KindT")

    class CustomGeneric(Generic[_KindT]):
        ...

    converters = {
        CustomGeneric: lambda value: f"generic: {value}",
        CustomGeneric[str]: lambda value: f"generic str: {value}",
        CustomGeneric[int]: lambda value: f"generic int: {value}",
    }
    cli = Radicli(converters=converters)
    ran = False

    @cli.command("test", a=Arg("--a"), b=Arg("--b"), c=Arg("--c"), d=Arg("--d"))
    def test(
        a: CustomGeneric,
        b: CustomGeneric[Path],
        c: CustomGeneric[str],
        d: CustomGeneric[int],
    ):
        assert a == "generic: x"
        assert b == "generic: y"
        assert c == "generic str: z"
        assert d == "generic int: 3"
        nonlocal ran
        ran = True

    cli.run(["", "test", "--a", "x", "--b", "y", "--c", "z", "--d", "3"])
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


def test_cli_version(capsys):
    version = "1.2.3"
    cli = Radicli(version=version)
    ran = False

    @cli.command("test", a=Arg("--a"))
    def test(a: str):
        assert a == "hello"
        nonlocal ran
        ran = True

    with pytest.raises(SystemExit):
        cli.run(["", "--version"])
    captured = capsys.readouterr()
    assert captured.out.strip() == version
    cli.run(["", "test", "--a", "hello"])
    assert ran


def test_cli_version_multiple_commands(capsys):
    # Test --version also works on the top-level with no command specified
    version = "1.2.3"
    cli = Radicli(version=version)
    ran1 = False
    ran2 = False

    @cli.command("test1", a=Arg("--a"))
    def test1(a: str):
        nonlocal ran1
        ran1 = True

    @cli.command("test2", a=Arg("--a"))
    def test2(a: str):
        nonlocal ran2
        ran2 = True

    with pytest.raises(SystemExit):
        cli.run(["", "--version"])
    captured = capsys.readouterr()
    assert captured.out.strip() == version
    assert not ran1
    assert not ran2


def test_cli_single_command():
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


def test_cli_single_command_subcommands():
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


@pytest.mark.parametrize(
    "raise_error, handle_errors, handler_return, expect_handled, expect_exit",
    [
        (None, [KeyError], None, False, False),
        (KeyError, [KeyError], None, True, False),
        (KeyError, [KeyError], 1, True, True),
        (KeyError, [], 1, True, True),
        (KeyError, [ValueError], 1, True, True),
    ],
)
def test_cli_errors(
    raise_error: Optional[Type[Exception]],
    handle_errors: List[Type[Exception]],
    handler_return: Optional[int],
    expect_handled: bool,
    expect_exit: bool,
):
    handler_ran = False

    def error_handler(e: Exception) -> Optional[int]:
        nonlocal handler_ran
        handler_ran = True
        return handler_return

    cli = Radicli(errors={e: error_handler for e in handle_errors})

    @cli.command("test")
    def test():
        nonlocal ran
        ran = True
        if raise_error is not None:
            raise raise_error

    ran = False

    if raise_error is not None and raise_error not in handle_errors:
        with pytest.raises(raise_error):
            cli.run(["", "test"])
    elif expect_exit:
        with pytest.raises(SystemExit):
            cli.run(["", "test"])
    else:
        cli.run(["", "test"])
        assert ran
        assert handler_ran is expect_handled


def test_cli_static_roundtrip(capsys):
    cli = Radicli(prog="test")

    @cli.command("hello", a=Arg("--a", help="aaa"), b=Arg("--b", help="bbb"))
    def hello(a, b):
        """Hello"""
        ...

    @cli.command("world", c=Arg(help="ccc"))
    def world(c):
        """World"""
        ...

    with make_tempdir() as dir_path:
        path = dir_path / "static.json"
        cli.to_static(path)

        static = StaticRadicli.load(path)

    assert static.prog == cli.prog
    assert len(static.commands) == len(cli.commands)
    for parent, commands in static.subcommands:
        assert parent in cli.subcommands
        assert len(cli.subcommands[parent]) == len(commands)

    hello1 = static.commands["hello"]
    hello2 = cli.commands["hello"]
    assert hello1.name == hello2.name
    assert hello1.description == hello2.description
    for arg1, arg2 in zip(hello1.args, hello2.args):
        assert arg1.help == arg2.help
        assert arg1.arg.option == arg2.arg.option
        assert arg1.arg.short == arg2.arg.short
        assert arg1.arg.help == arg2.arg.help

    with pytest.raises(SystemExit):
        static.run(["", "--help"])
    captured1 = capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.run(["", "--help"])
    captured2 = capsys.readouterr().out
    assert captured1 == captured2

    with pytest.raises(SystemExit):
        static.run(["", "hello", "--help"])
    captured1 = capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.run(["", "hello", "--help"])
    captured2 = capsys.readouterr().out
    assert captured1 == captured2

    with pytest.raises(SystemExit):
        static.run(["", "world", "--help"])
    captured1 = capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.run(["", "world", "--help"])
    captured2 = capsys.readouterr().out
    assert captured1 == captured2

    with make_tempdir() as dir_path:
        path = dir_path / "static.json"
        cli.to_static(path)

        static = StaticRadicli.load(path, debug=True)

    with pytest.raises(SystemExit):
        static.run(["", "hello", "--help"])
    captured = capsys.readouterr().out
    assert static._debug_start in captured

    static.disable = True
    static.run(["", "hello", "--help"])
    captured = capsys.readouterr().out
    assert not captured


@pytest.mark.parametrize(
    "arg_type",
    [
        str,
        int,
        float,
        bool,
        List[str],
        Path,
        ExistingPath,
        ExistingFilePath,
        ExistingDirPath,
        ExistingFilePathOrDash,
        Literal["a", "b", "c"],
    ],
)
def test_static_deserialize_types(arg_type):
    """Test that supported and built-in types are correctly deserialized from static"""
    get_converter = lambda v: DEFAULT_CONVERTERS.get(v)
    arg = get_arg(
        "test", Arg("--test"), arg_type, orig_type=arg_type, get_converter=get_converter
    )
    arg_json = arg.to_static_json()
    new_arg = ArgparseArg.from_static_json(arg_json)
    assert new_arg.type == arg.type
    assert new_arg.orig_type == stringify_type(arg.orig_type)
    assert new_arg.has_converter == arg.has_converter
    assert new_arg.action == arg.action


@pytest.mark.parametrize(
    "arg_type",
    [
        List[str],
        ZipFile,
        Optional[ZipFile],
        Union[ZipFile, str, Path],
        CustomGeneric,
        CustomGeneric[int],
        CustomGeneric[str],
        Optional[CustomGeneric],
    ],
)
def test_static_deserialize_types_custom_deserialize(arg_type):
    """Test deserialization with custom type deserializer"""

    split_string = get_list_converter(str)

    def convert_zipfile(value: str) -> ZipFile:
        return ZipFile(value, "r")

    def convert_generic(value: str) -> str:
        return f"generic: {value}"

    converters = {
        ZipFile: convert_zipfile,  # new type with custom converter
        List[str]: split_string,
        CustomGeneric: convert_generic,
        CustomGeneric[str]: str,
    }
    get_converter = lambda v: converters.get(v)
    # With converters set
    arg = get_arg(
        "test", Arg("--test"), arg_type, orig_type=arg_type, get_converter=get_converter
    )
    arg_json = arg.to_static_json()
    new_arg = ArgparseArg.from_static_json(arg_json, converters=converters)
    assert new_arg.type == arg.type
    assert new_arg.orig_type == stringify_type(arg.orig_type)
    assert new_arg.has_converter == arg.has_converter
    assert new_arg.action == arg.action
    # With no converters set
    arg = get_arg(
        "test", Arg("--test"), arg_type, orig_type=arg_type, get_converter=get_converter
    )
    arg_json = arg.to_static_json()
    new_arg = ArgparseArg.from_static_json(arg_json)
    assert new_arg.type is str
    assert new_arg.orig_type == stringify_type(arg.orig_type)


def test_static_default_serialization():
    cli = Radicli(prog="test")

    @cli.command("test", a=Arg("--a", short='-a'))
    def _(a: List[str]=[]):
        """Hello"""

    with make_tempdir() as dir_path:
        path = dir_path / "static.json"
        cli.to_static(path)

        static = StaticRadicli.load(path)

    static.run(["", "test", "-a", "1"])


@pytest.mark.parametrize(
    "arg_type,expected_type,expected_str",
    [
        (str, str, "str"),
        (List[str], List[str], "List[str]"),
        (Optional[List[str]], List[str], "List[str]"),
        (Union[str, int], str, "str"),
        (CustomGeneric, CustomGeneric, "CustomGeneric"),
        (CustomGeneric[str], CustomGeneric[str], "CustomGeneric[str]"),
        (ExistingFilePath, ExistingFilePath, "ExistingFilePath (Path)"),
        (ZipFile, ZipFile, "ZipFile"),
    ],
)
def test_cli_arg_display_type(arg_type, expected_type, expected_str):
    split_string = get_list_converter(str)

    def convert_zipfile(value: str) -> ZipFile:
        return ZipFile(value, "r")

    def convert_generic(value: str) -> str:
        return f"generic: {value}"

    converters = {
        **DEFAULT_CONVERTERS,
        ZipFile: convert_zipfile,  # new type with custom converter
        List[str]: split_string,
        CustomGeneric: convert_generic,
        CustomGeneric[str]: str,
    }

    def test(test: arg_type):  # type: ignore
        ...

    cmd = Command.from_function(
        "test", {"test": Arg("--test")}, test, converters=converters
    )
    arg = cmd.args[0]
    assert arg.display_type == expected_type
    assert format_type(arg.display_type) == expected_str


def test_cli_no_defaults():
    cli = Radicli(fill_defaults=False)
    ran = False

    @cli.command(
        "test",
        a=Arg(),
        b=Arg(),
        c=Arg("--c", "-C"),
        d=Arg("--d", "-D"),
        e=Arg("--e", "-E"),
    )
    def test(a: str, b: str = "1", *, c: int = 1, d: bool = False, e: str = "yo"):
        assert a == "hello"
        assert b == "1"
        assert c == 3
        assert d is True
        assert e == "yo"
        nonlocal ran
        ran = True

    args = ["hello", "--c", "3", "--d"]
    parsed = cli.parse(args, cli.commands["test"])
    assert parsed == {"a": "hello", "c": 3, "d": True}
    cli.run(["", *args])
    assert ran
    # Make sure that set defaults are still preserved
    args = ["hello", "--c", "1", "--d"]
    parsed = cli.parse(args, cli.commands["test"])
    assert parsed == {"a": "hello", "c": 1, "d": True}


def test_cli_booleans():
    cli = Radicli()

    @cli.command(
        "test",
        a=Arg("--a"),
        b=Arg("--b"),
        c=Arg("--c"),
    )
    def test(a: bool, b: bool = False, c: bool = True):
        ...

    args = ["--a", "--b", "--c"]
    parsed = cli.parse(args, cli.commands["test"])
    assert parsed == {"a": True, "b": True, "c": True}
    args = []
    parsed = cli.parse(args, cli.commands["test"])
    assert parsed == {"a": False, "b": False, "c": True}
    args = ["--no-c"]
    parsed = cli.parse(args, cli.commands["test"])
    assert parsed == {"a": False, "b": False, "c": False}
