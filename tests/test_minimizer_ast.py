from repro.minimizer import remove_units, units


def test_top_level_ranges_include_decorators_and_keep_formatting():
    source = 'import os\n\n# retained\n@decorator\ndef test_x():\n    assert True\n'
    found = units(source, top_level=True)
    assert [(x.start, x.end) for x in found] == [(1, 1), (4, 6)]
    assert remove_units(source, [found[0]]) == '\n# retained\n@decorator\ndef test_x():\n    assert True\n'


def test_only_statement_is_replaced_with_pass():
    source = 'def test_x():\r\n    assert False\r\n'
    assert remove_units(source, units(source, top_level=False)) == 'def test_x():\r\n    pass\r\n'
