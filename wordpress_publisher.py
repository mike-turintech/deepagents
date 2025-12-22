"""
WordPress Publishing Module for the Automated SEO Article Generator.

This module handles publishing articles to WordPress via the REST API using
Application Password authentication. It provides a clean interface for creating
posts with proper error handling and retry logic.

Usage:
    from wordpress_publisher import WordPressPublisher
    
    publisher = WordPressPublisher(
        site_url="https://naturaparga.com",
        username="admin",
        app_password="xxxx xxxx xxxx xxxx"
    )
    
    result = publisher.publish_post(
        title="My Article",
        content="<p>Article content here...</p>",
        excerpt="A brief summary of the article."
    )
    print(f"Published: {result['url']}")

API Endpoint: POST {site_url}/wp-json/wp/v2/posts
Authentication: Basic Auth with Application Password
"""

import base64
import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests


# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================
# Custom Exceptions
# ============================================================

class WordPressError(Exception):
    """Base exception for WordPress API errors."""
    pass


class WordPressAuthenticationError(WordPressError):
    """Raised when authentication fails (401 Unauthorized)."""
    
    def __init__(self, message: str = None):
        default_message = (
            "Authentication failed. Please check your credentials:\n"
            "  1. Verify WORDPRESS_USERNAME is correct\n"
            "  2. Ensure WORDPRESS_APP_PASSWORD is an Application Password,\n"
            "     not your regular login password\n"
            "  3. Generate a new Application Password at:\n"
            "     WordPress Admin → Users → Profile → Application Passwords"
        )
        super().__init__(message or default_message)


class WordPressPermissionError(WordPressError):
    """Raised when user lacks required permissions (403 Forbidden)."""
    
    def __init__(self, message: str = None):
        default_message = (
            "Permission denied. Your WordPress user does not have permission to publish posts.\n"
            "  1. Ensure the user has 'Author' role or higher\n"
            "  2. Check if Application Passwords are enabled on your site\n"
            "  3. Verify no security plugin is blocking REST API access"
        )
        super().__init__(message or default_message)


class WordPressRateLimitError(WordPressError):
    """Raised when rate limited by WordPress (429 Too Many Requests)."""
    
    def __init__(self, retry_after: int = None):
        message = "Rate limited by WordPress. Too many requests."
        if retry_after:
            message += f" Try again in {retry_after} seconds."
        super().__init__(message)
        self.retry_after = retry_after


class WordPressServerError(WordPressError):
    """Raised for server-side errors (5xx responses)."""
    
    def __init__(self, status_code: int, message: str = None):
        default_message = f"WordPress server error (HTTP {status_code}). The server may be temporarily unavailable."
        super().__init__(message or default_message)
        self.status_code = status_code


class WordPressConnectionError(WordPressError):
    """Raised when unable to connect to WordPress site."""
    
    def __init__(self, original_error: Exception = None):
        message = "Unable to connect to WordPress site. Please check:\n"
        message += "  1. The WORDPRESS_URL is correct and accessible\n"
        message += "  2. Your internet connection is working\n"
        message += "  3. The site is not blocking your IP"
        if original_error:
            message += f"\n\nOriginal error: {original_error}"
        super().__init__(message)


# ============================================================
# Data Classes
# ============================================================

@dataclass
class PublishResult:
    """Result from a successful publish operation."""
    post_id: int
    url: str
    status: str
    title: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for easy serialization."""
        return {
            "post_id": self.post_id,
            "url": self.url,
            "status": self.status,
            "title": self.title,
        }


# ============================================================
# WordPress Publisher Class
# ============================================================

class WordPressPublisher:
    """
    Client for publishing articles to WordPress via REST API.
    
    Uses Basic Authentication with Application Passwords for secure API access.
    Includes automatic retry logic for transient failures.
    
    Attributes:
        site_url: The WordPress site URL (e.g., "https://naturaparga.com")
        username: WordPress username
        max_retries: Maximum retry attempts for transient failures (default: 3)
        base_delay: Initial delay in seconds for exponential backoff (default: 1.0)
    """
    
    # API endpoint path for posts
    POSTS_ENDPOINT = "/wp-json/wp/v2/posts"
    
    def __init__(
        self,
        site_url: str,
        username: str,
        app_password: str,
        max_retries: int = 3,
        base_delay: float = 1.0,
        timeout: int = 30,
    ):
        """
        Initialize the WordPress publisher.
        
        Args:
            site_url: WordPress site URL (e.g., "https://naturaparga.com")
            username: WordPress username for authentication
            app_password: WordPress Application Password (NOT regular password)
            max_retries: Maximum retry attempts for transient failures
            base_delay: Initial delay in seconds for exponential backoff
            timeout: Request timeout in seconds
        """
        # Normalize URL (remove trailing slash)
        self.site_url = site_url.rstrip("/")
        self.username = username
        self._app_password = app_password
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.timeout = timeout
        
        # Build the API endpoint URL
        self._posts_url = f"{self.site_url}{self.POSTS_ENDPOINT}"
        
        # Build auth header
        self._auth_header = self._build_auth_header(username, app_password)
        
        # Standard headers for requests
        self._headers = {
            "Authorization": self._auth_header,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        
        logger.debug(f"Initialized WordPressPublisher for {self.site_url}")
    
    def _build_auth_header(self, username: str, app_password: str) -> str:
        """
        Build the Basic Auth header value.
        
        WordPress Application Passwords use Basic Authentication with the format:
        Authorization: Basic base64(username:app_password)
        
        Args:
            username: WordPress username
            app_password: WordPress Application Password
            
        Returns:
            The full Authorization header value
        """
        # Combine credentials in username:password format
        credentials = f"{username}:{app_password}"
        
        # Encode to base64
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("utf-8")
        
        return f"Basic {encoded}"
    
    def publish_post(
        self,
        title: str,
        content: str,
        excerpt: str,
        status: str = "publish",
        categories: Optional[list[int]] = None,
        tags: Optional[list[int]] = None,
    ) -> PublishResult:
        """
        Publish a post to WordPress.
        
        Args:
            title: The post title
            content: The post content (HTML)
            excerpt: Meta description/summary for the post
            status: Post status - 'publish' for live, 'draft' for testing
            categories: Optional list of category IDs
            tags: Optional list of tag IDs
            
        Returns:
            PublishResult with post_id, url, status, and title
            
        Raises:
            WordPressAuthenticationError: Invalid credentials (401)
            WordPressPermissionError: User lacks permissions (403)
            WordPressRateLimitError: Rate limited (429)
            WordPressServerError: Server error (5xx)
            WordPressConnectionError: Unable to connect
            WordPressError: Other API errors
        """
        # Build post data
        post_data = {
            "title": title,
            "content": content,
            "excerpt": excerpt,
            "status": status,
        }
        
        # Add optional fields if provided
        if categories:
            post_data["categories"] = categories
        if tags:
            post_data["tags"] = tags
        
        logger.info(f"Publishing post: '{title}' (status: {status})")
        logger.debug(f"Post data: {post_data}")
        
        # Execute with retry logic
        response = self._request_with_retry("POST", self._posts_url, json=post_data)
        
        # Parse successful response
        result = PublishResult(
            post_id=response["id"],
            url=response["link"],
            status=response["status"],
            title=response["title"]["rendered"] if isinstance(response["title"], dict) else title,
        )
        
        logger.info(f"Successfully published post ID {result.post_id}: {result.url}")
        return result
    
    def create_draft(
        self,
        title: str,
        content: str,
        excerpt: str,
    ) -> PublishResult:
        """
        Create a draft post (convenience method for testing).
        
        This is useful for testing the connection and credentials without
        actually publishing a live post.
        
        Args:
            title: The post title
            content: The post content (HTML)
            excerpt: Meta description/summary for the post
            
        Returns:
            PublishResult with post_id, url, status, and title
        """
        return self.publish_post(
            title=title,
            content=content,
            excerpt=excerpt,
            status="draft",
        )
    
    def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> dict:
        """
        Execute an HTTP request with retry logic for transient failures.
        
        Implements exponential backoff for:
        - 429 Too Many Requests
        - 5xx Server Errors
        - Connection timeouts
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments passed to requests
            
        Returns:
            Parsed JSON response data
            
        Raises:
            WordPressError subclass based on response status
        """
        last_exception = None
        
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"Request attempt {attempt}/{self.max_retries}: {method} {url}")
                
                response = requests.request(
                    method,
                    url,
                    headers=self._headers,
                    timeout=self.timeout,
                    **kwargs,
                )
                
                # Handle response based on status code
                return self._handle_response(response)
                
            except (WordPressRateLimitError, WordPressServerError) as e:
                # Transient errors - retry with backoff
                last_exception = e
                
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff
                    if isinstance(e, WordPressRateLimitError) and e.retry_after:
                        delay = e.retry_after
                    else:
                        delay = self.base_delay * (2 ** (attempt - 1))
                    
                    logger.warning(
                        f"Transient error on attempt {attempt}/{self.max_retries}. "
                        f"Retrying in {delay:.1f}s... Error: {e}"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} attempts failed. Last error: {e}")
                    raise
                    
            except requests.exceptions.Timeout:
                # Timeout - retry with backoff
                last_exception = WordPressConnectionError(
                    Exception(f"Request timed out after {self.timeout}s")
                )
                
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        f"Request timeout on attempt {attempt}/{self.max_retries}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries} attempts timed out.")
                    raise last_exception
                    
            except requests.exceptions.ConnectionError as e:
                # Connection error - don't retry, fail immediately
                logger.error(f"Connection failed: {e}")
                raise WordPressConnectionError(e)
                
            except requests.exceptions.RequestException as e:
                # Other request errors - fail immediately
                logger.error(f"Request failed: {e}")
                raise WordPressError(f"Request failed: {e}")
        
        # Should not reach here, but just in case
        if last_exception:
            raise last_exception
        raise WordPressError("Unknown error during request")
    
    def _handle_response(self, response: requests.Response) -> dict:
        """
        Handle the API response and raise appropriate exceptions.
        
        Args:
            response: The requests Response object
            
        Returns:
            Parsed JSON response data for successful requests
            
        Raises:
            WordPressError subclass based on response status
        """
        status_code = response.status_code
        
        logger.debug(f"Response status: {status_code}")
        
        # Success - 201 Created for new posts
        if status_code == 201:
            return response.json()
        
        # Also handle 200 OK (some operations return this)
        if status_code == 200:
            return response.json()
        
        # Authentication failed
        if status_code == 401:
            logger.error("Authentication failed (401 Unauthorized)")
            raise WordPressAuthenticationError()
        
        # Permission denied
        if status_code == 403:
            logger.error("Permission denied (403 Forbidden)")
            raise WordPressPermissionError()
        
        # Rate limited
        if status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after and retry_after.isdigit() else None
            logger.warning(f"Rate limited (429). Retry-After: {retry_after}")
            raise WordPressRateLimitError(retry_seconds)
        
        # Server errors
        if 500 <= status_code < 600:
            logger.error(f"Server error ({status_code})")
            raise WordPressServerError(status_code)
        
        # Other errors - try to extract message from response
        try:
            error_data = response.json()
            message = error_data.get("message", f"Unknown error (HTTP {status_code})")
            code = error_data.get("code", "unknown")
            logger.error(f"WordPress API error: {code} - {message}")
            raise WordPressError(f"WordPress API error ({code}): {message}")
        except ValueError:
            raise WordPressError(f"WordPress API error (HTTP {status_code}): {response.text[:200]}")


# ============================================================
# Utility Functions
# ============================================================

def test_credentials(
    site_url: str,
    username: str,
    app_password: str,
    delete_after: bool = True,
) -> bool:
    """
    Test WordPress credentials by creating (and optionally deleting) a draft post.
    
    This is useful for verifying that the Application Password is set up correctly
    before attempting to publish real content.
    
    Args:
        site_url: WordPress site URL
        username: WordPress username
        app_password: WordPress Application Password
        delete_after: If True, delete the test post after creation
        
    Returns:
        True if credentials are valid and working
        
    Raises:
        WordPressAuthenticationError: Invalid credentials
        WordPressPermissionError: User lacks permissions
        WordPressConnectionError: Unable to connect to site
    """
    logger.info("Testing WordPress credentials...")
    
    publisher = WordPressPublisher(
        site_url=site_url,
        username=username,
        app_password=app_password,
    )
    
    # Create a test draft post
    test_title = "[Test] SEO Generator Credential Verification"
    test_content = "<p>This is a test post created to verify API credentials. It can be safely deleted.</p>"
    test_excerpt = "Test post for API credential verification."
    
    try:
        result = publisher.create_draft(
            title=test_title,
            content=test_content,
            excerpt=test_excerpt,
        )
        
        logger.info(f"✅ Credentials verified! Test post created with ID: {result.post_id}")
        
        # Optionally delete the test post
        if delete_after:
            try:
                delete_url = f"{publisher._posts_url}/{result.post_id}?force=true"
                response = requests.delete(
                    delete_url,
                    headers=publisher._headers,
                    timeout=publisher.timeout,
                )
                if response.status_code in (200, 204):
                    logger.info(f"Test post {result.post_id} deleted successfully")
                else:
                    logger.warning(f"Could not delete test post: {response.status_code}")
            except Exception as e:
                logger.warning(f"Could not delete test post: {e}")
        else:
            logger.info(f"Test post left as draft: {result.url}")
        
        return True
        
    except (WordPressAuthenticationError, WordPressPermissionError):
        # Re-raise authentication/permission errors
        raise
    except Exception as e:
        logger.error(f"Credential test failed: {e}")
        raise


# ============================================================
# CLI Interface
# ============================================================

if __name__ == "__main__":
    import sys
    
    # Configure logging for CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    
    # Try to load config from environment
    try:
        from config import Config, ConfigurationError
        
        config = Config()
        
        print("Testing WordPress credentials...")
        print(f"  Site: {config.wordpress_url}")
        print(f"  User: {config.wordpress_username}")
        print()
        
        success = test_credentials(
            site_url=config.wordpress_url,
            username=config.wordpress_username,
            app_password=config.wordpress_app_password,
            delete_after=True,
        )
        
        if success:
            print("\n✅ WordPress credentials are valid and working!")
            print("   You can now use the publisher to create posts.")
            sys.exit(0)
            
    except ImportError:
        print("Error: Could not import config module.", file=sys.stderr)
        print("Make sure config.py exists and python-dotenv is installed.", file=sys.stderr)
        sys.exit(1)
        
    except ConfigurationError as e:
        print(f"Configuration Error:\n{e}", file=sys.stderr)
        sys.exit(1)
        
    except WordPressAuthenticationError as e:
        print(f"\n❌ Authentication Failed:\n{e}", file=sys.stderr)
        sys.exit(1)
        
    except WordPressPermissionError as e:
        print(f"\n❌ Permission Denied:\n{e}", file=sys.stderr)
        sys.exit(1)
        
    except WordPressConnectionError as e:
        print(f"\n❌ Connection Failed:\n{e}", file=sys.stderr)
        sys.exit(1)
        
    except WordPressError as e:
        print(f"\n❌ WordPress Error: {e}", file=sys.stderr)
        sys.exit(1)
