"""Roster integrity: correct agents present, banned agents absent, edges valid."""
from __future__ import annotations

from app.lib.agents.cards import EDGES, ROSTER

EXPECTED = {
    "maryam", "tariq", "momin", "zain", "hamza",
    "naqash", "fateh", "shams", "usman", "ihsan",
}
BANNED = {"naseer", "sohaib"}


def test_roster_exact_membership():
    assert set(ROSTER.keys()) == EXPECTED


def test_banned_agents_absent():
    for b in BANNED:
        assert b not in ROSTER
        assert all(b not in c.name.lower() for c in ROSTER.values())


def test_maryam_and_naqash_are_lead():
    assert ROSTER["maryam"].lead
    assert ROSTER["naqash"].lead


def test_hamza_is_monitor():
    assert ROSTER["hamza"].monitor


def test_edges_reference_real_agents():
    for e in EDGES:
        assert e.source in ROSTER, e.source
        assert e.target in ROSTER, e.target


def test_naqash_ihsan_direct_loop_no_momin():
    loop = [e for e in EDGES if {e.source, e.target} == {"naqash", "ihsan"}]
    assert len(loop) == 1
    assert loop[0].kind == "direct" and loop[0].bidirectional
    # Momin must not sit between Naqash and Ihsan.
    assert not any(
        {e.source, e.target} == {"momin", "ihsan"} for e in EDGES
    )
