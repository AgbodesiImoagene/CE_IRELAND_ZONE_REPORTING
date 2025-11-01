# OAuth SSO Setup Guide

## Overview

The application supports OAuth 2.0 authentication via Google and Facebook. Users can sign in with their social accounts and will still be required to complete 2FA after OAuth authentication.

## Endpoints

- `GET /api/v1/auth/oauth/{provider}/start` - Initiate OAuth flow (redirects to provider)
- `GET /api/v1/auth/oauth/{provider}/callback` - Handle OAuth callback

Where `{provider}` is either `google` or `facebook`.

## Configuration

Add the following environment variables to your `.env` file:

```env
# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Facebook OAuth
FACEBOOK_CLIENT_ID=your-facebook-app-id
FACEBOOK_CLIENT_SECRET=your-facebook-app-secret

# OAuth redirect base URL (must match provider callback URLs)
OAUTH_REDIRECT_BASE_URL=https://your-domain.com/api/v1/auth/oauth
```

## Setting up Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Configure OAuth consent screen
6. Set authorized redirect URIs:
   - `https://your-domain.com/api/v1/auth/oauth/google/callback`
   - `http://localhost:8000/api/v1/auth/oauth/google/callback` (for dev)
7. Copy Client ID and Client Secret to `.env`

## Setting up Facebook OAuth

1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Create a new app
3. Add "Facebook Login" product
4. Configure OAuth Redirect URIs:
   - `https://your-domain.com/api/v1/auth/oauth/facebook/callback`
   - `http://localhost:8000/api/v1/auth/oauth/facebook/callback` (for dev)
5. Copy App ID and App Secret to `.env`

## Flow

1. User clicks "Sign in with Google/Facebook"
2. Frontend redirects to `/api/v1/auth/oauth/{provider}/start`
3. Backend redirects to provider's OAuth consent page
4. User authorizes app
5. Provider redirects to `/api/v1/auth/oauth/{provider}/callback?code=...`
6. Backend exchanges code for access token
7. Backend fetches user info (email, ID)
8. Backend links identity to existing user (by email) OR creates new user
9. Backend returns `{"requires_2fa": true, "user_id": "..."}`
10. Frontend proceeds with 2FA flow (same as email/password login)

## Identity Linking

- If a user with the same email already exists, the OAuth identity is linked to that user
- If no user exists and email is provided, a new user is created (password_hash = None)
- SSO users still must complete 2FA before receiving access tokens

## Security Notes

- State parameter should be properly validated in production (currently simplified)
- Use HTTPS in production
- Store OAuth secrets securely (use secrets manager in production)
- Implement CSRF protection for OAuth flows

