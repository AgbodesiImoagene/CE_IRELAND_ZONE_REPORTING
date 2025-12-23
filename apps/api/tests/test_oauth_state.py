"""Tests for OAuth state management."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.auth.oauth_state import (
    STATE_TTL_SECONDS,
    generate_and_store_state,
    get_redis_client,
    validate_and_consume_state,
)


class TestGetRedisClient:
    """Test Redis client creation."""

    @pytest.mark.asyncio
    async def test_get_redis_client_returns_instrumented(self):
        """Test that get_redis_client returns an instrumented Redis client."""
        mock_client = AsyncMock()
        mock_instrumented_client = AsyncMock()

        # aioredis.from_url is async, so we need to make the mock awaitable
        mock_from_url = AsyncMock(return_value=mock_client)

        with patch("app.auth.oauth_state.aioredis.from_url", mock_from_url):
            # Patch InstrumentedRedis where it's imported (inside the function)
            with patch(
                "app.core.redis_instrumentation.InstrumentedRedis"
            ) as mock_instrumented:
                mock_instrumented.return_value = mock_instrumented_client
                result = await get_redis_client()

                assert result == mock_instrumented_client
                mock_from_url.assert_called_once()
                mock_instrumented.assert_called_once_with(mock_client)


class TestGenerateAndStoreState:
    """Test state generation and storage."""

    @pytest.mark.asyncio
    async def test_generate_and_store_state_creates_token(self):
        """Test that generate_and_store_state creates a secure token."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("app.auth.oauth_state.get_redis_client", return_value=mock_redis):
            state = await generate_and_store_state("google")

            # Verify token is generated (should be a URL-safe string)
            assert state is not None
            assert isinstance(state, str)
            assert len(state) > 0

            # Verify Redis operations
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args
            assert "oauth:state:google:" in call_args[0][0]  # key contains provider
            assert call_args[0][1] == STATE_TTL_SECONDS  # TTL is correct
            assert call_args[0][2] == "1"  # value is "1"

            mock_redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_and_store_state_different_providers(self):
        """Test that different providers get different keys."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("app.auth.oauth_state.get_redis_client", return_value=mock_redis):
            state1 = await generate_and_store_state("google")
            state2 = await generate_and_store_state("facebook")

            # States should be different
            assert state1 != state2

            # Keys should contain provider names
            calls = mock_redis.setex.call_args_list
            assert "oauth:state:google:" in calls[0][0][0]
            assert "oauth:state:facebook:" in calls[1][0][0]

    @pytest.mark.asyncio
    async def test_generate_and_store_state_closes_redis_on_error(self):
        """Test that Redis connection is closed even on error."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))
        mock_redis.aclose = AsyncMock()

        with patch("app.auth.oauth_state.get_redis_client", return_value=mock_redis):
            with pytest.raises(Exception):
                await generate_and_store_state("google")

            # Should still close connection
            mock_redis.aclose.assert_called_once()


class TestValidateAndConsumeState:
    """Test state validation and consumption."""

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_valid(self):
        """Test validating and consuming a valid state."""
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)  # State exists
        mock_redis.delete = AsyncMock(return_value=1)  # Successfully deleted
        mock_redis.aclose = AsyncMock()

        with patch("app.auth.oauth_state.get_redis_client", return_value=mock_redis):
            result = await validate_and_consume_state("google", "test-state-token")

            assert result is True
            mock_redis.exists.assert_called_once()
            mock_redis.delete.assert_called_once()
            mock_redis.aclose.assert_called_once()

            # Verify correct key format
            exists_call = mock_redis.exists.call_args[0][0]
            assert exists_call == "oauth:state:google:test-state-token"

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_invalid(self):
        """Test validating a non-existent state."""
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=0)  # State doesn't exist
        mock_redis.aclose = AsyncMock()

        with patch("app.auth.oauth_state.get_redis_client", return_value=mock_redis):
            result = await validate_and_consume_state("google", "invalid-state")

            assert result is False
            mock_redis.exists.assert_called_once()
            mock_redis.delete.assert_not_called()  # Should not delete if doesn't exist
            mock_redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_empty_string(self):
        """Test that empty state string returns False."""
        # Empty string returns early before getting Redis client
        result = await validate_and_consume_state("google", "")

        assert result is False
        # Should return early without calling Redis

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_none(self):
        """Test that None state returns False."""
        # None/falsy value returns early before getting Redis client
        result = await validate_and_consume_state("google", None)

        assert result is False
        # Should return early without calling Redis

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_closes_redis_on_error(self):
        """Test that Redis connection is closed even on error."""
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(side_effect=Exception("Redis error"))
        mock_redis.aclose = AsyncMock()

        with patch("app.auth.oauth_state.get_redis_client", return_value=mock_redis):
            with pytest.raises(Exception):
                await validate_and_consume_state("google", "test-state")

            # Should still close connection
            mock_redis.aclose.assert_called_once()

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_deletes_on_success(self):
        """Test that state is deleted after successful validation."""
        mock_redis = AsyncMock()
        mock_redis.exists = AsyncMock(return_value=1)
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.aclose = AsyncMock()

        with patch("app.auth.oauth_state.get_redis_client", return_value=mock_redis):
            await validate_and_consume_state("facebook", "valid-state")

            # Verify delete was called with correct key
            delete_call = mock_redis.delete.call_args[0][0]
            assert delete_call == "oauth:state:facebook:valid-state"

    @pytest.mark.asyncio
    async def test_validate_and_consume_state_replay_attack_prevention(self):
        """Test that consuming a state twice fails (replay attack prevention)."""
        mock_redis = AsyncMock()
        # First call: state exists
        # Second call: state doesn't exist (already consumed)
        mock_redis.exists = AsyncMock(side_effect=[1, 0])
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.aclose = AsyncMock()

        with patch("app.auth.oauth_state.get_redis_client", return_value=mock_redis):
            # First validation should succeed
            result1 = await validate_and_consume_state("google", "test-state")
            assert result1 is True

            # Second validation should fail (state already consumed)
            result2 = await validate_and_consume_state("google", "test-state")
            assert result2 is False

