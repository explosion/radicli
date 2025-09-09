from typing import Any, Callable, Iterable, Type, Union, Optional, Dict, Tuple
from typing import List, Literal, NewType, get_args, get_origin, TypeVar
from typing import TypedDict, cast
from enum import Enum
from uuid import UUID
from dataclasses import dataclass
from pathlib import Path
import inspect
import argparse
import re

# We need this Iterable type, which is the type origin of types.Iterable
try:
    from collections.abc import Iterable as IterableType  # Python 3.9+
except ImportError:
    from collections import Iterable as IterableType  # type: ignore

DEFAULT_PLACEHOLDER = argparse.SUPPRESS
BASE_TYPES_MAP = {"str": str, "int": int, "float": float, "Path": Path}
BASE_TYPES = list(BASE_TYPES_MAP.values())
ConverterType = Callable[[str], Any]
ConvertersType = Dict[Union[Type, object], ConverterType]
ArgTypeType = Optional[Union[Type, ConverterType]]
_Exc = TypeVar("_Exc", bound=Exception, covariant=True)
ErrorHandlerType = Callable[[Exception], Optional[int]]
ErrorHandlersType = Dict[Type[_Exc], Callable[[_Exc], Optional[int]]]


class StaticArg(TypedDict):
    id: str
    option: Optional[str]
    short: Optional[str]
    orig_help: Optional[str]
    default: Union[str, bool, None]
    help: Optional[str]
    action: Optional[str]
    choices: Optional[List[str]]
    has_converter: bool
    type: Optional[str]
    orig_type: Optional[str]


class StaticCommand(TypedDict):
    name: str
    args: List[StaticArg]
    description: Optional[str]
    allow_extra: bool
    parent: Optional[str]
    is_placeholder: bool


class StaticData(TypedDict):
    prog: Optional[str]
    help: str
    version: Optional[str]
    extra_key: str
    commands: Dict[str, StaticCommand]
    subcommands: Dict[str, Dict[str, StaticCommand]]


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

    def update(self, *args, **kwargs):
        raise NotImplementedError(self.error)


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


# This is included with argparse in Python 3.9+ and above, but we're also
# supporting 3.8 so the action is inlined here
class BooleanOptionalAction(argparse.Action):
    def __init__(
        self,
        option_strings,
        dest,
        default=None,
        type=None,
        choices=None,
        required=False,
        help=None,
        metavar=None,
    ):
        _option_strings = []
        for option_string in option_strings:
            _option_strings.append(option_string)
            if option_string.startswith("--"):
                option_string = "--no-" + option_string[2:]
                _option_strings.append(option_string)
        super().__init__(
            option_strings=_option_strings,
            dest=dest,
            nargs=0,
            default=default,
            type=type,
            choices=choices,
            required=required,
            help=help,
            metavar=metavar,
        )

    def __call__(self, parser, namespace, values, option_string=None):
        if option_string is not None and option_string in self.option_strings:
            setattr(namespace, self.dest, not option_string.startswith("--no-"))

    def format_usage(self) -> str:
        return " | ".join(self.option_strings)


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
    type: ArgTypeType = None
    orig_type: Union[ArgTypeType, str] = None
    default: Any = DEFAULT_PLACEHOLDER
    # We modify the help to add types so we store it twice to store old and new
    help: Optional[str] = None
    action: Optional[Union[str, Type[argparse.Action]]] = None
    choices: Optional[Union[List[str], List[Enum]]] = None
    has_converter: bool = False

    @property
    def display_type(self) -> Union[ArgTypeType, str]:
        default_type = self.type if self.type is not None else self.orig_type
        return self.orig_type if self.has_converter else default_type

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
            "default": self.default,
        }
        # Support defaults for positional arguments
        if not self.arg.option and self.default is not DEFAULT_PLACEHOLDER:
            kwargs["nargs"] = "?"
        # Not all arguments are valid for all options
        if self.type is not None:
            kwargs["type"] = self.type
        if self.choices is not None:
            kwargs["choices"] = self.choices
        return args, kwargs

    def to_static_json(self) -> StaticArg:
        """Convert the argument to a JSON-serializable dict."""
        return {
            "id": self.id,
            "option": self.arg.option,
            "short": self.arg.short,
            "orig_help": self.arg.help,
            "default": str(self.default)
            if self.default not in (False, None)
            else self.default,
            "help": self.help,
            "action": str(self.action) if self.action else None,
            "choices": list(c.value if isinstance(c, Enum) else c for c in self.choices)
            if self.choices
            else None,
            "has_converter": self.has_converter,
            "type": stringify_type(self.type),
            "orig_type": stringify_type(self.orig_type),
        }

    @classmethod
    def from_static_json(
        cls,
        data: StaticArg,
        converters: ConvertersType = SimpleFrozenDict(),
    ) -> "ArgparseArg":
        """Initialize the static argument from a JSON-serializable dict."""
        return ArgparseArg(
            id=data["id"],
            arg=Arg(data["option"], data["short"], help=data["orig_help"]),
            type=deserialize_type(data, converters),
            orig_type=data["orig_type"],
            default=[]
            if data['action'] == 'append'
            else DEFAULT_PLACEHOLDER
            if data["default"] == DEFAULT_PLACEHOLDER
            else data["default"],
            help=data["help"],
            action=data["action"],
            choices=data["choices"],
            has_converter=data["has_converter"],
        )


def deserialize_type(
    data: StaticArg,
    converters: ConvertersType = SimpleFrozenDict(),
) -> ArgTypeType:
    # No type or special args with no type
    if data["type"] is None or data["action"] in ("store_true", "count"):
        return None
    # Handle custom types: we use the orig_type here, since this corresponds to
    # what was actually set as an argument type hint
    orig_type = data["orig_type"]
    if orig_type is None:
        return None
    converters_map = {stringify_type(k): v for k, v in converters.items()}
    if orig_type in converters_map:
        return converters_map[orig_type]
    # Hacky check for generics
    if "[" in orig_type:
        origin = orig_type.split("[", 1)[0]
        if origin in converters_map:
            return converters_map[orig_type.split("[", 1)[0]]
    # Check defaults last to honor custom converters for builtins
    types_map = {**BASE_TYPES_MAP}
    for value in DEFAULT_CONVERTERS.values():
        types_map[stringify_type(value)] = value  # type: ignore
    if data["type"] in types_map:
        return types_map[data["type"]]
    return str


def get_arg(
    param: str,
    orig_arg: Arg,
    param_type: Any,
    *,
    orig_type: Union[ArgTypeType, str] = None,
    default: Optional[Any] = DEFAULT_PLACEHOLDER,
    get_converter: Optional[Callable[[Type], Optional[ConverterType]]] = None,
    has_converter: bool = False,
    skip_resolve: bool = False,
) -> ArgparseArg:
    """Generate an argument to add to argparse and interpret types if possible."""
    if isinstance(param_type, str):
        # Windows may pass param_types as str
        param_type = BASE_TYPES_MAP.get(param_type, None)
    arg = ArgparseArg(
        id=param,
        arg=orig_arg,
        type=param_type,
        help=orig_arg.help,
        default=default,
        orig_type=orig_type,
        has_converter=has_converter,
    )
    if orig_arg.count:
        arg.action = "count"
        arg.type = None
        if not arg.default:
            arg.default = 0
        return arg
    # Need to do this first so we can recursively resolve custom types like
    # Union[ExistingPath] etc.
    origin = get_origin(param_type)
    args = get_args(param_type)
    converter = get_converter(param_type) if get_converter else None
    if get_converter and not converter:
        # Check if we have a converter for the origin, e.g. for generics Foo[Bar]
        converter = get_converter(origin)  # type: ignore
    if converter:
        arg.type = converter
        arg.has_converter = True
        return arg
    if skip_resolve:
        return arg
    if origin is Union:
        if type(None) in args and default is DEFAULT_PLACEHOLDER:
            default = None
        arg_types = [a for a in args if a != type(None)]  # noqa: E721
        if arg_types:
            return get_arg(
                param,
                orig_arg,
                arg_types[0],
                orig_type=arg_types[0],
                default=default,
                get_converter=get_converter,
            )
    if param_type in BASE_TYPES:
        arg.type = param_type
        return arg
    if param_type is bool:
        if not orig_arg.option:
            raise InvalidArgumentError(
                arg.id,
                f"boolean arguments need to be flags, e.g. --{arg.id.replace('_', '-')}",
            )
        arg.type = None
        arg.default = False if default is not True else True
        arg.action = "store_true" if arg.default is False else BooleanOptionalAction
        return arg
    if inspect.isclass(param_type) and issubclass(param_type, Enum):
        arg.choices = list(param_type.__members__.keys())
        arg.type = lambda value: getattr(param_type, value, value)
        arg.has_converter = True
        return arg
    if not origin:
        raise UnsupportedTypeError(param, param_type)
    if origin is Literal and len(args):
        arg.choices = list(args)
        arg.type = type(args[0])
        return arg
    if origin in (list, IterableType):
        if len(args) and get_origin(args[0]) is Literal:
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


def stringify_type(arg_type: Any) -> Optional[str]:
    """Get a pretty-printed string for a type."""
    if isinstance(arg_type, str) or arg_type is None:
        return arg_type
    if hasattr(arg_type, "__name__"):
        type_str = arg_type.__name__
        args = get_args(arg_type)
        if args:
            # Built-in generic types are callables in Python 3.10+ so we want to
            # preserve args here and stringify them, too
            type_args = cast(List[str], [stringify_type(arg) for arg in args])
            type_str = f"{type_str}[{', '.join(type_args)}]"
        return type_str
    type_str = str(arg_type)
    return _stringify_type(str(arg_type))


subtype_matcher = re.compile(r"\[(.*)\]")


def _stringify_type(type_str: str) -> str:
    parts = []
    split_type = subtype_matcher.split(type_str)
    first = split_type.pop(0)
    split_first = first.rsplit(".", 1)
    parts.append(split_first[1] if len(split_first) == 2 else first)
    for substr in split_type:
        if substr:
            objs = [_stringify_type(sub.strip()) for sub in substr.split(",")]
            parts.extend(["[", ", ".join(objs), "]"])
    return "".join(parts)


def format_type(arg_type: Any) -> Optional[str]:
    """Get a pretty-printed string for a type."""
    type_str = stringify_type(arg_type)
    # Hacky check for cross-platform supertypes for NewType custom types
    if (
        (
            # Python < 3.10
            hasattr(arg_type, "__qualname__")
            and arg_type.__qualname__.startswith("NewType")
        )
        # Python 3.10+
        or (hasattr(arg_type, "__class__") and arg_type.__class__ is NewType)
    ) and (
        hasattr(arg_type, "__supertype__")
    ):  # type: ignore
        supertype = stringify_type(arg_type.__supertype__)  # type: ignore
        return f"{type_str} ({supertype})"
    return type_str


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
    if not text:
        return " "
    d = (text or "").strip()[:max_width]
    end = "." if "." in d or len(text or "") <= max_width else "..."
    return (d.rsplit(".", 1)[0] if "." in d else d) + end


def expand_error_subclasses(
    errors: Dict[Type[Exception], ErrorHandlerType]
) -> Dict[Type[Exception], ErrorHandlerType]:
    """Map subclasses of errors to their parent's handler."""
    output = {}
    for err, callback in errors.items():
        if hasattr(err, "__subclasses__"):
            for subclass in err.__subclasses__():
                output[subclass] = callback
        output[err] = callback
    return output


_InT = TypeVar("_InT", bound=Union[str, int, float])


def get_list_converter(
    type_func: Callable[[Any], _InT] = str, delimiter: str = ","
) -> Callable[[str], List[_InT]]:
    def converter(value: str) -> List[_InT]:
        if not value:
            return []
        if value.startswith("[") and value.endswith("]"):
            value = value[1:-1]
        result = []
        for p in value.split(delimiter):
            p = p.strip()
            if p.startswith("'") and p.endswith("'"):
                p = p[1:-1]
            if p.startswith('"') and p.endswith('"'):
                p = p[1:-1]
            p = type_func(p.strip())
            result.append(p)
        return result

    return converter


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


def convert_uuid(value: str) -> UUID:
    return UUID(value)


def convert_str_or_uuid(value: str) -> Union[str, UUID]:
    try:
        return UUID(value)
    except ValueError:
        return value


# Custom path types for custom converters
ExistingPath = NewType("ExistingPath", Path)
ExistingFilePath = NewType("ExistingFilePath", Path)
ExistingDirPath = NewType("ExistingDirPath", Path)

ExistingPathOrDash = Union[ExistingPath, Literal["-"]]
ExistingFilePathOrDash = Union[ExistingFilePath, Literal["-"]]
ExistingDirPathOrDash = Union[ExistingDirPath, Literal["-"]]
PathOrDash = Union[Path, Literal["-"]]
StrOrUUID = Union[str, UUID]


DEFAULT_CONVERTERS: ConvertersType = {
    ExistingPath: convert_existing_path,
    ExistingFilePath: convert_existing_file_path,
    ExistingDirPath: convert_existing_dir_path,
    ExistingPathOrDash: convert_existing_path_or_dash,
    ExistingFilePathOrDash: convert_existing_file_path_or_dash,
    ExistingDirPathOrDash: convert_existing_dir_path_or_dash,
    PathOrDash: convert_path_or_dash,
    UUID: convert_uuid,
    StrOrUUID: convert_str_or_uuid,
}
