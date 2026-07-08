from itertools import filterfalse, tee
from pathlib import Path
from typing import Any, Callable, Iterable, List, Tuple, TypeVar

from django.utils.datastructures import OrderedSet
from more_itertools import bucket

T = TypeVar("T")

def b64pad(s: str | bytes):
    padchar = b'=' if isinstance(s, bytes) else '='
    padlen = -len(s := s.lstrip(padchar)) % 4
    return s.ljust(padlen, padchar)


def split_by_predicate(source: Iterable[T], predicate: Callable[[T], bool]) -> Tuple[List[T], List[T]]:
    """
    Splits a source iterable into two lists based on a predicate.

    Args:
        source: The iterable to split.
        predicate: A callable that returns True or False for each element.

    Returns:
        A tuple containing two lists:
            - The first list with elements for which the predicate is True.
            - The second list with elements for which the predicate is False.
    """
    true_iter, false_iter = tee(source)  # Duplicate the iterable
    return list(filter(predicate, true_iter)), list(filterfalse(predicate, false_iter))


def ensure_dir(path: str | Path):
    if isinstance(path, str):
        path = Path(path).resolve()
    if path.exists() and not path.is_dir():
        raise ValueError(f"Path {path} is not a dir")
    path.mkdir(parents=True, exist_ok=True)
    return path


def getprop(o, prop: str, default=None):
    propseq = prop.split('.')
    while propseq:
        nextprop = propseq.pop(0)
        if o is None:
            break
        if isinstance(o, dict):
            o = o.get(nextprop)
        else:
            o = getattr(o, nextprop, None)
    return default if o is None else o


def position(_item, _list):
    try:
        return _list.index(_item)
    except ValueError:
        return len(_list)


def accept_reject(iterable: Iterable, tester: Callable[[Any], bool]) -> tuple[list, list]:
    qcb = bucket(iterable, tester)
    return list(qcb[True]), list(qcb[False])


def obj_to_dict(obj: Any) -> dict:
    return {k: getattr(obj, k, None) for k in dir(obj) if not k.startswith('_')}


def dict_list_to_tuple_list(dict_list: list[dict], *, with_header: bool = True):
    keys = OrderedSet()
    for d in dict_list:
        for k in d.keys():
            keys.add(k)
    tuple_list = [tuple(d.get(k, None) for k in keys) for d in dict_list]
    return [tuple(keys), *tuple_list] if with_header else tuple_list
