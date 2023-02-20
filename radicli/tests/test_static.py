import pytest
from radicli import Radicli, StaticRadicli, Arg

from .util import make_tempdir


def test_to_static_roundtrip(capsys):
    cli = Radicli(prog="test")

    @cli.command("hello", a=Arg("--a", help="aaa"), b=Arg("--b", help="bbb"))
    def hello(a, b):
        """Hello"""
        ...

    @cli.command("world", c=Arg(help="ccc"))
    def world(c):
        """World"""
        ...

    with make_tempdir() as dir_path:
        path = dir_path / "static.json"
        cli.to_static(path)

        static = StaticRadicli(path)

    assert static.prog == cli.prog
    assert len(static.commands) == len(cli.commands)
    for parent, commands in static.subcommands:
        assert parent in cli.subcommands
        assert len(cli.subcommands[parent]) == len(commands)

    hello1 = static.commands["hello"]
    hello2 = cli.commands["hello"]
    assert hello1.name == hello2.name
    assert hello1.description == hello2.description
    for (arg1, arg2) in zip(hello1.args, hello2.args):
        assert arg1.help == arg2.help
        assert arg1.arg.option == arg2.arg.option
        assert arg1.arg.short == arg2.arg.short
        assert arg1.arg.help == arg2.arg.help

    with pytest.raises(SystemExit):
        static.run(["", "--help"])
    captured1 = capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.run(["", "--help"])
    captured2 = capsys.readouterr().out
    assert captured1 == captured2

    with pytest.raises(SystemExit):
        static.run(["", "hello", "--help"])
    captured1 = capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.run(["", "hello", "--help"])
    captured2 = capsys.readouterr().out
    assert captured1 == captured2

    with pytest.raises(SystemExit):
        static.run(["", "world", "--help"])
    captured1 = capsys.readouterr().out
    with pytest.raises(SystemExit):
        cli.run(["", "world", "--help"])
    captured2 = capsys.readouterr().out
    assert captured1 == captured2
