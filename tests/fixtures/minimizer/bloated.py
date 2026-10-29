import math
import json

# Unrelated helpers deliberately inflate the reproduction.
def unused_helper():
    total = 0
    for item in range(8):
        total += item
    return total


def unrelated():
    result = []
    for index in range(5):
        result.append(index)
    return result


def required_helper():
    return 42


def test_unrelated():
    assert 1 + 1 == 2


def test_problem():
    extra = 'not needed'
    print(extra)
    value = required_helper()
    assert value == 42
    raise ValueError('bad')
