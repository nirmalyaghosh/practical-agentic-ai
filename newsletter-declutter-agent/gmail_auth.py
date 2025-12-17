"""
Gmail OAuth2 Authentication Module
Handles OAuth flow and token management for Gmail API access
"""

import os
import pickle
import time

from typing import Optional

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import (
    build,
    Resource,
)
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

from app_logger import get_logger


GMAIL_MODIFY_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
SCOPES = [GMAIL_MODIFY_SCOPE]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.pickle"

logger = get_logger("gmail_auth")


class GmailAuthenticator:
    """
    Handles Gmail OAuth2 authentication and service creation
    """

    def __init__(
            self,
            credentials_file: str = CREDENTIALS_FILE,
            token_file: str = TOKEN_FILE):
        """
        Initialize the authenticator

        Args:
            credentials_file: Path to OAuth2 credentials JSON
            from Google Cloud Console
            token_file: Path to store/load the access token
        """
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.creds: Optional[Credentials] = None
        self.error_terms = [
            "network",
            "timeout",
            "connection",
            "unreachable"
        ]

    def authenticate(self) -> Credentials:
        """
        Authenticate with Gmail API using OAuth2.

        This function handles the complete OAuth2 authentication flow:
        1. Checks for existing credentials file
        2. Loads saved credentials if available
        3. Refreshes expired tokens if possible
        4. Runs OAuth flow if no valid credentials exist

        Returns:
            Credentials object for Gmail API

        Raises:
            FileNotFoundError: If credentials.json is missing
            Exception: For other authentication errors
        """
        # Check if credentials file exists
        if not os.path.exists(self.credentials_file):
            error_msg = (
                f"Missing {self.credentials_file}\n"
                "Please follow the setup guide:\n"
                "1. Go to https://console.cloud.google.com\n"
                "2. Create a new project\n"
                "3. Enable Gmail API\n"
                "4. Create OAuth 2.0 credentials (Desktop app)\n"
                "5. Download as 'credentials.json'")
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        # Load existing token
        if os.path.exists(self.token_file):
            logger.info(f"Loading saved credentials from {self.token_file}...")
            try:
                with open(self.token_file, "rb") as token:
                    self.creds = pickle.load(token)
                logger.debug("Credentials loaded from file")
            except (pickle.UnpicklingError, EOFError) as e:
                logger.warning(f"Failed to load credentials (corrupted): {e}")
                self.creds = None

        # Check if credentials are valid
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing expired token...")

                # Try refresh token, with retry on network error
                refresh_succeeded = False
                for attempt in range(2):  # Try twice
                    try:
                        self.creds.refresh(Request())
                        logger.info("Token refreshed successfully")
                        refresh_succeeded = True
                        break

                    except RefreshError as e:
                        # Refresh expired token
                        # This is NOT retryable - need new OAuth flow
                        logger.warning(
                            f"Refresh token expired or revoked: {e}\n"
                            "This happens after long period of inactivity, "
                            "or if user revoked access."
                        )
                        logger.info("Starting new OAuth flow...")
                        self.creds = self._run_oauth_flow()
                        refresh_succeeded = True
                        break

                    except Exception as e:
                        # Distinguish network vs other errors
                        error_msg = str(e).lower()
                        is_network_error =\
                            any(term in error_msg for term in self.error_terms)

                        if is_network_error and attempt == 0:
                            # Network error during token refresh - retry once
                            logger.warning(
                                "Network error during token refresh "
                                f"(attempt {attempt + 1}/2): {e}"
                            )
                            # Brief pause before retry
                            time.sleep(2)
                            # Then
                            continue
                        else:
                            # Either not network error, or retry failed
                            error_type = "Network (retried)" \
                                if is_network_error \
                                else "Authentication/Other"
                            logger.error(
                                f"Token refresh failed: {e}\n"
                                f"Error type: {error_type}",
                                exc_info=True
                            )
                            logger.info("Starting new OAuth flow...")
                            self.creds = self._run_oauth_flow()
                            refresh_succeeded = True

                            break

                # If still unsuccesful
                if not refresh_succeeded:
                    logger.error("Token refresh failed after retries")
                    self.creds = self._run_oauth_flow()

            else:
                logger.info("No valid credentials found. "
                            "Starting OAuth flow...")
                self.creds = self._run_oauth_flow()

            # Save credentials for next run
            self._save_credentials()
        else:
            logger.info("Using valid existing credentials")

        return self.creds

    def get_gmail_service(self) -> Resource:
        """
        Get authenticated Gmail API service

        Returns:
            Gmail API service object
        """
        if not self.creds:
            self.authenticate()

        try:
            service = build("gmail", "v1", credentials=self.creds)
            logger.info("Gmail service initialized")
            return service
        except HttpError as error:
            logger.error(f"Error creating Gmail service: {error}")
            raise

    def revoke_access(self):
        """
        Revoke access and delete stored token
        """
        try:
            if os.path.exists(self.token_file):
                os.remove(self.token_file)
                logger.info(f"Deleted {self.token_file}")
                logger.info("Access revoked. "
                            "Run authenticate() again to re-authorize.")
            else:
                logger.info(f"No token file found at {self.token_file}")
        except Exception as e:
            logger.error(f"Failed to revoke access: {e}")
            raise

    def _run_oauth_flow(self) -> Credentials:
        """
        Run the OAuth2 flow to get user authorization

        Returns:
            Fresh credentials from OAuth flow
        """
        banner_lines = [
            "="*60,
            "OAUTH AUTHORIZATION REQUIRED",
            "="*60,
            "Your browser will open for Gmail authorization.",
            "Please:",
            "  1. Select your Google account",
            "  2. Review the permissions",
            "  3. Click 'Allow'",
            "="*60
        ]

        for line in banner_lines:
            logger.info(line)

        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file,
                SCOPES
            )

            # Run local server for OAuth callback
            creds = flow.run_local_server(
                port=0,  # Use random available port
                success_message="Authorization successful. "
                                "Window can be closed.",
                open_browser=True
            )

            logger.info("OAuth flow completed successfully")
            return creds
        except Exception as e:
            logger.error(f"OAuth flow failed: {e}")
            raise

    def _save_credentials(self):
        """
        Save credentials to pickle file for future use.

        Note: This is non-fatal - if saving fails, OAuth was still successful,
        user will just need to re-authenticate next time.
        """
        try:

            # Ensure directory exists
            token_dir = os.path.dirname(self.token_file)
            if token_dir:
                os.makedirs(token_dir, exist_ok=True)

            logger.info(f"Saving credentials to {self.token_file}...")
            with open(self.token_file, "wb") as token:
                pickle.dump(self.creds, token)
            logger.info("Credentials saved")
        except Exception as e:
            logger.warning(f"Failed to save credentials: {e}")
            logger.warning("Authentication succeeded, "
                           "but token won't persist. "
                           "Need to re-authenticate next time.")


def create_gmail_service() -> Resource:
    """
    Convenience function used to create an authenticated Gmail service.

    This function handles the complete authentication flow and returns
    a ready-to-use Gmail API service object.

    Returns:
        Resource: Authenticated Gmail API service object

    Raises:
        FileNotFoundError: If credentials file is missing
        Exception: For authentication errors
    """
    authenticator = GmailAuthenticator()
    return authenticator.get_gmail_service()


def test_gmail_connection(service: Resource) -> bool:
    """
    Helper function used to test if Gmail connection is working.

    Args:
        service: Gmail API service object

    Returns:
        True if connection works, False otherwise
    """

    try:
        # Try to get user profile
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress")
        total_messages = profile.get("messagesTotal")

        connection_info = [
            "="*60,
            "GMAIL CONNECTION TEST",
            "="*60,
            "Connected successfully!",
            f"Email: {email}",
            f"Total messages: {total_messages:,}",
            "="*60
        ]

        for line in connection_info:
            logger.info(line)

        return True
    except HttpError as error:
        logger.error(f"Connection test failed: {error}")
        return False


if __name__ == "__main__":
    """
    Used to test the OAuth flow
    """
    try:
        # Initialize authenticator
        auth = GmailAuthenticator()
        logger.info("Starting Gmail OAuth Test")

        # Get Gmail service
        gmail_service = auth.get_gmail_service()

        # Test connection
        if test_gmail_connection(service=gmail_service):
            logger.info("OAuth setup complete. Ready to use Gmail API.")
        else:
            logger.warning("OAuth completed but connection test failed.")

    except FileNotFoundError as e:
        # Log error using the default logger
        # since authenticator might not be created
        logger.error(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise
