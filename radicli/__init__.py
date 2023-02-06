from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, Tuple
import argparse
import sys
from dataclasses import dataclass
from inspect import signature
import catalogue

from .parser import ArgumentParser
from .util import Arg, ArgparseArg, get_arg, get_type_name, get_prog_name
from .util import SimpleFrozenDict, CommandNotFoundError
from .util import DEFAULT_CONVERTERS


_CallableT = TypeVar("_CallableT", bound=Callable)


@dataclass
class Command:
    name: str
    func: Callable
    args: List[ArgparseArg]
    description: Optional[str] = None
    allow_extra: bool = False
    parent: Optional[str] = None


class Radicli:
    name: str
    prog: Optional[str]
    help: Optional[str]
    converters: Dict[Union[Type, str], Callable[[str], Any]]
    extra_key: str
    subcommands: Dict[str, catalogue.Registry]
    _subcommand_key: str

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
        self.converters = dict(DEFAULT_CONVERTERS)  # make sure to copy
        self.converters.update(converters)
        self.extra_key = extra_key
        self.registry = catalogue.create(self.name, "commands")
        self.subcommands = {}
        self._subcommand_key = "subcommand"

    def command(self, name: str, **args) -> Callable[[_CallableT], _CallableT]:
        """The decorator used to wrap command functions."""
        return self._command(name, args, self.registry, allow_extra=False)

    def command_with_extra(
        self, name: str, **args
    ) -> Callable[[_CallableT], _CallableT]:
        """
        The decorator used to wrap command functions. Supports additional
        arguments passed in as the keyword arg self.extra_key as a list.
        """
        return self._command(name, args, self.registry, allow_extra=True)

    def subcommand(
        self, parent: str, name: str, **args
    ) -> Callable[[_CallableT], _CallableT]:
        """The decorator used to wrap subcommand functions."""
        return self._subcommand(parent, name, args, allow_extra=False)

    def subcommand_with_extra(
        self, parent: str, name: str, **args
    ) -> Callable[[_CallableT], _CallableT]:
        """
        The decorator used to wrap subcommand functions. Supports additional
        arguments passed in as the keyword arg self.extra_key as a list.
        """
        return self._subcommand(parent, name, args, allow_extra=True)

    def _subcommand(
        self, parent: str, name: str, args: Dict[str, Any], *, allow_extra: bool = False
    ) -> Callable[[_CallableT], _CallableT]:
        """The decorator used to wrap subcommands."""
        if parent not in self.subcommands:
            self.subcommands[parent] = catalogue.create(self.name, parent, name)
        return self._command(
            name, args, self.subcommands[parent], parent=parent, allow_extra=allow_extra
        )

    def _command(
        self,
        name: str,
        args: Dict[str, Any],
        registry: catalogue.Registry,
        *,
        allow_extra: bool = False,
        parent: Optional[str] = None,
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
                parent=parent,
            )
            registry.register(name, func=cmd)
            return cli_func

        return cli_wrapper

    def run(self, args: Optional[List[str]] = None) -> None:
        """
        Run the CLI. Should typically be used in the __main__.py nested under a
        `if __name__ == "__main__":` block.
        """
        run_args = args if args is not None else sys.argv
        if len(run_args) <= 1 or run_args[1] == "--help":
            if self.help:
                print(f"\n{self.help}\n")
            commands = self.registry.get_all()
            if commands:
                print("Available commands:")
                for name, cmd in commands.items():
                    print(f"{name}\t{cmd.description or ''}")
        else:
            command = run_args.pop(1)
            args = run_args[1:]
            subcommands = {}
            if command in self.subcommands:
                subcommands = self.subcommands[command].get_all()
            if command not in self.registry:
                if not subcommands:
                    raise CommandNotFoundError(command, list(self.registry.get_all()))
                # Add a dummy parent to support subcommands without parents
                dummy = Command(name=command, func=lambda x: None, args=[])
                self.registry.register(command, func=dummy)
            cmd = self.registry.get(command)
            values = self.parse(
                args,
                cmd.args,
                subcommands,
                name=cmd.name,
                description=cmd.description,
                allow_extra=cmd.allow_extra,
            )
            sub = values.pop(self._subcommand_key, None)
            func = subcommands[sub].func if sub else cmd.func
            func(**values)

    def parse(
        self,
        args: List[str],
        arg_info: List[ArgparseArg],
        subcommands: Dict[str, Command] = SimpleFrozenDict(),
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
        allow_extra: bool = False,
    ) -> Dict[str, Any]:
        """Parse a list of arguments. Can also be used for testing."""
        p = ArgumentParser(
            prog=get_prog_name(self.prog, name),
            description=description,
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        for arg in arg_info:
            if arg.id == self.extra_key:
                continue
            func_args, func_kwargs = arg.to_argparse()
            p.add_argument(*func_args, **func_kwargs)
        subparsers: Dict[str, Tuple[ArgumentParser, Command]] = {}
        if subcommands:
            # We're using the dest to determine whether subcommand was called
            sp = p.add_subparsers(
                title="Subcommands",
                dest=self._subcommand_key,
                parser_class=ArgumentParser,
            )
            for sub_name, sub_cmd in subcommands.items():
                subp = sp.add_parser(
                    sub_cmd.name,
                    description=sub_cmd.description,
                    help=sub_cmd.description,
                    prog=get_prog_name(self.prog, sub_cmd.parent, sub_name),
                )
                subparsers[sub_cmd.name] = (subp, sub_cmd)
                for sub_arg in sub_cmd.args:
                    if sub_arg.id == self.extra_key:
                        continue
                    sub_func_args, sub_func_kwargs = sub_arg.to_argparse()
                    subp.add_argument(*sub_func_args, **sub_func_kwargs)
        # Handling of subcommands is a bit convoluted
        # https://docs.python.org/3/library/argparse.html#sub-commands
        namespace, extra = p.parse_known_args(args)
        values = {**vars(namespace), self.extra_key: extra}
        sub_key = values.pop(self._subcommand_key, None)
        if not sub_key:  # we're not in a subcommand
            values = self._handle_extra(p, values, allow_extra)
            return values
        subparser, subcmd = subparsers[sub_key]
        sub_namespace, sub_extra = subparser.parse_known_args(args[1:])
        sub_values = {**vars(sub_namespace), self.extra_key: sub_extra}
        sub_values = self._handle_extra(p, sub_values, subcmd.allow_extra)
        return {**sub_values, self._subcommand_key: sub_key}

    def _handle_extra(
        self, parser: ArgumentParser, values: Dict[str, Any], allow_extra: bool
    ) -> Dict[str, Any]:
        """
        Handle extra arguments and raise error if needed. We're doing this
        manually to avoide false positive argparse errors with subcommands.
        """
        extra = values.get(self.extra_key)
        if not allow_extra:
            if extra:
                parser.error(f"unrecognized arguments: {' '.join(extra)}")
            values.pop(self.extra_key, None)
            return values
        return values
