"""Every pattern a paste meets, against inputs built to make backtracking blow up. Each
paste must parse in well under a second at the API's size limit (see config)."""
import multiprocessing as mp
import time

import pytest

from boredroom.parser import parse


def _timed(text, out):
    t = time.perf_counter()
    parse(text)
    out.put(time.perf_counter() - t)

LIMIT = 16_000
NASTY = [
    "1" * 40 + (" " + "1" * 40) * 4 + "!",
    ("1a " * 6000),
    "1," * 8000,
    "1/" * 8000,
    "x " * 8000 + "\n",
    "a ➡️ " * 3000,
    "[spoiler " * 2000 + "\n",
    " " * 15000 + "<This message was edited>x",
    "#1 " * 5000,
    "🟩" * 8000,
    "Score: " + "1" * 15000 + "x",
    "\n".join(["word #1 " + "9" * 50] * 200),
    "https://" + "a." * 7000 + "/",
]


@pytest.mark.parametrize("text", NASTY, ids=range(len(NASTY)))
def test_no_paste_takes_long(text):
    out = mp.Queue()
    p = mp.Process(target=_timed, args=(text[:LIMIT], out))
    p.start()
    p.join(5)  # a runaway pattern is killed, not waited for
    if p.is_alive():
        p.kill()
        pytest.fail("parsing took over 5 s")
    assert out.get(timeout=1) < 1.0
