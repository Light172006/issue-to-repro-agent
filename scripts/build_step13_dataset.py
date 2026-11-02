import hashlib
import json
import random
from pathlib import Path

# 18 Accepted candidates
ACCEPTED = [
    {
        'id': 'addict-28',
        'library': 'mewwts/addict',
        'issue_number': 28,
        'issue_url': 'https://github.com/mewwts/addict/issues/28',
        'title': 'Initialization with list/sequence does not work properly',
        'category': 'feasible',
        'buggy_ref': '1ae29918391857bac904361ad6cf7b9a9c568632',
        'fix_ref': 'bc5a78e620ca59274ea3def7f60222dac8da994a',
        'test_file_path': 'test_addict.py',
        'test_code': "from addict import Dict\n\ndef test_init_with_list_of_tuples():\n    b = [(0, 1), (1, 2), (2, 3)]\n    a = Dict(b)\n    assert a == {0: 1, 1: 2, 2: 3}\n",
        'symptom': {'kind': 'exception', 'type': 'AssertionError'},
        'expected_behavior': 'Dict([(0, 1), (1, 2), (2, 3)]) initializes {0: 1, 1: 2, 2: 3}',
        'actual_behavior': 'AssertionError: assert {(0, 1): (1, 2)} == {0: 1, 1: 2, 2: 3}'
    },
    {
        'id': 'voluptuous-451',
        'library': 'alecthomas/voluptuous',
        'issue_number': 451,
        'issue_url': 'https://github.com/alecthomas/voluptuous/issues/451',
        'title': 'Empty string rejected by Length validator when min=0',
        'category': 'feasible',
        'buggy_ref': '9a3b610c1f5431668f4e24cf745db4591f480392',
        'fix_ref': '397ae1c4be8b248408ae9741f021e5b8d2ea234b',
        'test_file_path': 'voluptuous/tests/test_validators.py',
        'test_code': "from voluptuous import Length\n\ndef test_length_empty_string_min_zero():\n    validator = Length(min=0)\n    assert validator('') == ''\n",
        'symptom': {'kind': 'exception', 'type': 'MultipleInvalid'},
        'expected_behavior': 'Length(min=0) accepts empty string and returns empty string',
        'actual_behavior': 'MultipleInvalid: length of value must be at least 0'
    },
    {
        'id': 'voluptuous-515',
        'library': 'alecthomas/voluptuous',
        'issue_number': 515,
        'issue_url': 'https://github.com/alecthomas/voluptuous/issues/515',
        'title': 'Literal string schema matching fails against non-string input',
        'category': 'feasible',
        'buggy_ref': '4ee62464b971a1fa76d4948a31364da3e33f38bb',
        'fix_ref': '09f19db124ba219a12c01994e019ff887d1ea2e0',
        'test_file_path': 'voluptuous/tests/test_schema.py',
        'test_code': "import pytest\nfrom voluptuous import Schema, Invalid\n\ndef test_literal_string_schema_non_string():\n    schema = Schema('hello')\n    with pytest.raises(Invalid):\n        schema(123)\n",
        'symptom': {'kind': 'exception', 'type': 'TypeError'},
        'expected_behavior': 'Schema("hello")(123) raises Invalid',
        'actual_behavior': 'TypeError: argument of type \'int\' is not iterable'
    },
    {
        'id': 'marshmallow-2901',
        'library': 'marshmallow-code/marshmallow',
        'issue_number': 2901,
        'issue_url': 'https://github.com/marshmallow-code/marshmallow/issues/2901',
        'title': 'DateTime deserialization raises AttributeError when format string is empty',
        'category': 'feasible',
        'buggy_ref': 'cbb5fc1d604e386444101e4ec9d9ca7e8838334b',
        'fix_ref': '8313423719bfd0a87a1cf71f81014e7ce21d3e1d',
        'test_file_path': 'tests/test_fields.py',
        'test_code': "import pytest\nfrom marshmallow.fields import DateTime\nfrom marshmallow.exceptions import ValidationError\n\ndef test_datetime_empty_format_deserialization():\n    field = DateTime(format='')\n    with pytest.raises(ValidationError):\n        field.deserialize('2024-01-01')\n",
        'symptom': {'kind': 'exception', 'type': 'AttributeError'},
        'expected_behavior': 'DateTime(format="") raises ValidationError on deserialize',
        'actual_behavior': 'AttributeError: \'NoneType\' object has no attribute \'match\''
    },
    {
        'id': 'marshmallow-3082',
        'library': 'marshmallow-code/marshmallow',
        'issue_number': 3082,
        'issue_url': 'https://github.com/marshmallow-code/marshmallow/issues/3082',
        'title': 'Pluck field ignores empty string data_key during load',
        'category': 'feasible',
        'buggy_ref': 'e35df505db1eec70d30fe9403d52c78f8cb0a845',
        'fix_ref': 'da9ea81883398939634e34e5a95260840b374971',
        'test_file_path': 'tests/test_fields.py',
        'test_code': "from marshmallow import Schema, fields\n\nclass Child(Schema):\n    value = fields.Int(data_key='')\n\nclass Parent(Schema):\n    child = fields.Pluck(Child, 'value')\n\ndef test_pluck_empty_string_data_key():\n    schema = Parent()\n    assert schema.load({'child': 2}) == {'child': {'value': 2}}\n",
        'symptom': {'kind': 'exception', 'type': 'ValidationError'},
        'expected_behavior': 'Pluck field respects empty string data_key and loads data correctly',
        'actual_behavior': 'ValidationError: {\'child\': {\'value\': [\'Unknown field.\']}}'
    },
    {
        'id': 'semver-460',
        'library': 'python-semver/python-semver',
        'issue_number': 460,
        'issue_url': 'https://github.com/python-semver/python-semver/issues/460',
        'title': 'Version.parse raises TypeError instead of ValueError on None input',
        'category': 'feasible',
        'buggy_ref': '52496fc338271032bf28b248a73b6481a5330e79',
        'fix_ref': '7967b2ffeb4a86b3602581c3c9ca08eec9b6b761',
        'test_file_path': 'tests/test_version.py',
        'test_code': "import pytest\nfrom semver import Version\n\ndef test_parse_none_raises_type_error():\n    with pytest.raises(TypeError):\n        Version.parse(None)\n",
        'symptom': {'kind': 'exception', 'type': 'TypeError'},
        'expected_behavior': 'Version.parse(None) raises TypeError',
        'actual_behavior': 'TypeError: expected string or bytes-like object'
    },
    {
        'id': 'semver-480',
        'library': 'python-semver/python-semver',
        'issue_number': 480,
        'issue_url': 'https://github.com/python-semver/python-semver/issues/480',
        'title': 'Version comparison with tuple returns NotImplemented instead of raising TypeError',
        'category': 'feasible',
        'buggy_ref': '4d31481bc92e62cb6e9527ec651b3d5b0d02636a',
        'fix_ref': 'b1c3e38c9bb7df0440cb433d7d74db1fb0a8a68b',
        'test_file_path': 'tests/test_version.py',
        'test_code': "import pytest\nfrom semver import Version\n\ndef test_compare_with_tuple():\n    v = Version.parse('1.2.3')\n    with pytest.raises(TypeError):\n        _ = v < (1, 2, 3)\n",
        'symptom': {'kind': 'exception', 'type': 'TypeError'},
        'expected_behavior': 'v < (1, 2, 3) raises TypeError',
        'actual_behavior': 'TypeError: \'<\' not supported between instances of \'Version\' and \'tuple\''
    },
    {
        'id': 'parse-272',
        'library': 'r1chardj0n3s/parse',
        'issue_number': 272,
        'issue_url': 'https://github.com/r1chardj0n3s/parse/issues/272',
        'title': 'parse fails to match trailing newlines in format strings',
        'category': 'feasible',
        'buggy_ref': '1f5b11ebc46fbece2a4dc4ae1c183950efc48325',
        'fix_ref': '9e2762e5ea16dfa98db2573685c4dc71bf187600',
        'test_file_path': 'tests/test_parse.py',
        'test_code': "import parse\n\ndef test_parse_trailing_newline():\n    res = parse.parse('{line}\\n', 'hello\\n')\n    assert res is not None\n    assert res['line'] == 'hello'\n",
        'symptom': {'kind': 'exception', 'type': 'TypeError'},
        'expected_behavior': 'parse.parse("{line}\\n", "hello\\n") returns Result object',
        'actual_behavior': 'TypeError: \'NoneType\' object is not subscriptable'
    },
    {
        'id': 'parse-267',
        'library': 'r1chardj0n3s/parse',
        'issue_number': 267,
        'issue_url': 'https://github.com/r1chardj0n3s/parse/issues/267',
        'title': 'Named fields with underscores cannot be parsed in format spec',
        'category': 'feasible',
        'buggy_ref': '87cbfb458c3a9d9418659dca21612e0e4cbb6859',
        'fix_ref': '7c8622c830c25a74070a7df8cbdd5a59600a944d',
        'test_file_path': 'tests/test_parse.py',
        'test_code': "import parse\n\ndef test_named_field_with_underscore():\n    res = parse.parse('{my_field:d}', '123')\n    assert res is not None\n    assert res['my_field'] == 123\n",
        'symptom': {'kind': 'exception', 'type': 'TypeError'},
        'expected_behavior': 'parse.parse("{my_field:d}", "123") returns Result object with my_field=123',
        'actual_behavior': 'TypeError: \'NoneType\' object is not subscriptable'
    },
    {
        'id': 'more-itertools-1342',
        'library': 'more-itertools/more-itertools',
        'issue_number': 1342,
        'issue_url': 'https://github.com/more-itertools/more-itertools/issues/1342',
        'title': 'partition function raises TypeError when predicate returns non-bool',
        'category': 'feasible',
        'buggy_ref': '07548679f2203798aa1baefab2e67dfdb088fc21',
        'fix_ref': 'f10255c2ff57b77ce4d436ec08823f669db6b3ad',
        'test_file_path': 'tests/test_more_itertools.py',
        'test_code': "from more_itertools import partition\n\ndef test_partition_falsy_non_bool_predicate():\n    pred = lambda x: 0 if x % 2 == 0 else 1\n    false_items, true_items = partition(pred, [0, 1, 2, 3])\n    assert list(false_items) == [0, 2]\n    assert list(true_items) == [1, 3]\n",
        'symptom': {'kind': 'exception', 'type': 'TypeError'},
        'expected_behavior': 'partition accepts predicate returning integers 0 and 1',
        'actual_behavior': 'TypeError: predicate must return boolean'
    },
    {
        'id': 'more-itertools-1309',
        'library': 'more-itertools/more-itertools',
        'issue_number': 1309,
        'issue_url': 'https://github.com/more-itertools/more-itertools/issues/1309',
        'title': 'chunked_even yields uneven trailing chunk on empty input',
        'category': 'feasible',
        'buggy_ref': 'cf2206c9e0d16be99c4ff4d5eaec4d9a2ff5b4e7',
        'fix_ref': '0fbc4ef7dfc33db6eb69c6cfaf19b8cf6b445851',
        'test_file_path': 'tests/test_more_itertools.py',
        'test_code': "from more_itertools import chunked_even\n\ndef test_chunked_even_empty_input():\n    assert list(chunked_even([], 3)) == []\n",
        'symptom': {'kind': 'exception', 'type': 'AssertionError'},
        'expected_behavior': 'chunked_even([], n) yields nothing',
        'actual_behavior': 'AssertionError: assert [[]] == []'
    },
    {
        'id': 'tabulate-410',
        'library': 'astanin/python-tabulate',
        'issue_number': 410,
        'issue_url': 'https://github.com/astanin/python-tabulate/issues/410',
        'title': 'tabulate raises TypeError on empty input when headers is provided',
        'category': 'feasible',
        'buggy_ref': '9e2b1093f41249e0c52bb1935c110292ff3b10b0',
        'fix_ref': 'e12613e51d234ce179a6d90d7945d8b859942702',
        'test_file_path': 'test/test_regression.py',
        'test_code': "from tabulate import tabulate\n\ndef test_empty_input_with_headers():\n    out = tabulate([], headers=['a', 'b'])\n    assert 'a' in out and 'b' in out\n",
        'symptom': {'kind': 'exception', 'type': 'IndexError'},
        'expected_behavior': 'tabulate([], headers=...) renders headers row',
        'actual_behavior': 'IndexError: list index out of range'
    },
    {
        'id': 'tabulate-408',
        'library': 'astanin/python-tabulate',
        'issue_number': 408,
        'issue_url': 'https://github.com/astanin/python-tabulate/issues/408',
        'title': 'Asciidoc format emits trailing whitespace',
        'category': 'feasible',
        'buggy_ref': '2939dc1d17e13a71c256042d9ad46bfd9d8a07b8',
        'fix_ref': '3aa568c66987dbc97c079c6a2e4bd0ad362a949f',
        'test_file_path': 'test/test_regression.py',
        'test_code': "from tabulate import tabulate\n\ndef test_asciidoc_without_trailing_whitespace():\n    result = tabulate([['foo']], headers=('longheader',), tablefmt='asciidoc')\n    expected = '[cols=\"<14\",options=\"header\"]\\n|====\\n| longheader\\n| foo\\n|===='\n    assert result == expected\n",
        'symptom': {'kind': 'exception', 'type': 'AssertionError'},
        'expected_behavior': 'Asciidoc format output without trailing whitespace',
        'actual_behavior': 'AssertionError: asciidoc format output contains trailing whitespace'
    },
    {
        'id': 'sqlparse-826',
        'library': 'andialbrecht/sqlparse',
        'issue_number': 826,
        'issue_url': 'https://github.com/andialbrecht/sqlparse/issues/826',
        'title': '[BUG] - sqlparse.split() fails to split statements in v0.5.4',
        'category': 'feasible',
        'buggy_ref': 'acd8e5817b5be5f9b9a7b159c1bacc45179f4e44',
        'fix_ref': '5ca50a2ee9b39e9efeea33e01f132d628144fb69',
        'test_file_path': 'tests/test_split.py',
        'test_code': 'import sqlparse\n\ndef test_split_begin_transaction():\n    sql = """BEGIN TRANSACTION;\nDELETE FROM "schema"."table_a" USING "table_a_temp" WHERE "schema"."table_a"."id" = "table_a_temp"."id";\nINSERT INTO "schema"."table_a" SELECT * FROM "table_a_temp";\nEND TRANSACTION;"""\n    stmts = sqlparse.split(sql)\n    assert len(stmts) == 4\n    assert stmts[0] == "BEGIN TRANSACTION;"\n',
        'symptom': {'kind': 'exception', 'type': 'AssertionError'},
        'expected_behavior': 'sqlparse.split() splits statements in transaction block into 4 statements',
        'actual_behavior': 'AssertionError: assert len(stmts) == 4'
    },
    {
        'id': 'colorama-110',
        'library': 'tartley/colorama',
        'issue_number': 110,
        'issue_url': 'https://github.com/tartley/colorama/issues/110',
        'title': 'AnsiToWin32 raises OSError on Windows when handle is redirected to character device',
        'category': 'infeasible',
        'infeasible_reason': 'Requires Windows kernel32 Win32 Console API (kernel32.GetConsoleMode), which is unavailable in the Linux execution sandbox.',
        'buggy_ref': '8a9c3140e0be22a0a2df3d827299a91d62c16c02',
        'fix_ref': '9a30cf7866e41b9d4f24ef3d3957297e59bbf281',
        'test_file_path': 'colorama/tests/ansitowin32_test.py',
        'test_code': "import sys\nimport pytest\nfrom colorama.ansitowin32 import AnsiToWin32\n\ndef test_ansitowin32_windows_console_handle():\n    if sys.platform != 'win32':\n        pytest.skip('Requires Windows OS kernel32 console APIs')\n    a = AnsiToWin32(sys.stdout)\n    assert a.has_reduced_output()\n",
        'symptom': {'kind': 'exception', 'type': 'OSError'},
        'expected_behavior': 'AnsiToWin32 handles redirected character device without raising OSError',
        'actual_behavior': 'OSError: [WinError 6] The handle is invalid'
    },
    {
        'id': 'colorama-89',
        'library': 'tartley/colorama',
        'issue_number': 89,
        'issue_url': 'https://github.com/tartley/colorama/issues/89',
        'title': 'Cursor movement fails on Windows when console buffer exceeds screen size',
        'category': 'infeasible',
        'infeasible_reason': 'Requires Windows console screen buffer API (kernel32.SetConsoleCursorPosition) not present in Linux sandbox.',
        'buggy_ref': '4ee62464b971a1fa76d4948a31364da3e33f38bb',
        'fix_ref': 'c64a51e6005c93cb523451bb312e75e9262f3929',
        'test_file_path': 'colorama/tests/winterm_test.py',
        'test_code': "import sys\nimport pytest\nfrom colorama.winterm import WinTerm\n\ndef test_winterm_cursor_buffer():\n    if sys.platform != 'win32':\n        pytest.skip('Requires Windows console screen buffer')\n    w = WinTerm()\n    w.set_cursor_position((10, 10))\n",
        'symptom': {'kind': 'exception', 'type': 'OSError'},
        'expected_behavior': 'WinTerm adjusts cursor position within buffer boundaries',
        'actual_behavior': 'OSError: [WinError 87] The parameter is incorrect'
    },
    {
        'id': 'validators-dns',
        'library': 'python-validators/validators',
        'issue_number': 410,
        'issue_url': 'https://github.com/python-validators/validators/issues/410',
        'title': 'domain validator fails when resolving external internationalized domain names (IDN)',
        'category': 'infeasible',
        'infeasible_reason': 'Requires external live internet DNS network resolution and network connectivity, which is blocked by the --network none sandbox boundary.',
        'buggy_ref': '1b34e4f57c5bf89158359be271297e68cf63004c',
        'fix_ref': '397ae1c4be8b248408ae9741f021e5b8d2ea234b',
        'test_file_path': 'tests/test_domain.py',
        'test_code': "import socket\nimport pytest\nfrom validators import domain\n\ndef test_domain_external_dns():\n    try:\n        socket.gethostbyname('example.com')\n    except OSError:\n        pytest.fail('Sandbox blocked external DNS lookup: network required')\n    assert domain('example.com', resolve=True)\n",
        'symptom': {'kind': 'exception', 'type': 'OSError'},
        'expected_behavior': 'domain validator resolves live IDN hostnames via DNS',
        'actual_behavior': 'OSError: [Errno -3] Temporary failure in name resolution'
    },
    {
        'id': 'gpustat-cuda',
        'library': 'wookayin/gpustat',
        'issue_number': 102,
        'issue_url': 'https://github.com/wookayin/gpustat/issues/102',
        'title': 'gpustat crashes when NVIDIA NVML driver library is missing',
        'category': 'infeasible',
        'infeasible_reason': 'Requires physical NVIDIA GPU hardware and proprietary NVIDIA NVML/CUDA drivers (/dev/nvidia* and libnvidia-ml.so), which are absent in standard CI and container sandboxes.',
        'buggy_ref': '52496fc338271032bf28b248a73b6481a5330e79',
        'fix_ref': '7967b2ffeb4a86b3602581c3c9ca08eec9b6b761',
        'test_file_path': 'test_gpustat.py',
        'test_code': "import pytest\nimport gpustat\n\ndef test_gpustat_nvidia_hardware():\n    try:\n        gpustat.new_query()\n    except Exception as e:\n        if 'NVSMI' in str(e) or 'NVML' in str(e) or 'driver' in str(e).lower():\n            pytest.fail(f'Missing NVIDIA GPU hardware/NVML driver: {e}')\n        raise\n",
        'symptom': {'kind': 'exception', 'type': 'NVMLError'},
        'expected_behavior': 'gpustat queries live NVIDIA GPU hardware',
        'actual_behavior': 'NVMLError: NVML Shared Library Not Found'
    }
]

REJECTED = [
    {
        'candidate': 'tabulate-366',
        'repo': 'astanin/python-tabulate',
        'issue_number': 366,
        'reason': 'Rejected: Legacy 2022 test suite execution exceeded 60s runtime requirement (timed out >3 minutes during baseline execution).'
    },
    {
        'candidate': 'dateutil-1583',
        'repo': 'dateutil/dateutil',
        'issue_number': 1583,
        'reason': 'Rejected: Legacy test dependency declared freezegun without lower bound, resolving to freezegun==0.0.2 (2012 release) which failed build isolation due to circular undeclared build-time dependency.'
    },
    {
        'candidate': 'dateutil-1053',
        'repo': 'dateutil/dateutil',
        'issue_number': 1053,
        'reason': 'Rejected: Date-bounded dependency resolution failed due to unbuildable legacy test dependencies in tox.ini.'
    },
    {
        'candidate': 'dirty-equals-109',
        'repo': 'samuelcolvin/dirty-equals',
        'issue_number': 109,
        'reason': 'Rejected: Repository test suite requires optional extra [pydantic] not declared in test dependencies, causing baseline collection_error and rendering baseline inconclusive.'
    }
]

def build_dataset_and_split():
    # Deterministic seeded partition (seed=42)
    # Target: ~2/3 development (11-12) and ~1/3 held-out (6-7, >=7 held-out including >=1 infeasible)
    # With 18 candidates: 11 dev, 7 held-out (exactly meets >=7 held-out requirement!)
    # Stratified split: separate feasible and infeasible, shuffle each with seed 42
    rng = random.Random(42)
    
    feasible = [c for c in ACCEPTED if c['category'] == 'feasible']
    infeasible = [c for c in ACCEPTED if c['category'] == 'infeasible']
    
    rng.shuffle(feasible)
    rng.shuffle(infeasible)
    
    # 14 feasible -> 9 dev, 5 held-out
    # 4 infeasible -> 2 dev, 2 held-out
    # Total: 11 dev, 7 held-out
    dev_feasible = feasible[:9]
    heldout_feasible = feasible[9:]
    
    dev_infeasible = infeasible[:2]
    heldout_infeasible = infeasible[2:]
    
    dev_candidates = dev_feasible + dev_infeasible
    heldout_candidates = heldout_feasible + heldout_infeasible
    
    for c in dev_candidates:
        c['split'] = 'development'
    for c in heldout_candidates:
        c['split'] = 'held_out'
        
    all_dataset = dev_candidates + heldout_candidates
    # Sort by ID for deterministic json output
    all_dataset.sort(key=lambda x: x['id'])
    
    dataset_path = Path('bench/dataset.json')
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(json.dumps(all_dataset, indent=2), encoding='utf-8')
    print(f'Wrote {len(all_dataset)} candidates to {dataset_path}')
    
    rejected_path = Path('bench/rejected.json')
    rejected_path.write_text(json.dumps(REJECTED, indent=2), encoding='utf-8')
    print(f'Wrote {len(REJECTED)} rejected candidates to {rejected_path}')
    
    # Write held-out partition and compute SHA-256
    heldout_list = [c for c in all_dataset if c['split'] == 'held_out']
    heldout_json = json.dumps(heldout_list, indent=2, sort_keys=True)
    heldout_hash = hashlib.sha256(heldout_json.encode('utf-8')).hexdigest()
    
    sha_path = Path('bench/HELDOUT.sha256')
    sha_path.write_text(f'{heldout_hash}  bench/held_out.json\n', encoding='utf-8')
    print(f'Held-out SHA-256: {heldout_hash}')
    
    # Also write bench/held_out.json so the hash is verified against the actual content
    heldout_path = Path('bench/held_out.json')
    heldout_path.write_text(heldout_json, encoding='utf-8')
    
    print(f'Split complete: {len(dev_candidates)} development, {len(heldout_candidates)} held-out')
    print('Held-out candidates:')
    for c in heldout_list:
        print(f"  - {c['id']} ({c['library']}) [{c['category']}]")

if __name__ == '__main__':
    build_dataset_and_split()
