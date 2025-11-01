from __future__ import annotations

from unittest.mock import AsyncMock, patch, MagicMock
from uuid import UUID

from app.auth.oauth_service import OAuthService


class TestOAuthStart:
    def test_oauth_start_google_not_configured(self, client):
        # Without Google credentials, should return 503
        response = client.get("/api/v1/oauth/google/start")
        assert response.status_code == 503

    @patch("app.auth.oauth_routes.generate_and_store_state")
    @patch("app.auth.oauth_routes.settings")
    @patch("app.auth.oauth_routes.get_oauth_client")
    def test_oauth_start_google_success(
        self, mock_get_client, mock_settings, mock_generate_state, client
    ):
        # Mock configuration
        mock_settings.google_client_id = "test-google-id"
        mock_settings.oauth_redirect_base_url = (
            "http://localhost:8000/api/v1/oauth"
        )

        # Mock state generation
        mock_generate_state.return_value = "generated_state_token"

        # Mock OAuth client
        mock_client = MagicMock()
        mock_client.create_authorization_url.return_value = (
            "https://accounts.google.com/o/oauth2/v2/auth?client_id=test",
            "generated_state_token",
        )
        mock_get_client.return_value = mock_client

        response = client.get("/api/v1/oauth/google/start", follow_redirects=False)
        # Should redirect to Google OAuth
        assert response.status_code in [302, 307]
        assert "accounts.google.com" in response.headers.get("location", "")
        # Verify state was generated and stored
        mock_generate_state.assert_called_once_with("google")

    def test_oauth_start_invalid_provider(self, client):
        response = client.get("/api/v1/oauth/invalid/start")
        assert response.status_code == 400
        assert "Unsupported provider" in response.json()["detail"]


class TestOAuthCallback:
    @patch("app.auth.oauth_routes.validate_and_consume_state")
    @patch("app.auth.oauth_routes.get_oauth_client")
    @patch("app.auth.oauth_routes.OAuthService.handle_oauth_callback")
    def test_oauth_callback_success(
        self,
        mock_handle_callback,
        mock_get_client,
        mock_validate_state,
        client,
        db,
        test_user,
    ):
        # Mock state validation (success)
        mock_validate_state.return_value = True

        # Mock OAuth client
        mock_client = AsyncMock()
        mock_token = {"access_token": "test-token"}
        mock_client.fetch_token = AsyncMock(return_value=mock_token)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "google123",
            "email": "test@example.com",
            "verified_email": True,
        }
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_get_client.return_value = mock_client

        # Mock service
        mock_handle_callback.return_value = (test_user, False)

        # Mock settings
        with patch("app.auth.oauth_routes.settings") as mock_settings:
            mock_settings.oauth_redirect_base_url = (
                "http://localhost:8000/api/v1/oauth"
            )

            response = client.get(
                "/api/v1/oauth/google/callback?code=test_code&state=test_state"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["requires_2fa"] is True
            assert UUID(data["user_id"]) == test_user.id
            # Verify state was validated
            mock_validate_state.assert_called_once_with("google", "test_state")

    def test_oauth_callback_missing_state(self, client):
        # Test missing state parameter
        response = client.get("/api/v1/oauth/google/callback?code=test_code")

        assert response.status_code == 400
        assert "Missing state parameter" in response.json()["detail"]

    @patch("app.auth.oauth_routes.validate_and_consume_state")
    def test_oauth_callback_invalid_state(self, mock_validate_state, client):
        # Mock state validation (failure)
        mock_validate_state.return_value = False

        response = client.get(
            "/api/v1/oauth/google/callback?code=test_code&state=invalid_state"
        )

        assert response.status_code == 400
        assert "Invalid or expired state parameter" in response.json()["detail"]
        mock_validate_state.assert_called_once_with("google", "invalid_state")

    @patch("app.auth.oauth_routes.validate_and_consume_state")
    @patch("app.auth.oauth_routes.get_oauth_client")
    def test_oauth_callback_no_token(
        self, mock_get_client, mock_validate_state, client
    ):
        # Mock state validation (success)
        mock_validate_state.return_value = True

        # Mock OAuth client returning no token
        mock_client = AsyncMock()
        mock_client.fetch_token = AsyncMock(return_value={})
        mock_get_client.return_value = mock_client

        with patch("app.auth.oauth_routes.settings") as mock_settings:
            mock_settings.oauth_redirect_base_url = (
                "http://localhost:8000/api/v1/oauth"
            )

            response = client.get(
                "/api/v1/oauth/google/callback?code=test_code&state=test_state"
            )

            assert response.status_code == 400
            assert "access token" in response.json()["detail"].lower()

    @patch("app.auth.oauth_routes.validate_and_consume_state")
    @patch("app.auth.oauth_routes.get_oauth_client")
    @patch("app.auth.oauth_routes.OAuthService.handle_oauth_callback")
    def test_oauth_callback_no_user_id(
        self,
        mock_handle_callback,
        mock_get_client,
        mock_validate_state,
        client,
    ):
        # Mock state validation (success)
        mock_validate_state.return_value = True

        # Mock OAuth client
        mock_client = AsyncMock()
        mock_token = {"access_token": "test-token"}
        mock_client.fetch_token = AsyncMock(return_value=mock_token)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "email": "test@example.com",
            # Missing 'id' field
        }
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        mock_get_client.return_value = mock_client

        with patch("app.auth.oauth_routes.settings") as mock_settings:
            mock_settings.oauth_redirect_base_url = (
                "http://localhost:8000/api/v1/oauth"
            )

            response = client.get(
                "/api/v1/oauth/google/callback?code=test_code&state=test_state"
            )

            assert response.status_code == 400
            assert "user ID" in response.json()["detail"]

    @patch("app.auth.oauth_routes.validate_and_consume_state")
    def test_oauth_callback_invalid_provider(self, mock_validate_state, client):
        # Mock state validation (success) so we can test provider validation
        mock_validate_state.return_value = True

        response = client.get(
            "/api/v1/oauth/invalid/callback?code=test&state=test_state"
        )
        assert response.status_code == 400
        assert "Unsupported provider" in response.json()["detail"]
        # Verify state was validated first
        mock_validate_state.assert_called_once_with("invalid", "test_state")


class TestOAuthIntegration:
    """Integration-style tests using real service methods."""

    def test_google_flow_integration(
        self, db, tenant_id, admin_user, test_role, test_org_unit
    ):
        """Test full OAuth flow with invitation-first workflow."""
        from app.users.service import UserProvisioningService

        # Simulate full OAuth flow
        provider = "google"
        provider_user_id = "google_integration_test"
        email = "integration@example.com"

        # Step 1: Create invitation first (required)
        invitation = UserProvisioningService.create_invitation(
            db=db,
            creator_id=admin_user.id,
            tenant_id=UUID(tenant_id),
            email=email,
            role_id=test_role.id,
            org_unit_id=test_org_unit.id,
            scope_type="self",
            custom_org_unit_ids=None,
            twofa_delivery="email",
        )

        # Step 2: Handle callback (user doesn't exist yet, but invitation exists)
        user, is_new = OAuthService.handle_oauth_callback(
            db, provider, provider_user_id, email, True
        )

        assert is_new is True
        assert user.email == email
        # Verify invitation was auto-activated
        db.refresh(invitation)
        assert invitation.used_at is not None

        # Step 3: Callback again (user now exists)
        user2, is_new2 = OAuthService.handle_oauth_callback(
            db, provider, provider_user_id, email, True
        )

        assert user2.id == user.id
        assert is_new2 is False

    def test_facebook_flow_integration(self, db, tenant_id, test_user):
        # Test linking Facebook to existing user
        provider = "facebook"
        provider_user_id = "fb_integration_test"

        user, is_new = OAuthService.handle_oauth_callback(
            db,
            provider,
            provider_user_id,
            "test@example.com",  # Matches test_user email
            False,
        )

        assert user.id == test_user.id
        assert is_new is False

        # Verify identity was linked
        identity = OAuthService.find_identity(db, provider, provider_user_id)
        assert identity is not None
        assert identity.user_id == test_user.id

