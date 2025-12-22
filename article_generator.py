"""
Article Content Generator for the Automated SEO Article Generator.

This module combines web research (via Tavily) with LLM content generation (Claude)
to create SEO-optimized travel articles about Parga, Greece.

Usage:
    from article_generator import ArticleGenerator
    
    generator = ArticleGenerator(
        anthropic_api_key="sk-ant-...",
        tavily_api_key="tvly-..."
    )
    
    result = generator.generate("Best beaches in Parga")
    print(result["title"])
    print(result["content"])

Output Format:
    {
        "title": "...",
        "content": "<html>...</html>",
        "excerpt": "...",
        "keywords": ["parga", "..."]
    }
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import anthropic
from tavily import TavilyClient


# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================
# Custom Exceptions
# ============================================================

class ArticleGeneratorError(Exception):
    """Base exception for article generator errors."""
    pass


class ResearchError(ArticleGeneratorError):
    """Raised when web research fails."""
    pass


class GenerationError(ArticleGeneratorError):
    """Raised when article generation fails."""
    pass


class RateLimitError(ArticleGeneratorError):
    """Raised when API rate limits are hit."""
    
    def __init__(self, service: str, retry_after: Optional[int] = None):
        message = f"{service} API rate limit exceeded."
        if retry_after:
            message += f" Retry after {retry_after} seconds."
        super().__init__(message)
        self.service = service
        self.retry_after = retry_after


class APIConnectionError(ArticleGeneratorError):
    """Raised when unable to connect to an API."""
    
    def __init__(self, service: str, original_error: Exception = None):
        message = f"Unable to connect to {service} API."
        if original_error:
            message += f" Error: {original_error}"
        super().__init__(message)
        self.service = service


# ============================================================
# Data Classes
# ============================================================

@dataclass
class ResearchResult:
    """Result from web research."""
    topic: str
    sources: list[dict] = field(default_factory=list)
    summary: str = ""
    raw_content: str = ""
    
    def to_prompt_context(self) -> str:
        """Format research for inclusion in LLM prompt."""
        if not self.sources:
            return "No research data available."
        
        context_parts = [
            f"Research Topic: {self.topic}",
            "",
            "Key Information from Web Research:",
            ""
        ]
        
        for i, source in enumerate(self.sources, 1):
            title = source.get("title", "Untitled")
            content = source.get("content", "")[:500]  # Limit content length
            url = source.get("url", "")
            
            context_parts.append(f"{i}. {title}")
            if content:
                context_parts.append(f"   {content}")
            if url:
                context_parts.append(f"   Source: {url}")
            context_parts.append("")
        
        return "\n".join(context_parts)


@dataclass
class ArticleResult:
    """Result from article generation."""
    title: str
    content: str  # HTML content
    excerpt: str  # Meta description (150-160 chars)
    keywords: list[str]
    word_count: int = 0
    tokens_used: int = 0
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "content": self.content,
            "excerpt": self.excerpt,
            "keywords": self.keywords,
            "word_count": self.word_count,
            "tokens_used": self.tokens_used,
        }


# ============================================================
# Prompt Templates
# ============================================================

ARTICLE_SYSTEM_PROMPT = """You are an expert travel writer with deep knowledge of Parga, Greece and the surrounding Epirus region. You have visited Parga many times and know its beaches, restaurants, hidden gems, local customs, and practical travel tips intimately.

Your writing style is:
- Friendly and conversational, but informative
- Specific and detailed with concrete recommendations
- Balanced between inspiration and practical advice
- Naturally incorporating SEO keywords without stuffing
- Structured for easy scanning with clear headings

You write for tourists planning to visit Parga, providing the kind of insider knowledge that helps them have an authentic, memorable experience."""

ARTICLE_USER_PROMPT_TEMPLATE = """Write a comprehensive, SEO-optimized travel article about the following topic related to Parga, Greece:

**Topic:** {topic}

**Research Data (use to ensure accuracy and include specific details):**
{research_context}

**Article Requirements:**

1. **Title**: Create an engaging, SEO-friendly title that naturally includes the main keyword. The title should be compelling and promise value to the reader.

2. **Structure**: Use this format:
   - Opening hook (capture attention immediately)
   - Introduction mentioning Parga and setting expectations
   - Body content with H2 and H3 headings for different sections
   - Practical tips and specific recommendations
   - Conclusion with a call-to-action

3. **Content Guidelines**:
   - Length: 800-1500 words
   - Include specific place names, price ranges (in euros), opening hours when relevant
   - Add local tips that demonstrate authentic knowledge
   - Mention nearby attractions or related activities
   - Use sensory descriptions to bring the destination to life
   - Include practical information (how to get there, best time to visit, what to bring)

4. **SEO Requirements**:
   - Use the main keyword in the title, first paragraph, and 2-3 headings
   - Include related keywords naturally throughout
   - Structure content for featured snippets where appropriate
   - Keep paragraphs relatively short for readability

5. **HTML Formatting**:
   - Use <h2> for main sections, <h3> for subsections
   - Use <p> tags for paragraphs
   - Use <ul> and <li> for lists
   - Use <strong> sparingly for emphasis
   - Do NOT include <html>, <head>, <body> tags - just the article content

**Output Format:**
Return your response as a valid JSON object with this exact structure:
```json
{{
    "title": "Your SEO-optimized title here",
    "content": "<h2>First Section</h2><p>Content...</p>...",
    "excerpt": "A compelling 150-160 character meta description for search engines.",
    "keywords": ["main keyword", "related keyword 1", "related keyword 2", ...]
}}
```

Important: 
- The excerpt MUST be between 150-160 characters
- The content should be 800-1500 words
- Ensure the JSON is valid and properly escaped
- Include "parga" as one of the keywords"""


# ============================================================
# Article Generator Class
# ============================================================

class ArticleGenerator:
    """
    Generates SEO-optimized travel articles about Parga using web research and Claude.
    
    Combines Tavily web search for current, accurate information with Claude's
    language generation capabilities to produce high-quality travel content.
    
    Attributes:
        anthropic_api_key: API key for Claude
        tavily_api_key: API key for Tavily web search
        model: Claude model to use (default: claude-sonnet-4-20250514)
        max_retries: Maximum retry attempts for transient failures
    """
    
    # Default Claude model (balanced cost/quality)
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    
    # Article constraints
    MIN_WORDS = 800
    MAX_WORDS = 1500
    EXCERPT_MIN_LENGTH = 150
    EXCERPT_MAX_LENGTH = 160
    
    def __init__(
        self,
        anthropic_api_key: str,
        tavily_api_key: str,
        model: str = None,
        max_retries: int = 3,
        openai_api_key: Optional[str] = None,  # Optional fallback
    ):
        """
        Initialize the article generator.
        
        Args:
            anthropic_api_key: Anthropic API key for Claude
            tavily_api_key: Tavily API key for web research
            model: Claude model to use (default: claude-sonnet-4-20250514)
            max_retries: Maximum retry attempts for transient failures
            openai_api_key: Optional OpenAI API key for fallback
        """
        self.anthropic_api_key = anthropic_api_key
        self.tavily_api_key = tavily_api_key
        self.model = model or self.DEFAULT_MODEL
        self.max_retries = max_retries
        self.openai_api_key = openai_api_key
        
        # Initialize API clients
        self._anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)
        self._tavily_client = TavilyClient(api_key=tavily_api_key)
        
        logger.debug(f"Initialized ArticleGenerator with model {self.model}")
    
    def research_topic(self, topic: str) -> ResearchResult:
        """
        Use Tavily to gather current information about a topic.
        
        Searches for relevant, up-to-date information about the given topic
        with a focus on Parga, Greece.
        
        Args:
            topic: The topic to research (e.g., "best beaches in Parga")
            
        Returns:
            ResearchResult containing sources and content
            
        Raises:
            ResearchError: If research fails
            RateLimitError: If Tavily rate limit is exceeded
            APIConnectionError: If unable to connect to Tavily
        """
        # Enhance query with location context
        search_query = f"{topic} Parga Greece"
        
        logger.info(f"Researching topic: {topic}")
        logger.debug(f"Search query: {search_query}")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Execute Tavily search
                response = self._tavily_client.search(
                    query=search_query,
                    search_depth="advanced",  # More thorough search
                    include_answer=True,  # Get a summary answer
                    max_results=5,  # Limit results for context window
                )
                
                # Parse response
                sources = []
                for result in response.get("results", []):
                    sources.append({
                        "title": result.get("title", ""),
                        "content": result.get("content", ""),
                        "url": result.get("url", ""),
                        "score": result.get("score", 0),
                    })
                
                # Build raw content for reference
                raw_content = "\n\n".join(
                    f"{s['title']}: {s['content']}" for s in sources
                )
                
                result = ResearchResult(
                    topic=topic,
                    sources=sources,
                    summary=response.get("answer", ""),
                    raw_content=raw_content,
                )
                
                logger.info(f"Research complete. Found {len(sources)} sources.")
                logger.debug(f"Research summary: {result.summary[:200]}...")
                
                return result
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for rate limiting
                if "rate" in error_str and "limit" in error_str:
                    logger.warning(f"Tavily rate limit hit on attempt {attempt}")
                    if attempt < self.max_retries:
                        delay = 2 ** attempt  # Exponential backoff
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    raise RateLimitError("Tavily")
                
                # Check for connection errors
                if "connect" in error_str or "timeout" in error_str:
                    logger.error(f"Tavily connection error: {e}")
                    if attempt < self.max_retries:
                        delay = 2 ** attempt
                        logger.info(f"Retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    raise APIConnectionError("Tavily", e)
                
                # Other errors
                logger.error(f"Research failed: {e}")
                raise ResearchError(f"Failed to research topic: {e}")
        
        raise ResearchError("Research failed after all retries")
    
    def generate_article(
        self,
        topic: str,
        research_data: ResearchResult,
    ) -> ArticleResult:
        """
        Generate an article using Claude based on research data.
        
        Args:
            topic: The article topic
            research_data: Research results from research_topic()
            
        Returns:
            ArticleResult containing the generated article
            
        Raises:
            GenerationError: If article generation fails
            RateLimitError: If Claude rate limit is exceeded
            APIConnectionError: If unable to connect to Claude
        """
        logger.info(f"Generating article for topic: {topic}")
        
        # Build the prompt with research context
        research_context = research_data.to_prompt_context()
        user_prompt = ARTICLE_USER_PROMPT_TEMPLATE.format(
            topic=topic,
            research_context=research_context,
        )
        
        logger.debug(f"Prompt length: {len(user_prompt)} characters")
        
        for attempt in range(1, self.max_retries + 1):
            try:
                # Call Claude API
                response = self._anthropic_client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=ARTICLE_SYSTEM_PROMPT,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                )
                
                # Log token usage
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                total_tokens = input_tokens + output_tokens
                
                logger.info(
                    f"Claude API call complete. "
                    f"Tokens: {input_tokens} in, {output_tokens} out, {total_tokens} total"
                )
                
                # Extract response content
                raw_response = response.content[0].text
                
                # Parse JSON response
                article_data = self._parse_article_response(raw_response)
                
                # Validate and build result
                result = self._build_article_result(article_data, total_tokens)
                
                logger.info(
                    f"Article generated: '{result.title}' "
                    f"({result.word_count} words)"
                )
                
                return result
                
            except anthropic.RateLimitError as e:
                logger.warning(f"Claude rate limit hit on attempt {attempt}")
                if attempt < self.max_retries:
                    delay = 2 ** attempt * 5  # Longer delay for Claude
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                raise RateLimitError("Claude (Anthropic)")
                
            except anthropic.APIConnectionError as e:
                logger.error(f"Claude connection error: {e}")
                if attempt < self.max_retries:
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                raise APIConnectionError("Claude (Anthropic)", e)
                
            except anthropic.APIStatusError as e:
                logger.error(f"Claude API error: {e}")
                raise GenerationError(f"Claude API error: {e}")
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Claude response as JSON: {e}")
                if attempt < self.max_retries:
                    logger.info("Retrying generation...")
                    continue
                raise GenerationError(f"Invalid JSON response from Claude: {e}")
                
            except Exception as e:
                logger.error(f"Unexpected error during generation: {e}")
                raise GenerationError(f"Article generation failed: {e}")
        
        raise GenerationError("Generation failed after all retries")
    
    def generate(self, topic: str) -> dict:
        """
        Full pipeline: research topic and generate article.
        
        This is the main entry point for article generation. It combines
        web research with LLM generation to produce a complete article.
        
        Args:
            topic: The article topic (e.g., "Best beaches in Parga")
            
        Returns:
            Dictionary with title, content, excerpt, and keywords
            
        Raises:
            ArticleGeneratorError: If any step fails
        """
        logger.info(f"Starting full generation pipeline for: {topic}")
        
        # Step 1: Research the topic
        research_data = self.research_topic(topic)
        
        # Step 2: Generate the article
        article = self.generate_article(topic, research_data)
        
        logger.info(f"Generation pipeline complete for: {topic}")
        
        return article.to_dict()
    
    def _parse_article_response(self, raw_response: str) -> dict:
        """
        Parse the JSON response from Claude.
        
        Handles various formats including markdown code blocks.
        
        Args:
            raw_response: Raw text response from Claude
            
        Returns:
            Parsed JSON as dictionary
            
        Raises:
            json.JSONDecodeError: If parsing fails
        """
        # Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw_response)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            # Try parsing the whole response as JSON
            json_str = raw_response.strip()
        
        # Parse JSON
        return json.loads(json_str)
    
    def _build_article_result(
        self,
        article_data: dict,
        tokens_used: int,
    ) -> ArticleResult:
        """
        Build and validate ArticleResult from parsed data.
        
        Args:
            article_data: Parsed JSON from Claude
            tokens_used: Total tokens used in generation
            
        Returns:
            Validated ArticleResult
            
        Raises:
            GenerationError: If required fields are missing or invalid
        """
        # Validate required fields
        required_fields = ["title", "content", "excerpt", "keywords"]
        for field_name in required_fields:
            if field_name not in article_data:
                raise GenerationError(f"Missing required field: {field_name}")
        
        title = article_data["title"]
        content = article_data["content"]
        excerpt = article_data["excerpt"]
        keywords = article_data["keywords"]
        
        # Validate and adjust excerpt length
        if len(excerpt) < self.EXCERPT_MIN_LENGTH:
            logger.warning(
                f"Excerpt too short ({len(excerpt)} chars). "
                f"Minimum is {self.EXCERPT_MIN_LENGTH}."
            )
        elif len(excerpt) > self.EXCERPT_MAX_LENGTH:
            # Truncate excerpt if too long
            excerpt = excerpt[:self.EXCERPT_MAX_LENGTH - 3] + "..."
            logger.info(f"Excerpt truncated to {len(excerpt)} characters")
        
        # Ensure "parga" is in keywords
        keywords_lower = [k.lower() for k in keywords]
        if "parga" not in keywords_lower:
            keywords.insert(0, "parga")
        
        # Calculate word count (strip HTML tags)
        text_content = re.sub(r'<[^>]+>', ' ', content)
        word_count = len(text_content.split())
        
        # Log word count validation
        if word_count < self.MIN_WORDS:
            logger.warning(
                f"Article word count ({word_count}) is below minimum ({self.MIN_WORDS})"
            )
        elif word_count > self.MAX_WORDS:
            logger.warning(
                f"Article word count ({word_count}) exceeds maximum ({self.MAX_WORDS})"
            )
        else:
            logger.debug(f"Article word count: {word_count} (within range)")
        
        return ArticleResult(
            title=title,
            content=content,
            excerpt=excerpt,
            keywords=keywords,
            word_count=word_count,
            tokens_used=tokens_used,
        )


# ============================================================
# CLI Interface for Testing
# ============================================================

if __name__ == "__main__":
    import sys
    from config import Config, ConfigurationError
    
    # Configure logging for CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    try:
        # Load configuration
        config = Config()
        
        # Create generator
        generator = ArticleGenerator(
            anthropic_api_key=config.anthropic_api_key,
            tavily_api_key=config.tavily_api_key,
            openai_api_key=config.openai_api_key,
        )
        
        # Default test topic
        topic = "Best beaches in Parga"
        
        # Allow custom topic from command line
        if len(sys.argv) > 1:
            topic = " ".join(sys.argv[1:])
        
        print(f"\n{'=' * 60}")
        print(f"Article Generator Test")
        print(f"{'=' * 60}")
        print(f"\nTopic: {topic}\n")
        
        # Generate article
        print("Generating article...")
        result = generator.generate(topic)
        
        # Display results
        print(f"\n{'=' * 60}")
        print(f"Generated Article")
        print(f"{'=' * 60}")
        print(f"\nTitle: {result['title']}")
        print(f"\nExcerpt ({len(result['excerpt'])} chars):")
        print(f"  {result['excerpt']}")
        print(f"\nKeywords: {', '.join(result['keywords'])}")
        print(f"\nWord Count: {result['word_count']}")
        print(f"Tokens Used: {result['tokens_used']}")
        print(f"\n{'=' * 60}")
        print("Content Preview (first 500 chars):")
        print(f"{'=' * 60}")
        print(result['content'][:500] + "...")
        
        print(f"\n✅ Article generated successfully!")
        
    except ConfigurationError as e:
        print(f"❌ Configuration Error:\n{e}", file=sys.stderr)
        sys.exit(1)
    except ArticleGeneratorError as e:
        print(f"❌ Generation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}", file=sys.stderr)
        sys.exit(1)
