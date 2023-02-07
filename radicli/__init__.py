from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Tuple
import argparse
import sys
from dataclasses import dataclass
from inspect import signature
import catalogue

from .parser import ArgumentParser
from .util import Arg, ArgparseArg, get_arg, join_strings, format_type, format_table
from .util import SimpleFrozenDict, CommandNotFoundError, CliParserError
from .util import DEFAULT_CONVERTERS

# Make available for import
from .util import ExistingPath, ExistingFilePath, ExistingDirPath  # noqa: F401
from .util import ExistingPathOrDash, ExistingFilePathOrDash, PathOrDash  # noqa: F401
from .util import ExistingDirPathOrDash  # noqa: F401


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
    converters: Dict[Type, Callable[[str], Any]]
    extra_key: str
    subcommands: Dict[str, catalogue.Registry]
    _subcommand_key: str

    def __init__(
        self,
        name: str,
        prog: Optional[str] = None,
        help: Optional[str] = None,
        converters: Dict[Type, Callable[[str], Any]] = SimpleFrozenDict(),
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
        self._subcommand_key = "__subcommand__"  # should not conflict with arg name!

    # Using underscored argument names here to prevent conflicts if CLI commands
    # define arguments called "name" that are passed in via **args
    def command(self, _name: str, **args: Arg) -> Callable[[_CallableT], _CallableT]:
        """The decorator used to wrap command functions."""
        return self._command(_name, args, self.registry, allow_extra=False)

    def command_with_extra(
        self, _name: str, **args: Arg
    ) -> Callable[[_CallableT], _CallableT]:
        """
        The decorator used to wrap command functions. Supports additional
        arguments passed in as the keyword arg self.extra_key as a list.
        """
        return self._command(_name, args, self.registry, allow_extra=True)

    def subcommand(
        self, _parent: str, _name: str, **args: Arg
    ) -> Callable[[_CallableT], _CallableT]:
        """The decorator used to wrap subcommand functions."""
        return self._subcommand(_parent, _name, args, allow_extra=False)

    def subcommand_with_extra(
        self, _parent: str, _name: str, **args: Arg
    ) -> Callable[[_CallableT], _CallableT]:
        """
        The decorator used to wrap subcommand functions. Supports additional
        arguments passed in as the keyword arg self.extra_key as a list.
        """
        return self._subcommand(_parent, _name, args, allow_extra=True)

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
            for param, arg_info in args.items():
                param_type = sig_types[param]

                def get_converter(arg_type: Type) -> Optional[Callable]:
                    return self.converters.get(arg_type, arg_info.converter)

                converter = get_converter(param_type)
                arg_type = converter or param_type
                arg = get_arg(
                    param,
                    arg_type,
                    name=arg_info.option,
                    shorthand=arg_info.short,
                    help=arg_info.help,
                    default=sig_defaults[param],
                    count=arg_info.count,
                    skip_resolve=converter is not None,
                    get_converter=get_converter,
                )
                has_converter = converter is not None or arg.has_converter
                display_type = param_type if has_converter else arg_type
                arg.help = join_strings(arg.help, f"({format_type(display_type)})")
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
            commands = self.registry.get_all()
            print(self._format_info(commands, self.subcommands))
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
                dummy = Command(name=command, func=lambda *x, **y: None, args=[])
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
            prog=join_strings(self.prog, name),
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
                    prog=join_strings(self.prog, sub_cmd.parent, sub_name),
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
        if sub_key not in subparsers:
            raise CliParserError(f"invalid subcommand: '{sub_key}'")
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

    def _format_info(
        self,
        commands: Dict[str, Command],
        subcommands: Dict[str, catalogue.Registry],
        max_width: int = 70,
    ) -> str:
        """Nicely format the available command overview and add subcommands."""
        data = []
        for name, cmd in commands.items():
            d = (cmd.description or "").strip()[:max_width]
            d = d.rsplit("." if "." in d else " ", 1)[0] + ("." if "." in d else "...")
            data.append((f"  {name}", d))
            if name in subcommands:
                col = f"Subcommands: {', '.join(subcommands[name].get_all())}"
                data.append(("", col))
        for name in subcommands:
            if name not in commands:
                col = f"Subcommands: {', '.join(subcommands[name].get_all())}"
                data.append((f"  {name}", col))
        info = [self.help, "Available commands:", format_table(data)]
        return join_strings(*info, char="\n")
