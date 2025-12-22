"""
Topic Management System for the Automated SEO Article Generator.

This module maintains a pool of Parga-related article topics, tracks published
content, and selects the next topic to write about while avoiding duplicates.

Usage:
    from topic_manager import TopicManager
    
    manager = TopicManager()
    
    # Get next topic
    topic, category = manager.get_next_topic()
    
    # Log publication
    manager.log_publication(topic, "Article Title", "https://wordpress.com/article-url")
    
    # View history
    history = manager.get_published_history()
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# Configure module logger
logger = logging.getLogger(__name__)


# ============================================================
# Default Topic Pool
# ============================================================

DEFAULT_TOPIC_POOL = {
    "beaches": {
        "name": "Beaches",
        "topics": [
            "Valtos Beach",
            "Lichnos Beach",
            "Sarakiniko Beach",
            "Piso Krioneri",
            "Ai Giannakis Beach"
        ]
    },
    "restaurants_food": {
        "name": "Restaurants & Food",
        "topics": [
            "Traditional tavernas in Parga",
            "Local cuisine guide to Parga",
            "Seafood specialties in Parga"
        ]
    },
    "attractions": {
        "name": "Attractions",
        "topics": [
            "Parga Castle",
            "Ali Pasha's Castle in Parga",
            "Nekromanteion of Acheron"
        ]
    },
    "activities": {
        "name": "Activities",
        "topics": [
            "Boat trips to Paxos and Antipaxos from Parga",
            "Kayaking in Parga",
            "Hiking trails near Parga",
            "Snorkeling spots in Parga"
        ]
    },
    "day_trips": {
        "name": "Day Trips",
        "topics": [
            "Day trip to Sivota from Parga",
            "Day trip to Ioannina from Parga",
            "Day trip to Meteora from Parga",
            "Acheron River rafting",
            "Day trip to Preveza from Parga"
        ]
    },
    "practical_guides": {
        "name": "Practical Guides",
        "topics": [
            "Getting to Parga",
            "Best time to visit Parga",
            "Local transportation in Parga",
            "Accommodation tips for Parga"
        ]
    }
}


# ============================================================
# Topic Manager Class
# ============================================================

class TopicManager:
    """
    Manages a pool of Parga-related article topics with publication tracking.
    
    Features:
    - Maintains a topic pool organized by categories
    - Tracks published articles to avoid duplicates
    - Rotates through categories for content variety
    - Avoids selecting recently published topics (last 10)
    
    Attributes:
        topics_file: Path to the topics.json file
        published_file: Path to the published.json file
        cooldown_count: Number of selections before a topic can be reused (default: 10)
    """
    
    DEFAULT_TOPICS_FILE = "topics.json"
    DEFAULT_PUBLISHED_FILE = "published.json"
    DEFAULT_COOLDOWN = 10
    
    def __init__(
        self,
        topics_file: str = None,
        published_file: str = None,
        cooldown_count: int = None
    ):
        """
        Initialize the TopicManager.
        
        Args:
            topics_file: Path to topics JSON file (default: topics.json)
            published_file: Path to published articles log (default: published.json)
            cooldown_count: Number of selections before topic can be reused (default: 10)
        """
        self.topics_file = Path(topics_file or self.DEFAULT_TOPICS_FILE)
        self.published_file = Path(published_file or self.DEFAULT_PUBLISHED_FILE)
        self.cooldown_count = cooldown_count if cooldown_count is not None else self.DEFAULT_COOLDOWN
        
        # Track last category used for rotation
        self._last_category_index = -1
        
        # Initialize files if they don't exist
        self._ensure_topics_file()
        self._ensure_published_file()
        
        logger.info(f"TopicManager initialized with topics_file={self.topics_file}, published_file={self.published_file}")
    
    def _ensure_topics_file(self) -> None:
        """Create topics.json with default pool if it doesn't exist."""
        if not self.topics_file.exists():
            logger.info(f"Creating default topics file at {self.topics_file}")
            self._save_topic_pool(DEFAULT_TOPIC_POOL)
    
    def _ensure_published_file(self) -> None:
        """Create published.json with empty structure if it doesn't exist."""
        if not self.published_file.exists():
            logger.info(f"Creating empty published file at {self.published_file}")
            self._save_published({
                "articles": [],
                "last_category_index": -1
            })
    
    def _load_topic_pool(self) -> dict:
        """Load topic pool from JSON file."""
        try:
            with open(self.topics_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading topics file: {e}")
            raise RuntimeError(f"Failed to load topics from {self.topics_file}: {e}")
    
    def _save_topic_pool(self, pool: dict) -> None:
        """Save topic pool to JSON file."""
        try:
            with open(self.topics_file, "w", encoding="utf-8") as f:
                json.dump(pool, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Error saving topics file: {e}")
            raise RuntimeError(f"Failed to save topics to {self.topics_file}: {e}")
    
    def _load_published(self) -> dict:
        """Load published articles log from JSON file."""
        try:
            with open(self.published_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading published file: {e}")
            raise RuntimeError(f"Failed to load published log from {self.published_file}: {e}")
    
    def _save_published(self, data: dict) -> None:
        """Save published articles log to JSON file."""
        try:
            with open(self.published_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Error saving published file: {e}")
            raise RuntimeError(f"Failed to save published log to {self.published_file}: {e}")
    
    def _get_recent_topics(self) -> set:
        """Get set of recently published topics (within cooldown window)."""
        published = self._load_published()
        articles = published.get("articles", [])
        
        # Get the last N topics (where N = cooldown_count)
        recent_articles = articles[-self.cooldown_count:] if articles else []
        return {article.get("topic", "").lower() for article in recent_articles}
    
    def get_next_topic(self) -> tuple[str, str]:
        """
        Select the next topic to write about.
        
        Uses category rotation for variety and avoids recently published topics.
        
        Returns:
            Tuple of (topic_name, category_name)
            
        Raises:
            RuntimeError: If no available topics found (all in cooldown)
        """
        topic_pool = self._load_topic_pool()
        published = self._load_published()
        recent_topics = self._get_recent_topics()
        
        # Get category order and last used index
        categories = list(topic_pool.keys())
        last_index = published.get("last_category_index", -1)
        
        # Try each category in rotation
        num_categories = len(categories)
        for offset in range(num_categories):
            # Calculate next category index (rotate from last used)
            next_index = (last_index + 1 + offset) % num_categories
            category_key = categories[next_index]
            category_data = topic_pool[category_key]
            category_name = category_data.get("name", category_key)
            topics = category_data.get("topics", [])
            
            # Find an available topic in this category
            for topic in topics:
                if topic.lower() not in recent_topics:
                    # Found an available topic - update last category index
                    published["last_category_index"] = next_index
                    self._save_published(published)
                    
                    logger.info(f"Selected topic: '{topic}' from category: '{category_name}'")
                    return topic, category_name
        
        # If all topics are in cooldown, reset and pick the oldest one
        articles = published.get("articles", [])
        if articles:
            # Pick the oldest published topic to reuse
            oldest = articles[0]
            logger.warning(f"All topics in cooldown, reusing oldest: {oldest.get('topic')}")
            return oldest.get("topic", "Parga Travel Guide"), oldest.get("category", "Practical Guides")
        
        # Fallback: return first topic from first category
        first_category_key = categories[0]
        first_category = topic_pool[first_category_key]
        first_topic = first_category["topics"][0]
        logger.warning(f"No published history, selecting first topic: {first_topic}")
        return first_topic, first_category.get("name", first_category_key)
    
    def log_publication(
        self,
        topic: str,
        title: str,
        url: str,
        category: Optional[str] = None
    ) -> dict:
        """
        Record a published article.
        
        Args:
            topic: The topic that was written about
            title: The article title
            url: The WordPress URL of the published article
            category: Optional category name (auto-detected if not provided)
            
        Returns:
            The publication record that was saved
        """
        published = self._load_published()
        
        # Auto-detect category if not provided
        if not category:
            category = self._find_category_for_topic(topic)
        
        # Create publication record
        record = {
            "topic": topic,
            "title": title,
            "url": url,
            "category": category,
            "date": datetime.now().isoformat()
        }
        
        # Append to articles list
        if "articles" not in published:
            published["articles"] = []
        published["articles"].append(record)
        
        # Save updated log
        self._save_published(published)
        
        logger.info(f"Logged publication: '{title}' at {url}")
        return record
    
    def _find_category_for_topic(self, topic: str) -> str:
        """Find the category a topic belongs to."""
        topic_pool = self._load_topic_pool()
        topic_lower = topic.lower()
        
        for category_key, category_data in topic_pool.items():
            topics_lower = [t.lower() for t in category_data.get("topics", [])]
            if topic_lower in topics_lower:
                return category_data.get("name", category_key)
        
        return "Unknown"
    
    def get_published_history(self, limit: Optional[int] = None) -> list[dict]:
        """
        Get the publication history for debugging/review.
        
        Args:
            limit: Optional max number of records to return (most recent first)
            
        Returns:
            List of publication records, most recent first
        """
        published = self._load_published()
        articles = published.get("articles", [])
        
        # Return in reverse chronological order
        articles = list(reversed(articles))
        
        if limit:
            articles = articles[:limit]
        
        return articles
    
    def get_topic_pool(self) -> dict:
        """Get the current topic pool."""
        return self._load_topic_pool()
    
    def get_all_topics(self) -> list[tuple[str, str]]:
        """
        Get all topics as a flat list.
        
        Returns:
            List of (topic, category_name) tuples
        """
        topic_pool = self._load_topic_pool()
        all_topics = []
        
        for category_key, category_data in topic_pool.items():
            category_name = category_data.get("name", category_key)
            for topic in category_data.get("topics", []):
                all_topics.append((topic, category_name))
        
        return all_topics
    
    def add_topic(self, topic: str, category_key: str) -> bool:
        """
        Add a new topic to a category.
        
        Args:
            topic: The topic to add
            category_key: The category key (e.g., 'beaches', 'activities')
            
        Returns:
            True if topic was added, False if it already exists
        """
        topic_pool = self._load_topic_pool()
        
        if category_key not in topic_pool:
            logger.error(f"Category '{category_key}' not found")
            return False
        
        topics = topic_pool[category_key].get("topics", [])
        
        # Check if topic already exists (case-insensitive)
        if topic.lower() in [t.lower() for t in topics]:
            logger.warning(f"Topic '{topic}' already exists in category '{category_key}'")
            return False
        
        topics.append(topic)
        topic_pool[category_key]["topics"] = topics
        self._save_topic_pool(topic_pool)
        
        logger.info(f"Added topic '{topic}' to category '{category_key}'")
        return True
    
    def generate_new_topics(self, category_key: Optional[str] = None) -> list[str]:
        """
        Placeholder for future LLM-based topic generation.
        
        This method will be implemented to use an LLM to generate new,
        creative topic ideas based on existing topics and published history.
        
        Args:
            category_key: Optional category to generate topics for
            
        Returns:
            List of newly generated topic suggestions (currently empty)
        """
        # TODO: Implement LLM-based topic generation
        # This could:
        # 1. Analyze existing topics and published history
        # 2. Use Claude to suggest new, trending, or seasonal topics
        # 3. Ensure suggestions are unique and relevant to Parga
        
        logger.info("generate_new_topics() called - feature not yet implemented")
        return []
    
    def get_stats(self) -> dict:
        """
        Get statistics about the topic pool and publications.
        
        Returns:
            Dictionary with topic and publication statistics
        """
        topic_pool = self._load_topic_pool()
        published = self._load_published()
        articles = published.get("articles", [])
        
        # Count topics per category
        category_stats = {}
        total_topics = 0
        for category_key, category_data in topic_pool.items():
            category_name = category_data.get("name", category_key)
            topic_count = len(category_data.get("topics", []))
            category_stats[category_name] = topic_count
            total_topics += topic_count
        
        return {
            "total_topics": total_topics,
            "total_published": len(articles),
            "categories": category_stats,
            "cooldown_count": self.cooldown_count,
            "topics_in_cooldown": len(self._get_recent_topics())
        }


# ============================================================
# CLI Interface for Testing
# ============================================================

if __name__ == "__main__":
    import sys
    
    # Configure logging for CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    
    print("=" * 60)
    print("Topic Manager - Test CLI")
    print("=" * 60)
    
    # Initialize manager
    manager = TopicManager()
    
    # Show stats
    stats = manager.get_stats()
    print(f"\nTopic Pool Statistics:")
    print(f"  Total topics: {stats['total_topics']}")
    print(f"  Total published: {stats['total_published']}")
    print(f"  Cooldown count: {stats['cooldown_count']}")
    print(f"  Topics in cooldown: {stats['topics_in_cooldown']}")
    print(f"\n  Categories:")
    for category, count in stats['categories'].items():
        print(f"    - {category}: {count} topics")
    
    # Test get_next_topic multiple times
    print(f"\n{'=' * 60}")
    print("Testing get_next_topic() - 5 calls:")
    print("=" * 60)
    
    for i in range(5):
        topic, category = manager.get_next_topic()
        print(f"  {i+1}. [{category}] {topic}")
        
        # Simulate publication logging
        if len(sys.argv) > 1 and sys.argv[1] == "--log":
            manager.log_publication(
                topic=topic,
                title=f"Guide to {topic}",
                url=f"https://example.com/article-{i+1}",
                category=category
            )
    
    # Show published history if we logged
    if len(sys.argv) > 1 and sys.argv[1] == "--log":
        print(f"\n{'=' * 60}")
        print("Published History:")
        print("=" * 60)
        history = manager.get_published_history(limit=10)
        for article in history:
            print(f"  - {article['date'][:10]}: {article['title']}")
            print(f"    URL: {article['url']}")
    
    print(f"\n{'=' * 60}")
    print("Test complete!")
    print("=" * 60)
    
    # Usage hints
    print("\nUsage:")
    print("  python topic_manager.py          # Test topic selection")
    print("  python topic_manager.py --log    # Test with publication logging")
