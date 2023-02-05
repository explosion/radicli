from typing import Any, Callable, Iterable, Type, Union, Optional, Dict, Tuple, List
from typing import get_origin, get_args
from dataclasses import dataclass
from pathlib import Path
import collections


BASE_TYPES = [str, int, float, Path]


class UnsupportedTypeError(Exception):
    def __init__(self, arg: str, annot: Any):
        self.arg = arg
        self.annot = annot
        self.message = f"Unsupported type for '{self.arg}': {self.annot}"


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
    default: Any = None
    action: Optional[str] = None
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
            "default": self.default,
            "action": self.action,
            "help": self.help,
        }
        # Not all arguments are valid for all options
        if self.type is not None:
            kwargs["type"] = self.type
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
        arg.type = None
        arg.default = False
        arg.action = "store_true"
        return arg
    origin = get_origin(param_type)
    if not origin:
        raise UnsupportedTypeError(param, param_type)
    args = get_args(param_type)
    if origin in (list, collections.abc.Iterable):
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
