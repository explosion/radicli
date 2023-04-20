from typing import TYPE_CHECKING, Optional, List
from collections import defaultdict
from pathlib import Path
import re

from .util import format_type, BooleanOptionalAction, DEFAULT_PLACEHOLDER

if TYPE_CHECKING:
    from .cli import Radicli, Command

DEFAULT_DOCS_COMNENT = "This file is auto-generated"
whitespace_matcher = re.compile(r"\s+", re.ASCII)


def document_cli(
    cli: "Radicli",
    title: Optional[str] = None,
    description: Optional[str] = None,
    comment: Optional[str] = DEFAULT_DOCS_COMNENT,
    path_root: Optional[Path] = None,
) -> str:
    """Generate Markdown-formatted documentation for a CLI."""
    lines = []
    start_heading = 2 if title is not None else 1
    if comment is not None:
        lines.append(f"<!-- {comment} -->")
    if title is not None:
        lines.append(f"# {title}")
    if description is not None:
        lines.append(_strip(description))
    prefix = f"{cli.prog} " if cli.prog else ""
    cli_title = f"`{cli.prog}`" if cli.prog else "CLI"
    lines.append(f"{'#' * start_heading} {cli_title}")
    if cli.help:
        lines.append(cli.help)
    for cmd in cli.commands.values():
        lines.extend(_command(cmd, start_heading + 1, prefix, path_root))
        if cmd.name in cli.subcommands:
            for sub_cmd in cli.subcommands[cmd.name].values():
                lines.extend(_command(sub_cmd, start_heading + 2, prefix, path_root))
    for name in cli.subcommands:
        by_parent = defaultdict(list)
        if name not in cli.commands:
            sub_cmds = cli.subcommands[name]
            by_parent[name].extend(sub_cmds.values())
        for parent, sub_cmds in by_parent.items():  # subcommands without placeholders
            lines.append(f"{'#' * (start_heading + 1)} `{prefix + parent}`")
            for sub_cmd in sub_cmds:
                lines.extend(_command(sub_cmd, start_heading + 2, prefix, path_root))
    return "\n\n".join(lines)


def _command(
    cmd: "Command", level: int, prefix: str, path_root: Optional[Path]
) -> List[str]:
    lines = []
    lines.append(f"{'#' * level} `{prefix + cmd.display_name}`")
    if cmd.description:
        lines.append(_strip(cmd.description))
    if cmd.args:
        table = []
        for ap_arg in cmd.args:
            name = f"`{ap_arg.arg.option or ap_arg.id}`"
            if ap_arg.action == BooleanOptionalAction and ap_arg.default is True:
                assert ap_arg.arg.option
                name += f"/`--no-{ap_arg.arg.option[2:]}`"
            if ap_arg.arg.short:
                name += ", " + f"`{ap_arg.arg.short}`"
            default = ""
            if ap_arg.default is not DEFAULT_PLACEHOLDER:
                if isinstance(ap_arg.default, Path):
                    default_value = ap_arg.default
                    if path_root is not None:
                        default_value = default_value.relative_to(path_root)
                else:
                    default_value = repr(ap_arg.default)
                default = f"`{default_value}`"
            arg_type = format_type(ap_arg.display_type)
            arg_code = f"`{arg_type}`" if arg_type else ""
            table.append((name, arg_code, ap_arg.arg.help or "", default))
        header = ["Argument", "Type", "Description", "Default"]
        head = f"| {' | '.join(header)} |"
        divider = f"| {' | '.join('---' for _ in range(len(header)))} |"
        body = "\n".join(f"| {' | '.join(row)} |" for row in table)
        lines.append(f"{head}\n{divider}\n{body}")
    return lines


def _strip(text: str) -> str:
    return whitespace_matcher.sub(" ", text).strip()
