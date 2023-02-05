from typing import Callable, Any, List, Dict, Optional
import catalogue
from inspect import signature
import argparse

from .util import ArgparseArg, Arg, get_arg, SimpleFrozenDict


class Radicli:
    def __init__(
        self,
        name: str,
        help: Optional[str] = None,
        version: Optional[str] = None,
        converters: Dict[Any, Callable[[str], Any]] = SimpleFrozenDict(),
    ) -> None:
        """Initialize the CLI and create the registry."""
        self.name = name
        self.help = help
        self.version = version
        self.converters = converters
        self.registry = catalogue.create(self.name, "commands")

    def command(self, name: str, **args) -> Callable[[Callable], Callable]:
        """The decorator used to wrap command functions."""

        def cli_wrapper(cli_func: Callable) -> Callable[[Callable], Callable]:
            sig = signature(cli_func)
            sig_types = {}
            sig_defaults = {}
            for param_name, param_value in sig.parameters.items():
                sig_types[param_name] = param_value.annotation
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
                cli_args.append(arg)
            self.registry.register(name, func=(cli_func, cli_args))
            return cli_func

        return cli_wrapper

    def run(self) -> None:
        """
        Run the CLI. Should typically be used in the __main__.py nested under a
        `if __name__ == "__main__":` block.
        """
        import sys

        if len(sys.argv) <= 1:
            # TODO: handle generic help case, print help, list subcommands
            ...
        else:
            command = sys.argv.pop(1)
            args = sys.argv[1:]
            func, arg_info = self.registry.get(command)
            values = self.parse(args, arg_info, description=func.__doc__)
            func(**values)

    def parse(
        self,
        args: List[str],
        arg_info: List[ArgparseArg],
        *,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parse a list of arguments. Can also be used for testing."""
        p = argparse.ArgumentParser(description=description)
        for arg in arg_info:
            func_args, func_kwargs = arg.to_argparse()
            p.add_argument(*func_args, **func_kwargs)
        if self.version:
            p.add_argument("--version", action="version", version=self.version)
        return vars(p.parse_args(args))
