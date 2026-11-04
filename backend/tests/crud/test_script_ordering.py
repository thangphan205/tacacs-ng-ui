"""Profile/ruleset scripts and rulesets are emitted in an explicit, editable order.

tac_plus-ng stops at the first matching permit/deny, so this order decides which
privilege level a user gets (issue #339).
"""

import uuid
from collections.abc import Generator

import pytest
from sqlmodel import Session, select

from app.crud import profilescripts, rulesets, rulesetscripts
from app.crud.ordering import chain_errors
from app.crud.profiles import profile_generator
from app.crud.rulesets import ruleset_generator
from app.models import (
    Profile,
    ProfileScript,
    ProfileScriptCreate,
    ProfileScriptSet,
    ProfileScriptUpdate,
    Ruleset,
    RulesetCreate,
    RulesetScript,
    RulesetScriptCreate,
)


def _tag() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def profile(db: Session) -> Generator[Profile, None, None]:
    row = Profile(name=f"order-{_tag()}", action="deny")
    db.add(row)
    db.commit()
    db.refresh(row)
    yield row
    db.delete(row)
    db.commit()


def _add_script(
    db: Session,
    profile: Profile,
    value: str,
    *,
    condition: str = "if",
    key: str = "device",
    action: str = "permit",
    position: int | None = None,
    priv: str | None = "15",
) -> ProfileScript:
    script = profilescripts.create_profilescript(
        session=db,
        profilescript_create=ProfileScriptCreate(
            condition=condition,
            key=key,
            value=value,
            action=action,
            profile_id=profile.id,
            position=position,
        ),
    )
    if priv is not None:
        db.add(ProfileScriptSet(key="priv-lvl", value=priv, profilescript_id=script.id))
        db.commit()
    return script


def _order(db: Session, profile: Profile) -> list[str]:
    rows = db.exec(
        select(ProfileScript)
        .where(ProfileScript.profile_id == profile.id)
        .order_by(ProfileScript.position)
    ).all()
    return [r.value for r in rows]


def _block(out: str, profile: Profile) -> str:
    start = out.index(f"profile {profile.name} {{")
    return out[start : out.index("\n    }\n", start)]


def test_new_scripts_append_with_dense_positions(db: Session, profile: Profile) -> None:
    for value in ("a", "b", "c"):
        _add_script(db, profile, value)
    rows = db.exec(
        select(ProfileScript)
        .where(ProfileScript.profile_id == profile.id)
        .order_by(ProfileScript.position)
    ).all()
    assert [(r.value, r.position) for r in rows] == [("a", 0), ("b", 1), ("c", 2)]


def test_generator_follows_position_and_is_stable(
    db: Session, profile: Profile
) -> None:
    _add_script(db, profile, "dev1")
    _add_script(db, profile, "shell", key="service", priv="1")
    dev2 = _add_script(db, profile, "dev2")

    # The new device rule sits below the catch-all; move it above.
    profilescripts.move_profilescript(session=db, db_profilescript=dev2, position=1)
    assert _order(db, profile) == ["dev1", "dev2", "shell"]

    block = _block(profile_generator(session=db), profile)
    assert block.index("device==dev2") < block.index("service==shell")
    assert _block(profile_generator(session=db), profile) == block


def test_update_keeps_position(db: Session, profile: Profile) -> None:
    first = _add_script(db, profile, "a")
    _add_script(db, profile, "b")
    profilescripts.update_profilescript(
        session=db,
        db_profilescript=first,
        profilescript_in=ProfileScriptUpdate(
            condition="if",
            key="device",
            value="a2",
            action="deny",
            description="edited",
        ),
    )
    assert _order(db, profile) == ["a2", "b"]


def test_create_at_position_inserts(db: Session, profile: Profile) -> None:
    _add_script(db, profile, "a")
    _add_script(db, profile, "c")
    _add_script(db, profile, "b", position=1)
    assert _order(db, profile) == ["a", "b", "c"]


def test_delete_closes_the_gap(db: Session, profile: Profile) -> None:
    _add_script(db, profile, "a")
    middle = _add_script(db, profile, "b")
    _add_script(db, profile, "c")
    profilescripts.delete_profilescript(session=db, db_profilescript=middle)
    rows = db.exec(
        select(ProfileScript)
        .where(ProfileScript.profile_id == profile.id)
        .order_by(ProfileScript.position)
    ).all()
    assert [(r.value, r.position) for r in rows] == [("a", 0), ("c", 1)]


def test_move_refuses_to_orphan_an_else(db: Session, profile: Profile) -> None:
    _add_script(db, profile, "a")
    orphan = _add_script(db, profile, "x", condition="else")
    with pytest.raises(ValueError, match="'else'"):
        profilescripts.move_profilescript(
            session=db, db_profilescript=orphan, position=0
        )
    assert _order(db, profile) == ["a", "x"]


def test_create_at_refused_position_leaves_no_row(
    db: Session, profile: Profile
) -> None:
    _add_script(db, profile, "a")
    with pytest.raises(ValueError):
        _add_script(db, profile, "x", condition="elif", position=0, priv=None)
    assert _order(db, profile) == ["a"]


def test_chain_errors() -> None:
    assert chain_errors(["if", "elif", "else", "if", "if"]) == []
    assert len(chain_errors(["else"])) == 1
    assert len(chain_errors(["if", "else", "elif"])) == 1
    assert len(chain_errors(["if", "else", "else"])) == 1


def test_script_without_sets_is_emitted(db: Session, profile: Profile) -> None:
    _add_script(db, profile, "blocked", action="deny", priv=None)
    _add_script(db, profile, "shell", key="service", priv="1")
    block = _block(profile_generator(session=db), profile)
    assert "if (device==blocked){" in block
    assert block.index("device==blocked") < block.index("service==shell")


def test_profile_else_renders_without_test(db: Session, profile: Profile) -> None:
    _add_script(db, profile, "shell", key="service")
    _add_script(db, profile, "ignored", condition="else", priv="1")
    block = _block(profile_generator(session=db), profile)
    assert "else{" in block
    assert "else (" not in block


@pytest.fixture
def two_rulesets(db: Session) -> Generator[tuple[Ruleset, Ruleset], None, None]:
    tag = _tag()
    made = [
        rulesets.create_ruleset(
            session=db,
            ruleset_create=RulesetCreate(name=f"rs-{tag}-{n}", action="deny"),
        )
        for n in ("broad", "narrow")
    ]
    for rs in made:
        rulesetscripts.create_rulesetscript(
            session=db,
            rulesetscript_create=RulesetScriptCreate(
                condition="if",
                key="group",
                value=rs.name,
                action="permit",
                ruleset_id=rs.id,
            ),
        )
    yield made[0], made[1]
    for rs in made:
        current = db.get(Ruleset, rs.id)
        if current is not None:
            rulesets.delete_ruleset(session=db, db_ruleset=current)


def test_ruleset_order_is_editable(
    db: Session, two_rulesets: tuple[Ruleset, Ruleset]
) -> None:
    broad, narrow = two_rulesets
    out = ruleset_generator(session=db)
    assert out.index(f"rule {broad.name} ") < out.index(f"rule {narrow.name} ")

    rulesets.move_ruleset(session=db, db_ruleset=narrow, position=0)
    out = ruleset_generator(session=db)
    assert out.index(f"rule {narrow.name} ") < out.index(f"rule {broad.name} ")
    positions = sorted(r.position for r in db.exec(select(Ruleset)).all())
    assert positions == list(range(len(positions)))


def test_ruleset_script_move_and_else_chain(
    db: Session, two_rulesets: tuple[Ruleset, Ruleset]
) -> None:
    broad, _ = two_rulesets
    extra = rulesetscripts.create_rulesetscript(
        session=db,
        rulesetscript_create=RulesetScriptCreate(
            condition="else",
            key="x",
            value="y",
            action="deny",
            ruleset_id=broad.id,
        ),
    )
    with pytest.raises(ValueError):
        rulesetscripts.move_rulesetscript(
            session=db, db_rulesetscript=extra, position=0
        )
    rows = db.exec(
        select(RulesetScript)
        .where(RulesetScript.ruleset_id == broad.id)
        .order_by(RulesetScript.position)
    ).all()
    assert [r.condition for r in rows] == ["if", "else"]


# --- Review regressions ------------------------------------------------------


def test_create_at_position_checks_against_the_real_baseline(
    db: Session, profile: Profile
) -> None:
    # [if, else] is valid. An `else` inserted first must be refused even though
    # appending it would also have been invalid.
    _add_script(db, profile, "a")
    _add_script(db, profile, "b", condition="else")
    with pytest.raises(ValueError):
        _add_script(db, profile, "x", condition="else", position=0, priv=None)
    assert _order(db, profile) == ["a", "b"]


def test_plain_create_cannot_open_with_else(db: Session, profile: Profile) -> None:
    with pytest.raises(ValueError, match="'else'"):
        _add_script(db, profile, "x", condition="else", priv=None)
    assert _order(db, profile) == []


def test_edit_cannot_break_the_chain(db: Session, profile: Profile) -> None:
    first = _add_script(db, profile, "a")
    _add_script(db, profile, "b", condition="elif")
    with pytest.raises(ValueError):
        profilescripts.update_profilescript(
            session=db,
            db_profilescript=first,
            profilescript_in=ProfileScriptUpdate(
                condition="else", key="device", value="a", action="permit"
            ),
        )
    db.refresh(first)
    assert first.condition == "if"


def test_delete_cannot_orphan_an_elif(db: Session, profile: Profile) -> None:
    head = _add_script(db, profile, "a")
    _add_script(db, profile, "b", condition="elif")
    with pytest.raises(ValueError):
        profilescripts.delete_profilescript(session=db, db_profilescript=head)
    assert _order(db, profile) == ["a", "b"]


def test_moving_to_another_profile_appends_densely(
    db: Session, profile: Profile
) -> None:
    other = Profile(name=f"order-{_tag()}", action="deny")
    db.add(other)
    db.commit()
    db.refresh(other)
    try:
        for value in ("a", "b", "c", "d"):
            _add_script(db, profile, value)
        moving = db.exec(
            select(ProfileScript).where(
                ProfileScript.profile_id == profile.id, ProfileScript.value == "d"
            )
        ).one()
        profilescripts.update_profilescript(
            session=db,
            db_profilescript=moving,
            profilescript_in=ProfileScriptUpdate(
                condition="if",
                key="device",
                value="d",
                action="permit",
                profile_id=other.id,
            ),
        )
        assert moving.position == 0
        assert _order(db, profile) == ["a", "b", "c"]
        remaining = db.exec(
            select(ProfileScript).where(ProfileScript.profile_id == profile.id)
        ).all()
        assert sorted(s.position for s in remaining) == [0, 1, 2]
    finally:
        db.delete(other)
        db.commit()
