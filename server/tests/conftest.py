from datetime import datetime, timezone

import pytest

from boredroom.parser import parse

# 11:30 IST on 30 Oct 2026: every game's puzzle for that day is out
NOW = datetime(2026, 10, 30, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def p():
    def _p(text, now=NOW, tz="Asia/Kolkata"):
        return parse(text, now=now, tz=tz)
    return _p


def one(parsed):
    assert len(parsed.results) == 1, parsed.to_dict()
    return parsed.results[0]
