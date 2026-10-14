from unittest.mock import MagicMock, patch

from src.infrastructure.config import settings
from src.infrastructure.gateway import reset_key_cache, resolve_router_key


def test_resolve_router_key_caches_database_query():
    # Ensure no explicit env key is forcing early return
    with patch.object(settings, "LLM_GATEWAY_KEY", ""):
        reset_key_cache()

        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = ("sk-cached-test-key",)
        mock_conn.cursor.return_value = mock_cur
        mock_conn.__enter__.return_value = mock_conn

        with (
            patch("os.path.exists", return_value=True),
            patch("sqlite3.connect", return_value=mock_conn) as mock_connect,
        ):
            for _ in range(10):
                key = resolve_router_key()
                assert key == "sk-cached-test-key"

            # sqlite3.connect must be called exactly once across the 10 invocations
            assert mock_connect.call_count == 1
