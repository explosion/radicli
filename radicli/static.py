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
            name: Command.from_static_json(cmd)
            for name, cmd in data["commands"].items()
        }
        self.subcommands = {
            parent: {name: Command.from_static_json(sub) for name, sub in subs.items()}
            for parent, subs in data["subcommands"].items()
        }
        self.path = path
        self.data = data
        self.debug = debug
        self._debug_start = "===== STATIC ====="
        self._debug_end = "=== END STATIC ==="

    def run(self, args: Optional[List[str]] = None):
        """
        Run the static CLI. Should usually happen before importing and running
        the live CLI so the static CLI can show help or raise errors and
        exit, without requiring importing the live CLI.
        """
        if self.debug:
            print(self._debug_start)
        super().run(args)
        if self.debug:
            print(self._debug_end)
