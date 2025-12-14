import aiohttp
import asyncio
import logging
import os

from pathlib import Path

from playwright.async_api import (
    async_playwright,
    Page,
)
logger = logging.getLogger(__name__)

# Store browser data in a persistent directory
USER_DATA_DIR = Path("./browser_data")
USER_DATA_DIR.mkdir(exist_ok=True)


async def _apply_stealth(page: Page):
    """
    Apply stealth JavaScript to hide automation indicators.
    This is what actually removes the "browser not secure" warning.
    """
    await page.add_init_script("""
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        // Mock plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });

        // Mock languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
        });

        // Add chrome object (makes it look like Chrome)
        window.chrome = {
            runtime: {},
        };

        // Fix permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)


async def extract_posts(
        page: Page,
        limit: int = 10) -> list[dict]:
    """
    Helper function used to extract posts from feed.
    """
    logger.info(f"Extracting up to {limit} posts from feed...")

    # Navigate to feed if not already there
    if "feed" not in page.url:
        await page.goto("https://www.linkedin.com/feed/",
                        wait_until="domcontentloaded")
        await asyncio.sleep(3)

    # Scroll to load more posts
    logger.debug("Scrolling to load posts...")
    for scroll_num in range(3):
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.8)")
        await asyncio.sleep(2)
        logger.debug(f"  Scroll {scroll_num + 1}/3 complete")

    # Wait for posts to render
    await asyncio.sleep(2)

    # Extract post containers
    posts = []
    try:
        # Try multiple container selectors
        containers = await page.query_selector_all(
            '[data-id^="urn:li:activity"], .feed-shared-update-v2, [data-urn]'
        )
        logger.info(f"Found {len(containers)} post containers on page")

        for idx, container in enumerate(containers[:limit]):
            try:
                # Try multiple author selectors
                author_el = None
                author_selectors = [
                    ".update-components-actor__name",
                    ".feed-shared-actor__name",
                    ".update-components-actor__title",
                    '[data-test-id="main-feed-activity-card__entity-lockup"] '
                    'span[aria-hidden="true"]',
                    '.app-aware-link span[aria-hidden="true"]'
                ]

                for selector in author_selectors:
                    author_el = await container.query_selector(selector)
                    if author_el:
                        break

                # Try multiple text selectors
                text_el = None
                text_selectors = [
                    '.feed-shared-update-v2__description',
                    '.feed-shared-text',
                    '.break-words',
                    '[data-test-id="main-feed-activity-card__commentary"]',
                    '.feed-shared-inline-show-more-text'
                ]

                for selector in text_selectors:
                    text_el = await container.query_selector(selector)
                    if text_el:
                        break

                if author_el and text_el:
                    author_text = (await author_el.inner_text()).strip()
                    post_text = (await text_el.inner_text()).strip()

                    # Skip empty posts
                    if not post_text:
                        logger.debug(f"  Post {idx + 1}: Skipped (empty text)")
                        continue

                    posts.append({
                        "author": author_text,
                        "text": post_text,
                    })
                    logger.debug(f"  Post {idx + 1}: "
                                 f"Extracted from {author_text[:30]}...")
                else:
                    logger.debug(f"  Post {idx + 1}: "
                                 f"Skipped (author={author_el is not None}, "
                                 f"text={text_el is not None})")

            except Exception as e:
                logger.debug(f"  Post {idx + 1}: Error - {e}")
                continue

        logger.info(f"Successfully extracted {len(posts)} posts")
        return posts

    except Exception as e:
        logger.error(f"Failed to extract posts: {e}")
        return []


async def get_authenticated_context(playwright):
    """
    Helper function used to create or reuse a persistent browser context
    with anti-detection measures.
    This maintains cookies and login state between runs.
    """
    logger.info("Creating persistent browser context...")

    context = await playwright.chromium.launch_persistent_context(
        user_data_dir=str(USER_DATA_DIR),
        headless=False,
        slow_mo=100,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--disable-setuid-sandbox",
        ],
        ignore_default_args=['--enable-automation'],
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/131.0.0.0 Safari/537.36',
    )

    # Apply stealth JavaScript to all existing pages
    for page in context.pages:
        await _apply_stealth(page=page)

    # Apply stealth to new pages - properly await the coroutine
    async def apply_stealth_handler(page):
        await _apply_stealth(page)

    context.on("page", apply_stealth_handler)

    logger.info("Browser context ready with anti-detection")
    return context


async def _handle_verification_if_needed(
        page: Page,
        max_wait_seconds: int):
    """
    Handle 2FA, email verification, or other challenges
    """
    current_url = page.url

    # Check if we're on a verification/challenge page
    keywords = ["checkpoint", "challenge", "verify"]
    if any(keyword in current_url for keyword in keywords):
        logger.warning("LinkedIn requires verification")
        logger.warning("Please complete verification in the browser window")
        logger.warning(f"Waiting up to {max_wait_seconds} seconds...")

        try:
            # Wait for redirect to feed after verification
            timeout_ms = max_wait_seconds * 1000
            await page.wait_for_url("**/feed/**", timeout=timeout_ms)
            logger.info("Verification completed successfully")
        except Exception as e:
            logger.error(f"Verification timeout or failed: {e}")
            raise Exception("LinkedIn verification required but not completed")


async def login(
        page: Page,
        max_wait_seconds: int = 300,
        use_google_sso: bool = False):
    """
    Helper function used to login to LinkedIn - handles multiple authentication
    scenarios:
    1. Already logged in (via cookies)
    2. Regular email/password login
    3. Google SSO
    4. 2FA/verification challenges
    """
    logger.info("Checking LinkedIn authentication status...")

    # First, check if already logged in by going to feed
    await page.goto("https://www.linkedin.com/feed/",
                    wait_until="domcontentloaded")
    await asyncio.sleep(3)  # Give it time to load

    # If we're on the feed page, we're already logged in
    if "feed" in page.url:
        logger.info("Already logged in to LinkedIn")
        return

    logger.info("Not logged in, initiating login process...")

    # Navigate to login page if not already there
    if "login" not in page.url:
        await page.goto("https://www.linkedin.com/login")
        await page.wait_for_load_state("networkidle")

    # Check if we have credentials in environment
    email = os.getenv("LINKEDIN_EMAIL")
    password = os.getenv("LINKEDIN_PASSWORD")

    if email and password:
        logger.info("Using email/password authentication")
        await _login_with_credentials(
            page=page,
            email=email,
            password=password)
    elif use_google_sso:
        logger.info("Using Google SSO")
        await _login_with_google_sso(page=page)
    else:
        logger.warning("No credentials found. Waiting for manual login...")
        await _wait_for_manual_login(
            page=page,
            max_wait_seconds=max_wait_seconds)

    # Check for verification challenges
    await _handle_verification_if_needed(page, max_wait_seconds)

    logger.info("Successfully authenticated to LinkedIn")


async def _login_with_credentials(
        page: Page,
        email: str,
        password: str,
        wait_seconds: int = 45):
    """
    Helper function used to perform login with email and password
    """
    try:
        # Fill in credentials
        wait_ms = wait_seconds * 1000
        await page.fill("#username", email, timeout=wait_ms)
        await asyncio.sleep(0.5)

        await page.fill("#password", password, timeout=wait_ms)
        await asyncio.sleep(0.5)

        # Click sign in
        await page.click('button[type="submit"]')
        # Wait for navigation with longer timeout
        await asyncio.sleep(5)

        logger.info("Credentials submitted")

    except Exception as e:
        logger.error(f"Error during credential login: {e}")
        raise


async def _login_with_google_sso(page: Page):
    """
    Perform login with Google SSO
    """
    try:
        # Get Google OAuth2 credentials
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

        if not all([client_id, client_secret, redirect_uri]):
            raise ValueError("Missing Google OAuth2 credentials")

        # Build Google OAuth2 URL
        auth_url = (
            "https://accounts.google.com/o/oauth2/auth?client_id="
            f"{client_id}&response_type=code&redirect_uri="
            f"{redirect_uri}&scope=openid+email+profile&access_type=offline"
        )

        # Navigate to Google login
        await page.goto(auth_url)
        logger.info("Initiated Google SSO login")

        # Wait for redirect back with code
        await page.wait_for_url("**/callback?code=**")

        # Extract code from URL
        current_url = page.url
        code = current_url.split("code=")[1].split("&")[0]

        # Exchange code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }

        # Make token request
        async with aiohttp.ClientSession() as session:
            async with session.post(token_url, data=payload) as resp:
                tokens = await resp.json()

                # Store tokens securely
                # TODO: Implement secure token storage
                logger.info("Google SSO login successful")
                return tokens

    except Exception as e:
        logger.error(f"Error during Google SSO login: {e}")
        raise


async def _wait_for_manual_login(
        page: Page,
        max_wait_seconds: int):
    """
    Helper function used to wait for user to log in manually.
    """
    logger.info("\n" + "="*60)
    logger.info("MANUAL LOGIN REQUIRED")
    logger.info("="*60)
    logger.info("Please log in to LinkedIn in the browser window.")
    logger.info("You can use:")
    logger.info("  - Email/password")
    logger.info("  - Google sign-in")
    logger.info("  - Any other authentication method")
    logger.info(f"Timeout: {max_wait_seconds} seconds")
    logger.info("="*60 + "\n")

    try:
        # Wait for successful login (user reaches feed page)
        await page.wait_for_url("**/feed/**", timeout=max_wait_seconds * 1000)
        logger.info("Manual login detected!")
    except Exception as e:
        logger.error(f"Manual login timeout: {e}")
        mw = max_wait_seconds
        raise Exception(f"Login not completed within {mw} seconds")


async def test_login():
    """
    Test function to verify login works
    Run this separately: python -c "import asyncio;
    from li_ui_actions import test_login; asyncio.run(test_login())"
    """
    async with async_playwright() as p:
        context = await get_authenticated_context(p)

        try:
            pages = context.pages
            page = pages[0] if pages else await context.new_page()

            await login(page=page, max_wait_seconds=300)

            print("Login test successful!")
            print("Browser will stay open for 10 seconds for verification...")
            await asyncio.sleep(10)

        finally:
            await context.close()


if __name__ == "__main__":
    # Run test if executed directly
    asyncio.run(test_login())
