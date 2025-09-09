import typing
from typing import Union, Generic, List, TypeVar
from pathlib import Path
import pathlib
from uuid import UUID
import pytest
import shutil
from radicli.util import stringify_type, get_list_converter, get_arg, Arg

_KindT = TypeVar("_KindT", bound=Union[str, int, float, Path])


class CustomGeneric(Generic[_KindT]):
    ...


@pytest.mark.parametrize(
    "arg_type,expected",
    [
        (str, "str"),
        (bool, "bool"),
        (Path, "Path"),
        (List[int], "List[int]"),
        (CustomGeneric, "CustomGeneric"),
        (CustomGeneric[str], "CustomGeneric[str]"),
        (UUID, "UUID"),
        (shutil.rmtree, "rmtree"),
        (typing.List[pathlib.Path], "List[Path]"),
        (
            typing.Dict[Union[str, int], Union[str, pathlib.Path, int]],
            "Dict[Union[str, int], Union[str, Path, int]]",
        ),
        (Union[str, typing.Tuple[str, Path]], "Union[str, Tuple[str, Path]]"),
        ("foo.bar", "foo.bar"),
        (None, None),
    ],
)
def test_stringify_type(arg_type, expected):
    assert stringify_type(arg_type) == expected


@pytest.mark.parametrize(
    "item_type,value,expected",
    [
        # Separated string
        (str, "hello, world,test", ["hello", "world", "test"]),
        (int, " 1,2,3 ", [1, 2, 3]),
        (float, "0.123,5,  1.234", [0.123, 5.0, 1.234]),
        # Quoted list
        (str, "[hello, world]", ["hello", "world"]),
        (str, '["hello", "world"]', ["hello", "world"]),
        (str, "['hello', 'world']", ["hello", "world"]),
        (int, "[1,2,3]", [1, 2, 3]),
        (int, '["1","2","3"]', [1, 2, 3]),
        (int, "['1','2','3']", [1, 2, 3]),
        (float, "[0.23,2,3.45]", [0.23, 2.0, 3.45]),
        (float, '["0.23","2","3.45"]', [0.23, 2.0, 3.45]),
        (float, "['0.23','2','3.45']", [0.23, 2.0, 3.45]),
    ],
)
def test_get_list_converter(item_type, value, expected):
    converter = get_list_converter(item_type)
    assert converter(value) == expected

def test_get_arg_string_type():
    arg_info = Arg()
    result = get_arg("test_param", arg_info, "str")
    assert result.type is str

def test_get_arg_regular_type():
    arg_info = Arg()
    result = get_arg("test_param", arg_info, int)
    assert result.type is int