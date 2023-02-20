from typing import Dict, Any, List, Union, Optional
from pathlib import Path
import json

from . import Radicli, Command
from .util import Arg, ArgparseArg, DEFAULT_PLACEHOLDER


class StaticRadicli(Radicli):
    path: Path
    data: Dict[str, Any]
    debug: bool

    def __init__(self, path: Union[str, Path], debug: bool = False):
        path = Path(path)
        if not path.exists() or not path.is_file():
            raise ValueError(f"Not a valid file path: {path}")
        with path.open("r", encoding="utf8") as f:
            data = json.load(f)
        super().__init__(
            prog=data["prog"],
            help=data["help"],
            version=data["version"],
            extra_key=data["extra_key"],
        )
        self.commands = {
            name: cmd_from_json(cmd) for name, cmd in data["commands"].items()
        }
        self.subcommands = {
            parent: {name: cmd_from_json(sub) for name, sub in subs.items()}
            for parent, subs in data["subcommands"].items()
        }
        self.path = path
        self.data = data
        self.debug = debug

    def run(self, args: Optional[List[str]] = None):
        if self.debug:
            print("===== STATIC =====")
        super().run(args)
        if self.debug:
            print("=== END STATIC ===")


def cmd_from_json(data: Dict[str, Any]) -> "Command":
    return Command(
        name=data["name"],
        func=lambda *args, **kwargs: None,
        args=args_from_json(data["args"]),
        description=data["description"],
        allow_extra=data["allow_extra"],
        parent=data["parent"],
        is_placeholder=data["is_placeholder"],
    )


def args_from_json(data: List[Dict[str, Any]]) -> List[ArgparseArg]:
    args = []
    for arg in data:
        ap_arg = ArgparseArg(
            id=arg["id"],
            arg=Arg(arg["option"], arg["short"]),
            type=str if not arg["action"] else None,
            orig_type=str if not arg["action"] else None,
            default=DEFAULT_PLACEHOLDER
            if arg["default"] == DEFAULT_PLACEHOLDER
            else arg["default"],
            help=arg["help"],
            action=arg["action"],
            choices=arg["choices"],
            has_converter=arg["has_converter"],
        )
        args.append(ap_arg)
    return args
