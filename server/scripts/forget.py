"""Delete people and everything that's theirs (see boredroom/admin.py).

    uv run python scripts/forget.py USERNAME [USERNAME ...] [--yes]

Without --yes it says what would go and changes nothing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from boredroom.admin import forget  # noqa: E402
from boredroom.config import Config  # noqa: E402
from boredroom.db import make_engine, make_sessionmaker  # noqa: E402
from boredroom.errors import ApiError  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("usernames", nargs="+")
    ap.add_argument("--yes", action="store_true", help="really delete")
    args = ap.parse_args()
    s = make_sessionmaker(make_engine(Config().database_url))()
    for name in args.usernames:
        try:
            f = forget(s, name)
        except ApiError as e:
            print(f"{name}: {e.description}")
            continue
        extra = "".join([f"; boards deleted: {', '.join(f.boards_deleted)}" if f.boards_deleted else "",
                         f"; chair passed: {', '.join(f.chairs_passed)}" if f.chairs_passed else ""])
        print(f"{name}: {f.results} results, {f.pastes} pastes{extra}")
    if args.yes:
        s.commit()
        print("deleted.")
    else:
        s.rollback()
        print("nothing changed (dry run). add --yes to delete.")


if __name__ == "__main__":
    main()
