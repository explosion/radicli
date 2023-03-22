<a href="https://explosion.ai"><img src="https://explosion.ai/assets/img/logo.svg" width="125" height="125" align="right" /></a>

# radicli: Radically lightweight command-line interfaces

`radicli` is a small, zero-dependency Python package for creating command line interfaces, built on top of Python's [`argparse`](https://docs.python.org/3/library/argparse.html) module. It introduces minimal overhead, preserves your original Python functions and uses **type hints** to parse values provided on the CLI. It supports all common types out-of-the-box, including complex ones like `List[str]`, `Literal` and `Enum`, and allows registering **custom types** with custom converters, as well as custom CLI-only **error handling**, exporting a **static representation** for faster `--help` and errors and auto-generated **Markdown documentation**.

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

Alternatively, you can also use `Radicli.call`:

```python
# cli.py
from radicli import Radicli, Arg

def hello(name: str, age: int):
     print(f"Hello {name} ({age})!")

if __name__ == "__main__":
    args = dict(name=Arg(help="Your name"), age=Arg("--age", "-a", help="Your age"))
    command = Command.from_function("hello", args, hello)
    Radicli().call(command)
```

```
$ python cli.py Alex --age 35
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

`Enum`s are also supported and in this case, the enum key can be provided on the CLI and the function receives the selected enum member.

```python
class ColorEnum(Enum):
    red = "the color red"
    blue = "the color blue"
    green = "the color green"

@cli.command("hello", color=Arg("--color", help="Pick a color"))
def hello(color: ColorEnum):
    print(color)  # this will be the enum, e.g. ColorEnum.red
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

For generic types that can have arguments, e.g. `List` and `List[str]`, the converters are checked for both the exact type, as well as the origin. This means you can have multiple converters for different generics, as well as a fallback:

```
converters = {
    List[str]: convert_string_list,
    List[int]: convert_int_list,
    List: convert_other_lists,
}
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

### Command aliases by stacking decorators

The command and subcommand decorators can be stacked to make the same function available via different command aliases. In this case, you just need to make sure that all decorators receive the same argument annotations, e.g. by moving them out to a variable.

```python
args = dict(
    name=Arg(help="Your name"),
    age=Arg("--age", "-a", help="Your age")
)

@cli.command("hello", **args)
@cli.command("hey", **args)
@cli.subcommand("greet", "person", **args)
def hello(name: str, age: int):
    print(f"Hello {name} ({age})!")
```

```
$ python cli.py hello --name Alex --age 35
$ python cli.py hey --name Alex --age 35
$ python cli.py greet person --name Alex --age 35
```

### Error handling

One common problem when adding CLIs to a code base is error handling. When called in a CLI context, you typically want to pretty-print any errors and avoid long tracebacks. However, you don't want to use those errors and plain `SystemExit`s with no traceback in helper functions that are used in other places, or when the CLI functions are called directly from Python or during testing.

To solve this, `radicli` lets you provide an error map via the `errors` argument on initialization. It maps `Exception` types like `ValueError` or fully custom error subclasses to handler functions. If an error of that type is raised, the handler is called and will receive the error. The handler can optionally return an exit code – in this case, `radicli` will perform a `sys.exit` using that code. If no error code is returned, no exit is performed and the handler can either take care of the exiting itself or choose to not exit.

```python
from radicli import Radicli
from termcolor import colored

def pretty_print_error(error: Exception) -> int:
    print(colored(f"🚨 {error}", "red"))
    return 1

cli = Radicli(errors={ValueError: handle_error})

@cli.command("hello", name=Arg("--name"))
def hello(name: str):
    if name == "Alex":
        raise ValueError("Invalid name")
```

```
$ python cli.py hello --name Alex
🚨 Invalid name
```

```bash
>>> hello("Alex")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ValueError: Invalid name
```

This approach is especially powerful with custom error subclasses. Here you can decide which arguments the error should take and how this information should be displayed on the CLI vs. in a regular non-CLI context.

```python
class CustomError(Exception):
    def __init__(self, text: str, additional_info: Any = "") -> None:
        self.text = text
        self.additional_info
        self.message = f"{self.text} {self.additional_info}"
        super().__init__(self.message)

def handle_custom_error(error: CustomError) -> int:
    print(colored(error.text, "red"))
    print(error.additional_info)
    return 1
```

### Using static data for faster help and errors

CLIs often require various other Python packages that need to be imported – for example, you might need to import `pytorch` and `tensorflow`, or load other resources in the global scope. This all adds to the CLI's load time, so even showing the `--help` message may take several seconds to run. That's all unnecessary and makes for a frustrating developer experience.

`radicli` lets you generate a static representation of your CLI as a JSON file, including everything needed to output help messages and to check that the command exists and the correct and required arguments are provided. If the static CLI doesn't perform a system exit via printing the help message or raising an error, you can import and run the "live" CLI to continue. This lets you **defer the import until it's really needed**, i.e. to convert the arguments to the expected types and executing the command function.

```python
cli.to_static("./static.json")
```

```python
from radicli import StaticRadicli

static = StaticRadicli.load("./static.json")

if __name__ == "__main__":
    static.run()

    # This only runs if the static CLI doesn't error or print help
    from .cli import cli
    cli.run()
```

If the CLI is part of a Python package, you can generate the static JSON file during your build process and ship the pre-generated JSON file with your package.

`StaticRadicli` also provides a `disable` argument to disable static parsing during development (or if a certain environment variable is set). Setting `debug=True` will print an additional start and optional end marker (if the static CLI didn't exit before) to indicate that the static CLI ran.

### Auto-documenting the CLI

The `Radicli.document` method lets you generate a simple Markdown-formatted documentation for your CLI with an optional`title` and `description` added to the top. You can also include this call in your CI or build process to ensure the documentation is always up to date.

```python
with Path("README.md").open("w", encoding="utf8") as f:
    f.write(cli.document())
```

The `path_root` lets you provide a custom `Path` that's used as the relative root for all paths specified as default arguments. This means that absolute paths won't make it into your README.

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

| Name             | Type                | Description                                                                                                                                           |
| ---------------- | ------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `name`           | `str`               | The name of the command.                                                                                                                              |
| `func`           | `Callable`          | The decorated command function.                                                                                                                       |
| `args`           | `List[ArgparseArg]` | The internal representation of the argument annotations. `Argparse.arg` lets you access the original `Arg`.                                           |
| `description`    | `Optional[str]`     | The command description, taken from the function docstring.                                                                                           |
| `allow_extra`    | `bool`              | Whether to allow extra arguments.                                                                                                                     |
| `parent`         | `Optional[str]`     | Name of the parent command if command is a subcommand.                                                                                                |
| `is_placeholder` | `bool`              | Whether the command is a placeholder, created by `Radicli.placeholder`. Checking this can sometimes be useful, e.g. for testing. Defaults to `False`. |
| `display_name`   | `str`               | The display name including the parent if available, e.g. `parent child`.                                                                              |

#### <kbd>classmethod</kbd> `Command.from_function`

Create a command from a function and its argument annotations and use the type hints and defaults defined in the function to generate the arguments. This is what happens under the hood in the command decorators and it can be used if you need to construct a `Command` manually.

```python
def hello(name: str, age: int):
    print(f"Hello {name} ({age})!")

args = {"name": Arg(), "age": Arg("--age", help="Your age")}
command = Command.from_function("hello", args, hello)
```

| Argument      | Type                               | Description                                                                                                 |
| ------------- | ---------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| `name`        | `str`                              | The name of the command.                                                                                    |
| `args`        | `Dict[str, Arg]`                   | The command argument annotation, defined as `Arg` dataclasses.                                              |
| `func`        | `Callable`                         | The command function.                                                                                       |
| `parent`      | `Optional[str]`                    | Name of the parent command if command is a subcommand.                                                      |
| `allow_extra` | `bool`                             | Whether to allow extra arguments.                                                                           |
| `extra_key`   | `str`                              | Name of function argument that receives extra arguments if `allow_extra` is `True`. Defaults to `"_extra"`. |
| `converters`  | `Dict[Type, Callable[[str], Any]]` | Dict mapping types to global converter functions.                                                           |
| **RETURNS**   | `Command`                          | The command.                                                                                                |

### <kbd>class</kbd> `Radicli`

#### Attributes

| Name          | Type                                                          | Description                                                                                                                                                                              |
| ------------- | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prog`        | `Optional[str]`                                               | Program name displayed in `--help` prompt usage examples, e.g. `"python -m spacy"`.                                                                                                      |
| `help`        | `str`                                                         | Help text for the CLI, displayed in top-level `--help`. Defaults to `""`.                                                                                                                |
| `version`     | `Optional[str]`                                               | Version available via `--version`, if set.                                                                                                                                               |
| `converters`  | `Dict[Type, Callable[[str], Any]]`                            | Dict mapping types to global converter functions.                                                                                                                                        |
| `errors`      | `Dict[Type[Exception], Callable[[Exception], Optional[int]]]` | Dict mapping errors types to global error handlers. If the handler returns an exit code, a `sys.exit` will be raised using that code. See [error handling](#error-handling) for details. |
| `commands`    | `Dict[str, Command]`                                          | The commands added to the CLI, keyed by name.                                                                                                                                            |
| `subcommands` | `Dict[str, Dict[str, Command]]`                               | The subcommands added to the CLI, keyed by parent name, then keyed by subcommand name.                                                                                                   |

#### <kbd>method</kbd> `Radicli.__init__`

Initialize the CLI and create the registry.

```python
from radicli import Radicli

cli = Radicli(prog="python -m spacy")
```

| Argument     | Type                                                          | Description                                                                                                                                                                              |
| ------------ | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `prog`       | `Optional[str]`                                               | Program name displayed in `--help` prompt usage examples, e.g. `"python -m spacy"`.                                                                                                      |
| `help`       | `str`                                                         | Help text for the CLI, displayed in top-level `--help`. Defaults to `""`.                                                                                                                |
| `version`    | `Optional[str]`                                               | Version available via `--version`, if set.                                                                                                                                               |
| `converters` | `Dict[Type, Callable[[str], Any]]`                            | Dict mapping types to converter functions. All arguments with these types will then be passed to the respective converter.                                                               |
| `errors`     | `Dict[Type[Exception], Callable[[Exception], Optional[int]]]` | Dict mapping errors types to global error handlers. If the handler returns an exit code, a `sys.exit` will be raised using that code. See [error handling](#error-handling) for details. |
| `extra_key`  | `str`                                                         | Name of function argument that receives extra arguments if the `command_with_extra` or `subcommand_with_extra` decorator is used. Defaults to `"_extra"`.                                |

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
@cli.subcommand("hello", "world", name=Arg(help="Your name"))
def hello_world(name: str) -> None:
    print(f"Hello world, {name}!")
```

```
$ python cli.py hello world Alex
Hello world, Alex!
```

```python
@cli.subcommand_with_extra("hello", "world", name=Arg(help="Your name"))
def hello_world(name: str, _extra: List[str]) -> None:
    print(f"Hello world, {name}!", _extra)
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

#### <kbd>method</kbd> `Radicli.call`

Call a command with args.

```python
command = cli.commands["hello"]
cli.call(command, ["Alex", "--age", "35"])
```

| Argument  | Type                  | Description                                                                               |
| --------- | --------------------- | ----------------------------------------------------------------------------------------- |
| `command` | `Command`             | The command.                                                                              |
| `args`    | `Optional[List[str]]` | Optional command to pass in. Will be read from `sys.argv` if not set (standard use case). |

#### <kbd>method</kbd> `Radicli.parse`

Parse a list of arguments for a given command. Typically internals, but can also be used for testing.

```python
command = cli.commands["hello"]
values = cli.parse(["Alex", "--age", "35"], command)
command.func(**values)
```

| Argument        | Type                 | Description                                                                                                            |
| --------------- | -------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| `args`          | `List[str]`          | The string arguments, e.g. what's received from the command line.                                                      |
| `command`       | `Command`            | The command.                                                                                                           |
| `subcommands`   | `Dict[str, Command]` | Subcommands of the parent command, if available, keyed by subcommand name. Defaults to `{}`.                           |
| `allow_partial` | `bool`               | Allow partial parsing and still return the parsed values, even if required arguments are missing. Defaults to `False`. |
| **RETURNS**     | `Dict[str, Any]`     | The parsed values keyed by argument name that can be passed to the command function.                                   |

#### <kbd>method</kbd> `Radicli.document`

Generate a Markdown-formatted documentation for a CLI.

```python
with Path("README.md").open("w", encodig="utf8") as f:
    f.write(cli.document())
```

| Argument      | Type             | Description                                                                                                                                                                           |
| ------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `title`       | `Optional[str]`  | Title to add to the top of the file. Defaults to `None`.                                                                                                                              |
| `description` | `Optional[str]`  | Description to add to the top of th file. Defaults to `None`.                                                                                                                         |
| `comment`     | `Optional[str]`  | Text of the HTML comment added to the top of the file, usually indicating that it's auto-generated. If `None`, no comment will be added. Defaults to `"This file is auto-generated"`. |
| `path_root`   | `Optional[Path]` | Custom path used as relative root for argument defaults of type `Path`, to prevent local absolute paths from ending up in the documentation. Defaults to `None`.                      |
| **RETURNS**   | `str`            | The Markdown-formatted docs.                                                                                                                                                          |

#### <kbd>method</kbd> `Radicli.to_static`

Export a static JSON representation of the CLI for `StaticRadicli`.

```python
cli.to_static("./static.json")
```

| Argument    | Type               | Description                     |
| ----------- | ------------------ | ------------------------------- |
| `file_path` | `Union[str, Path]` | The path to the JSON file.      |
| **RETURNS** | `Path`             | The path the data was saved to. |

#### <kbd>method</kbd> `Radicli.to_static_json`

Generate a static representation of the CLI for `StaticRadicli` as a JSON-serializable dict.

```python
data = cli.to_static_json()
```

| Argument    | Type             | Description      |
| ----------- | ---------------- | ---------------- |
| **RETURNS** | `Dict[str, Any]` | The static data. |

### <kbd>class</kbd> `StaticRadicli`

Subclass of `Radicli` and static version of the CLI that can be loaded from a static representation of the CLI, generated with `Radicli.to_static`. The static CLI can run before importing and running the live CLI and will take care of showing help messages and doing basic argument checks, e.g. to ensure all arguments are correct and present. This can make your CLI help significantly faster by deferring the import of the live CLI until it's really needed, i.e. to convert the values and execute the function.

```python
static = StaticRadicli.load("./static.json")

if __name__ == "__main__":
    static.run()
    # This only runs if the static CLI doesn't error or print help
    from .cli import cli
    cli.run()
```

#### <kbd>classmethod</kbd> `StaticRadicli.load`

Load the static CLI from a JSON file generated with `Radicli.to_static`.

```python
static = StaticRadicli.load("./static.json")
```

| Argument     | Type                               | Description                                                                                                                                                                  |
| ------------ | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `file_path`  | `Union[str, Path]`                 | The JSON file to load.                                                                                                                                                       |
| `disable`    | `bool`                             | Whether to disable static parsing. Can be useful during development. Defaults to `False`.                                                                                    |
| `debug`      | `bool`                             | Enable debugging mode and print an additional start and optional end marker (if the static CLI didn't exit before) to indicate that the static CLI ran. Defaults to `False`. |
| `converters` | `Dict[Type, Callable[[str], Any]]` | Dict mapping types to global converter functions that will be used to deserialize types.                                                                                     |

#### <kbd>method</kbd> `StaticRadicli.__init__`

Initialize the static CLI with the JSON-serializable static representation.

```python
data = cli.to_static_json()
static = StaticRadicli(data)
```

| Argument     | Type                               | Description                                                                                                                                                                  |
| ------------ | ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `data`       | `Dict[str, Any]`                   | The static data.                                                                                                                                                             |
| `disable`    | `bool`                             | Whether to disable static parsing. Can be useful during development. Defaults to `False`.                                                                                    |
| `debug`      | `bool`                             | Enable debugging mode and print an additional start and optional end marker (if the static CLI didn't exit before) to indicate that the static CLI ran. Defaults to `False`. |
| `converters` | `Dict[Type, Callable[[str], Any]]` | Dict mapping types to global converter functions that will be used to deserialize types.                                                                                     |

#### <kbd>method</kbd> `StaticRadicli.run`

Run the static CLI. Typically called before running the live CLI and will perform a system exit if a help message was printed (`0`) or if argument names were missing or incorrect (`1`). This means you can defer loading the live CLI until it's really needed, , i.e. to convert the values and execute the function.

```python
if __name__ == "__main__":
    static.run()

    from .cli import cli
    cli.run()
```

| Argument | Type                  | Description                                                                               |
| -------- | --------------------- | ----------------------------------------------------------------------------------------- |
| `args`   | `Optional[List[str]]` | Optional command to pass in. Will be read from `sys.argv` if not set (standard use case). |

### Custom types and converters

The package includes several converters enabled by default, as well as custom types implemented as `NewType`s with pre-defined converter functions. If these types are used in the decorated function, the values received from the CLI will be converted and validated accordingly.

| Name                     | Type                        | Description                                                                                                                             |
| ------------------------ | --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `ExistingPath`           | `Path`                      | Returns a path and checks that it exists.                                                                                               |
| `ExistingFilePath`       | `Path`                      | Returns a path and checks that it exists and is a file.                                                                                 |
| `ExistingDirPath`        | `Path`                      | Returns a path and checks that it exists and is a directory.                                                                            |
| `ExistingPathOrDash`     | `Union[Path, Literal["-"]]` | Returns an existing path but also accepts `"-"` (typically used to indicate that a function should read from standard input).           |
| `ExistingFilePathOrDash` | `Union[Path, Literal["-"]]` | Returns an existing file path but also accepts `"-"` (typically used to indicate that a function should read from standard input).      |
| `ExistingDirPathOrDash`  | `Union[Path, Literal["-"]]` | Returns an existing directory path but also accepts `"-"` (typically used to indicate that a function should read from standard input). |
| `PathOrDash`             | `Union[Path, Literal["-"]]` | Returns a path but also accepts `"-"` (typically used to indicate that a function should read from standard input).                     |
| `UUID`                   | `UUID`                      | Converts a value to a UUID.                                                                                                             |
| `StrOrUUID`              | `Union[str, UUID]`          | Converts a value to a UUID if valid, otherwise returns the string.                                                                      |

#### `get_list_converter`

Helper function that creates a list converter that takes a string of list items separated by a delimiter and returns a list of items of a given type. This can be useful if you prefer lists to be defined as comma-separated strings on the CLI instead of via repeated arguments.

```python
@cli.command("hello", items=Arg("--items", converter=get_list_converter(str)))
def hello(items: List[str]) -> None:
    print(items)
```

| Argument    | Type                                       | Description                                                                                                   |
| ----------- | ------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| `type_func` | `Callable[[Any], Union[bool, int, float]]` | The function to convert the list items. Can be a builtin like `str` or `int`, or a custom converter function. |
| `delimiter` | `str`                                      | Delimiter of the string. Defaults to `","`.                                                                   |
| **RETURNS** | `Callable[[str], List]`                    | Converter function that converts a string to a list of the given type.                                        |
