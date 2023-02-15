from typing import Any, NoReturn
from enum import Enum
import argparse
import sys

from .util import format_arg_help, CliParserError


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CliParserError(message)

    # Overriding this internal function so we can have more control over how
    # errors are handled and (not) masked internally
    def _get_value(self, action: argparse.Action, arg_string: str) -> Any:
        type_func = self._registry_get("type", action.type, action.type)
        if not callable(type_func):
            raise argparse.ArgumentError(action, f"{type_func!r} is not callable")
        try:
            result = type_func(arg_string)
        except argparse.ArgumentTypeError:
            name = getattr(action.type, "__name__", repr(action.type))
            raise argparse.ArgumentError(action, str(sys.exc_info()[1]))
        except (TypeError, ValueError) as e:
            name = getattr(action.type, "__name__", repr(action.type))
            arg = argparse._get_action_name(action)
            msg = f"argument {arg}: error encountered in {name} for value: {arg_string}\n{e}"
            raise CliParserError(msg) from e
        return result

    def _check_value(self, action: argparse.Action, value: Any) -> None:
        if action.choices is not None:
            check_value = value.name if isinstance(value, Enum) else value
            if check_value not in action.choices:
                choices = ", ".join(map(repr, action.choices))
                msg = f"invalid choice: {check_value!r} (choose from {choices})"
                raise argparse.ArgumentError(action, msg)


class HelpFormatter(argparse.HelpFormatter):
    """Custom help formatter that truncates text and adds defaults."""

    def _get_help_string(self, action: argparse.Action) -> str:
        help = str(action.help)
        if action.metavar is not None:  # trying to only truncate command help
            help = format_arg_help(help)
        if action.default is not argparse.SUPPRESS:
            defaulting_nargs = [argparse.OPTIONAL, argparse.ZERO_OR_MORE]
            if action.option_strings or action.nargs in defaulting_nargs:
                help += " (default: %(default)s)"
        return help
