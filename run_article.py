#!/usr/bin/env python3
"""
Main Orchestrator Script for the Automated SEO Article Generator.

This script ties together all components (topic selection, web research,
article generation, WordPress publishing) into a single automated pipeline.

Usage:
    # Generate and publish a single article
    python run_article.py
    
    # Dry run (generate but don't publish)
    python run_article.py --dry-run
    
    # Use specific topic
    python run_article.py --topic "Valtos Beach"
    
    # Verbose logging
    python run_article.py --verbose

Exit Codes:
    0: Success
    1: Configuration error
    2: Topic selection failed
    3: Web search failed
    4: Article generation failed
    5: WordPress publishing failed
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path


# ============================================================
# Exit Codes
# ============================================================

class ExitCode:
    """Exit codes for monitoring scheduled task success/failure."""
    SUCCESS = 0
    CONFIG_ERROR = 1
    TOPIC_ERROR = 2
    RESEARCH_ERROR = 3
    GENERATION_ERROR = 4
    PUBLISHING_ERROR = 5


# ============================================================
# Logging Setup
# ============================================================

def setup_logging(verbose: bool = False) -> logging.Logger:
    """
    Configure logging to both file and console.
    
    Args:
        verbose: If True, enable DEBUG level logging.
        
    Returns:
        Configured logger instance.
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    log_file = logs_dir / "article_generator.log"
    
    # Set log level
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Create formatter
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_formatter = logging.Formatter(
        "%(levelname)s: %(message)s"
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    root_logger.handlers.clear()
    
    # File handler - always logs everything
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Console handler - respects verbose setting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Get logger for this module
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_file.absolute()}")
    
    return logger


# ============================================================
# CLI Argument Parsing
# ============================================================

def parse_args() -> argparse.Namespace:
    """
    Parse command line arguments.
    
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Automated SEO Article Generator for Parga, Greece",
        epilog="For more information, see README.md"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate article but skip WordPress publishing"
    )
    
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        metavar="TOPIC",
        help='Override automatic topic selection (e.g., --topic "Valtos Beach")'
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug-level logging"
    )
    
    return parser.parse_args()


# ============================================================
# Main Pipeline
# ============================================================

def run_pipeline(
    topic_override: str = None,
    dry_run: bool = False,
    logger: logging.Logger = None,
) -> int:
    """
    Execute the full article generation pipeline.
    
    Steps:
        1. Initialize all modules
        2. Select topic (from manager or CLI override)
        3. Research topic via Tavily web search
        4. Generate article content with LLM
        5. Publish to WordPress (unless dry-run)
        6. Log successful publication to topic manager
    
    Args:
        topic_override: Optional topic to use instead of automatic selection
        dry_run: If True, skip WordPress publishing
        logger: Logger instance
        
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("Starting Article Generation Pipeline")
    logger.info("=" * 60)
    
    # ----------------------------------------------------------
    # Step 1: Load Configuration
    # ----------------------------------------------------------
    logger.info("Step 1: Loading configuration...")
    
    try:
        from config import Config, ConfigurationError
        config = Config()
        logger.info(f"Configuration loaded successfully")
        logger.debug(f"WordPress URL: {config.wordpress_url}")
        logger.debug(f"Dry run mode: {dry_run or config.dry_run}")
        
        # CLI --dry-run overrides config
        if dry_run:
            effective_dry_run = True
        else:
            effective_dry_run = config.dry_run
            
    except ImportError as e:
        logger.error(f"Failed to import config module: {e}")
        logger.error("Make sure config.py exists and python-dotenv is installed")
        return ExitCode.CONFIG_ERROR
        
    except ConfigurationError as e:
        logger.error(f"Configuration error:\n{e}")
        return ExitCode.CONFIG_ERROR
    
    # ----------------------------------------------------------
    # Step 2: Initialize Modules
    # ----------------------------------------------------------
    logger.info("Step 2: Initializing modules...")
    
    try:
        from topic_manager import TopicManager
        from article_generator import ArticleGenerator, ResearchError, GenerationError
        from wordpress_publisher import (
            WordPressPublisher,
            WordPressError,
            WordPressAuthenticationError,
            WordPressPermissionError,
            WordPressConnectionError,
        )
        
        topic_manager = TopicManager()
        logger.debug("TopicManager initialized")
        
        article_generator = ArticleGenerator(
            anthropic_api_key=config.anthropic_api_key,
            tavily_api_key=config.tavily_api_key,
            openai_api_key=config.openai_api_key,
        )
        logger.debug("ArticleGenerator initialized")
        
        if not effective_dry_run:
            wordpress_publisher = WordPressPublisher(
                site_url=config.wordpress_url,
                username=config.wordpress_username,
                app_password=config.wordpress_app_password,
            )
            logger.debug("WordPressPublisher initialized")
        else:
            wordpress_publisher = None
            logger.info("Dry run mode - WordPress publisher not initialized")
            
        logger.info("All modules initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize modules: {e}")
        return ExitCode.CONFIG_ERROR
    
    # ----------------------------------------------------------
    # Step 3: Select Topic
    # ----------------------------------------------------------
    logger.info("Step 3: Selecting topic...")
    
    try:
        if topic_override:
            topic = topic_override
            category = "Custom"
            logger.info(f"Using topic override: '{topic}'")
        else:
            topic, category = topic_manager.get_next_topic()
            logger.info(f"Selected topic: '{topic}' (Category: {category})")
            
    except Exception as e:
        logger.error(f"Topic selection failed: {e}")
        return ExitCode.TOPIC_ERROR
    
    # ----------------------------------------------------------
    # Step 4: Research Topic
    # ----------------------------------------------------------
    logger.info("Step 4: Researching topic via Tavily...")
    
    try:
        research_data = article_generator.research_topic(topic)
        logger.info(f"Research complete. Found {len(research_data.sources)} sources.")
        logger.debug(f"Research summary: {research_data.summary[:200]}...")
        
    except ResearchError as e:
        logger.error(f"Research failed: {e}")
        return ExitCode.RESEARCH_ERROR
        
    except Exception as e:
        logger.error(f"Unexpected error during research: {e}")
        return ExitCode.RESEARCH_ERROR
    
    # ----------------------------------------------------------
    # Step 5: Generate Article
    # ----------------------------------------------------------
    logger.info("Step 5: Generating article with Claude...")
    
    try:
        article = article_generator.generate_article(topic, research_data)
        logger.info(f"Article generated: '{article.title}'")
        logger.info(f"Word count: {article.word_count}")
        logger.info(f"Tokens used: {article.tokens_used}")
        logger.debug(f"Keywords: {', '.join(article.keywords)}")
        
    except GenerationError as e:
        logger.error(f"Article generation failed: {e}")
        return ExitCode.GENERATION_ERROR
        
    except Exception as e:
        logger.error(f"Unexpected error during generation: {e}")
        return ExitCode.GENERATION_ERROR
    
    # ----------------------------------------------------------
    # Step 6: Publish to WordPress (unless dry-run)
    # ----------------------------------------------------------
    if effective_dry_run:
        logger.info("Step 6: DRY RUN - Skipping WordPress publishing")
        logger.info("-" * 40)
        logger.info("Generated Article Preview:")
        logger.info(f"  Title: {article.title}")
        logger.info(f"  Excerpt: {article.excerpt}")
        logger.info(f"  Word count: {article.word_count}")
        logger.info(f"  Keywords: {', '.join(article.keywords)}")
        logger.info("-" * 40)
        
        # Calculate elapsed time
        elapsed = time.time() - start_time
        logger.info(f"Pipeline completed in {elapsed:.1f} seconds (dry run)")
        logger.info("=" * 60)
        
        return ExitCode.SUCCESS
    
    logger.info("Step 6: Publishing to WordPress...")
    
    try:
        publish_result = wordpress_publisher.publish_post(
            title=article.title,
            content=article.content,
            excerpt=article.excerpt,
            status="publish",
        )
        
        logger.info(f"Article published successfully!")
        logger.info(f"  Post ID: {publish_result.post_id}")
        logger.info(f"  URL: {publish_result.url}")
        logger.info(f"  Status: {publish_result.status}")
        
    except WordPressAuthenticationError as e:
        logger.error(f"WordPress authentication failed: {e}")
        return ExitCode.PUBLISHING_ERROR
        
    except WordPressPermissionError as e:
        logger.error(f"WordPress permission denied: {e}")
        return ExitCode.PUBLISHING_ERROR
        
    except WordPressConnectionError as e:
        logger.error(f"WordPress connection failed: {e}")
        return ExitCode.PUBLISHING_ERROR
        
    except WordPressError as e:
        logger.error(f"WordPress publishing failed: {e}")
        return ExitCode.PUBLISHING_ERROR
        
    except Exception as e:
        logger.error(f"Unexpected error during publishing: {e}")
        return ExitCode.PUBLISHING_ERROR
    
    # ----------------------------------------------------------
    # Step 7: Log Publication to Topic Manager
    # ----------------------------------------------------------
    logger.info("Step 7: Logging publication to topic manager...")
    
    try:
        topic_manager.log_publication(
            topic=topic,
            title=article.title,
            url=publish_result.url,
            category=category if category != "Custom" else None,
        )
        logger.info("Publication logged successfully")
        
    except Exception as e:
        # Don't fail the pipeline if logging fails - article is already published
        logger.warning(f"Failed to log publication (non-fatal): {e}")
    
    # ----------------------------------------------------------
    # Complete
    # ----------------------------------------------------------
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"Pipeline completed successfully in {elapsed:.1f} seconds")
    logger.info(f"Published: {article.title}")
    logger.info(f"URL: {publish_result.url}")
    logger.info("=" * 60)
    
    return ExitCode.SUCCESS


# ============================================================
# Main Entry Point
# ============================================================

def main() -> int:
    """
    Main entry point for the article generator.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Parse command line arguments
    args = parse_args()
    
    # Set up logging
    logger = setup_logging(verbose=args.verbose)
    
    # Log startup information
    logger.info(f"Article Generator started at {datetime.now().isoformat()}")
    if args.dry_run:
        logger.info("Running in DRY RUN mode")
    if args.topic:
        logger.info(f"Topic override: '{args.topic}'")
    
    # Run the pipeline
    try:
        exit_code = run_pipeline(
            topic_override=args.topic,
            dry_run=args.dry_run,
            logger=logger,
        )
    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        exit_code = 1
    except Exception as e:
        logger.exception(f"Unhandled exception in pipeline: {e}")
        exit_code = 1
    
    # Log final status
    if exit_code == ExitCode.SUCCESS:
        logger.info("Article generator completed successfully")
    else:
        logger.error(f"Article generator failed with exit code {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
