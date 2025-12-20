import os
import re

from typing import (
    Any,
    Dict,
    List,
    TypeVar,
)

from googleapiclient.discovery import Resource


from app_logger import get_logger
from utils import (
    rate_limited,
    retry_with_backoff
)


logger = get_logger(__name__)
T = TypeVar("T")


def analyze_engagement(
    service: Resource,
    newsletter_ids: List[str],
    threshold_days: int = 90
) -> Dict[str, Any]:
    """
    Analyze engagement rates for specific newsletter senders.

    Calculates open rate by comparing UNREAD label status across
    recent emails from each sender. Open rate >30% suggests user
    engagement (recommendation: keep). Open rate <30% suggests
    low value (recommendation: unsubscribe).

    Args:
        service: Gmail API service object
        newsletter_ids: List of newsletter sender email addresses
        threshold_days: Only consider emails from last N days (default: 90)

    Returns:
        Dictionary containing engagement analysis
        following the structure:
        {
            "success": True,
            "engagement_data": {
                "sender@example.com": {
                    "total_received": 45,
                    "read_count": 32,
                    "open_rate": 71.1,
                    "recommendation": "keep"
                }
            }
        }

    Raises:
        HttpError: If Gmail API returns non-retryable error
    """
    n = len(newsletter_ids)
    logger.info(f"Analyzing engagement for {n} newsletters...")
    engagement = {}

    max_results = int(os.environ.get("MAX_RESULTS_ANALYZE", "50"))
    min_open_rate = int(os.environ.get("MIN_OPEN_RATE", "30"))
    for newsletter_id in newsletter_ids:
        try:
            # Search for emails from this sender
            query = f"from:{newsletter_id} newer_than:{threshold_days}d"
            results = retry_with_backoff(
                func=service.users().messages().list(
                    userId="me",
                    q=query,
                    maxResults=max_results
                ).execute,
                max_attempts=3
            )

            messages = results.get("messages", [])
            total = len(messages)
            read_count = 0

            # Check read status for each email
            for msg in messages:
                msg_data = service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata"
                ).execute()

                # Check if email was read (not in UNREAD label)
                labels = msg_data.get("labelIds", [])
                if "UNREAD" not in labels:
                    read_count += 1

            open_rate = (read_count / total * 100) if total > 0 else 0

            engagement[newsletter_id] = {
                "total_received": total,
                "read_count": read_count,
                "unread_count": total - read_count,
                "open_rate": round(open_rate, 1),
                "recommendation": "keep" if open_rate > min_open_rate else
                "consider_unsubscribe"
            }

            logger.debug(f"{newsletter_id}: {read_count}/{total} read "
                         f"({open_rate:.1f}%)")

        except Exception as e:
            logger.error(f"Error analyzing {newsletter_id}: {e}")
            engagement[newsletter_id] = {
                "error": str(e)
            }

    logger.info("Engagement analysis complete")
    return {
        "success": True,
        "engagement_data": engagement
    }


def extract_unsubscribe_links(service, sender_emails: List[str]) -> Dict:
    """
    Extract unsubscribe links from newsletters.

    Args:
        service: Gmail API service object
        sender_emails: List of newsletter sender email addresses

    Returns:
        Dictionary containing unsubscribe information
    """
    n = len(sender_emails)
    logger.info(f"Extracting unsubscribe links for {n} newsletters...")
    unsubscribe_info = {}

    for sender in sender_emails:
        try:
            # Get one recent email from this sender
            query = f"from:{sender}"
            results = service.users().messages().list(
                userId="me",
                q=query,
                maxResults=1
            ).execute()

            messages = results.get("messages", [])
            if not messages:
                logger.warning(f"No recent emails found from {sender}")
                unsubscribe_info[sender] = {
                    "error": "No recent emails found"
                }
                continue

            # Get full message to access headers
            msg = service.users().messages().get(
                userId="me",
                id=messages[0]["id"],
                format="full"
            ).execute()

            headers = {
                h["name"]: h["value"] for h in msg["payload"]["headers"]
            }

            # Extract List-Unsubscribe header
            list_unsub = headers.get("List-Unsubscribe", "")

            # Parse unsubscribe HTTP link
            link_match = re.search(r"<(https?://[^>]+)>", list_unsub)
            unsubscribe_link = link_match.group(1) if link_match else None

            # Parse mailto unsubscribe
            mailto_match = re.search(r"<mailto:([^>]+)>", list_unsub)
            mailto_link = mailto_match.group(1) if mailto_match else None

            unsubscribe_info[sender] = {
                "unsubscribe_link": unsubscribe_link,
                "mailto_unsubscribe": mailto_link,
                "method": "link" if unsubscribe_link else
                ("mailto"if mailto_link else "manual")
            }

            logger.debug(f"{sender}: {unsubscribe_info[sender]["method"]}")

        except Exception as e:
            logger.error(f"Error extracting link for {sender}: {e}")
            unsubscribe_info[sender] = {
                "error": str(e)
            }

    logger.info("Unsubscribe link extraction complete")
    return {
        "success": True,
        "unsubscribe_data": unsubscribe_info
    }


def scan_newsletters(service, days_back: int = -1) -> Dict:
    """
    Scan Gmail for newsletter subscriptions.

    Args:
        service: Gmail API service object
        days_back: Number of days to look back

    Returns:
        Dictionary containing newsletter scan results
    """

    if days_back < 1:
        days_back = int(os.environ.get("MAX_LOOKBACK_DAYS", "90"))

    logger.info(f"Scanning newsletters from the last {days_back} days...")
    query = f"newer_than:{days_back}d"
    newsletters = {}

    try:
        max_results = int(os.environ.get("MAX_RESULTS_SCAN", "50"))
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results
        ).execute()

        messages = results.get("messages", [])
        logger.info(f"Found {len(messages)} recent emails to analyze")

        # Adaptive rate limiting to respect Gmail API quotas
        # Starts at 20ms between calls, adapts based on API responses.
        @rate_limited(min_interval=0.02)
        def fetch_message_metadata(msg_id: str) -> Dict:
            return service.users().messages().get(
                userId="me",
                id=msg_id,
                format="metadata",
                metadataHeaders=["From", "Subject", "List-Unsubscribe"]
            ).execute()

        for msg in messages:
            msg_data = fetch_message_metadata(msg["id"])

            headers = {
                h["name"]: h["value"]
                for h in msg_data["payload"]["headers"]
            }

            # Check if it is a newsletter (has List-Unsubscribe header)
            if "List-Unsubscribe" in headers:
                sender = headers.get("From", "Unknown")

                # Extract email address from "Name <email@domain.com>" format
                sender_email_match = re.search(r"<(.+?)>", sender)
                sender_email = sender_email_match.group(1) \
                    if sender_email_match else sender

                if sender_email not in newsletters:
                    sender_name = sender.split("<")[0].strip() if "<" \
                        in sender else sender
                    newsletters[sender_email] = {
                        "sender_name": sender_name,
                        "count": 0,
                        "sample_subjects": []
                    }

                newsletters[sender_email]["count"] += 1

                # Collect up to 3 sample subjects
                if len(newsletters[sender_email]["sample_subjects"]) < 3:
                    subject = headers.get("Subject", "No subject")
                    newsletters[sender_email]["sample_subjects"]\
                        .append(subject)

        logger.info("Scan complete. "
                    f"Found {len(newsletters)} unique newsletters")

        return {
            "success": True,
            "total_newsletters": len(newsletters),
            "newsletters": newsletters,
            "scan_period_days": days_back,
            "total_emails_scanned": len(messages)
        }

    except Exception as e:
        logger.error(f"Error scanning newsletters: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }


# Function dispatch mapping
available_functions = {
    "scan_newsletters": scan_newsletters,
    "analyze_engagement": analyze_engagement,
    "extract_unsubscribe_links": extract_unsubscribe_links
}
