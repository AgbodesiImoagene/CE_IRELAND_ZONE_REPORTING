"""Tests for request information extraction utilities."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import Request

from app.common.request_info import (
    get_request_ip,
    get_request_user_agent,
    get_request_info,
)


class TestGetRequestIP:
    """Test IP address extraction from requests."""

    def test_get_request_ip_from_x_forwarded_for(self):
        """Test extracting IP from X-Forwarded-For header."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        mock_request.client = None

        ip = get_request_ip(mock_request)

        assert ip == "192.168.1.1"

    def test_get_request_ip_from_x_forwarded_for_single(self):
        """Test extracting IP from X-Forwarded-For with single IP."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"X-Forwarded-For": "192.168.1.1"}
        mock_request.client = None

        ip = get_request_ip(mock_request)

        assert ip == "192.168.1.1"

    def test_get_request_ip_from_x_forwarded_for_with_whitespace(self):
        """Test extracting IP from X-Forwarded-For with whitespace."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"X-Forwarded-For": "  192.168.1.1  ,  10.0.0.1  "}
        mock_request.client = None

        ip = get_request_ip(mock_request)

        assert ip == "192.168.1.1"

    def test_get_request_ip_from_client_host(self):
        """Test extracting IP from client.host when no X-Forwarded-For."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_client = Mock()
        mock_client.host = "192.168.1.100"
        mock_request.client = mock_client

        ip = get_request_ip(mock_request)

        assert ip == "192.168.1.100"

    def test_get_request_ip_no_client(self):
        """Test extracting IP when client is None."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = None

        ip = get_request_ip(mock_request)

        assert ip is None

    def test_get_request_ip_x_forwarded_for_takes_precedence(self):
        """Test that X-Forwarded-For takes precedence over client.host."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1"}
        mock_client = Mock()
        mock_client.host = "192.168.1.100"
        mock_request.client = mock_client

        ip = get_request_ip(mock_request)

        assert ip == "10.0.0.1"


class TestGetRequestUserAgent:
    """Test user agent extraction from requests."""

    def test_get_request_user_agent_exists(self):
        """Test extracting user agent when header exists."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        user_agent = get_request_user_agent(mock_request)

        assert user_agent == "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

    def test_get_request_user_agent_missing(self):
        """Test extracting user agent when header is missing."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}

        user_agent = get_request_user_agent(mock_request)

        assert user_agent is None

    def test_get_request_user_agent_empty_string(self):
        """Test extracting user agent when header is empty string."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"User-Agent": ""}

        user_agent = get_request_user_agent(mock_request)

        assert user_agent == ""


class TestGetRequestInfo:
    """Test combined request info extraction."""

    @pytest.mark.asyncio
    async def test_get_request_info_with_all_data(self):
        """Test extracting both IP and user agent."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "X-Forwarded-For": "192.168.1.1",
            "User-Agent": "Mozilla/5.0",
        }
        mock_request.client = None

        ip, user_agent = await get_request_info(mock_request)

        assert ip == "192.168.1.1"
        assert user_agent == "Mozilla/5.0"

    @pytest.mark.asyncio
    async def test_get_request_info_missing_data(self):
        """Test extracting info when data is missing."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = None

        ip, user_agent = await get_request_info(mock_request)

        assert ip is None
        assert user_agent is None

    @pytest.mark.asyncio
    async def test_get_request_info_from_client(self):
        """Test extracting info using client.host."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {"User-Agent": "Mozilla/5.0"}
        mock_client = Mock()
        mock_client.host = "192.168.1.100"
        mock_request.client = mock_client

        ip, user_agent = await get_request_info(mock_request)

        assert ip == "192.168.1.100"
        assert user_agent == "Mozilla/5.0"

