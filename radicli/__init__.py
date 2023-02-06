from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union
import argparse
import sys
from dataclasses import dataclass
from inspect import signature
import catalogue

from .util import Arg, ArgparseArg, SimpleFrozenDict, get_arg, get_type_name


_CallableT = TypeVar("_CallableT", bound=Callable)


@dataclass
class Command:
    name: str
    func: Callable
    args: List[ArgparseArg]
    description: Optional[str]
    allow_extra: bool = False


class Radicli:
    name: str
    help: Optional[str]
    converters: Dict[Union[Type, str], Callable[[str], Any]]

    def __init__(
        self,
        name: str,
        prog: Optional[str] = None,
        help: Optional[str] = None,
        converters: Dict[Union[Type, str], Callable[[str], Any]] = SimpleFrozenDict(),
        extra_key: str = "_extra",
    ) -> None:
        """Initialize the CLI and create the registry."""
        self.name = name
        self.prog = prog
        self.help = help
        self.converters = converters
        self.extra_key = extra_key
        self.registry = catalogue.create(self.name, "commands")

    def command(self, name: str, **args) -> Callable[[_CallableT], _CallableT]:
        """The decorator used to wrap command functions."""
        return self._command(name, args, allow_extra=False)

    def command_with_extra(
        self, name: str, **args
    ) -> Callable[[_CallableT], _CallableT]:
        """
        The decorator used to wrap command functions. Supports additional
        arguments, which are passed in as the keyword argument _extra as a list.
        """
        return self._command(name, args, allow_extra=True)

    def _command(
        self, name: str, args: Dict[str, Any], *, allow_extra: bool = False
    ) -> Callable[[_CallableT], _CallableT]:
        """The decorator used to wrap command functions."""

        def cli_wrapper(cli_func: _CallableT) -> _CallableT:
            sig = signature(cli_func)
            sig_types = {}
            sig_defaults = {}
            for param_name, param_value in sig.parameters.items():
                annot = param_value.annotation
                if param_name == self.extra_key:
                    annot = List[str]  # set automatically since we know it
                elif annot == param_value.empty:
                    annot = str  # default to string for unset types
                sig_types[param_name] = annot
                sig_defaults[param_name] = (
                    param_value.default
                    if param_value.default != param_value.empty
                    else ...  # placeholder for unset defaults
                )
                if param_name not in args:  # support args not in decorator
                    args[param_name] = Arg()
            cli_args = []
            for param, arg in args.items():
                converter = self.converters.get(sig_types[param], arg.converter)
                arg_type = converter or sig_types[param]
                arg = get_arg(
                    param,
                    arg_type,
                    name=arg.option,
                    shorthand=arg.short,
                    help=arg.help,
                    default=sig_defaults[param],
                    skip_resolve=converter is not None,
                )
                arg.help = f"{get_type_name(arg_type)} - {arg.help or ''}"
                cli_args.append(arg)
            cmd = Command(
                name=name,
                func=cli_func,
                args=cli_args,
                description=cli_func.__doc__,
                allow_extra=allow_extra,
            )
            self.registry.register(name, func=cmd)
            return cli_func

        return cli_wrapper

    def run(self) -> None:
        """
        Run the CLI. Should typically be used in the __main__.py nested under a
        `if __name__ == "__main__":` block.
        """
        if len(sys.argv) <= 1 or sys.argv[1] == "--help":
            if self.help:
                print(f"\n{self.help}\n")
            commands = self.registry.get_all()
            if commands:
                print("Available commands:")
                for name, cmd in commands.items():
                    print(f"{name}\t{cmd.description or ''}")
        else:
            command = sys.argv.pop(1)
            args = sys.argv[1:]
            cmd = self.registry.get(command)
            values = self.parse(
                args, cmd.args, description=cmd.description, allow_extra=cmd.allow_extra
            )
            cmd.func(**values)

    def parse(
        self,
        args: List[str],
        arg_info: List[ArgparseArg],
        *,
        description: Optional[str] = None,
        allow_extra: bool = False,
    ) -> Dict[str, Any]:
        """Parse a list of arguments. Can also be used for testing."""
        p = argparse.ArgumentParser(
            prog=self.prog,
            description=description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        for arg in arg_info:
            if arg.id == self.extra_key:
                continue
            func_args, func_kwargs = arg.to_argparse()
            p.add_argument(*func_args, **func_kwargs)
        if allow_extra:
            namespace, extra = p.parse_known_args(args)
            return {**vars(namespace), self.extra_key: extra}
        else:
            return vars(p.parse_args(args))
