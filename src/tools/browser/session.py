"""
Browser session manager for web automation.

Manages browser lifecycle, session state, and resource cleanup.
Supports multiple concurrent sessions with isolated browser contexts.
"""

import asyncio

# Global session manager singleton
_session_manager = None


def get_session_manager() -> "BrowserSessionManager":
    """Get or create the global session manager singleton."""
    global _session_manager
    if _session_manager is None:
        _session_manager = BrowserSessionManager(
            options=BrowserOptions(headless=True, timeout=30000)
        )
    return _session_manager


from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from src.utils.logger import get_logger

# Get logger with proper name binding
logger = get_logger(__name__)


# ======================================================================
# Configuration Models
# ======================================================================


class BrowserOptions(BaseModel):
    """Configuration options for browser instances."""

    headless: bool = Field(
        default=True,
        description="Run browser in headless mode (no GUI)",
    )
    user_agent: Optional[str] = Field(
        default=None,
        description="Custom user agent string",
    )
    viewport_width: int = Field(
        default=1280,
        description="Browser viewport width in pixels",
    )
    viewport_height: int = Field(
        default=720,
        description="Browser viewport height in pixels",
    )
    timeout: int = Field(
        default=30000,
        description="Default timeout for operations (ms)",
    )
    slow_mo: int = Field(
        default=0,
        description="Slow down operations by specified ms (useful for debugging)",
    )


class SessionState(BaseModel):
    """Serializable session state for persistence."""

    session_id: str = Field(..., description="Unique session identifier")
    cookies: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Browser cookies",
    )
    localStorage: dict[str, str] = Field(
        default_factory=dict,
        description="Local storage data",
    )
    sessionStorage: dict[str, str] = Field(
        default_factory=dict,
        description="Session storage data",
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Session creation timestamp",
    )
    last_accessed: datetime = Field(
        default_factory=datetime.now,
        description="Last access timestamp",
    )


# ======================================================================
# Browser Session
# ======================================================================


@dataclass
class BrowserSession:
    """Represents an isolated browser session.

    Each session has its own browser context, cookies, and storage.
    """

    session_id: str
    browser: Any  # playwright.async_api.AsyncBrowser
    context: Any  # playwright.async_api.AsyncBrowserContext
    page: Any  # playwright.async_api.AsyncPage
    options: BrowserOptions
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)

    async def navigate(self, url: str, wait_until: str = "load") -> dict[str, Any]:
        """Navigate to a URL.

        Args:
            url: The URL to navigate to
            wait_until: When to consider navigation succeeded
                ("load", "domcontentloaded", "networkidle")

        Returns:
            Dict with navigation result and page info
        """
        self.last_accessed = datetime.now()
        logger.info(f"[{self.session_id}] Navigating to {url}")

        try:
            response = await self.page.goto(
                url,
                wait_until=wait_until,
                timeout=self.options.timeout,
            )

            return {
                "success": True,
                "url": self.page.url,
                "status": response.status if response else None,
                "title": await self.page.title(),
                "session_id": self.session_id,
            }
        except Exception as e:
            logger.error(f"[{self.session_id}] Navigation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "url": url,
                "session_id": self.session_id,
            }

    async def snapshot(self) -> dict[str, Any]:
        """Get page content for element recognition.

        Returns structured elements including article/blog content.

        Returns:
            Dict with page HTML content and structured elements
        """
        self.last_accessed = datetime.now()

        try:
            # Get page content as HTML
            content = await self.page.content()

            # Get page title
            title = await self.page.title()

            # Extract structured elements from the page
            elements = await self.page.evaluate("""() => {
                const result = {
                    articles: [],
                    links: [],
                    headings: [],
                    meta: {}
                };

                // Find article/post containers (common blog patterns)
                const articleSelectors = [
                    'article',
                    '[class*="post"]',
                    '[class*="entry"]',
                    '[class*="article"]',
                    '[class*="item"]',
                    '[class*="card"]'
                ];

                const articles = new Set();
                articleSelectors.forEach(selector => {
                    document.querySelectorAll(selector).forEach(el => {
                        const articlesInEl = el.querySelectorAll('article, [class*="post"], [class*="entry"]');
                        if (articlesInEl.length === 0) {
                            // This element itself is an article container
                            articles.add(el);
                        }
                    });
                });

                // Extract article details
                articles.forEach(article => {
                    // Find title (h1, h2, h3 or class containing 'title')
                    const titleEl = article.querySelector('h1, h2, h3, [class*="title"], [class*="heading"]');
                    const title = titleEl ? titleEl.textContent.trim().substring(0, 200) : '';

                    // Find link (usually wrapping the title or in the article)
                    const linkEl = article.querySelector('a[href]') || article.closest('a[href]');
                    const url = linkEl ? linkEl.href : '';

                    // Find excerpt/intro (p with class containing 'excerpt', 'summary', 'intro', 'desc', or first p)
                    let excerpt = '';
                    const excerptEl = article.querySelector('p[class*="excerpt"], p[class*="summary"], p[class*="intro"], p[class*="desc"]') ||
                                     article.querySelector('p');
                    if (excerptEl) {
                        excerpt = excerptEl.textContent.trim().substring(0, 500);
                    }

                    // Get CSS selector for this article
                    let selector = article.tagName.toLowerCase();
                    if (article.id) {
                        selector += '#' + article.id;
                    } else if (article.className) {
                        const classes = article.className.split(' ').filter(c => c && !c.includes('post') && !c.includes('entry')).slice(0, 2);
                        if (classes.length > 0) {
                            selector += '.' + classes.join('.');
                        }
                    }

                    result.articles.push({
                        title,
                        url,
                        excerpt,
                        selector
                    });
                });

                // Get all standalone links (not in articles)
                document.querySelectorAll('a[href]').forEach(el => {
                    const isInArticle = el.closest('article, [class*="post"], [class*="entry"]');
                    if (!isInArticle && el.textContent.trim()) {
                        result.links.push({
                            text: el.textContent.trim().substring(0, 100),
                            href: el.href,
                            selector: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') + (el.className ? '.' + el.className.split(' ')[0] : '')
                        });
                    }
                });

                // Get all headings (h1-h6)
                document.querySelectorAll('h1, h2, h3, h4, h5, h6').forEach(el => {
                    result.headings.push({
                        tag: el.tagName,
                        text: el.textContent.trim().substring(0, 200),
                        selector: el.tagName.toLowerCase() + (el.id ? '#' + el.id : '')
                    });
                });

                // Meta info
                result.meta = {
                    title: document.title,
                    url: window.location.href,
                    description: document.querySelector('meta[name="description"]')?.content || '',
                    keywords: document.querySelector('meta[name="keywords"]')?.content || ''
                };

                return result;
            }""")

            return {
                "success": True,
                "html": content,
                "elements": elements,
                "url": self.page.url,
                "title": title,
            }
        except Exception as e:
            logger.error(f"[{self.session_id}] Snapshot failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def screenshot(
        self,
        path: Optional[str] = None,
        full_page: bool = False,
    ) -> dict[str, Any]:
        """Take a screenshot of the current page.

        Args:
            path: Optional path to save screenshot
            full_page: Capture full scrollable page

        Returns:
            Dict with screenshot result and base64 data
        """
        self.last_accessed = datetime.now()

        try:
            screenshot = await self.page.screenshot(
                path=path,
                full_page=full_page,
            )

            import base64

            return {
                "success": True,
                "screenshot": base64.b64encode(screenshot).decode(),
                "path": path,
                "url": self.page.url,
            }
        except Exception as e:
            logger.error(f"[{self.session_id}] Screenshot failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def click(
        self,
        selector: str,
        button: str = "left",
        modifiers: list[str] | None = None,
    ) -> dict[str, Any]:
        """Click an element on the page.

        Args:
            selector: CSS selector for the element
            button: Mouse button ("left", "right", "middle")
            modifiers: Modifier keys ("Alt", "Control", "Shift", "Meta")

        Returns:
            Dict with click result
        """
        self.last_accessed = datetime.now()
        logger.info(f"[{self.session_id}] Clicking {selector}")

        try:
            await self.page.click(
                selector,
                button=button,
                modifiers=modifiers or [],
                timeout=self.options.timeout,
            )

            return {
                "success": True,
                "selector": selector,
            }
        except Exception as e:
            logger.error(f"[{self.session_id}] Click failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "selector": selector,
            }

    async def type_text(
        self,
        selector: str,
        text: str,
        clear: bool = True,
    ) -> dict[str, Any]:
        """Type text into an input element.

        Args:
            selector: CSS selector for the element
            text: Text to type
            clear: Clear existing text before typing

        Returns:
            Dict with typing result
        """
        self.last_accessed = datetime.now()
        logger.info(f"[{self.session_id}] Typing into {selector}")

        try:
            if clear:
                await self.page.fill(selector, "")
            await self.page.type(selector, text)

            return {
                "success": True,
                "selector": selector,
                "text_length": len(text),
            }
        except Exception as e:
            logger.error(f"[{self.session_id}] Type failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "selector": selector,
            }

    async def fill_form(self, fields: dict[str, str]) -> dict[str, Any]:
        """Fill multiple form fields.

        Args:
            fields: Dict mapping selectors to values

        Returns:
            Dict with fill result for each field
        """
        self.last_accessed = datetime.now()
        logger.info(f"[{self.session_id}] Filling {len(fields)} fields")

        results = {}
        for selector, value in fields.items():
            try:
                await self.page.fill(selector, str(value))
                results[selector] = {"success": True}
            except Exception as e:
                logger.error(f"[{self.session_id}] Failed to fill {selector}: {e}")
                results[selector] = {"success": False, "error": str(e)}

        success_count = sum(1 for r in results.values() if r.get("success"))
        return {
            "success": success_count == len(fields),
            "results": results,
            "filled": success_count,
            "total": len(fields),
        }

    async def wait_for(
        self,
        selector: Optional[str] = None,
        timeout: Optional[int] = None,
    ) -> dict[str, Any]:
        """Wait for an element or timeout.

        Args:
            selector: Optional CSS selector to wait for
            timeout: Timeout in ms (defaults to browser options)

        Returns:
            Dict with wait result
        """
        self.last_accessed = datetime.now()
        timeout = timeout or self.options.timeout

        if selector:
            logger.info(f"[{self.session_id}] Waiting for {selector}")
            try:
                await self.page.wait_for_selector(selector, timeout=timeout)
                return {"success": True, "selector": selector}
            except Exception as e:
                return {
                    "success": False,
                    "error": str(e),
                    "selector": selector,
                }
        else:
            # Just wait for timeout
            await asyncio.sleep(timeout / 1000)
            return {"success": True, "waited_ms": timeout}

    async def evaluate(self, javascript: str) -> dict[str, Any]:
        """Execute JavaScript in the page context.

        Args:
            javascript: JavaScript code to execute

        Returns:
            Dict with evaluation result
        """
        self.last_accessed = datetime.now()
        logger.debug(f"[{self.session_id}] Evaluating JavaScript")

        try:
            result = await self.page.evaluate(javascript)
            return {
                "success": True,
                "result": result,
            }
        except Exception as e:
            logger.error(f"[{self.session_id}] Evaluation failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    async def save_state(self) -> SessionState:
        """Save session state for later restoration.

        Returns:
            SessionState with cookies and storage data
        """
        self.last_accessed = datetime.now()

        # Get cookies
        cookies = await self.context.cookies()

        # Get local storage
        localStorage = await self.page.evaluate(
            "() => JSON.stringify({...localStorage})"
        )

        # Get session storage
        sessionStorage = await self.page.evaluate(
            "() => JSON.stringify({...sessionStorage})"
        )

        return SessionState(
            session_id=self.session_id,
            cookies=cookies,
            localStorage=localStorage,
            sessionStorage=sessionStorage,
            created_at=self.created_at,
            last_accessed=self.last_accessed,
        )

    async def close(self) -> None:
        """Close the browser session and cleanup resources."""
        logger.info(f"[{self.session_id}] Closing session")

        try:
            await self.page.close()
            await self.context.close()
            # Note: Don't close browser here, managed by session manager
        except Exception as e:
            logger.error(f"[{self.session_id}] Error closing session: {e}")


# ======================================================================
# Session Manager
# ======================================================================


class BrowserSessionManager:
    """Manages browser sessions with automatic cleanup.

    Features:
    - Browser pooling and reuse
    - Session isolation with separate contexts
    - Automatic resource cleanup
    - Session timeout management
    """

    def __init__(
        self,
        options: BrowserOptions | None = None,
        max_sessions: int = 10,
        session_timeout: int = 3600,
    ):
        """Initialize the session manager.

        Args:
            options: Default browser options for new sessions
            max_sessions: Maximum number of concurrent sessions
            session_timeout: Session timeout in seconds
        """
        self.options = options or BrowserOptions()
        self.max_sessions = max_sessions
        self.session_timeout = session_timeout

        self._browser: Any = None
        self._sessions: dict[str, BrowserSession] = {}
        self._current_session_id: str | None = None  # Track current session
        self._lock = asyncio.Lock()

        self.logger = get_logger(__name__)

    async def _get_browser(self) -> Any:
        """Get or create browser instance."""
        if self._browser is None:
            from playwright.async_api import async_playwright

            playwright = await async_playwright().start()

            self._browser = await playwright.chromium.launch(
                headless=self.options.headless,
                slow_mo=self.options.slow_mo,
            )

            self.logger.info("Browser launched")

        return self._browser

    async def create_session(
        self,
        session_id: str | None = None,
        options: BrowserOptions | None = None,
    ) -> BrowserSession:
        """Create a new browser session.

        Args:
            session_id: Optional session ID (auto-generated if None)
            options: Optional browser options for this session

        Returns:
            BrowserSession instance

        Raises:
            RuntimeError: If max sessions limit reached
        """
        async with self._lock:
            # Check session limit
            if len(self._sessions) >= self.max_sessions:
                # Clean up expired sessions first
                await self._cleanup_expired_sessions()

                if len(self._sessions) >= self.max_sessions:
                    raise RuntimeError(
                        f"Maximum sessions ({self.max_sessions}) reached"
                    )

            # Generate session ID if not provided
            session_id = session_id or str(uuid4())

            # Get browser
            browser = await self._get_browser()

            # Create isolated context
            context = await browser.new_context(
                viewport={
                    "width": (options or self.options).viewport_width,
                    "height": (options or self.options).viewport_height,
                },
                user_agent=(options or self.options).user_agent,
            )

            # Create page
            page = await context.new_page()
            page.set_default_timeout((options or self.options).timeout)

            # Create session
            session = BrowserSession(
                session_id=session_id,
                browser=browser,
                context=context,
                page=page,
                options=options or self.options,
            )

            self._sessions[session_id] = session
            self._current_session_id = session_id  # Set as current session
            self.logger.info(f"Session created: {session_id}")

            return session

    async def get_session(self, session_id: str) -> BrowserSession | None:
        """Get an existing session by ID.

        Args:
            session_id: Session identifier

        Returns:
            BrowserSession or None if not found
        """
        session = self._sessions.get(session_id)
        if session:
            session.last_accessed = datetime.now()
        return session

    async def get_current_session(self) -> BrowserSession | None:
        """Get the current (most recently used) session.

        Returns:
            BrowserSession or None if no active session
        """
        if self._current_session_id:
            return await self.get_session(self._current_session_id)
        return None

    async def close_session(self, session_id: str) -> bool:
        """Close and remove a session.

        Args:
            session_id: Session identifier

        Returns:
            True if session was closed, False if not found
        """
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                await session.close()
                self.logger.info(f"Session closed: {session_id}")
                return True
            return False

    async def _cleanup_expired_sessions(self) -> int:
        """Clean up sessions that have exceeded the timeout.

        Returns:
            Number of sessions cleaned up
        """
        now = datetime.now()
        expired_ids = []

        for session_id, session in self._sessions.items():
            elapsed = (now - session.last_accessed).total_seconds()
            if elapsed > self.session_timeout:
                expired_ids.append(session_id)

        for session_id in expired_ids:
            await self.close_session(session_id)

        if expired_ids:
            self.logger.info(f"Cleaned up {len(expired_ids)} expired sessions")

        return len(expired_ids)

    async def cleanup_all_sessions(self) -> None:
        """Close all sessions and shutdown browser."""
        async with self._lock:
            # Close all sessions
            for session_id in list(self._sessions.keys()):
                await self.close_session(session_id)

            # Close browser
            if self._browser:
                await self._browser.close()
                self._browser = None
                self.logger.info("Browser closed")

    def list_sessions(self) -> list[str]:
        """List all active session IDs.

        Returns:
            List of session IDs
        """
        return list(self._sessions.keys())

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with cleanup."""
        await self.cleanup_all_sessions()
