"""
scrape_all_chapters.py - Scrape ALL Madison ordinance chapters

This scraper:
1. Gets list of all chapters from the table of contents
2. For each chapter, loads the page and extracts all content
3. Splits content into individual sections
4. Saves everything as separate section documents

This creates the complete dataset for our search index.
"""

import asyncio
import json
import re
from pathlib import Path

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup


# UI text to remove from content
UI_STRINGS_TO_REMOVE = [
    "Share Link",
    "Print",
    "Download (docx)",
    "Download (Docx) of sections",
    "Email",
    "Compare",
    "Share Link to section",
    "Print section",
    "Email section",
    "Compare versions",
    "Loading, please wait",
    "Loading complete",
]


def clean_content(text: str) -> str:
    """Remove UI elements and clean up content."""
    # Remove known UI strings
    for ui_string in UI_STRINGS_TO_REMOVE:
        text = text.replace(ui_string, "")

    # Remove multiple newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    # Remove leading/trailing whitespace from lines
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


def split_into_sections(full_content: str, chapter_name: str, chapter_url: str) -> list[dict]:
    """
    Split a chapter's full content into individual sections.

    Pattern matches: "1.01 - TITLE", "28.04(1) - TITLE"
    """
    sections = []

    # Pattern for section headers
    # Matches: 1.01, 28.04, 28.04(1), 28.04(1)(a)
    section_pattern = r'(\d+\.\d+(?:\(\d+\))?(?:\([a-z]\))?)\s*[-\.]\s*([A-Z][A-Z0-9\s,\-\(\)\'\"\.;&]+?)(?=\n)'

    matches = list(re.finditer(section_pattern, full_content))

    if not matches:
        # No sections found - return whole chapter as one doc
        return [{
            "section_number": "",
            "title": chapter_name,
            "content": clean_content(full_content),
            "chapter": chapter_name,
            "url": chapter_url
        }]

    for i, match in enumerate(matches):
        section_num = match.group(1)
        section_title = match.group(2).strip().rstrip('.')

        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(full_content)

        section_content = full_content[start_pos:end_pos].strip()
        section_content = clean_content(section_content)

        # Skip if content is too short (likely just a header)
        if len(section_content) < 100:
            continue

        sections.append({
            "section_number": section_num,
            "title": f"{section_num} - {section_title}",
            "content": section_content,
            "chapter": chapter_name,
            "url": chapter_url
        })

    return sections


async def get_chapter_list(page) -> list[dict]:
    """Get list of all chapters from the table of contents."""
    print("Getting chapter list from table of contents...")

    toc_url = "https://library.municode.com/wi/madison/codes/code_of_ordinances"
    await page.goto(toc_url, wait_until="networkidle")
    await asyncio.sleep(3)

    # Try to expand all volume sections to reveal chapters
    print("Expanding volume sections...")
    expand_selectors = [
        "[aria-expanded='false']",
        ".tree-toggle",
        "[class*='expand']",
        ".toggle-btn"
    ]
    for selector in expand_selectors:
        try:
            buttons = await page.query_selector_all(selector)
            for btn in buttons[:30]:  # Expand first 30
                try:
                    if await btn.is_visible():
                        await btn.click()
                        await asyncio.sleep(0.3)
                except:
                    pass
        except:
            pass

    await asyncio.sleep(2)

    html = await page.content()
    soup = BeautifulSoup(html, "lxml")

    chapters = []

    # Find all chapter links in the TOC
    # Municode uses links with nodeId parameter
    for a_tag in soup.select("a[href*='nodeId=']"):
        href = a_tag.get("href", "")
        text = a_tag.get_text(strip=True)

        # Look for chapter patterns - match "CHAPTER 32" anywhere in text
        if re.search(r'CHAPTER\s+\d+', text, re.IGNORECASE):
            if href.startswith("/"):
                full_url = f"https://library.municode.com{href}"
            else:
                full_url = href

            chapters.append({
                "name": text,
                "url": full_url
            })

    # Remove duplicates
    seen = set()
    unique_chapters = []
    for ch in chapters:
        if ch["url"] not in seen:
            seen.add(ch["url"])
            unique_chapters.append(ch)

    # Sort by chapter number
    def get_chapter_num(ch):
        match = re.search(r'CHAPTER\s+(\d+)', ch["name"], re.IGNORECASE)
        return int(match.group(1)) if match else 999

    unique_chapters.sort(key=get_chapter_num)

    print(f"Found {len(unique_chapters)} chapters")
    for ch in unique_chapters:
        print(f"  - {ch['name'][:50]}")

    return unique_chapters


async def scrape_chapter(page, chapter_name: str, chapter_url: str) -> list[dict]:
    """Scrape a single chapter and return its sections."""

    print(f"\n  Loading: {chapter_name[:50]}...")
    await page.goto(chapter_url, wait_until="networkidle")
    await asyncio.sleep(3)

    # Close any modals
    close_selectors = [
        "button[aria-label='Close']",
        ".close-btn",
        "button:has-text('Close')",
        "button:has-text('Skip')",
        "button:has-text('Got it')"
    ]
    for selector in close_selectors:
        try:
            buttons = await page.query_selector_all(selector)
            for btn in buttons:
                if await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.3)
        except:
            pass

    # Wait for content
    try:
        await page.wait_for_selector(".chunk", timeout=10000)
    except:
        pass

    # Scroll to load lazy content
    for _ in range(3):
        await page.evaluate("window.scrollBy(0, 2000)")
        await asyncio.sleep(0.3)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(1)

    # Extract content
    html = await page.content()
    soup = BeautifulSoup(html, "lxml")

    # Remove UI elements
    for selector in ["script", "style", "nav", "header", "footer",
                     ".sidebar", ".toc", ".toolbar", ".modal",
                     "[class*='walkthrough']", "[class*='tooltip']"]:
        for el in soup.select(selector):
            el.decompose()

    # Get content from chunks
    content_parts = []
    chunks = soup.select(".chunk")
    if chunks:
        for chunk in chunks:
            text = chunk.get_text(separator="\n", strip=True)
            if len(text) > 50:
                content_parts.append(text)

    # Fallback to other containers
    if not content_parts:
        for selector in ["#documentBody", ".document-body", "main", "article"]:
            container = soup.select_one(selector)
            if container:
                text = container.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    content_parts.append(text)
                    break

    full_content = "\n\n".join(content_parts)

    if len(full_content) < 200:
        print(f"    [!] Low content: {len(full_content)} chars")
        return []

    # Split into sections
    sections = split_into_sections(full_content, chapter_name, chapter_url)
    print(f"    -> {len(sections)} sections, {len(full_content)} chars total")

    return sections


async def main():
    """Main scraping function."""
    print("=" * 60)
    print("MADISON ORDINANCES - FULL SCRAPE")
    print("=" * 60)

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0"
    )
    page = await context.new_page()
    page.set_default_timeout(60000)

    all_sections = []

    try:
        # Get list of chapters
        chapters = await get_chapter_list(page)

        if not chapters:
            print("No chapters found! Using fallback list...")
            # Fallback: known chapter URLs
            chapters = [
                {"name": "CHAPTER 1 - CONSTRUCTION AND EFFECT", "url": "https://library.municode.com/wi/madison/codes/code_of_ordinances?nodeId=COORMAWIVOICH1--10_CH1COEFORTHPU"},
                {"name": "CHAPTER 3 - GENERAL PROVISIONS", "url": "https://library.municode.com/wi/madison/codes/code_of_ordinances?nodeId=COORMAWIVOICH1--10_CH3GEPR"},
                {"name": "CHAPTER 28 - ZONING", "url": "https://library.municode.com/wi/madison/codes/code_of_ordinances?nodeId=COORMAWIVOICH11--33_CH28ZOCOOR"},
            ]

        print(f"\nScraping {len(chapters)} chapters...")

        for i, chapter in enumerate(chapters):
            print(f"\n[{i+1}/{len(chapters)}] {chapter['name'][:50]}")

            try:
                sections = await scrape_chapter(page, chapter["name"], chapter["url"])
                all_sections.extend(sections)

                # Save progress periodically
                if (i + 1) % 5 == 0:
                    print(f"\n  Checkpoint: {len(all_sections)} sections so far")
                    output_path = Path("data/raw/madison_ordinances_checkpoint.json")
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(all_sections, f, indent=2, ensure_ascii=False)

            except Exception as e:
                print(f"    [ERROR] {e}")
                continue

            # Small delay between chapters
            await asyncio.sleep(1)

        # Save final results
        output_path = Path("data/raw/madison_ordinances_full.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_sections, f, indent=2, ensure_ascii=False)

        print("\n" + "=" * 60)
        print("SCRAPING COMPLETE")
        print("=" * 60)
        print(f"Total sections: {len(all_sections)}")
        print(f"Saved to: {output_path}")

        # Summary by chapter
        chapter_counts = {}
        for section in all_sections:
            ch = section.get("chapter", "Unknown")[:30]
            chapter_counts[ch] = chapter_counts.get(ch, 0) + 1

        print("\nSections per chapter:")
        for ch, count in sorted(chapter_counts.items()):
            print(f"  {ch}: {count}")

    finally:
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    asyncio.run(main())
