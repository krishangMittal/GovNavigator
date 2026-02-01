"""
web_app.py - Web interface for GovNavigator

A glassmorphism UI for searching Madison ordinances.
Run with: uvicorn web_app:app --reload
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from pathlib import Path

from src.search.index import SearchIndex

app = FastAPI(title="GovNavigator")

INDEX_PATH = Path("data/processed/search_index.json")
search_index = None

@app.on_event("startup")
async def load_index():
    global search_index
    if INDEX_PATH.exists():
        search_index = SearchIndex.load(str(INDEX_PATH))
        print(f"Loaded {len(search_index.documents)} documents")


def render_page(content: str, query: str = "") -> str:
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GovNavigator</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            min-height: 100vh;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            color: #fff;
            overflow-x: hidden;
        }}

        /* Animated background orbs */
        .bg-orb {{
            position: fixed;
            border-radius: 50%;
            filter: blur(80px);
            opacity: 0.5;
            z-index: 0;
            animation: float 20s ease-in-out infinite;
        }}

        .orb-1 {{
            width: 600px;
            height: 600px;
            background: linear-gradient(135deg, #667eea, #764ba2);
            top: -200px;
            left: -200px;
        }}

        .orb-2 {{
            width: 500px;
            height: 500px;
            background: linear-gradient(135deg, #f093fb, #f5576c);
            bottom: -150px;
            right: -150px;
            animation-delay: -10s;
        }}

        .orb-3 {{
            width: 300px;
            height: 300px;
            background: linear-gradient(135deg, #4facfe, #00f2fe);
            top: 50%;
            left: 50%;
            animation-delay: -5s;
        }}

        @keyframes float {{
            0%, 100% {{ transform: translate(0, 0) scale(1); }}
            33% {{ transform: translate(30px, -30px) scale(1.05); }}
            66% {{ transform: translate(-20px, 20px) scale(0.95); }}
        }}

        .container {{
            position: relative;
            z-index: 1;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px 20px;
        }}

        header {{
            text-align: center;
            margin-bottom: 40px;
        }}

        .logo {{
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(135deg, #fff 0%, #a8c0ff 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 8px;
        }}

        .tagline {{
            font-size: 1rem;
            font-weight: 300;
            color: rgba(255,255,255,0.7);
            letter-spacing: 0.5px;
        }}

        /* Glass card */
        .glass {{
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            box-shadow:
                0 8px 32px rgba(0, 0, 0, 0.3),
                inset 0 1px 0 rgba(255, 255, 255, 0.1);
        }}

        .search-card {{
            padding: 32px;
            margin-bottom: 24px;
        }}

        .search-form {{
            display: flex;
            gap: 12px;
        }}

        .search-input {{
            flex: 1;
            padding: 18px 24px;
            font-size: 1rem;
            font-family: 'Inter', sans-serif;
            font-weight: 400;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 16px;
            color: #fff;
            outline: none;
            transition: all 0.3s ease;
        }}

        .search-input::placeholder {{
            color: rgba(255, 255, 255, 0.4);
        }}

        .search-input:focus {{
            background: rgba(255, 255, 255, 0.12);
            border-color: rgba(255, 255, 255, 0.3);
            box-shadow: 0 0 0 4px rgba(102, 126, 234, 0.2);
        }}

        .search-btn {{
            padding: 18px 32px;
            font-size: 1rem;
            font-family: 'Inter', sans-serif;
            font-weight: 600;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            white-space: nowrap;
        }}

        .search-btn:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.4);
        }}

        .search-btn:active {{
            transform: translateY(0);
        }}

        .examples {{
            margin-top: 24px;
            padding-top: 24px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .examples-label {{
            font-size: 0.8rem;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.5);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }}

        .example-tags {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .example-tag {{
            padding: 10px 18px;
            font-size: 0.85rem;
            font-weight: 500;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 100px;
            color: rgba(255, 255, 255, 0.8);
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
        }}

        .example-tag:hover {{
            background: rgba(255, 255, 255, 0.15);
            border-color: rgba(255, 255, 255, 0.2);
            color: #fff;
        }}

        /* Results */
        .results-card {{
            overflow: hidden;
        }}

        .results-header {{
            padding: 20px 28px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .results-header h2 {{
            font-size: 0.9rem;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.7);
        }}

        .result-item {{
            padding: 24px 28px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            transition: background 0.2s ease;
        }}

        .result-item:hover {{
            background: rgba(255, 255, 255, 0.03);
        }}

        .result-item:last-child {{
            border-bottom: none;
        }}

        .result-title {{
            font-size: 1.05rem;
            font-weight: 600;
            color: #fff;
            margin-bottom: 10px;
            line-height: 1.4;
        }}

        .result-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 14px;
            font-size: 0.8rem;
        }}

        .badge {{
            padding: 5px 12px;
            border-radius: 8px;
            font-weight: 500;
        }}

        .badge-section {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }}

        .badge-chapter {{
            background: rgba(255, 255, 255, 0.1);
            color: rgba(255, 255, 255, 0.7);
        }}

        .badge-score {{
            background: rgba(34, 197, 94, 0.2);
            color: #4ade80;
        }}

        .result-excerpt {{
            font-size: 0.9rem;
            font-weight: 400;
            color: rgba(255, 255, 255, 0.6);
            line-height: 1.7;
            margin-bottom: 14px;
        }}

        .result-link {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85rem;
            font-weight: 500;
            color: #a8c0ff;
            text-decoration: none;
            transition: color 0.2s ease;
        }}

        .result-link:hover {{
            color: #fff;
        }}

        .result-link svg {{
            width: 16px;
            height: 16px;
        }}

        .no-results {{
            padding: 60px 28px;
            text-align: center;
        }}

        .no-results h3 {{
            font-size: 1.1rem;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.8);
            margin-bottom: 8px;
        }}

        .no-results p {{
            font-size: 0.9rem;
            color: rgba(255, 255, 255, 0.5);
        }}

        .stats {{
            text-align: center;
            padding: 30px;
            font-size: 0.8rem;
            color: rgba(255, 255, 255, 0.4);
        }}

        footer {{
            text-align: center;
            padding: 20px;
            font-size: 0.8rem;
            color: rgba(255, 255, 255, 0.3);
        }}

        footer a {{
            color: rgba(255, 255, 255, 0.5);
            text-decoration: none;
        }}

        footer a:hover {{
            color: #fff;
        }}

        @media (max-width: 600px) {{
            .logo {{
                font-size: 2rem;
            }}

            .search-form {{
                flex-direction: column;
            }}

            .search-btn {{
                width: 100%;
            }}

            .result-meta {{
                flex-direction: column;
                gap: 8px;
            }}

            .search-card, .result-item {{
                padding: 20px;
            }}
        }}
    </style>
</head>
<body>
    <!-- Background orbs -->
    <div class="bg-orb orb-1"></div>
    <div class="bg-orb orb-2"></div>
    <div class="bg-orb orb-3"></div>

    <div class="container">
        <header>
            <h1 class="logo">GovNavigator</h1>
            <p class="tagline">AI-Powered Madison Municipal Code Search</p>
        </header>

        <div class="glass search-card">
            <form class="search-form" action="/search" method="post">
                <input
                    type="text"
                    name="query"
                    class="search-input"
                    placeholder="Ask about Madison laws..."
                    value="{query}"
                    autofocus
                >
                <button type="submit" class="search-btn">Search</button>
            </form>

            <div class="examples">
                <div class="examples-label">Popular searches</div>
                <div class="example-tags">
                    <a href="/search?q=noise+complaint" class="example-tag">Noise complaints</a>
                    <a href="/search?q=landlord+security+deposit" class="example-tag">Security deposits</a>
                    <a href="/search?q=dog+leash+park" class="example-tag">Dog leash laws</a>
                    <a href="/search?q=building+permit" class="example-tag">Building permits</a>
                    <a href="/search?q=alcohol+license" class="example-tag">Alcohol licenses</a>
                    <a href="/search?q=parking+regulations" class="example-tag">Parking rules</a>
                </div>
            </div>
        </div>

        {content}

        <div class="stats">
            Searching 1,029 ordinance sections across 45 chapters
        </div>

        <footer>
            <a href="https://library.municode.com/wi/madison/codes/code_of_ordinances" target="_blank">
                Official Madison Municipal Code
            </a>
        </footer>
    </div>

    <script>
        document.querySelectorAll('.example-tag').forEach(el => {{
            el.addEventListener('click', (e) => {{
                e.preventDefault();
                document.querySelector('.search-input').value = el.textContent;
                document.querySelector('.search-form').submit();
            }});
        }});
    </script>
</body>
</html>'''


@app.get("/", response_class=HTMLResponse)
async def home():
    return render_page("")


@app.post("/search", response_class=HTMLResponse)
async def search_post(query: str = Form(...)):
    return await do_search(query)


@app.get("/search", response_class=HTMLResponse)
async def search_get(q: str = ""):
    if q:
        return await do_search(q)
    return render_page("")


async def do_search(query: str):
    if not search_index:
        return render_page('<div class="glass results-card"><div class="no-results">Search index not loaded</div></div>', query)

    results = search_index.search(query, max_results=10)

    if not results:
        content = '''
        <div class="glass results-card">
            <div class="no-results">
                <h3>No results found</h3>
                <p>Try different keywords or check your spelling</p>
            </div>
        </div>
        '''
        return render_page(content, query)

    results_html = f'''
    <div class="glass results-card">
        <div class="results-header">
            <h2>{len(results)} results for "{query}"</h2>
        </div>
    '''

    for r in results:
        doc = r["document"]
        score = r["score"]

        title = doc.get("title", "Untitled")
        section = doc.get("section_number", "")
        chapter = doc.get("chapter", "")[:45]
        url = doc.get("url", "#")
        excerpt = doc.get("content", "")[:250].replace("\n", " ")
        excerpt = excerpt.replace("to section section section versions", "").strip()

        results_html += f'''
        <div class="result-item">
            <div class="result-title">{title}</div>
            <div class="result-meta">
                {f'<span class="badge badge-section">§ {section}</span>' if section else ''}
                <span class="badge badge-chapter">{chapter}</span>
                <span class="badge badge-score">{score:.0%} match</span>
            </div>
            <div class="result-excerpt">{excerpt}...</div>
            <a href="{url}" target="_blank" class="result-link">
                View full ordinance
                <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/>
                </svg>
            </a>
        </div>
        '''

    results_html += '</div>'
    return render_page(results_html, query)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
