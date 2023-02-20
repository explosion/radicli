from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Tuple
from typing import Union, cast
import sys
from dataclasses import dataclass
from inspect import signature
from pathlib import Path
import json

from .parser import ArgumentParser, HelpFormatter
from .util import Arg, ArgparseArg, get_arg, join_strings, format_type, format_table
from .util import format_arg_help, expand_error_subclasses, SimpleFrozenDict
from .util import CommandNotFoundError, CliParserError, CommandExistsError
from .util import ConverterType, ConvertersType, ErrorHandlersType
from .util import DEFAULT_CONVERTERS, DEFAULT_PLACEHOLDER


_CallableT = TypeVar("_CallableT", bound=Callable)


@dataclass
class Command:
    name: str
    func: Callable
    args: List[ArgparseArg]
    description: Optional[str] = None
    allow_extra: bool = False
    parent: Optional[str] = None
    is_placeholder: bool = False

    @property
    def display_name(self) -> str:
        return f"{self.parent} {self.name}" if self.parent else self.name


class Radicli:
    prog: Optional[str]
    help: Optional[str]
    version: Optional[str]
    converters: ConvertersType
    extra_key: str
    commands: Dict[str, Command]
    subcommands: Dict[str, Dict[str, Command]]
    errors: ErrorHandlersType
    _subcommand_key: str
    _help_arg: str
    _version_arg: str

    def __init__(
        self,
        *,
        prog: Optional[str] = None,
        help: str = "",
        version: Optional[str] = None,
        converters: ConvertersType = SimpleFrozenDict(),
        errors: Optional[ErrorHandlersType] = None,
        extra_key: str = "_extra",
    ) -> None:
        """Initialize the CLI and create the registry."""
        self.prog = prog
        self.help = help.strip()
        self.version = version
        self.converters = dict(DEFAULT_CONVERTERS)  # make sure to copy
        self.converters.update(converters)
        self.extra_key = extra_key
        self.commands = {}
        self.subcommands = {}
        self.errors = dict(errors) if errors is not None else {}
        self._subcommand_key = "__subcommand__"  # should not conflict with arg name!
        self._help_arg = "--help"
        self._version_arg = "--version"

    # Using underscored argument names here to prevent conflicts if CLI commands
    # define arguments called "name" that are passed in via **args
    def command(self, _name: str, **args: Arg) -> Callable[[_CallableT], _CallableT]:
        """The decorator used to wrap command functions."""
        return self._command(_name, args, self.commands, allow_extra=False)

    def command_with_extra(
        self, _name: str, **args: Arg
    ) -> Callable[[_CallableT], _CallableT]:
        """
        The decorator used to wrap command functions. Supports additional
        arguments passed in as the keyword arg self.extra_key as a list.
        """
        return self._command(_name, args, self.commands, allow_extra=True)

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
            self.subcommands[parent] = {}
        return self._command(
            name, args, self.subcommands[parent], parent=parent, allow_extra=allow_extra
        )

    def _command(
        self,
        name: str,
        args: Dict[str, Any],
        registry: Dict[str, Command],
        *,
        allow_extra: bool = False,
        parent: Optional[str] = None,
    ) -> Callable[[_CallableT], _CallableT]:
        """The decorator used to wrap command functions."""

        def cli_wrapper(cli_func: _CallableT) -> _CallableT:
            if name in registry:
                raise CommandExistsError(name)
            cmd = self.make_command(
                name, args, cli_func, parent=parent, allow_extra=allow_extra
            )
            registry[name] = cmd
            return cli_func

        return cli_wrapper

    def make_command(
        self,
        name: str,
        args: Dict[str, Any],
        func: Callable,
        *,
        parent: Optional[str] = None,
        allow_extra: bool = False,
    ) -> Command:
        sig = signature(func)
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
                else DEFAULT_PLACEHOLDER  # placeholder for unset defaults
            )
            if param_name not in args:  # support args not in decorator
                args[param_name] = Arg()
        cli_args = []
        for param, arg_info in args.items():
            if param not in sig_types:  # unknown argument
                path = join_strings(parent, name)
                err = f"argument not found in function for '{path}': {param}"
                raise CliParserError(err)

            def get_converter(arg_type: Type) -> Optional[ConverterType]:
                return self.converters.get(arg_type, arg_info.converter)

            param_type = sig_types[param]
            converter = get_converter(param_type)
            arg_type = converter or param_type
            arg = get_arg(
                param,
                arg_info,
                arg_type,
                orig_type=param_type,
                default=sig_defaults[param],
                skip_resolve=converter is not None,
                get_converter=get_converter,
            )
            arg.help = join_strings(arg.help, f"({format_type(arg.display_type)})")
            cli_args.append(arg)
        return Command(
            name=name,
            func=func,
            args=cli_args,
            description=func.__doc__,
            allow_extra=allow_extra,
            parent=parent,
        )

    def placeholder(self, name: str, *, description: Optional[str] = None) -> None:
        """Add empty parent command placeholder with help for subcommands."""
        if name in self.commands:
            raise CommandExistsError(name)

        def func(*args, **kwargs) -> None:
            sub = self.subcommands.get(name, {})
            # If this runs, we want to show the help instead of doing nothing
            self.parse([self._help_arg], [], sub, name=name, description=description)

        dummy = Command(
            name=name, func=func, args=[], description=description, is_placeholder=True
        )
        self.commands[name] = dummy

    def run(self, args: Optional[List[str]] = None) -> None:
        """
        Run the CLI. Should typically be used in the __main__.py nested under a
        `if __name__ == "__main__":` block.
        """
        run_args = args if args is not None else [*sys.argv]
        if len(run_args) <= 1 or run_args[1] == self._help_arg:
            print(self.format_info())
        else:
            # Make single command CLIs available without command name
            if len(self.commands) == 1 and len(self.subcommands) <= 1:
                single_cmd = list(self.commands.keys())[0]
                if run_args[1] != single_cmd:
                    run_args.insert(1, single_cmd)
            command = run_args.pop(1)
            args = run_args[1:]
            if self.version and command == self._version_arg:
                print(self.version)
                sys.exit(0)
            subcommands = self.subcommands.get(command, {})
            if command not in self.commands:
                if not subcommands:
                    raise CommandNotFoundError(command, list(self.commands))
                # Add a dummy parent to support subcommands without parents
                self.placeholder(command)
            cmd = self.commands[command]
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
            # Catch specific error types (and their subclasses), and invoke
            # their handler callback. Handlers can return an integer exit code,
            # which will be passed to sys.exit.
            errors_map = expand_error_subclasses(self.errors)
            try:
                func(**values)
            except tuple(errors_map.keys()) as e:
                handler = errors_map[e.__class__]
                err_code = handler(e)
                if err_code is not None:
                    sys.exit(err_code)

    def get_parsers(
        self,
        arg_info: List[ArgparseArg],
        subcommands: Dict[str, Command] = SimpleFrozenDict(),
        *,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Tuple[ArgumentParser, Dict[str, Tuple[ArgumentParser, Command]]]:
        """Get parser for a given command."""
        p = ArgumentParser(
            prog=join_strings(self.prog, name),
            description=description,
            formatter_class=HelpFormatter,
            add_help=not any(a.arg.option == self._help_arg for a in arg_info),
            argument_default=DEFAULT_PLACEHOLDER,
        )
        if self.version:
            p.add_argument(self._version_arg, action="version", version=self.version)
        self._add_args(p, arg_info)
        subparsers: Dict[str, Tuple[ArgumentParser, Command]] = {}
        if subcommands:
            # We're using the dest to determine whether subcommand was called
            sp = p.add_subparsers(
                title="Subcommands",
                dest=self._subcommand_key,
                parser_class=ArgumentParser,
            )
            for sub_name, sub_cmd in subcommands.items():
                add_help = not any(a.arg.option == self._help_arg for a in sub_cmd.args)
                subp = sp.add_parser(
                    sub_cmd.name,
                    description=sub_cmd.description,
                    help=sub_cmd.description,
                    prog=join_strings(self.prog, sub_cmd.parent, sub_name),
                    add_help=add_help,
                    formatter_class=HelpFormatter,
                    argument_default=DEFAULT_PLACEHOLDER,
                )
                subparsers[sub_cmd.name] = (subp, sub_cmd)
                self._add_args(subp, sub_cmd.args)
        return p, subparsers

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
        p, subparsers = self.get_parsers(
            arg_info, subcommands, name=name, description=description
        )
        # Handling of subcommands is a bit convoluted
        # https://docs.python.org/3/library/argparse.html#sub-commands
        namespace, extra = p.parse_known_args(args)
        values = {**vars(namespace), self.extra_key: extra}
        sub_key = values.pop(self._subcommand_key, None)
        if not sub_key:  # we're not in a subcommand
            cmds = self.commands[name] if name in self.commands else None
            return self._validate(cmds, values, allow_extra)
        if sub_key not in subparsers:
            raise CliParserError(f"invalid subcommand: '{sub_key}'")
        subparser, subcmd = subparsers[cast(str, sub_key)]
        sub_namespace, sub_extra = subparser.parse_known_args(args[1:])
        sub_values = {**vars(sub_namespace), self.extra_key: sub_extra}
        sub_values = self._validate(subcmd, sub_values, subcmd.allow_extra)
        return {**sub_values, self._subcommand_key: sub_key}

    def _add_args(self, parser: ArgumentParser, args: List[ArgparseArg]) -> None:
        """Add arguments to a parser or subparser."""
        for arg in args:
            if arg.id == self.extra_key:
                continue
            func_args, func_kwargs = arg.to_argparse()
            parser.add_argument(*func_args, **func_kwargs)

    def _validate(
        self, command: Optional[Command], values: Dict[str, Any], allow_extra: bool
    ) -> Dict[str, Any]:
        """
        Validate required args separately to avoid subparser conflicts.
        Handle extra arguments and raise error if needed. We're doing this
        manually to avoide false positive argparse errors with subcommands.
        """
        extra = values.get(self.extra_key)
        if not allow_extra:
            if extra:
                raise CliParserError(f"unrecognized arguments: {' '.join(extra)}")
            values.pop(self.extra_key, None)
        if command:
            required = []
            for arg in command.args:
                if arg.id not in values or values[arg.id] is DEFAULT_PLACEHOLDER:
                    required.append(arg.arg.option or arg.id)
            if required:
                err = f"the following arguments are required: {', '.join(required)}"
                raise CliParserError(err)
        return values

    def format_info(self) -> str:
        """Nicely format the available command overview and add subcommands."""
        data = []
        for name, cmd in self.commands.items():
            data.append((f"  {name}", format_arg_help(cmd.description)))
            if name in self.subcommands:
                col = f"Subcommands: {', '.join(self.subcommands[name])}"
                data.append(("", col))
        for name in self.subcommands:
            if name not in self.commands:
                col = f"Subcommands: {', '.join(self.subcommands[name])}"
                data.append((f"  {name}", col))
        info = [self.help, "\nAvailable commands:", format_table(data)]
        return join_strings(*info, char="\n")

    def to_static(self, path: Union[str, Path]) -> Path:
        data = cli_to_json(self)
        path = Path(path)
        with path.open("w", encoding="utf8") as f:
            f.write(json.dumps(data))
        return path


def cli_to_json(cli: Radicli) -> Dict[str, Any]:
    return {
        "prog": cli.prog,
        "help": cli.help,
        "version": cli.version,
        "extra_key": cli.extra_key,
        "commands": {cmd.name: cmd_to_json(cmd) for cmd in cli.commands.values()},
        "subcommands": {
            parent: {sub.name: cmd_to_json(sub) for sub in subs.values()}
            for parent, subs in cli.subcommands.items()
        },
    }


def cmd_to_json(cmd: Command) -> Dict[str, Any]:
    return {
        "name": cmd.name,
        "args": args_to_json(cmd.args),
        "description": cmd.description,
        "allow_extra": cmd.allow_extra,
        "parent": cmd.parent,
        "is_placeholder": cmd.is_placeholder,
    }


def args_to_json(args: List[ArgparseArg]) -> List[Dict[str, Any]]:
    data = []
    for arg in args:
        arg_data = {
            "id": arg.id,
            "option": arg.arg.option,
            "short": arg.arg.short,
            "default": str(arg.default),
            "help": arg.help,
            "action": str(arg.action) if arg.action else None,
            "choices": list(arg.choices) if arg.choices else None,
            "has_converter": arg.has_converter,
        }
        data.append(arg_data)
    return data
