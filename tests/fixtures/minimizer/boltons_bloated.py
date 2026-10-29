import json
import math
import pickle
from boltons.dictutils import OMD

# Unrelated setup simulates a verbose generated reproduction.
UNUSED = {'one': 1, 'two': 2}


def unrelated_helper():
    values = []
    for index in range(5):
        values.append(index * 2)
    return values


def another_helper(value):
    return str(value).upper()


def test_unrelated_one():
    assert len(UNUSED) == 2


def test_unrelated_two():
    assert unrelated_helper() == [0, 2, 4, 6, 8]


def test_repro():
    ignored = another_helper('debug')
    print(ignored)
    items = OMD({'a': 1})
    data = pickle.dumps(items)
    restored = pickle.loads(data)
    assert list(restored.iteritems()) == list(items.iteritems())
