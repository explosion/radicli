from typing import List, Union, Optional
from pathlib import Path
import json

from .cli import Radicli, Command
from .util import StaticData, ConvertersType, SimpleFrozenDict


class StaticRadicli(Radicli):
    data: StaticData
    disable: bool
    debug: bool

    def __init__(
        self,
        data: StaticData,
        disable: bool = False,
        debug: bool = False,
        converters: ConvertersType = SimpleFrozenDict(),
    ) -> None:
        super().__init__(
            prog=data["prog"],
            help=data["help"],
            version=data["version"],
            extra_key=data["extra_key"],
        )
        self.commands = {
            name: Command.from_static_json(cmd, converters)
            for name, cmd in data["commands"].items()
        }
        self.subcommands = {
            parent: {
                name: Command.from_static_json(sub, converters)
                for name, sub in subs.items()
            }
            for parent, subs in data["subcommands"].items()
        }
        self.data = data
        self.disable = disable
        self.debug = debug
        self._debug_start = "===== STATIC ====="
        self._debug_end = "=== END STATIC ==="

    def run(self, args: Optional[List[str]] = None) -> None:
        """
        Run the static CLI. Should usually happen before importing and running
        the live CLI so the static CLI can show help or raise errors and
        exit, without requiring importing the live CLI.
        """
        if self.disable:
            return
        if self.debug:
            print(self._debug_start)
        super().run(args)
        if self.debug:
            print(self._debug_end)

    @classmethod
    def load(
        cls,
        file_path: Union[str, Path],
        debug: bool = False,
        disable: bool = False,
        converters: ConvertersType = SimpleFrozenDict(),
    ) -> "StaticRadicli":
        """Load the static CLI from a file path created with Radicli.to_static."""
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            raise ValueError(f"Not a valid file path: {path}")
        with path.open("r", encoding="utf8") as f:
            data = json.load(f)
        return cls(data, disable=disable, debug=debug, converters=converters)
