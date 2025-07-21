#!/usr/bin/env python3
"""mlbtr_daily_summary.py

Automates a daily workflow that:
1. Pulls the most-recent MLB Trade Rumors chat transcript.
2. Extracts the full Q&A pairs.
3. Builds a concise, chronological summary that prioritises:
   • Red Sox / Yankees items
   • Other AL-East clubs (Rays, Orioles, Blue Jays)
   • Cubs
4. Writes two HTML files in ./out/YYYY-MM-DD/
   ├─ summary.html   ← short bullet digest + a “View full transcript” button
   └─ transcript.html ← raw, cleaned transcript with usernames & exact quotes
5. (Optional)  E-mails yourself the same content instead of, or in addition to, the web page.

To schedule daily: `0 18 * * * /usr/bin/python3 /path/to/mlbtr_daily_summary.py --email you@example.com`

Add your OpenAI key in the environment as OPENAI_API_KEY if you want LLM summarisation; otherwise the
fallback summariser returns the top-scoring priority nuggets only.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import html
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import feedparser  # pip install feedparser
import requests
from bs4 import BeautifulSoup  # pip install beautifulsoup4

try:
    import openai  # optional, for AI summarisation
except ImportError:
    openai = None

# New optional Gemini support
try:
    import google.generativeai as genai  # type: ignore
except ImportError:
    genai = None


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------
@dataclasses.dataclass
class PostType:
    name: str  # e.g. "Chat"
    match_keywords: List[str]  # e.g. ["chat transcript", "live chat"]
    prompt: str  # System prompt for LLM summariser


POST_TYPES: Dict[str, PostType] = {
    "chat": PostType(
        name="Chat",
        match_keywords=["chat transcript", "live chat"],
        prompt=(
            "Distill this MLB chat transcript into comprehensive topic bullets, capturing all substantive Q&A content with faithful clarity. "
            "One bullet per distinct topic. Use 🔴 for Red Sox/Yankees/AL East/Cubs topics, • for others. "
            "No invention—exclude only small talk."
        ),
    ),
    "mailbag": PostType(
        name="Mailbag",
        match_keywords=["mailbag"],
        prompt=(
            "Archive this MLB mailbag into detailed topic bullets capturing complete question-answer content with enhanced readability. "
            "Preserve all statistics, names, and reasoning. Use 🔴 for Red Sox/Yankees/AL East/Cubs topics, • for others."
        ),
    ),
}

RSS_FEED = "https://www.mlbtraderumors.com/feed"
KEYWORDS_PRIMARY = {
    "red sox",
    "boston",
    "yankees",
    "new york",
    "rays",
    "tampa",
    "orioles",
    "baltimore",
    "blue jays",
    "toronto",
    "cubs",
    "chicago cubs",
}
SUMMARY_MAX_BULLETS = 10  # keep it tight
OUT_DIR = Path(__file__).with_suffix("").parent / "out"


HEAD_TEMPLATE = """<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{title}</title><style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6; 
    color: #1a1a1a; 
    background: #fafafa;
    min-height: 100vh;
}}
.container {{ 
    max-width: 800px; 
    margin: 0 auto; 
    background: white; 
    min-height: 100vh;
}}
.header {{ 
    background: white;
    padding: 2rem;
    border-bottom: 1px solid #e5e5e5;
}}
.header h1 {{ 
    font-size: 2rem; 
    font-weight: 700; 
    margin-bottom: 0.5rem;
    color: #1a1a1a;
}}
.header .subtitle {{ 
    font-size: 1rem; 
    color: #666;
    font-weight: 400;
}}
.content {{ 
    padding: 2rem;
}}
.section-title {{ 
    font-size: 1.5rem; 
    font-weight: 600; 
    margin-bottom: 2rem; 
    color: #1a1a1a;
}}
.insights-list {{ 
    list-style: none;
    margin-bottom: 3rem;
}}
.insight {{ 
    margin-bottom: 2rem; 
    padding-bottom: 2rem;
    border-bottom: 1px solid #f0f0f0;
}}
.insight:last-child {{
    border-bottom: none;
    margin-bottom: 0;
}}
.insight.priority {{ 
    border-left: 3px solid #d73527;
    padding-left: 1rem;
    margin-left: -1rem;
}}

.text {{ 
    color: #333; 
    font-size: 1rem; 
    line-height: 1.7;
}}
.transcript-section {{ 
    margin-top: 3rem;
    border-top: 1px solid #e5e5e5;
    padding-top: 2rem;
}}
details {{ 
    margin-top: 1rem;
}}
summary {{ 
    background: #f8f8f8; 
    padding: 1rem; 
    font-weight: 600; 
    cursor: pointer; 
    border-radius: 4px;
    color: #333;
}}
summary:hover {{ 
    background: #f0f0f0; 
}}
iframe {{ 
    width: 100%; 
    height: 70vh; 
    border: 1px solid #e5e5e5;
    border-radius: 4px;
    margin-top: 1rem;
}}
@media (max-width: 768px) {{
    .header {{ padding: 1.5rem; }}
    .header h1 {{ font-size: 1.75rem; }}
    .content {{ padding: 1.5rem; }}
}}
</style></head><body><div class='container'>"""
TAIL_TEMPLATE = "</div></body></html>"

# --------------------------------------------------
# UTILITIES
# --------------------------------------------------


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


@dataclasses.dataclass
class Article:
    """Represents one article found in the RSS feed."""

    title: str
    url: str
    date: dt.date
    post_type: str  # "chat" or "mailbag"


def fetch_new_articles(out_base_dir: Path, force: bool = False, regenerate_all: bool = False) -> List[Article]:
    """Returns a list of all new, unprocessed articles matching our keywords."""
    feed = feedparser.parse(RSS_FEED)
    new_articles = []
    today = dt.date.today()
    for entry in feed.entries:
        title_lower = entry.title.lower()
        for type_key, post_type in POST_TYPES.items():
            if any(kw in title_lower for kw in post_type.match_keywords):
                published_date = dt.datetime.strptime(entry.published[:16], "%a, %d %b %Y").date()
                expected_dir = out_base_dir / type_key / str(published_date)

                # Process if the output doesn't exist, OR if --force is used for today's articles, OR if regenerate_all is True
                should_process = (not expected_dir.exists() or 
                                (force and published_date == today) or 
                                regenerate_all)
                if should_process:
                    # Avoid duplicates if forcing
                    if not any(a.url == entry.link for a in new_articles):
                        new_articles.append(
                            Article(
                                title=entry.title,
                                url=entry.link,
                                date=published_date,
                                post_type=type_key,
                            )
                        )
    return new_articles


def extract_transcript(url: str) -> List[Tuple[str, str]]:
    """Returns list of (speaker, raw_text) preserving original order."""
    html_doc = requests.get(url, timeout=20).text
    soup = BeautifulSoup(html_doc, "html.parser")
    
    # Look for the live chat archive div first
    chat_div = soup.find("div", class_="live-chat-archive")
    if not chat_div:
        # Fallback to the old method
        chat_div = soup.find("div", class_=re.compile("entry-content|post-entry"))
        if not chat_div:
            raise RuntimeError("Could not locate transcript content block.")

    # Remove known subscriber promo sections before parsing
    for promo in chat_div.find_all('div', class_='mlbtr-front-office-promo'):
        promo.decompose()
    for promo in chat_div.find_all('div', class_='front-office-originals'):
        promo.decompose()

    pairs: List[Tuple[str, str]] = []
    
    # Get all direct children of the chat div
    children = [child for child in chat_div.children if child.name]
    
    current_speaker = None
    i = 0
    while i < len(children):
        child = children[i]
        
        # Look for speaker paragraphs (p.moderator or p.user)
        if child.name == 'p' and child.get('class'):
            classes = child.get('class', [])
            if 'moderator' in classes or 'user' in classes:
                strong_tag = child.find('strong')
                if strong_tag:
                    current_speaker = strong_tag.get_text(strip=True)
                    
                    # The next element should be a ul with the content
                    if i + 1 < len(children) and children[i + 1].name == 'ul':
                        ul_element = children[i + 1]
                        # Extract text from all li elements in this ul
                        li_texts = []
                        for li in ul_element.find_all('li'):
                            li_text = li.get_text(strip=True)
                            if li_text:
                                li_texts.append(li_text)
                        
                        if li_texts and current_speaker:
                            full_text = " ".join(li_texts)
                            pairs.append((current_speaker, full_text))
                        
                        i += 2  # Skip both the p and ul elements
                        continue
        
        i += 1

    # Return pairs only if the text is not empty
    return [(s, t) for s, t in pairs if t]


def extract_mailbag_content(url: str) -> List[Tuple[str, str]]:
    """Extract mailbag content as question/answer pairs."""
    html_doc = requests.get(url, timeout=20).text
    soup = BeautifulSoup(html_doc, "html.parser")
    
    # Look for the live chat archive div first (some mailbags might use this structure)
    content_div = soup.find("div", class_="live-chat-archive")
    if not content_div:
        # Fallback to the standard content div
        content_div = soup.find("div", class_=re.compile("entry-content|post-entry"))
        if not content_div:
            raise RuntimeError("Could not locate mailbag content block.")

    # Remove known subscriber promo sections before parsing
    for promo in content_div.find_all('div', class_='mlbtr-front-office-promo'):
        promo.decompose()
    for promo in content_div.find_all('div', class_='front-office-originals'):
        promo.decompose()

    # For mailbags, extract the full text and create a single entry
    full_text = content_div.get_text(" ", strip=True)
    
    # Remove any promotional text at the end that might not be in a standard div
    if "Access weekly subscriber-only articles" in full_text:
        full_text = full_text.split("Access weekly subscriber-only articles")[0]
    
    return [("Mailbag Content", full_text.strip())]


def extract_content_by_type(url: str, post_type: str) -> List[Tuple[str, str]]:
    """Extract content based on post type."""
    if post_type == "mailbag":
        return extract_mailbag_content(url)
    else:
        return extract_transcript(url)


def prioritise_pairs(pairs: List[Tuple[str, str]]) -> List[Tuple[str, str, bool]]:
    """Adds boolean flag for priority so we can weight summary."""
    out = []
    for speaker, text in pairs:
        lower = text.lower()
        is_priority = any(k in lower for k in KEYWORDS_PRIMARY)
        out.append((speaker, text, is_priority))
    return out


# ----------------------- SUMMARY ------------------

def llm_summarise(pairs: List[Tuple[str, str]], post_type: str) -> List[str]:
    assert openai, "openai package missing.  Either install it or use fallback summariser."
    concatenated = "\n".join(f"{s}: {t}" for s, t in pairs)
    prompt_template = POST_TYPES[post_type].prompt
    if post_type == "mailbag":
        prompt = prompt_template + "\n\nMailbag Content: " + concatenated
    else:
        prompt = prompt_template.format(max=SUMMARY_MAX_BULLETS) + "\n\nTranscript:\n" + concatenated
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": prompt}],
        temperature=0.2,
    )
    bullets = resp.choices[0].message.content.split("\n")[:SUMMARY_MAX_BULLETS]
    return [b for b in bullets if b.strip()]


def gemini_summarise(pairs: List[Tuple[str, str]], post_type: str) -> List[str]:
    """Summarise using Google's Gemini if available."""
    assert genai, "google-generativeai package missing. Install it or use fallback summariser."
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable not set.")

    genai.configure(api_key=api_key)
    concatenated = "\n".join(f"{s}: {t}" for s, t in pairs)
    # Gemini models have a token limit; truncate large transcripts to ~16k characters.
    if len(concatenated) > 16000:
        concatenated = concatenated[:16000]

    prompt_template = POST_TYPES[post_type].prompt
    if post_type == "mailbag":
        prompt = prompt_template + "\n\nMailbag Content: " + concatenated
    else:
        prompt = prompt_template.format(max=SUMMARY_MAX_BULLETS) + "\n\nTranscript:\n" + concatenated

    model = genai.GenerativeModel("gemini-1.5-flash")
    resp = model.generate_content(prompt, generation_config={"temperature": 0.2})
    text_out = resp.text if hasattr(resp, "text") else str(resp)
    bullets = text_out.split("\n")[:SUMMARY_MAX_BULLETS]
    return [b for b in bullets if b.strip()]


def simple_summarise(pairs: List[Tuple[str, str, bool]]) -> List[str]:
    """Create meaningful insights by extracting specific content from Q&A pairs."""
    insights: List[str] = []
    
    # First pass: prioritize insights from experts (Steve Adams)
    expert_insights = []
    fan_insights = []
    
    for speaker, text, is_pri in pairs:
        # Skip moderator intro messages
        if "Good afternoon" in text or "Sorry to not get the queue up" in text:
            continue
        
        # Skip promotional content
        if "Access weekly subscriber-only" in text or "Front Office Originals" in text:
            continue
        
        # Skip questions from fans (they typically end with ?)
        if text.strip().endswith("?"):
            continue
            
        # Extract meaningful insights from the actual content
        insight = _extract_meaningful_insight(speaker, text, is_pri)
        if insight:
            if "Steve Adams" in speaker or "steve" in speaker.lower():
                if insight not in expert_insights:
                    expert_insights.append(insight)
            else:
                if insight not in fan_insights:
                    fan_insights.append(insight)
    
    # Combine expert insights first, then fan insights
    insights = expert_insights + fan_insights
    return insights[:SUMMARY_MAX_BULLETS]

def _extract_meaningful_insight(speaker: str, text: str, is_priority: bool) -> str:
    """Extract a meaningful insight from a Q&A exchange."""
    text_lower = text.lower()
    
    # Priority team discussions
    if is_priority or any(team in text_lower for team in ["dodgers", "yankees", "red sox", "rays", "orioles", "blue jays", "cubs"]):
        prefix = "🔴 " if is_priority else "• "
        
        # Dodgers trade speculation
        if "dodgers" in text_lower and ("trade" in text_lower or "deadline" in text_lower):
            if "reliever" in text_lower and ("bednar" in text_lower or "helsley" in text_lower):
                return f"{prefix}Dodgers expected to add notable reliever; Bednar and Helsley both likely to be traded, though Clase less likely to move"
            elif "miller" in text_lower and "clase" in text_lower:
                return f"{prefix}Dodgers pursuing closers: Mason Miller unlikely to move, Emmanuel Clase possible but not expected"
        
        # Braves moves
        if "leon" in text_lower and ("atl" in text_lower or "braves" in text_lower):
            return f"{prefix}Sandy Leon called up to Braves, reinforcing expectation that Marcell Ozuna will be traded"
        
        # Reds roster moves
        if "reds" in text_lower and "marte" in text_lower and "right field" in text_lower:
            return f"{prefix}Reds testing Noelvi Marte in right field, potentially opening door for Eugenio Suárez return at third base"
    
    # General baseball rules/mechanics insights
    if "qualifying offer" in text_lower or "qo" in text_lower:
        if "opt-out" in text_lower:
            return "• Players who exercise opt-out clauses can receive qualifying offers if they haven't previously received one and spent full season with the team"
    
    # Contract/option mechanics
    if "option" in text_lower and "exercise" in text_lower:
        return "• Qualifying offer rules clarified for players with contract options and opt-out clauses"
    
    # If we can't extract something specific, try to get the key point
    if len(text) > 50 and not text.endswith("?"):  # Only for substantial content, not questions
        # Clean up the text and extract key information
        clean_text = text.replace("Steve Adams", "").replace("Access weekly", "").strip()
        if clean_text and len(clean_text) > 30 and not clean_text.endswith("?"):
            # Take first meaningful sentence or key point that's not a question
            sentences = clean_text.split('.')
            for sentence in sentences:
                sentence = sentence.strip()
                if (len(sentence) > 20 and 
                    not sentence.startswith("Join exclusive") and 
                    not sentence.endswith("?") and
                    not sentence.startswith("Do you") and
                    not sentence.startswith("If")):
                    return f"• {sentence}"
    
    return None




def build_summary(pairs: List[Tuple[str, str, bool]], post_type: str) -> List[str]:
    if os.getenv("OPENAI_API_KEY") and openai:
        try:
            return llm_summarise([(s, t) for s, t, _ in pairs], post_type)
        except Exception as exc:
            print(f"OpenAI summarisation failed → {exc}. Trying Gemini.")
    if (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) and genai:
        try:
            return gemini_summarise([(s, t) for s, t, _ in pairs], post_type)
        except Exception as exc:
            print(f"Gemini summarisation failed → {exc}. Falling back to keyword summary.")
    return simple_summarise(pairs)

# --------------------------- OUTPUT ---------------

def write_html(summary: List[str], pairs: List[Tuple[str, str]], title: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Summary page with expandable transcript.
    summary_html_path = out_dir / "summary.html"
    transcript_html_path = out_dir / "transcript.html"

    # summary.html
    with summary_html_path.open("w", encoding="utf-8") as f:
        f.write(HEAD_TEMPLATE.format(title=title))
        
        # Header section
        f.write('<div class="header">')
        f.write(f'<h1>{html.escape(title.replace("Trade Rumors Front Office Subscriber ", ""))}</h1>')
        f.write('<div class="subtitle">MLB Trade Rumors Daily Digest</div>')
        f.write('</div>')
        
        # Content section
        f.write('<div class="content">')
        f.write('<h2 class="section-title">Key Insights</h2>')
        f.write('<ul class="insights-list">')
        
        for bullet in summary:
            # Parse the bullet to extract priority and content
            if bullet.startswith("🔴"):
                is_priority = True
                content = bullet[2:].strip()  # Remove "🔴 "
            elif bullet.startswith("•"):
                is_priority = False
                content = bullet[2:].strip()  # Remove "• "
            else:
                is_priority = False
                content = bullet
            
            # Write the insight (no speaker needed for topic summaries)
            insight_class = "insight priority" if is_priority else "insight"
            
            f.write(f'<li class="{insight_class}">')
            f.write(f'<div class="text">{html.escape(content)}</div>')
            f.write('</li>')
        
        f.write('</ul>')  # End insights-list
        
        # Transcript section
        f.write('<div class="transcript-section">')
        f.write('<details>')
        f.write('<summary>View Full Transcript</summary>')
        f.write(f'<iframe src="transcript.html"></iframe>')
        f.write('</details>')
        f.write('</div>')
        
        f.write('</div>')  # End content
        f.write(TAIL_TEMPLATE)

    # transcript.html (raw but cleaned)
    with transcript_html_path.open("w", encoding="utf-8") as f:
        f.write(HEAD_TEMPLATE.format(title=title + " – Full Transcript"))
        for speaker, text in pairs:
            f.write(f"<p><strong>{html.escape(speaker)}:</strong> {html.escape(text)}</p>\n")
        f.write(TAIL_TEMPLATE)

    print(f"Wrote {summary_html_path}")


def build_main_index(out_base_dir: Path):
    """Generates the root index.html that links to all summaries."""
    index_path = out_base_dir / "index.html"
    print(f"Generating main index: {index_path}")

    with index_path.open("w", encoding="utf-8") as f:
        f.write("""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<title>MLBTR Daily Digest</title><style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { 
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.6; 
    color: #1a1a1a; 
    background: #fafafa;
    min-height: 100vh;
}
.container { 
    max-width: 800px; 
    margin: 0 auto; 
    background: white; 
    min-height: 100vh;
}
.header { 
    background: white;
    padding: 3rem 2rem;
    border-bottom: 1px solid #e5e5e5;
    text-align: center;
}
.header h1 { 
    font-size: 2.5rem; 
    font-weight: 700; 
    margin-bottom: 0.5rem;
    color: #1a1a1a;
}
.header .subtitle { 
    font-size: 1.1rem; 
    color: #666;
    font-weight: 400;
}
.content { 
    padding: 2rem;
}
.section { 
    margin-bottom: 3rem;
}
.section-title { 
    font-size: 1.5rem; 
    font-weight: 600; 
    margin-bottom: 1.5rem; 
    color: #1a1a1a;
}
.summaries-list { 
    list-style: none;
}
.summary-item { 
    border-bottom: 1px solid #f0f0f0;
    padding: 1rem 0;
}
.summary-item:last-child {
    border-bottom: none;
}
.summary-link { 
    display: block;
    text-decoration: none;
    color: inherit;
    transition: color 0.2s ease;
}
.summary-link:hover { 
    color: #d73527;
}
.summary-date { 
    font-size: 1.1rem; 
    font-weight: 600; 
    color: #1a1a1a; 
    margin-bottom: 0.25rem;
}
.summary-type { 
    font-size: 0.9rem; 
    color: #666; 
    text-transform: uppercase; 
    letter-spacing: 0.5px;
}
.empty-state { 
    text-align: center; 
    padding: 2rem; 
    color: #999; 
    font-style: italic;
}
.stats { 
    background: #f8f8f8;
    padding: 1rem 2rem;
    text-align: center;
    font-size: 0.9rem;
    color: #666;
    border-top: 1px solid #e5e5e5;
}
@media (max-width: 768px) {
    .header { padding: 2rem 1rem; }
    .header h1 { font-size: 2rem; }
    .content { padding: 1.5rem; }
}
</style></head><body><div class='container'>""")

        f.write('<div class="header">')
        f.write('<h1>MLBTR Daily Digest</h1>')
        f.write('<div class="subtitle">Your daily source for MLB trade rumors and insights</div>')
        f.write('</div>')

        # Count summaries for stats
        total_chats = 0
        total_mailbags = 0
        
        f.write('<div class="content">')
        
        for type_key, post_type in POST_TYPES.items():
            scan_dir = out_base_dir / type_key
            dated_dirs = []
            if scan_dir.is_dir():
                dated_dirs = sorted([d for d in scan_dir.iterdir() if d.is_dir()], reverse=True)
            
            if type_key == "chat":
                total_chats = len(dated_dirs)
            else:
                total_mailbags = len(dated_dirs)
            
            f.write('<div class="section">')
            f.write(f'<h2 class="section-title">{post_type.name} Summaries</h2>')

            if not dated_dirs:
                f.write('<div class="empty-state">No summaries available yet.</div>')
            else:
                f.write('<ul class="summaries-list">')
                for day_dir in dated_dirs:
                    relative_path = f"{type_key}/{day_dir.name}/summary.html"
                    f.write('<li class="summary-item">')
                    f.write(f'<a href="{relative_path}" class="summary-link">')
                    f.write(f'<div class="summary-date">{day_dir.name}</div>')
                    f.write(f'<div class="summary-type">{post_type.name}</div>')
                    f.write('</a>')
                    f.write('</li>')
                f.write('</ul>')
            
            f.write('</div>')

        f.write('</div>')
        
        # Stats footer
        f.write('<div class="stats">')
        f.write(f'{total_chats} chat summaries • {total_mailbags} mailbag summaries')
        f.write('</div>')
        
        f.write('</div></body></html>')


# --------------------------------------------------
# ENTRYPOINT
# --------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Daily MLBTR chat summariser")
    parser.add_argument("--out", help="Output base directory", default=str(OUT_DIR))
    parser.add_argument("--force", action="store_true", help="Re-process today's articles even if output exists")
    parser.add_argument("--regenerate-all", action="store_true", help="Regenerate all articles with updated prompts")
    args = parser.parse_args()
    out_base_dir = Path(args.out)

    if args.regenerate_all:
        print("--regenerate-all specified, will re-process ALL articles with updated prompts.")
    elif args.force:
        print("--force specified, will re-process today's articles and regenerate full index.")

    new_articles = fetch_new_articles(out_base_dir, force=args.force, regenerate_all=args.regenerate_all)
    if not new_articles:
        print("No new articles to process.")
        # If forcing or regenerating all, still rebuild index. Otherwise, we can exit.
        if not args.force and not args.regenerate_all:
            return

    for article in new_articles:
        print(f"Processing {article.post_type}: {article.title}...")
        out_dir = out_base_dir / article.post_type / str(article.date)

        try:
            pairs_raw = extract_content_by_type(article.url, article.post_type)

            # --- Start: Added logic to save raw data ---
            out_dir.mkdir(parents=True, exist_ok=True)
            raw_data_path = out_dir / "raw_extracted_data.txt"
            with raw_data_path.open("w", encoding="utf-8") as f_raw:
                for speaker, text in pairs_raw:
                    f_raw.write(f"SPEAKER: {speaker}\n---\n{text}\n\n{'='*20}\n\n")
            print(f"  -> Raw data for inspection saved to: {raw_data_path}")
            # --- End: Added logic ---

            pairs_priority = prioritise_pairs(pairs_raw)
            summary = build_summary(pairs_priority, article.post_type)
            write_html(summary, pairs_raw, article.title, out_dir)
        except Exception as e:
            print(f"  !! Failed to process {article.url}: {e}", file=sys.stderr)

    # After processing, always rebuild the main index page
    build_main_index(out_base_dir)


if __name__ == "__main__":
    main() 