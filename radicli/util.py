from typing import Any, Callable, Iterable, Type, Union, Optional, Dict, Tuple
from typing import List, Literal, TypeVar, get_origin, get_args
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
import inspect

# We need this Iterable type, which is the type origin of types.Iterable
try:
    from collections.abc import Iterable as IterableType  # Python 3.9+
except ImportError:
    from collections import Iterable as IterableType  # type: ignore


BASE_TYPES = [str, int, float, Path]


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
    converter: Optional[Callable[[str], Any]] = None


@dataclass
class ArgparseArg:
    """Internal argument dataclass defining values passed to argparse."""

    id: str
    name: Optional[str] = None
    shorthand: Optional[str] = None
    type: Optional[Union[Type, Callable[[str], Any]]] = None
    default: Any = ...
    action: Optional[str] = None
    choices: Optional[Union[List[str], List[Enum]]] = None
    help: Optional[str] = None

    def to_argparse(self) -> Tuple[List[str], Dict[str, Any]]:
        """Helper method to generate args and kwargs for Parser.add_argument."""
        args = []
        if self.name:
            args.append(self.name)
        if self.shorthand:
            args.append(self.shorthand)
        kwargs = {
            "dest": self.id,
            "action": self.action,
            "help": self.help,
        }
        if self.default != ...:
            kwargs["default"] = self.default
        # Support defaults for positional arguments
        if not self.name and self.default != ...:
            kwargs["nargs"] = "?"
        # Not all arguments are valid for all options
        if self.type is not None:
            kwargs["type"] = self.type
        if self.choices is not None:
            kwargs["choices"] = self.choices
        return args, kwargs


def get_arg(
    param: str,
    param_type: Any,
    *,
    name: Optional[str] = None,
    shorthand: Optional[str] = None,
    help: Optional[str] = None,
    default: Optional[Any] = ...,
    skip_resolve: bool = False,
) -> ArgparseArg:
    """Generate an argument to add to argparse and interpret types if possible."""
    arg = ArgparseArg(
        id=param,
        name=name,
        shorthand=shorthand,
        help=help,
        type=param_type,
    )
    if default != ...:
        arg.default = default
    if skip_resolve:
        return arg
    if param_type in BASE_TYPES:
        arg.type = param_type
        return arg
    if param_type == bool:
        if not name:
            msg = f"boolean arguments need to be flags, e.g. --{arg.id}"
            raise InvalidArgumentError(arg.id, msg)
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
    origin = get_origin(param_type)
    if not origin:
        raise UnsupportedTypeError(param, param_type)
    args = get_args(param_type)
    if origin == Literal and len(args):
        arg.choices = list(args)
        arg.type = type(args[0])
        return arg
    if origin in (list, IterableType):
        arg.type = find_base_type(args)
        arg.action = "append"
        return arg
    if origin == Union:
        arg_types = [a for a in args if a != type(None)]  # noqa: E721
        if arg_types:
            return get_arg(param, arg_types[0], name=name, help=help, default=default)
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
    # Nicer formatting for our own TypeVars
    if isinstance(arg_type, TypeVar) and arg_type.__bound__:
        return f"{arg_type.__name__} ({format_type(arg_type.__bound__)})"
    if hasattr(arg_type, "__name__"):
        return arg_type.__name__
    type_str = str(arg_type)
    # Strip out typing for built-in types, leave path for custom
    return type_str.replace("typing.", "")


def join_strings(*strings, char: str = " ") -> str:
    return char.join(x for x in strings if x)


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


def convert_existing_file_path_or_dash(path_str: str) -> Union[Path, str]:
    if path_str == "-":
        return path_str
    return convert_existing_file_path(path_str)


# Custom path types for custom converters
ExistingPath = TypeVar("ExistingPath", bound=Path)
ExistingFilePath = TypeVar("ExistingFilePath", bound=Path)
ExistingDirPath = TypeVar("ExistingDirPath", bound=Path)
ExistingFilePathOrDash = TypeVar(
    "ExistingFilePathOrDash", bound=Union[Path, Literal["-"]]
)

DEFAULT_CONVERTERS: Dict[Union[Type, str], Callable[[str], Any]] = {
    ExistingPath: convert_existing_path,
    ExistingFilePath: convert_existing_file_path,
    ExistingDirPath: convert_existing_dir_path,
    ExistingFilePathOrDash: convert_existing_file_path_or_dash,
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

    def update(self, other):
        raise NotImplementedError(self.error)
