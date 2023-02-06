from typing import Any
import argparse

from .util import CliParserError


class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliParserError(message)

    # Overriding this internal function so we can have more control over how
    # errors are handled and (not) masked internally
    def _get_value(self, action: argparse.Action, arg_string: str) -> Any:
        type_func = self._registry_get("type", action.type, action.type)
        if not callable(type_func):
            msg = "%r is not callable"
            raise argparse.ArgumentError(action, msg % type_func)
        # convert the value to the appropriate type
        try:
            result = type_func(arg_string)
        # ArgumentTypeErrors indicate errors
        except argparse.ArgumentTypeError:
            name = getattr(action.type, "__name__", repr(action.type))
            msg = str(argparse._sys.exc_info()[1])
            raise argparse.ArgumentError(action, msg)
        # TypeErrors or ValueErrors also indicate errors
        except (TypeError, ValueError) as e:
            name = getattr(action.type, "__name__", repr(action.type))
            arg = argparse._get_action_name(action)
            msg = f"argument {arg}: error encountered in {name} for value: {arg_string}\n{e}"
            raise CliParserError(msg) from e
        # return the converted value
        return result
