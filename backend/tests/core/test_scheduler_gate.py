"""A standby must never start the background write loops (issue #346)."""

from unittest.mock import patch

import pytest

from app.api.routes import aaa_statistics
from app.main import _scheduler_enabled
from app.models import HaConfig


def _cfg(scheduler_enabled: bool) -> HaConfig:
    return HaConfig(id=1, node_name="primary", scheduler_enabled=scheduler_enabled)


def test_standby_ignores_replicated_scheduler_flag() -> None:
    # On a standby the HaConfig row is the primary's, so it says True here.
    with patch("app.main.settings.NODE_ROLE", "standby"):
        assert _scheduler_enabled(_cfg(True)) is False
        assert _scheduler_enabled(None) is False


@pytest.mark.parametrize("flag", [True, False])
def test_primary_follows_db_flag(flag: bool) -> None:
    with patch("app.main.settings.NODE_ROLE", "primary"):
        assert _scheduler_enabled(_cfg(flag)) is flag


def test_primary_without_row_falls_back_to_env() -> None:
    with (
        patch("app.main.settings.NODE_ROLE", "primary"),
        patch("app.main.settings.SCHEDULER_ENABLED", False),
    ):
        assert _scheduler_enabled(None) is False


def test_standby_does_not_collect_from_peers() -> None:
    with (
        patch.object(aaa_statistics.settings, "NODE_ROLE", "standby"),
        patch.object(
            aaa_statistics.settings, "PEER_BACKEND_URL", "http://primary:8000"
        ),
        patch.object(aaa_statistics.settings, "INTERNAL_SYNC_TOKEN", "token"),
        patch.object(aaa_statistics.httpx, "Client") as client,
    ):
        assert aaa_statistics._collect_from_peers("2026-11-04") == {}
        client.assert_not_called()
