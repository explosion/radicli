<a href="https://explosion.ai"><img src="https://explosion.ai/assets/img/logo.svg" width="125" height="125" align="right" /></a>

# radicli: Radically lightweight command-line interfaces

`radicli` is a small, zero-dependency Python package for creating command line interfaces, built on top of Python's [`argparse`](https://docs.python.org/3/library/argparse.html) module. It introduces minimal overhead, preserves your original Python functions and uses type hints to parse values provided on the CLI. It supports all common types out-of-the-box, including complex ones like `List[str]`, `Literal` and `Enum`, and allows registering custom types with custom converters.

> **Important note:** This package aims to be a simple option based on the requirements of our libraries. If you're looking for a more full-featured CLI toolkit, check out [`typer`](https://typer.tiangolo.com), [`click`](https://click.palletsprojects.com) or [`plac`](https://plac.readthedocs.io/en/latest/).

[![GitHub Actions](https://github.com/explosion/radicli/actions/workflows/test.yml/badge.svg)](https://github.com/explosion/radicli/actions/workflows/test.yml)
[![Current Release Version](https://img.shields.io/github/v/release/explosion/radicli.svg?style=flat-square&include_prereleases&logo=github)](https://github.com/explosion/radicli/releases)
[![pypi Version](https://img.shields.io/pypi/v/radicli.svg?style=flat-square&logo=pypi&logoColor=white)](https://pypi.org/project/radicli/)

## ⏳ Installation

Note that `radicli` currently requires **Python 3.8+**.

```bash
pip install radicli
```

## 👩‍💻 Usage

The `Radicli` class sets up the CLI and provides decorators for commands and subcommands. The `Arg` dataclass can be used to describe how the arguments should be presented on the CLI. Types and defaults are read from the Python functions. You typically don't have to change anything about how you implement your Python functions to make them available as a CLI command.

```python
# cli.py
from radicli import Radicli, Arg

cli = Radicli()

@cli.command(
    "hello",
    name=Arg(help="Your name"),
    age=Arg("--age", "-a", help="Your age"),
    greet=Arg("--greet", "-G", help="Whether to greet"),
)
def hello(name: str, age: int, greet: bool = False):
    """Description of the function for help text."""
    if greet:
        print(f"Hello {name} ({age})!")

if __name__ == "__main__":
    cli.run()
```

```
$ python cli.py hello Alex --age 35 --greet
Hello Alex (35)!
```

If a file only specifies a **single command** (with or without subcommands), you can optionally leave out the
command name. So the above example script can also be called like this:

```
$ python cli.py Alex --age 35 --greet
Hello Alex (35)!
```

### Subcommands

`radicli` supports one level of nested subcommands. The parent command may exist independently, but it doesn't have to.

```python
@cli.subcommand("parent", "child1", name=Arg("--name", help="Your name"))
def parent_child1(name: str):
    ...

@cli.subcommand("parent", "child2", name=Arg("--age", help="Your age"))
def parent_child2(age: int):
    ...
```

```
$ python cli.py parent child1 --name Alex
$ python cli.py parent child2 --age 35
```

### Working with types

For built-in callable types like `str`, `int` or `float`, the string value received from the CLI is passed to the callable, e.g. `int(value)`. More complex, nested types are resolved recursively. The library also provides several built-in [custom types](#custom-types-and-converters) for handling things like file paths.

> ⚠️ Note that there's a limit to what can reasonably be supported by a CLI interface so it's recommended to avoid overly complex types. For a `Union` type, the **first** type of the union is used. `Optional` types are expected to be left unset to default to `None`. If a value is provided, the type marked as optional is used, e.g. `str` for `Optional[str]`.

#### Lists

By default, list types are implemented by allowing the CLI argument to occur more than once. The value of each element is parsed using the type defined for list members.

```python
@cli.command("hello", fruits=Arg("--fruits", help="One or more fruits"))
def hello(fruits: List[str]):
    print(fruits)
```

```
$ python cli.py hello --fruits apple --fruits banana --fruits cherry
['apple', 'banana', 'cherry']
```

If you don't like this syntax, you can also add a `converter` to the `Arg` definition that handles the value differently, e.g. by splitting a comma-separated string. This would let the user write `--fruits apple,banana,cherry`, while still passing a list to the Python function.

#### Literals and Enums

Arguments that can only be one of a given set of values can be typed as a `Literal`. Any values not in the list will raise a CLI error.

```python
@cli.command("hello", color=Arg("--color", help="Pick a color"))
def hello(color: Literal["red", "blue", "green"]):
    print(color)  # this will be a string
```

`Enum`s are also supported and in this case, the enum value (string) can be provided on the CLI and the function receives the selected enum member.

> ⚠️ Note that enum members don't show up as nicely in the command's `--help` and error messages, which can potentially lead to confusion. It's therefore better to use `Literal`s if possible.

```python
class ColorEnum(Enum):
    RED = "red"
    BLUE = "blue"
    GREEN = "green"

@cli.command("hello", color=Arg("--color", help="Pick a color"))
def hello(color: ColorEnum):
    print(color)  # this will be the enum, e.g. ColorEnum.RED
```

### Using custom types and converters

`radicli` supports defining custom converter functions to handle individual arguments, as well as all instances of a given type globally. Converters take the string value provided on the CLI and should return the value passed to the function, consistent with the type. They can also raise validation errors.

```python
format_name = lambda value: value.upper()

@cli.command("hello", name=Arg("--name", converter=format_name))
def hello(name: str):
    print(f"Hello {name}"!)
```

```
$ python cli.py hello --name Alex
Hello ALEX!
```

#### Global converters for custom types

The `converters` argument lets you provide a dict of types mapped to converter functions when initializing `Radicli`. If an argument of that target type is encountered, the input string value is converted automatically. This ensures your Python functions remain composable and don't need additional logic only to satisfy the CLI usage.

The following example shows how to register a custom converter that loads a [spaCy](https://spacy.io) pipeline from a string name, while allowing the function itself to require the `Language` object itself:

```python
import radicli
import spacy

def load_spacy_model(name: str) -> spacy.language.Language:
    return spacy.load(name)

converters = {spacy.language.Language: load_spacy_model}
cli = Radicli(converters=converters)

@cli.command(
    "process",
    nlp=Arg(help="The spaCy pipeline to use"),
    name=Arg("--text", help="The text to process")
)
def process_text(nlp: spacy.language.Language, text: str):
    doc = nlp(text)
    print(doc.text, [token.pos_ for token in doc])
```

```
$ python test.py process en_core_web_sm --text Hello world!
Hello world! ['INTJ', 'NOUN', 'PUNCT']
```

If you want to alias an existing type to add custom handling for it, you can create a `NewType`. This is also how the built-in [`Path` converters](#custom-types-and-converters) are implemented. In help messages, the type it is based on will be displayed together with the custom name.

```python
from typing import NewType
from pathlib import Path

ExistingPath = NewType("ExistingPath", Path)

def convert_existing_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.exists():
        raise ValueError(f"path does not exist: {path_str}")
    return path

converters = {ExistingPath: convert_existing_path}
```

### Allowing extra arguments

If you want to capture and consume extra arguments not defined in the function and argument annotations, you can use the `command_with_extra` or `subcommand_with_extra` decorators. Extra arguments are passed to the function as a list of strings to an argument `_extra` (which you can change via the `extra_key` setting when initializing the CLI). spaCy uses this feature to pass settings to `pip` in its [`download` command](https://spacy.io/api/cli#download) or to allow arbitrary [configuration overrides](https://spacy.io/usage/training#config-overrides) during training.

```python
@cli.command_with_extra("hello", name=Arg("--name", help="Your name"))
def hello(name: str, _extra: List[str] = []):
    print(f"Hello {name}!", _extra)
```

```
$ python cli.py hello --name Alex --age 35 --color blue
Hello Alex! ['--age', '35', '--color', 'blue']
```

## 🎛 API

### <kbd>dataclass</kbd> `Arg`

Dataclass for describing argument meta information. This is typically used in the command decorators and only includes information for how the argument should be handled on the CLI. Argument types and defaults are read from the Python function.

| Argument    | Type                             | Description                                                                                                 |
| ----------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `option`    | `Optional[str]`                  | Option to use on the CLI, e.g. `--arg`. If unset, argument will be treated as positional.                   |
| `short`     | `Optional[str]`                  | Shorthand for option, e.g. `-A`.                                                                            |
| `help`      | `Optional[str]`                  | Help text for argument, used for `--help`.                                                                  |
| `count`     | `bool`                           | Only count and return number of times an argument is used, e.g. `--verbose` or `-vvv` (for shorthand `-v`). |
| `converter` | `Optional[Callable[[str], Any]]` | Converter function that takes the string from the CLI value and returns a value passed to the function.     |

### <kbd>dataclass</kbd> `Command`

Internal representation of a CLI command. Can be accessed via `Radicli.commands` and `Radicli.subcommands`.

| Name           | Type                | Description                                                                                                 |
| -------------- | ------------------- | ----------------------------------------------------------------------------------------------------------- |
| `name`         | `str`               | The name of the command.                                                                                    |
| `func`         | `Callable`          | The decorated command function.                                                                             |
| `args`         | `List[ArgparseArg]` | The internal representation of the argument annotations. `Argparse.arg` lets you access the original `Arg`. |
| `description`  | `Optional[str]`     | The command description, taken from the function docstring.                                                 |
| `allow_extra`  | `bool`              | Whether to allow extra arguments.                                                                           |
| `parent`       | `Optional[str]`     | Name of the parent command if command is a subcommand.                                                      |
| `display_name` | `str`               | The display name including the parent if available, e.g. `parent child`.                                    |

### <kbd>class</kbd> `Radicli`

#### Attributes

| Name          | Type                               | Description                                                                            |
| ------------- | ---------------------------------- | -------------------------------------------------------------------------------------- |
| `prog`        | `str`                              | Program name displayed in `--help` propmt usage examples, e.g. `"python -m spacy"`.    |
| `help`        | `str`                              | Help text for the CLI, displayed in top-level `--help`.                                |
| `converters`  | `Dict[Type, Callable[[str], Any]]` | Dict mapping types to global converter functions.                                      |
| `commands`    | `Dict[str, Command]`               | The commands added to the CLI, keyed by name.                                          |
| `subcommands` | `Dict[str, Dict[str, Command]]`    | The subcommands added to the CLI, keyed by parent name, then keyed by subcommand name. |

#### <kbd>method</kbd> `Radicli.__init__`

Initialize the CLI and create the registry.

```python
from radicli import Radicli

cli = Radicli(prog="python -m spacy")
```

| Argument     | Type                               | Description                                                                                                                                               |
| ------------ | ---------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prog`       | `Optional[str]`                    | Program name displayed in `--help` prompt usage examples, e.g. `"python -m spacy"`.                                                                       |
| `help`       | `Optional[str]`                    | Help text for the CLI, displayed in top-level `--help`.                                                                                                   |
| `converters` | `Dict[Type, Callable[[str], Any]]` | Dict mapping types to converter functions. All arguments with these types will then be passed to the respective converter.                                |
| `extra_key`  | `str`                              | Name of function argument that receives extra arguments if the `command_with_extra` or `subcommand_with_extra` decorator is used. Defaults to `"_extra"`. |

#### <kbd>decorator</kbd> `Radicli.command`, `Radicli.command_with_extra`

The decorator used to wrap top-level command functions.

```python
@cli.command(
    "hello",
    name=Arg(help="Your name"),
    age=Arg("--age", "-a", help="Your age"),
    greet=Arg("--greet", "-G", help="Whether to greet"),
)
def hello(name: str, age: int, greet: bool = False) -> None:
    if greet:
        print(f"Hello {name} ({age})")
```

```
$ python cli.py hello Alex --age 35 --greet
Hello Alex (35)
```

```python
@cli.command_with_extra(
    "hello",
    name=Arg(help="Your name"),
    age=Arg("--age", "-A", help="Your age"),
)
def hello(name: str, age: int, _extra: List[str]) -> None:
    print(f"Hello {name} ({age})", _extra)
```

```
$ python cli.py hello Alex --age 35 --color red
Hello Alex (35) ['--color', 'red']
```

| Argument    | Type       | Description                                                                                                                                                                       |
| ----------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`      | `str`      | Name of the command.                                                                                                                                                              |
| `**args`    | `Arg`      | Keyword arguments defining the argument information. Names need to match the function arguments. If no argument annotations are defined, all arguments are treated as positional. |
| **RETURNS** | `Callable` | The wrapped function.                                                                                                                                                             |

#### <kbd>decorator</kbd> `Radicli.subcommand`, `Radicli.subcommand_with_extra`

The decorator used to wrap one level of subcommand functions.

```python
@cli.subcommand("hello", "world" name=Arg(help="Your name"))
def hello_world(name: str) -> None:
    print(f"Hello world, {name}!")
```

```
$ python cli.py hello world Alex
Hello world, Alex!
```

```python
@cli.subcommand_with_extra("hello", "world" name=Arg(help="Your name"))
def hello_world(name: str, _extra: List[str]) -> None:
    print(f"Hello world, {name}!", _extra])
```

```
$ python cli.py hello world Alex --color blue
Hello world, Alex! ['--color', 'blue']
```

| Argument    | Type       | Description                                                                                      |
| ----------- | ---------- | ------------------------------------------------------------------------------------------------ |
| `parent`    | `str`      | Name of the parent command (doesn't need to exist).                                              |
| `name`      | `str`      | Name of the subcommand.                                                                          |
| `**args`    | `Arg`      | Keyword arguments defining the argument information. Names need to match the function arguments. |
| **RETURNS** | `Callable` | The wrapped function.                                                                            |

#### <kbd>method</kbd> `Radicli.placeholder`

Add empty parent command with custom description text for subcommands without
an executable parent.

```python
cli.placeholder("parent", description="This is the top-level command description")

@cli.subcommand("parent", "child", name=Arg("--name", help="Your name"))
def child(name: str) -> None:
    print(f"Hello {name}!")
```

| Argument      | Type            | Description                         |
| ------------- | --------------- | ----------------------------------- |
| `name`        | `str`           | Name of the command.                |
| `description` | `Optional[str]` | Command description for help texts. |

#### <kbd>method</kbd> `Radicli.run`

Run the CLI. Typically called in a `if __name__ == "__main__":` block at the end of a file or in a package's `__main__.py` to allow executing the CLI via `python -m [package]`.

```python
if __name__ == "__main__":
    cli.run()
```

| Argument | Type                  | Description                                                                               |
| -------- | --------------------- | ----------------------------------------------------------------------------------------- |
| `args`   | `Optional[List[str]]` | Optional command to pass in. Will be read from `sys.argv` if not set (standard use case). |

### Custom types and converters

The package includes several custom types implemented as `TypeVar`s with pre-defined converter functions. If these custom types are used in the decorated function, the values received from the CLI will be converted and validated accordingly.

| Name                     | Type                        | Description                                                                                                                             |
| ------------------------ | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `ExistingPath`           | `Path`                      | Returns a path and checks that it exists.                                                                                               |
| `ExistingFilePath`       | `Path`                      | Returns a path and checks that it exists and is a file.                                                                                 |
| `ExistingDirPath`        | `Path`                      | Returns a path and checks that it exists and is a directory.                                                                            |
| `ExistingPathOrDash`     | `Union[Path, Literal["-"]]` | Returns an existing path but also accepts `"-"` (typically used to indicate that a function should read from standard input).           |
| `ExistingFilePathOrDash` | `Union[Path, Literal["-"]]` | Returns an existing file path but also accepts `"-"` (typically used to indicate that a function should read from standard input).      |
| `ExistingDirPathOrDash`  | `Union[Path, Literal["-"]]` | Returns an existing directory path but also accepts `"-"` (typically used to indicate that a function should read from standard input). |
| `PathOrDash`             | `Union[Path, Literal["-"]]` | Returns a path but also accepts `"-"` (typically used to indicate that a function should read from standard input).                     |
