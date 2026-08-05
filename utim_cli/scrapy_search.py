"""
Scrapy-based web scraping enhancement for the web_search tool.
Provides robust, async-capable scraping with proper HTTP semantics.
"""

import asyncio
import os
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ScrapedContent:
    """Container for scraped page content."""
    url: str
    title: str
    text: str
    error: Optional[str] = None


async def scrape_urls_with_playwright(urls: List[str], use_js: bool = False, timeout: int = 10) -> Dict[str, str]:
    """
    Scrape URLs using Scrapy with optional Playwright for JavaScript rendering.
    
    Args:
        urls: List of URLs to scrape
        use_js: Whether to use Playwright for JavaScript-heavy sites
        timeout: Request timeout in seconds
    
    Returns:
        Dictionary mapping URL to scraped text content
    """
    from scrapy import Spider, Request
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings
    from scrapy.utils.log import configure_logging
    
    results = {}
    
    if use_js and len(urls) > 0:
        # Use Playwright for JS rendering
        return await _scrape_with_playwright(urls, timeout)
    else:
        # Use regular Scrapy for static content
        return await _scrape_static(urls, timeout)


async def _scrape_with_playwright(urls: List[str], timeout: int) -> Dict[str, str]:
    """Scrape URLs using Playwright for JavaScript rendering."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        # Fallback to static scraping if Playwright not available
        return await _scrape_static(urls, timeout)
    
    results = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
        
        for url in urls:
            try:
                page = await context.new_page()
                await page.goto(url, wait_until="networkidle", timeout=timeout * 1000)
                content = await page.content()
                
                # Extract text content
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                    script.decompose()
                
                text = soup.get_text(separator='\n', strip=True)
                # Clean up whitespace
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                results[url] = '\n'.join(lines)[:6000]
                
                await page.close()
            except Exception as e:
                results[url] = f"Error: {str(e)}"
        
        await context.close()
        await browser.close()
    
    return results


async def _scrape_static(urls: List[str], timeout: int) -> Dict[str, str]:
    """Scrape URLs using standard Scrapy (no JavaScript)."""
    import shutil
    
    # Check if scrapy-playwright is available
    use_playwright = shutil.which('playwright') is not None
    
    # Create a temporary Scrapy project settings
    from scrapy.settings import Settings
    
    settings = Settings()
    settings.set('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    settings.set('ROBOTSTXT_OBEY', True)
    settings.set('DOWNLOAD_TIMEOUT', timeout)
    settings.set('CONCURRENT_REQUESTS', min(len(urls), 8))
    settings.set('CONCURRENT_REQUESTS_PER_DOMAIN', 2)
    settings.set('RETRY_TIMES', 2)
    settings.set('LOG_LEVEL', 'ERROR')
    
    # Configure Playwright if available
    if use_playwright:
        settings.set('PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT', timeout * 1000)
    
    # Import here to avoid issues if not installed
    try:
        from scrapy.crawler import CrawlerRunner
        from twisted.internet import asyncioreactor
        asyncioreactor.install()
    except ImportError:
        # Fall back to simple requests if Scrapy has issues
        return _fallback_requests_scraping(urls, timeout)
    
    # Create inline spider
    from scrapy import Spider
    from itemadapter import ItemAdapter
    
    class InlineSpider(Spider):
        name = 'inline_spider'
        
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.results = {}
            self.urls_to_scrape = urls
        
        def start_requests(self):
            for url in self.urls_to_scrape:
                yield Request(url=url, callback=self.parse, errback=self.errback)
        
        def parse(self, response):
            # Extract text with BeautifulSoup
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove unwanted elements
                for elem in soup(["script", "style", "nav", "header", "footer", "aside"]):
                    elem.decompose()
                
                text = soup.get_text(separator='\n', strip=True)
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                self.results[response.url] = '\n'.join(lines)[:6000]
            except Exception as e:
                self.results[response.url] = f"Parse error: {str(e)}"
            
            yield {'url': response.url}
        
        def errback(self, failure):
            self.results[failure.request.url] = f"Error: {str(failure.value)}"
    
    # Run the spider
    from twisted.internet import reactor
    from scrapy.crawler import CrawlerRunner
    
    runner = CrawlerRunner(settings)
    spider = InlineSpider()
    
    try:
        d = runner.crawl(spider)
        d.addBoth(lambda _: reactor.stop())
        reactor.run()
    except Exception:
        # Fallback if reactor issues
        return _fallback_requests_scraping(urls, timeout)
    
    return spider.results or _fallback_requests_scraping(urls, timeout)


def _fallback_requests_scraping(urls: List[str], timeout: int) -> Dict[str, str]:
    """Fallback to requests-based scraping if Scrapy fails."""
    import requests
    import re
    import html as html_lib
    
    results = {}
    
    for url in urls:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                html_content = r.text
                # Remove scripts, styles
                html_content = re.sub(r'<(script|style).*?>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
                # Remove html tags
                text = re.sub(r'<.*?>', ' ', html_content)
                text = html_lib.unescape(text)
                # Format whitespace
                lines = [l.strip() for l in text.splitlines() if l.strip()]
                results[url] = '\n'.join(lines)[:6000]
        except Exception as e:
            results[url] = f"Error: {str(e)}"
    
    return results


def enhanced_scrape_urls(urls: List[str], use_js: bool = False, timeout: int = 10) -> Dict[str, str]:
    """
    Synchronous wrapper for scrape_urls_with_playwright.
    
    This is the main entry point used by web_search.
    """
    try:
        # Try async approach first
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If event loop is already running, use a new one
            return asyncio.run(scrape_urls_with_playwright(urls, use_js, timeout))
        else:
            return loop.run_until_complete(scrape_urls_with_playwright(urls, use_js, timeout))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(scrape_urls_with_playwright(urls, use_js, timeout))
    except Exception:
        # Fallback to sync requests
        return _fallback_requests_scraping(urls, timeout)