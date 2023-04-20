from typing import Literal, cast
from pathlib import Path
from dataclasses import dataclass
from radicli import Radicli, Arg, ExistingFilePath


def test_document_cli():
    cli = Radicli(prog="rdc", help="This is a CLI")

    # Regular command
    @cli.command(
        "command1",
        arg1=Arg(help="Argument one"),
        arg2=Arg("--arg2", "-a2", help="Argument two"),
        arg3=Arg("--arg3", "-A3", help="Argument three"),
    )
    def command1(arg1: str, arg2: int = 2, arg3: bool = False):
        """This is command one."""
        ...

    # Placeholder with subcommands
    cli.placeholder("command2", description="This is command two")

    @cli.subcommand(
        "command2",
        "child",
        arg1=Arg("--arg1", "-a1", help="Argument one"),
        arg2=Arg("--arg2", help="Argument two"),
    )
    def child1(arg1: Path, arg2: Literal["foo", "bar"] = "bar"):
        """This is command 2 and its child."""
        ...

    @dataclass
    class MyCustomType:
        foo: str
        bar: str

    def convert_my_custom_type(v: str) -> MyCustomType:
        foo, bar = v.split(",")
        return MyCustomType(foo=foo, bar=bar)

    # Subcommand without parent
    @cli.subcommand(
        "command3",
        "child",
        arg1=Arg(help="Argument one", converter=convert_my_custom_type),
        arg2=Arg(help="Argument two"),
        arg3=Arg("--arg3", help="Argument three"),
    )
    def child2(
        arg1: MyCustomType,
        arg2: ExistingFilePath = cast(
            ExistingFilePath, Path(__file__).parent / "__init__.py"
        ),
        arg3: bool = True,
    ):
        """This is command 3 and its child."""

    docs = cli.document(
        title="Documentation",
        description="Here are the docs for my CLI",
        path_root=Path(__file__).parent,
    )
    assert docs == EXPECTED.strip()


EXPECTED = """
<!-- This file is auto-generated -->

# Documentation

Here are the docs for my CLI

## `rdc`

This is a CLI

### `rdc command1`

This is command one.

| Argument | Type | Description | Default |
| --- | --- | --- | --- |
| `arg1` | `str` | Argument one |  |
| `--arg2`, `-a2` | `int` | Argument two | `2` |
| `--arg3`, `-A3` | `bool` | Argument three | `False` |

### `rdc command2`

This is command two

#### `rdc command2 child`

This is command 2 and its child.

| Argument | Type | Description | Default |
| --- | --- | --- | --- |
| `--arg1`, `-a1` | `Path` | Argument one |  |
| `--arg2` | `str` | Argument two | `'bar'` |

### `rdc command3`

#### `rdc command3 child`

This is command 3 and its child.

| Argument | Type | Description | Default |
| --- | --- | --- | --- |
| `arg1` | `MyCustomType` | Argument one |  |
| `arg2` | `ExistingFilePath (Path)` | Argument two | `__init__.py` |
| `--arg3`/`--no-arg3` | `bool` | Argument three | `True` |
"""
