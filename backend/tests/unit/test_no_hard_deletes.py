"""Static ban on hard deletes in application code and migrations (US-00.4).

RecliniQ only ever soft-deletes (US-00.2). The session guard and the ``BEFORE DELETE`` trigger
catch hard deletes at runtime; this scan catches them at review time, before any code runs.

It flags:
* calls to SQLAlchemy's ``delete()`` (``delete(...)``, ``sa.delete(...)``, ``sqlalchemy.delete``);
* ``session.delete(entity)`` and legacy ``query(...).delete()`` chains;
* string literals containing a raw ``DELETE FROM`` statement.

A flagged line is allowed only when it, or the line directly above it, carries
``# hard-delete-ok: <reason>`` (for tables in ``SOFT_DELETE_EXEMPT_TABLES``). Markers that no
longer sit next to a delete are reported too, so exemptions don't outlive their code.
"""

import ast
import re
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
SCANNED_DIRS = (BACKEND_ROOT / "app", BACKEND_ROOT / "alembic" / "versions")

MARKER = re.compile(r"#\s*hard-delete-ok:(?P<reason>.*)$")
RAW_DELETE = re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE)
SQLALCHEMY_MODULES = frozenset({"sa", "sqlalchemy"})
SESSION_NAMES = frozenset({"session", "_session", "db", "db_session"})


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def _receiver_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _delete_kind(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name) and func.id == "delete":
        return "SQLAlchemy delete()"
    if not isinstance(func, ast.Attribute) or func.attr != "delete":
        return None
    receiver = func.value
    if isinstance(receiver, ast.Name) and receiver.id in SQLALCHEMY_MODULES:
        return "SQLAlchemy delete()"
    if _receiver_name(receiver) in SESSION_NAMES:
        return "session.delete()"
    if isinstance(receiver, ast.Call):
        return "query(...).delete()"
    return None


def find_hard_deletes(source: str, path: str = "<source>") -> list[Violation]:
    lines = source.splitlines()
    markers: dict[int, str] = {}
    for number, text in enumerate(lines, start=1):
        match = MARKER.search(text)
        if match:
            markers[number] = match.group("reason").strip()

    found: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source, filename=path)):
        if isinstance(node, ast.Call):
            kind = _delete_kind(node)
            if kind:
                found.append((node.lineno, kind))
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and RAW_DELETE.search(node.value)
        ):
            found.append((node.lineno, "raw SQL DELETE"))

    violations: list[Violation] = []
    used_markers: set[int] = set()
    for line, kind in sorted(found):
        marker_line = next((n for n in (line, line - 1) if n in markers), None)
        if marker_line is None:
            violations.append(
                Violation(
                    path,
                    line,
                    f"hard delete ({kind}); soft-delete instead or mark it "
                    "`# hard-delete-ok: <reason>` for an exempt table",
                )
            )
            continue
        used_markers.add(marker_line)
        if not markers[marker_line]:
            violations.append(Violation(path, marker_line, "hard-delete-ok marker needs a reason"))

    for line in sorted(markers.keys() - used_markers):
        violations.append(Violation(path, line, "stale hard-delete-ok marker (no delete here)"))
    return violations


def scan_tree() -> list[Violation]:
    violations: list[Violation] = []
    for directory in SCANNED_DIRS:
        for file in sorted(directory.rglob("*.py")):
            relative = file.relative_to(BACKEND_ROOT).as_posix()
            violations += find_hard_deletes(file.read_text(encoding="utf-8"), relative)
    return violations


def test_codebase_has_no_unmarked_hard_deletes() -> None:
    violations = scan_tree()
    assert violations == [], "\n".join(str(v) for v in violations)


def test_flags_orm_bulk_delete() -> None:
    source = "from sqlalchemy import delete\nstmt = delete(User).where(User.id == 1)\n"
    assert [v.line for v in find_hard_deletes(source)] == [2]


def test_flags_module_qualified_delete() -> None:
    assert len(find_hard_deletes("import sqlalchemy as sa\nsa.delete(User)\n")) == 1


def test_flags_session_delete() -> None:
    source = "async def f(session):\n    await session.delete(user)\n"
    assert [v.line for v in find_hard_deletes(source)] == [2]


def test_flags_self_session_delete() -> None:
    assert len(find_hard_deletes("self._session.delete(user)\n")) == 1


def test_flags_legacy_query_delete() -> None:
    assert len(find_hard_deletes("session.query(User).filter(x).delete()\n")) == 1


def test_flags_raw_sql_delete() -> None:
    source = 'op.execute("delete from users where id = 1")\n'
    assert len(find_hard_deletes(source)) == 1


def test_marked_delete_passes_on_same_line_or_line_above() -> None:
    same_line = "delete(Counter)  # hard-delete-ok: exempt counters table\n"
    line_above = "# hard-delete-ok: exempt counters table\ndelete(Counter)\n"
    assert find_hard_deletes(same_line) == []
    assert find_hard_deletes(line_above) == []


def test_marker_without_reason_fails() -> None:
    violations = find_hard_deletes("delete(Counter)  # hard-delete-ok:\n")
    assert [v.message for v in violations] == ["hard-delete-ok marker needs a reason"]


def test_stale_marker_fails() -> None:
    violations = find_hard_deletes("# hard-delete-ok: was a purge\nx = 1\n")
    assert [v.message for v in violations] == ["stale hard-delete-ok marker (no delete here)"]


def test_soft_delete_and_unrelated_calls_pass() -> None:
    source = (
        "await repo.soft_delete(user, actor_id=None)\n"
        "cache.delete(key)\n"
        'op.execute("CREATE TRIGGER t BEFORE DELETE ON users")\n'
    )
    assert find_hard_deletes(source) == []
