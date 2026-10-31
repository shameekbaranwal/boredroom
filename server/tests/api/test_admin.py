import pytest

from boredroom.admin import forget
from boredroom.errors import ApiError
from boredroom.models import Board, Membership, Person, Result

WIKI = "Seawater ➡️ Babe Ruth ⏰ 02:09 🦶5 🔗 https://www.thewikigamedaily.com"


def test_forget_takes_everything_and_passes_the_chair(db, seat):
    a, b = seat("ivan"), seat("judy")
    code = a.post("/boards", {"name": "soup"}).json["invite"]["code"]
    a.post("/boards", {"name": "solo"})
    b.post("/boards/join", {"code": code})
    a.post("/pastes", {"text": WIKI})
    b.post("/pastes", {"text": WIKI})

    f = forget(db, "ivan")
    db.commit()
    assert (f.results, f.pastes, f.boards_deleted, f.chairs_passed) == (1, 1, ["solo"], ["soup → judy"])
    assert db.query(Person).filter_by(username="ivan").first() is None
    assert [x.slug for x in db.query(Board)] == ["soup"]
    assert db.query(Membership).one().role == "chair"
    assert db.query(Result).count() == 1  # judy's stays
    assert a.get("/me").status_code == 401  # their tokens went too
    with pytest.raises(ApiError):
        forget(db, "ivan")
