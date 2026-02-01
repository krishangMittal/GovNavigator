"""
municode_scraper.py - Scrapes municipal code from Municode.com

=== WHAT IS WEB SCRAPING? ===
Web scraping is automatically extracting data from websites.
Playwright controls a real browser to handle JavaScript-rendered content.

=== KEY LEARNING: ITERATIVE DEVELOPMENT ===
Scraping is trial and error - you try, inspect results, adjust, repeat.
"""

import asyncio
import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout
from bs4 import BeautifulSoup


class MunicodeScraper:
    """
    Scrapes municipal ordinances from Municode.com.

    === CLASS EXPLANATION ===
    A class bundles data and functions together.
    - __init__: Sets up the object when created
    - Methods: Functions that operate on the object's data
    - self: Reference to the current instance
    """

    def __init__(self, jurisdiction: str = "wi/madison"):
        """
        Initialize the scraper.

        Args:
            jurisdiction: The state/city path (e.g., "wi/madison")
        """
        self.jurisdiction = jurisdiction
        self.base_url = f"https://library.municode.com/{jurisdiction}/codes/code_of_ordinances"

        # Will be set when browser starts
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self._playwright = None

        # Output directory for scraped data
        self.output_dir = Path("data/raw")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Track scraped URLs to avoid duplicates
        self.scraped_urls: set[str] = set()

    async def start_browser(self):
        """
        Launch the browser.

        === ASYNC/AWAIT EXPLANATION ===
        - async def: This function can pause and resume
        - await: Pause here until the async operation completes
        - This lets us do other things while waiting for slow operations
        """
        print("Starting browser...")

        self._playwright = await async_playwright().start()

        self.browser = await self._playwright.chromium.launch(
            headless=True  # Set False to see the browser window
        )

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
        )

        self.page = await context.new_page()
        self.page.set_default_timeout(30000)

        print("Browser started!")

    async def close_browser(self):
        """Clean up browser resources."""
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        print("Browser closed.")

    async def wait_for_content(self):
        """Wait for JavaScript to load content."""
        try:
            await self.page.wait_for_selector(
                ".document-frame, .chunk-content, #documentContent, article",
                timeout=10000
            )
            await asyncio.sleep(1)
        except PlaywrightTimeout:
            print("  Content load timeout, continuing...")

    async def get_toc_links(self) -> list[dict]:
        """
        Get all section links from the table of contents.

        Returns:
            List of dicts with 'title' and 'url' keys
        """
        print(f"Loading: {self.base_url}")

        await self.page.goto(self.base_url, wait_until="domcontentloaded")
        await self.wait_for_content()

        html = await self.page.content()
        soup = BeautifulSoup(html, "lxml")

        links = []

        # Find all links with nodeId (Municode's internal navigation)
        for a_tag in soup.select("a[href*='nodeId=']"):
            href = a_tag.get("href", "")
            text = a_tag.get_text(strip=True)

            # Skip navigation elements
            if not text or len(text) < 3:
                continue
            if text.lower() in ["expand", "collapse", "next", "previous", "share"]:
                continue

            # Build full URL
            if href.startswith("/"):
                full_url = f"https://library.municode.com{href}"
            elif href.startswith("http"):
                full_url = href
            else:
                full_url = urljoin(self.base_url, href)

            if full_url not in self.scraped_urls:
                links.append({"title": text[:200], "url": full_url})
                self.scraped_urls.add(full_url)

        print(f"Found {len(links)} unique links")
        return links

    async def scrape_section_content(self, url: str) -> Optional[dict]:
        """
        Scrape a single ordinance section.

        Args:
            url: URL of the section to scrape

        Returns:
            Dict with section data, or None if failed
        """
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
            await self.wait_for_content()

            html = await self.page.content()
            soup = BeautifulSoup(html, "lxml")

            # === EXTRACTION STRATEGY ===
            # Try multiple selectors since website structure varies
            content_text = ""

            # Try main content area
            content_area = soup.select_one(".document-frame, #documentContent")
            if content_area:
                for nav in content_area.select("nav, .toolbar, .share-button"):
                    nav.decompose()
                content_text = content_area.get_text(separator="\n", strip=True)

            # Fallback: chunk content
            if not content_text or len(content_text) < 100:
                chunks = soup.select(".chunk-content")
                if chunks:
                    content_text = "\n\n".join(
                        c.get_text(separator="\n", strip=True) for c in chunks
                    )

            # Fallback: any main element
            if not content_text or len(content_text) < 100:
                main = soup.select_one("article, main, .content")
                if main:
                    content_text = main.get_text(separator="\n", strip=True)

            if not content_text or len(content_text) < 50:
                return None

            # === IMPROVED EXTRACTION ===
            # Municode content often starts with "3.02 - TITLE NAME" format
            # Let's parse section number and title from the content itself

            section_number = ""
            title = ""

            # Pattern to match "3.02 - CONTINUITY OF GOVERNMENT" at start of content
            # or "CHAPTER 28 - ZONING CODE" format
            section_title_pattern = r'^[\s\n]*(\d+\.?\d*(?:\(\d+\))?(?:\([a-z]\))?)\s*[-\.]\s*([A-Z][A-Z\s,\-\(\)]+?)(?:\.|[\n])'
            chapter_pattern = r'^[\s\n]*(CHAPTER\s+\d+)\s*[-\.]\s*([A-Z][A-Z\s,\-]+?)(?:\.|[\n])'

            # Try section pattern first (e.g., "3.02 - CONTINUITY OF GOVERNMENT")
            match = re.search(section_title_pattern, content_text[:500])
            if match:
                section_number = match.group(1)
                title = f"{section_number} - {match.group(2).strip()}"
            else:
                # Try chapter pattern (e.g., "CHAPTER 28 - ZONING CODE")
                match = re.search(chapter_pattern, content_text[:500], re.IGNORECASE)
                if match:
                    section_number = match.group(1)
                    title = f"{match.group(1)} - {match.group(2).strip()}"
                else:
                    # Fallback: just find any section number
                    simple_pattern = r'(\d+\.\d+(?:\(\d+\))?)'
                    match = re.search(simple_pattern, content_text[:300])
                    if match:
                        section_number = match.group(1)

            # If still no title, try HTML elements
            if not title:
                title_elem = soup.select_one("h1, .document-title, .chunk-title")
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    # Don't use generic titles
                    if title.lower() in ["madison, wi", "code of ordinances", ""]:
                        title = f"Section {section_number}" if section_number else "Untitled"

            # Extract chapter from breadcrumb
            chapter = ""
            breadcrumb = soup.select_one(".breadcrumb, [class*='breadcrumb']")
            if breadcrumb:
                chapter = breadcrumb.get_text(strip=True)

            # Clean content
            content_text = re.sub(r'\n{3,}', '\n\n', content_text)
            content_text = re.sub(r' {2,}', ' ', content_text)

            return {
                "section_number": section_number,
                "title": title[:300] if title else "Untitled",
                "chapter": chapter[:200],
                "content": content_text[:15000],
                "url": url,
                "jurisdiction": "Madison, WI"
            }

        except Exception as e:
            print(f"  Error: {e}")
            return None

    async def scrape_all(self, max_sections: int = 50) -> list[dict]:
        """
        Main scraping function.

        Args:
            max_sections: Maximum sections to scrape

        Returns:
            List of scraped ordinance dicts
        """
        ordinances = []

        try:
            await self.start_browser()

            # Step 1: Get TOC
            print("\n=== Step 1: Getting Table of Contents ===")
            toc_links = await self.get_toc_links()

            if not toc_links:
                print("No links found!")
                return []

            # Step 2: Scrape sections
            print(f"\n=== Step 2: Scraping up to {max_sections} sections ===")

            scraped_count = 0
            for i, link in enumerate(toc_links):
                if scraped_count >= max_sections:
                    break

                print(f"[{scraped_count + 1}/{max_sections}] {link['title'][:50]}...")

                result = await self.scrape_section_content(link["url"])

                if result and len(result.get("content", "")) > 100:
                    ordinances.append(result)
                    scraped_count += 1
                    print(f"  -> Got {len(result['content'])} chars")

                await asyncio.sleep(0.5)  # Be nice to the server

            print(f"\nSuccessfully scraped {len(ordinances)} ordinances!")

        finally:
            await self.close_browser()

        return ordinances

    def save_results(self, ordinances: list[dict], filename: str = "madison_ordinances.json"):
        """Save results to JSON file."""
        if not ordinances:
            print("No ordinances to save.")
            return None

        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ordinances, f, indent=2, ensure_ascii=False)

        print(f"\nSaved {len(ordinances)} ordinances to {output_path}")

        # Show preview
        print("\nSample of scraped content:")
        for i, ord in enumerate(ordinances[:3]):
            print(f"\n{i+1}. {ord['title'][:60]}")
            print(f"   Section: {ord['section_number'] or 'N/A'}")
            print(f"   Preview: {ord['content'][:100]}...")

        return output_path


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Madison Municipal Code Scraper")
    print("=" * 60)

    scraper = MunicodeScraper("wi/madison")
    ordinances = await scraper.scrape_all(max_sections=30)

    if ordinances:
        scraper.save_results(ordinances)
    else:
        print("\nNo substantial content found.")
        print("The website structure may have changed.")


if __name__ == "__main__":
    asyncio.run(main())
