"""
Configuration management for the Automated SEO Article Generator.

This module loads and validates environment variables using python-dotenv.
It provides a centralized configuration class that fails fast with clear
error messages if required variables are missing.

Usage:
    from config import Config
    
    config = Config()
    print(config.wordpress_url)
    print(config.anthropic_api_key)
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv


class ConfigurationError(Exception):
    """Raised when required configuration is missing or invalid."""
    pass


@dataclass
class Config:
    """
    Configuration container for the SEO Article Generator.
    
    Loads environment variables on initialization and validates that all
    required variables are present. Raises ConfigurationError with clear
    messages if validation fails.
    
    Attributes:
        wordpress_url: The target WordPress site URL
        wordpress_username: WordPress admin username
        wordpress_app_password: WordPress Application Password for API auth
        anthropic_api_key: Claude API key for content generation
        openai_api_key: Optional OpenAI API key (fallback LLM)
        tavily_api_key: Tavily API key for web research
        log_level: Logging level (default: INFO)
        dry_run: If True, generates content but doesn't publish
    """
    
    # WordPress settings
    wordpress_url: str = field(default="")
    wordpress_username: str = field(default="")
    wordpress_app_password: str = field(default="")
    
    # AI/LLM settings
    anthropic_api_key: str = field(default="")
    openai_api_key: Optional[str] = field(default=None)
    
    # Research settings
    tavily_api_key: str = field(default="")
    
    # Optional settings
    log_level: str = field(default="INFO")
    dry_run: bool = field(default=False)
    
    def __post_init__(self):
        """Load and validate configuration after initialization."""
        self._load_env()
        self._validate()
    
    def _load_env(self) -> None:
        """Load environment variables from .env file."""
        # Load .env file if it exists (won't override existing env vars)
        load_dotenv()
        
        # WordPress settings (required)
        self.wordpress_url = os.getenv("WORDPRESS_URL", "").strip()
        self.wordpress_username = os.getenv("WORDPRESS_USERNAME", "").strip()
        self.wordpress_app_password = os.getenv("WORDPRESS_APP_PASSWORD", "").strip()
        
        # AI/LLM settings
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip() or None
        
        # Research settings (required)
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "").strip()
        
        # Optional settings
        self.log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        self.dry_run = os.getenv("DRY_RUN", "false").strip().lower() in ("true", "1", "yes")
    
    def _validate(self) -> None:
        """
        Validate that all required configuration variables are present.
        
        Raises:
            ConfigurationError: If any required variables are missing.
        """
        missing_vars = []
        
        # Check required WordPress settings
        if not self.wordpress_url:
            missing_vars.append("WORDPRESS_URL")
        if not self.wordpress_username:
            missing_vars.append("WORDPRESS_USERNAME")
        if not self.wordpress_app_password:
            missing_vars.append("WORDPRESS_APP_PASSWORD")
        
        # Check required AI settings
        if not self.anthropic_api_key:
            missing_vars.append("ANTHROPIC_API_KEY")
        
        # Check required research settings
        if not self.tavily_api_key:
            missing_vars.append("TAVILY_API_KEY")
        
        # If any required variables are missing, raise an error
        if missing_vars:
            error_message = self._format_missing_vars_error(missing_vars)
            raise ConfigurationError(error_message)
        
        # Validate URL format
        if not self.wordpress_url.startswith(("http://", "https://")):
            raise ConfigurationError(
                f"WORDPRESS_URL must start with http:// or https://\n"
                f"  Current value: {self.wordpress_url}\n"
                f"  Expected format: https://example.com"
            )
        
        # Validate log level
        valid_log_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if self.log_level not in valid_log_levels:
            raise ConfigurationError(
                f"LOG_LEVEL must be one of: {', '.join(valid_log_levels)}\n"
                f"  Current value: {self.log_level}"
            )
    
    def _format_missing_vars_error(self, missing_vars: list[str]) -> str:
        """Format a helpful error message for missing variables."""
        lines = [
            "Missing required environment variables:",
            "",
        ]
        
        for var in missing_vars:
            hint = self._get_hint_for_var(var)
            lines.append(f"  • {var}")
            if hint:
                lines.append(f"    └─ {hint}")
        
        lines.extend([
            "",
            "Setup instructions:",
            "  1. Copy .env.example to .env: cp .env.example .env",
            "  2. Edit .env and fill in your values",
            "  3. See README.md for detailed instructions on obtaining API keys",
        ])
        
        return "\n".join(lines)
    
    def _get_hint_for_var(self, var: str) -> str:
        """Get a helpful hint for a missing variable."""
        hints = {
            "WORDPRESS_URL": "The URL of your WordPress site (e.g., https://naturaparga.com)",
            "WORDPRESS_USERNAME": "Your WordPress admin username",
            "WORDPRESS_APP_PASSWORD": "WordPress Application Password (Users → Profile → Application Passwords)",
            "ANTHROPIC_API_KEY": "Get your key at https://console.anthropic.com/settings/keys",
            "TAVILY_API_KEY": "Get your key at https://tavily.com (free tier available)",
        }
        return hints.get(var, "")
    
    @property
    def has_openai(self) -> bool:
        """Check if OpenAI API key is configured."""
        return self.openai_api_key is not None
    
    def __repr__(self) -> str:
        """Return a safe string representation (hides sensitive values)."""
        return (
            f"Config("
            f"wordpress_url='{self.wordpress_url}', "
            f"wordpress_username='{self.wordpress_username}', "
            f"wordpress_app_password='***', "
            f"anthropic_api_key='***', "
            f"openai_api_key={'***' if self.openai_api_key else 'None'}, "
            f"tavily_api_key='***', "
            f"log_level='{self.log_level}', "
            f"dry_run={self.dry_run})"
        )


def get_config() -> Config:
    """
    Factory function to get a validated Config instance.
    
    Returns:
        Config: A validated configuration instance.
        
    Raises:
        ConfigurationError: If required configuration is missing.
    """
    return Config()


# Module-level convenience: validate config when imported with --check flag
if __name__ == "__main__":
    try:
        config = get_config()
        print("✅ Configuration loaded successfully!")
        print(f"\nConfiguration summary:")
        print(f"  WordPress URL: {config.wordpress_url}")
        print(f"  WordPress User: {config.wordpress_username}")
        print(f"  Anthropic API Key: {'✓ Configured' if config.anthropic_api_key else '✗ Missing'}")
        print(f"  OpenAI API Key: {'✓ Configured' if config.has_openai else '○ Not configured (optional)'}")
        print(f"  Tavily API Key: {'✓ Configured' if config.tavily_api_key else '✗ Missing'}")
        print(f"  Log Level: {config.log_level}")
        print(f"  Dry Run: {config.dry_run}")
    except ConfigurationError as e:
        print(f"❌ Configuration Error:\n\n{e}", file=sys.stderr)
        sys.exit(1)
