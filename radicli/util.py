from typing import Any, Callable, Iterable, Type, Union, Optional, Dict, Tuple
from typing import List, Literal, NewType, get_args, get_origin
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import inspect
import argparse

# We need this Iterable type, which is the type origin of types.Iterable
try:
    from collections.abc import Iterable as IterableType  # Python 3.9+
except ImportError:
    from collections import Iterable as IterableType  # type: ignore


BASE_TYPES = [str, int, float, Path]
ConverterType = Callable[[str], Any]
ConvertersType = Dict[Union[Type, object], ConverterType]


class CliParserError(SystemExit):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class UnsupportedTypeError(Exception):
    def __init__(self, arg: str, annot: Any) -> None:
        self.arg = arg
        self.annot = annot
        self.message = f"Unsupported type for '{self.arg}': {self.annot}"
        super().__init__(self.message)


class CommandNotFoundError(Exception):
    def __init__(self, name: str, options: List[str]) -> None:
        self.name = name
        self.options = options
        self.message = (
            f"Can't find command '{self.name}'. Available: {', '.join(self.options)}"
        )
        super().__init__(self.message)


class CommandExistsError(Exception):
    def __init__(self, name: str) -> None:
        self.name = name
        self.message = f"Command '{self.name}' already exists"
        super().__init__(self.message)


class InvalidArgumentError(Exception):
    def __init__(self, arg_id: str, message: str):
        self.id = arg_id
        self.msg = message
        self.message = f"Invalid argument '{self.id}': {self.msg}"
        super().__init__(self.message)


@dataclass
class Arg:
    """Field for defining the CLI argument in the decorator."""

    option: Optional[str] = None
    short: Optional[str] = None
    help: Optional[str] = None
    converter: Optional[ConverterType] = None
    count: bool = False


@dataclass
class ArgparseArg:
    """Internal argument dataclass defining values passed to argparse."""

    id: str
    arg: Arg
    type: Optional[Union[Type, Callable[[str], Any]]] = None
    default: Any = ...
    # We modify the help to add types so we store it twice to store old and new
    help: Optional[str] = None
    action: Optional[Union[str, Type[argparse.Action]]] = None
    choices: Optional[Union[List[str], List[Enum]]] = None
    has_converter: bool = False

    def to_argparse(self) -> Tuple[List[str], Dict[str, Any]]:
        """Helper method to generate args and kwargs for Parser.add_argument."""
        args: List[str] = []
        if self.arg.option:
            args.append(self.arg.option)
        if self.arg.short:
            args.append(self.arg.short)
        kwargs: Dict[str, Any] = {
            "dest": self.id,
            "action": self.action,
            "help": self.help,
        }
        if self.default is not ...:
            kwargs["default"] = self.default
        # Support defaults for positional arguments
        if not self.arg.option and self.default is not ...:
            kwargs["nargs"] = "?"
        # Not all arguments are valid for all options
        if self.type is not None:
            kwargs["type"] = self.type
        if self.choices is not None:
            kwargs["choices"] = self.choices
        return args, kwargs


def get_arg(
    param: str,
    orig_arg: Arg,
    param_type: Any,
    *,
    default: Optional[Any] = ...,
    get_converter: Optional[Callable[[Type], Optional[ConverterType]]] = None,
    skip_resolve: bool = False,
) -> ArgparseArg:
    """Generate an argument to add to argparse and interpret types if possible."""
    arg = ArgparseArg(id=param, arg=orig_arg, type=param_type, help=orig_arg.help)
    if default is not ...:
        arg.default = default
    if orig_arg.count:
        arg.action = "count"
        arg.type = None
        if not arg.default:
            arg.default = 0
        return arg
    converter = get_converter(param_type) if get_converter else None
    if converter:
        arg.type = converter
        arg.has_converter = True
        return arg
    if skip_resolve:
        return arg
    # Need to do this first so we can recursively resolve custom types like
    # Union[ExistingPath] etc.
    origin = get_origin(param_type)
    args = get_args(param_type)
    if origin == Union:
        arg_types = [a for a in args if a != type(None)]  # noqa: E721
        if arg_types:
            return get_arg(
                param,
                orig_arg,
                arg_types[0],
                default=default,
                get_converter=get_converter,
            )
    if param_type in BASE_TYPES:
        arg.type = param_type
        return arg
    if param_type == bool:
        if not orig_arg.option:
            raise InvalidArgumentError(
                arg.id,
                f"boolean arguments need to be flags, e.g. --{arg.id.replace('_', '-')}",
            )
        arg.type = None
        if default is True:
            raise InvalidArgumentError(arg.id, "boolean flags need to default to False")
        arg.default = False
        arg.action = "store_true"
        return arg
    if inspect.isclass(param_type) and issubclass(param_type, Enum):
        arg.choices = list(param_type.__members__.values())
        arg.type = lambda value: param_type.__members__.get(value, value)
        return arg
    if not origin:
        raise UnsupportedTypeError(param, param_type)
    if origin == Literal and len(args):
        arg.choices = list(args)
        arg.type = type(args[0])
        return arg
    if origin in (list, IterableType):
        if len(args) and get_origin(args[0]) == Literal:
            literal_args = get_args(args[0])
            if literal_args:
                arg.type = type(literal_args[0])
                arg.choices = list(literal_args)
                arg.action = "append"
                return arg
        arg.type = find_base_type(args)
        arg.action = "append"
        return arg
    raise UnsupportedTypeError(param, param_type)


def find_base_type(
    args: Iterable[Any], default_type: Callable[[str], Any] = str
) -> Callable[[str], Any]:
    """Check a list of types for the next available basic type, e.g. str."""
    for base_type in BASE_TYPES:
        if base_type in args:
            return base_type
    return default_type


def format_type(arg_type: Any) -> str:
    """Get a pretty-printed string for a type."""
    if isinstance(arg_type, type(NewType)) and hasattr(arg_type, "__supertype__"):  # type: ignore
        return f"{arg_type.__name__} ({format_type(arg_type.__supertype__)})"  # type: ignore
    if hasattr(arg_type, "__name__"):
        return arg_type.__name__
    type_str = str(arg_type)
    # Strip out typing for built-in types, leave path for custom
    return type_str.replace("typing.", "")


def join_strings(*strings: Optional[str], char: str = " ") -> str:
    return char.join(x for x in strings if x)


def format_table(data: List[Tuple[str, str]]) -> str:
    widths = [[len(str(col)) for col in item] for item in data]
    max_widths = [min(max(w), 50) for w in list(zip(*widths))]
    rows = []
    for item in data:
        cols = []
        for i, col in enumerate(item):
            cols.append(("{:%d}" % max_widths[i]).format(str(col or "")))
        rows.append((" " * 3).join(cols))
    return "\n" + "\n".join(rows) + "\n"


def format_arg_help(text: Optional[str], max_width: int = 70) -> str:
    d = (text or "").strip()[:max_width]
    return d.rsplit("." if "." in d else " ", 1)[0] + ("." if "." in d else "...")


def convert_existing_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.exists():
        raise CliParserError(f"path does not exist: {path_str}")
    return path


def convert_existing_file_path(path_str: str) -> Path:
    path = convert_existing_path(path_str)
    if not path.is_file():
        raise CliParserError(f"path is not a file path: {path_str}")
    return path


def convert_existing_dir_path(path_str: str) -> Path:
    path = convert_existing_path(path_str)
    if not path.is_dir():
        raise CliParserError(f"path is not a directory path: {path_str}")
    return path


def convert_existing_path_or_dash(path_str: str) -> Union[Path, str]:
    if path_str == "-":
        return path_str
    return convert_existing_path(path_str)


def convert_existing_file_path_or_dash(path_str: str) -> Union[Path, str]:
    if path_str == "-":
        return path_str
    return convert_existing_file_path(path_str)


def convert_existing_dir_path_or_dash(path_str: str) -> Union[Path, str]:
    if path_str == "-":
        return path_str
    return convert_existing_dir_path(path_str)


def convert_path_or_dash(path_str: str) -> Union[Path, str]:
    if path_str == "-":
        return path_str
    return Path(path_str)


# Custom path types for custom converters
ExistingPath = NewType("ExistingPath", Path)
ExistingFilePath = NewType("ExistingFilePath", Path)
ExistingDirPath = NewType("ExistingDirPath", Path)

ExistingPathOrDash = Union[ExistingPath, Literal["-"]]
ExistingFilePathOrDash = Union[ExistingFilePath, Literal["-"]]
ExistingDirPathOrDash = Union[ExistingDirPath, Literal["-"]]
PathOrDash = Union[Path, Literal["-"]]


DEFAULT_CONVERTERS: ConvertersType = {
    ExistingPath: convert_existing_path,
    ExistingFilePath: convert_existing_file_path,
    ExistingDirPath: convert_existing_dir_path,
    ExistingPathOrDash: convert_existing_path_or_dash,
    ExistingFilePathOrDash: convert_existing_file_path_or_dash,
    ExistingDirPathOrDash: convert_existing_dir_path_or_dash,
    PathOrDash: convert_path_or_dash,
}


class SimpleFrozenDict(dict):
    """Simplified implementation of a frozen dict, mainly used as default
    function or method argument (for arguments that should default to empty
    dictionary).
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.error = "Can't write to frozen dict. This is likely an internal error."

    def __setitem__(self, key, value):
        raise NotImplementedError(self.error)

    def pop(self, key: Any, default=None):
        raise NotImplementedError(self.error)

    def update(self, other, **kwargs):
        raise NotImplementedError(self.error)
