import logging
import re

from datetime import datetime, timedelta
from typing import (
    Any,
    Dict,
    List,
)


logger = logging.getLogger(__name__)


async def extract_post(container) -> Dict[str, Any]:
    """
    Extract relevant fields from a LinkedIn post container element.
    """

    post_data = {}
    try:
        # Extract published date
        published_date = await _extract_post_publish_date(container)
        # Extract author
        author = await _extract_post_author(container)
        # Extract text
        text = await _extract_post_text(container)
        # Extract post URL
        post_url = await _extract_post_url(container)
        # Extract engagement counts
        engagement_counts = await _extract_post_engagement_counts(
            container=container)

        # Return None if all fields are empty
        if not any([published_date, author, text, post_url,
                    any(engagement_counts.values())]):
            logger.warning("No data extracted from post")
            return post_data

        post_data = {
            "published_date": published_date,
            "author": author,
            "text": text.strip() if text else None,
            "url": post_url.strip() if post_url else None,
            **engagement_counts,
        }

    except Exception as e:
        logger.debug(f"Caught exception extracting post data: {e}")
        raise

    return post_data


async def _extract_post_author(container) -> str | None:
    """
    Helper function used to extract the author of a post
    from its container element.
    """

    # Extract the author of the post (multiple possible selectors)
    author = None
    author_selectors = [
        ".update-components-actor__name",
        ".feed-shared-actor__name",
        ".update-components-actor__title",
        '[data-test-id="main-feed-activity-card__entity-lockup"] '
        'span[aria-hidden="true"]',
        '.app-aware-link span[aria-hidden="true"]'
    ]

    try:
        author = await _try_selectors(
            container=container,
            selectors=author_selectors)
        if author and "\n" in author:
            author = author.split("\n")[0].strip()

    except Exception as e:
        logger.debug(f"Failed to extract author: {e}")

    author = author.strip() if author else None
    return author


async def _extract_post_engagement_counts(container) -> dict[str, int]:
    """
    Helper function used to extract engagement engagement metrics
    (reactions, comments, reshares) of a post from its container element.
    """

    reactions, comments, reshares = 0, 0, 0

    # Extract the reactions count (multiple possible selectors)
    reaction_selectors = [
        ".social-details-social-counts__reactions-count",
        '[data-test-id="social-actions__reaction-count"]',
        'button[aria-label*="reaction"] span[aria-hidden="true"]'
    ]
    reactions = await _extract_post_social_counts(
        container=container,
        selectors=reaction_selectors,
        field_name="reactions") or 0

    # Extract comments count (multiple possible selectors)
    comment_selectors = [
        ".social-details-social-counts__comments",
        '[data-test-id="social-actions__comment-count"]',
        'button[aria-label*="comment"] span[aria-hidden="true"]'
    ]
    comments = await _extract_post_social_counts(
        container=container,
        selectors=comment_selectors,
        field_name="comments") or 0

    # Extract reshares count (multiple possible selectors)
    reshare_selectors = [
        ".social-details-social-counts__item--reposts",
        '[data-test-id="social-actions__reshare-count"]',
        'button[aria-label*="repost"] span'
    ]
    reshares = await _extract_post_social_counts(
        container=container,
        selectors=reshare_selectors,
        field_name="reshares") or 0

    # Putting them together
    engagement_counts = {
        "reactions": reactions,
        "comments": comments,
        "reshares": reshares,
    }
    return engagement_counts


async def _extract_post_publish_date(container) -> str | None:
    """
    Helper function used to extract the publish date of a post
    from its container element.
    """

    # Extract the publish date of the post (multiple possible selectors)
    published_date = "Unknown"
    time_selectors = [
        ".update-components-actor__sub-description",
        ".feed-shared-actor__sub-description",
        "time",
        '[data-test-id="main-feed-activity-card__update-time"]',
        ".feed-shared-actor__sub-description time"
    ]

    try:
        for selector in time_selectors:
            time_el = await container.query_selector(selector)
            if time_el:
                # Try to get datetime attribute first
                published_date = await time_el.get_attribute("datetime")
                if not published_date:
                    # Fall back to text content
                    published_date = (await time_el.inner_text()).strip()

                    # Try to parse as relative date
                    if re.match(r'^\d+[hdwmy]$', published_date.lower()):
                        published_date = _parse_relative_date(published_date)

                break

    except Exception as e:
        logger.debug(f"Failed to extract publish date: {e}")

    return published_date


async def _extract_post_social_counts(
        container,
        selectors: List[str],
        field_name: str) -> int | None:

    try:
        for selector in selectors:
            el = await container.query_selector(selector)
            if el:
                text = (await el.inner_text()).strip()
                # Parse number from text like "1,234" or "1.2K"
                return _parse_engagement_count(text=text)
    except Exception as e:
        logger.debug(f"Failed to extract {field_name}: {e}")

    return None


async def _extract_post_text(container) -> str | None:
    """
    Helper function used to extract the text content of a post
    from its container element.
    """

    # Extract the text of the post (multiple possible selectors)
    post_text = None
    text_el = None
    text_selectors = [
        ".feed-shared-update-v2__description",
        ".feed-shared-text",
        ".break-words",
        '[data-test-id="main-feed-activity-card__commentary"]',
        ".feed-shared-inline-show-more-text"
    ]

    try:
        for selector in text_selectors:
            text_el = await container.query_selector(selector)
            if text_el:
                post_text = (await text_el.inner_text()).strip()
                break

        if text_el:
            post_text = (await text_el.inner_text()).strip()
    except Exception as e:
        logger.debug(f"Failed to extract post text: {e}")

    return post_text


async def _extract_post_url(container) -> str | None:
    """
    Helper function used to extract the URL of a post
    from its container element.
    """

    # Extract the URL of the post (multiple possible selectors)
    post_url = "Unknown"
    try:
        # Strategy 1: Try to extract href from link elements
        url_selectors = [
            "time ~ a",
            ".feed-shared-actor__sub-description a",
            ".update-components-actor__sub-description a",
            'a.app-aware-link[href*="/feed/update/"]',
            'a[href*="/posts/"]',
        ]

        post_url = await _try_selectors_for_attribute(
            container=container,
            selectors=url_selectors,
            attribute="href"
        )

        # Filter to ensure it is a post URL
        if post_url and not ("/feed/update/" in post_url
                             or "/posts/" in post_url):
            post_url = None

        # Strategy 2: Construct from data attributes
        if not post_url:
            data_id = await container.get_attribute("data-id")
            if not data_id:
                data_id = await container.get_attribute("data-urn")

            if data_id and "urn:li:activity:" in data_id:
                post_url = f"/feed/update/{data_id}/"

        # Make absolute URL
        if post_url:
            if post_url.startswith('/'):
                post_url = f"https://www.linkedin.com{post_url}"
            elif not post_url.startswith('http'):
                post_url = f"https://www.linkedin.com/{post_url}"

            return post_url

    except Exception as e:
        logger.debug(f"Failed to extract post URL: {e}")

    return post_url


def _parse_engagement_count(text: str) -> int:
    """
    Helper function used to parse engagement counts
    like "1,234" or "1.2K" or "5M"
    """
    if not text:
        return 0

    # Remove non-numeric characters except K, M, B, comma, period
    text = text.strip().upper()

    try:
        # Handle K (thousands), M (millions), B (billions)
        if "K" in text:
            number = float(text.replace("K", "").replace(",", ""))
            return int(number * 1000)
        elif "M" in text:
            number = float(text.replace("M", "").replace(",", ""))
            return int(number * 1000000)
        elif "B" in text:
            number = float(text.replace("B", "").replace(",", ""))
            return int(number * 1000000000)
        else:
            # Regular number, remove commas
            return int(text.replace(",", "").replace(".", ""))
    except (ValueError, AttributeError):
        return 0


def _parse_relative_date(text: str) -> str:
    """
    Helper function used to convert relative date strings like "2h", "3d", "1w"
    to absolute datetime strings.

    This function returns ISO format datetime string.
    """
    if not text:
        return "Unknown"

    text = text.strip().lower()

    # Dictionary of time units
    time_units = {
        "m": "minutes",
        "h": "hours",
        "d": "days",
        "w": "weeks",
        "mo": "months",
        "y": "years"
    }

    # Try to match patterns like "2h", "3d", "1w"
    match = re.match(r'^(\d+)([hdwmy])$', text)
    if match:
        value = int(match.group(1))
        unit = match.group(2)

        if unit in time_units:
            # Calculate the past date
            now = datetime.now()
            past_date = None
            if unit == 'h':
                past_date = now - timedelta(hours=value)
            elif unit == 'd':
                past_date = now - timedelta(days=value)
            elif unit == 'w':
                past_date = now - timedelta(weeks=value)
            elif unit == 'm':
                # Approximate months as 30 days
                past_date = now - timedelta(days=value*30)
            elif unit == 'y':
                past_date = now - timedelta(days=value*365)

            if past_date:
                return past_date.isoformat()

    return "Unknown"


async def _try_selectors(container, selectors: List[str]) -> str | None:
    last_error = None
    for selector in selectors:
        try:
            el = await container.query_selector(selector)
            if el:
                text = (await el.inner_text()).strip()
                if text:
                    return text
        except Exception as e:
            last_error = e
            logger.debug(f"Selector '{selector}' failed: {e}")

    if last_error:
        logger.debug(f"All selectors failed, last error: {last_error}")
    return None


async def _try_selectors_for_attribute(
        container,
        selectors: List[str],
        attribute: str) -> str | None:
    """
    Helper function to try multiple selectors and extract an attribute value.
    Similar to `_try_selectors` but for attributes instead of text.
    """
    for selector in selectors:
        try:
            el = await container.query_selector(selector)
            if el:
                value = await el.get_attribute(attribute)
                if value:
                    logger.debug("Found {} using selector: {}"
                                 .format(attribute, selector))
                    return value
        except Exception as e:
            logger.debug(f"Selector '{selector}' failed: {e}")

    return None
