from repro.report import write_report


def test_needs_info_has_questions_and_no_test(tmp_path):
    path = write_report(tmp_path, {'status': 'needs_info', 'status_detail': 'More detail needed'},
                        questions=['What happened?'])
    text = path.read_text()
    assert 'What happened?' in text
    assert 'Reproduction test' not in text
    assert 'not been posted' in text


def test_reproduced_report_uses_saved_test_and_redacts(tmp_path):
    (tmp_path / 'test_repro.py').write_text('def test_x():\n    assert False\n')
    path = write_report(tmp_path, {'status': 'reproduced', 'verification': 'completed',
                                   'confidence': 'high', 'status_detail': 'secret-value'},
                        secrets=('secret-value',))
    text = path.read_text()
    assert 'def test_x()' in text
    assert '[REDACTED]' in text and 'secret-value' not in text
    assert '**high**' in text


def test_unverified_candidate_is_not_claimed(tmp_path):
    (tmp_path / 'test_repro.py').write_text('def test_x(): pass')
    text = write_report(tmp_path, {'status': 'reproduced', 'verification': 'pending'}).read_text()
    assert 'status: not_reproduced' in text
    assert 'def test_x' not in text


def test_report_includes_recorded_environment(tmp_path):
    import json
    (tmp_path / 'test_repro.py').write_text('def test_x(): assert False')
    (tmp_path / 'environment.json').write_text(json.dumps({'repo': 'a/b', 'selected_ref': '1.2',
                                                           'commit': 'abc', 'python': '3.11'}))
    text = write_report(tmp_path, {'status': 'reproduced', 'verification': 'completed',
                                   'confidence': 'medium'}).read_text()
    assert 'Repository: a/b' in text and 'Python: 3.11' in text
