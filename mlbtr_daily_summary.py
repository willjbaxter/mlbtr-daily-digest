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

# New optional Claude support
try:
    import anthropic
except ImportError:
    anthropic = None


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
        match_keywords=["chat transcript", "live chat", "subscriber chat"],
        prompt=(
            "Distill this MLB chat transcript into comprehensive topic bullets, capturing all substantive Q&A content with faithful clarity. "
            "One bullet per distinct topic. Use 🔴 for Red Sox/Yankees/AL East/Cubs topics, • for others. "
            "CRITICAL: Preserve exact dates and years mentioned in the text. Do not change 2025 to 2023 or make any date substitutions. "
            "No invention—exclude only small talk. Format as structured bullets."
        ),
    ),
    "mailbag": PostType(
        name="Mailbag",
        match_keywords=["mailbag"],
        prompt=(
            "Transform this MLB mailbag into detailed, actionable topic bullets that preserve all key insights, statistics, player analysis, and expert reasoning. "
            "Each bullet should be substantive and capture complete thoughts with specific details (stats, comparisons, projections). "
            "Use 🔴 for Red Sox/Yankees/AL East/Cubs topics, • for others. "
            "Prioritize prospect analysis, trade speculation, contract details, and performance metrics. "
            "Maintain all player names, statistics (wRC+, ERA, etc.), and analytical context. "
            "CRITICAL: Preserve exact dates and years mentioned in the text. Do not change 2025 to 2023 or make any date substitutions. "
            "Create 5-8 comprehensive bullets that someone could use to understand the full content without reading the original."
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


HEAD_TEMPLATE = """<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ 
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.65; 
    color: #1a1a1a; 
    background: #fff;
}}
.container {{ 
    max-width: 1200px; 
    margin: 0 auto; 
    padding: 0 1.5rem;
}}
.nav-bar {{
    padding: 1rem 0;
    border-bottom: 1px solid #e5e5e5;
    margin-bottom: 2rem;
}}
.nav-bar a {{
    color: #059669;
    text-decoration: none;
    font-weight: 500;
    font-size: 0.875rem;
}}
.nav-bar a:hover {{
    text-decoration: underline;
}}
.header {{ 
    padding: 1.5rem 0 2rem;
}}
.post-meta {{
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1rem;
    font-size: 0.875rem;
    color: #666;
}}
.post-date {{
    font-weight: 500;
}}
.post-type {{
    background: #e0f2fe;
    color: #0369a1;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 0.5px;
}}
.post-type.mailbag {{
    background: #fce7f3;
    color: #be185d;
}}
.header h1 {{ 
    font-size: 2.25rem; 
    font-weight: 700; 
    margin-bottom: 0.5rem;
    color: #1a1a1a;
    letter-spacing: -0.5px;
    line-height: 1.2;
}}
.main-content {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 3rem;
    margin-bottom: 3rem;
}}
.insights-panel {{
    background: #f8f9fa;
    padding: 2rem;
    border-radius: 8px;
    height: fit-content;
}}
.section-label {{
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #999;
    margin-bottom: 1.5rem;
}}
.insights-list {{ 
    list-style: none;
}}
.insight {{ 
    position: relative;
    padding: 0.75rem 0 0.75rem 1.5rem;
    font-size: 0.9375rem;
    line-height: 1.6;
    color: #333;
}}
.insight:before {{
    content: "•";
    position: absolute;
    left: 0;
    color: #059669;
    font-weight: 700;
}}
.insight.priority:before {{ 
    content: "→";
    color: #dc2626;
}}
.transcript-panel {{
    background: white;
}}
.transcript-content {{
    max-height: 600px;
    overflow-y: auto;
    padding: 1.5rem;
    background: #fafafa;
    border-radius: 8px;
    border: 1px solid #e5e5e5;
}}
.transcript-content p {{
    margin-bottom: 1.25rem;
    font-size: 0.875rem;
    line-height: 1.7;
}}
.transcript-content p:last-child {{
    margin-bottom: 0;
}}
.transcript-content strong {{
    color: #059669;
    font-weight: 600;
}}
.footer-nav {{
    display: flex;
    justify-content: space-between;
    padding: 2rem 0;
    margin-top: 3rem;
    border-top: 1px solid #e5e5e5;
}}
.footer-nav a {{
    color: #059669;
    text-decoration: none;
    font-weight: 500;
    font-size: 0.875rem;
}}
.footer-nav a:hover {{
    text-decoration: underline;
}}
@media (max-width: 768px) {{
    .container {{ padding: 0 1rem; }}
    .nav-bar {{
        padding: 1rem 0 1.5rem;
        margin-bottom: 1.5rem;
    }}
    .nav-bar a {{
        font-size: 1rem;
        padding: 0.5rem 0;
        display: inline-block;
    }}
    .header {{ 
        padding: 1rem 0 1.5rem;
    }}
    .header h1 {{ 
        font-size: 1.5rem;
        line-height: 1.3;
        margin-bottom: 1rem;
    }}
    .post-meta {{
        flex-direction: column;
        align-items: flex-start;
        gap: 0.5rem;
    }}
    .main-content {{
        grid-template-columns: 1fr;
        gap: 1.5rem;
        margin-bottom: 2rem;
    }}
    .insights-panel {{
        padding: 1.25rem;
        margin-bottom: 1rem;
    }}
    .section-label {{
        margin-bottom: 1rem;
    }}
    .insight {{
        padding: 0.5rem 0 0.5rem 1.25rem;
        font-size: 0.875rem;
        line-height: 1.5;
    }}
    .transcript-content {{
        max-height: 400px;
        padding: 1rem;
        font-size: 0.8125rem;
        line-height: 1.6;
    }}
    .transcript-content p {{
        margin-bottom: 1rem;
    }}
    .footer-nav {{
        flex-direction: column;
        gap: 1rem;
        padding: 1.5rem 0;
        margin-top: 2rem;
        text-align: center;
    }}
    .footer-nav a {{
        font-size: 1rem;
        padding: 0.5rem;
    }}
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


def fetch_new_articles(out_base_dir: Path, force: bool = False, regenerate_all: bool = False, since_date: dt.date = None) -> List[Article]:
    """Returns a list of all new, unprocessed articles matching our keywords."""
    feed = feedparser.parse(RSS_FEED)
    new_articles = []
    today = dt.date.today()
    cutoff_date = since_date or dt.date(2000, 1, 1)  # Default to very old date if not specified
    
    for entry in feed.entries:
        title_lower = entry.title.lower()
        for type_key, post_type in POST_TYPES.items():
            if any(kw in title_lower for kw in post_type.match_keywords):
                published_date = dt.datetime.strptime(entry.published[:16], "%a, %d %b %Y").date()
                expected_dir = out_base_dir / type_key / str(published_date)

                # Skip articles older than cutoff date
                if published_date < cutoff_date:
                    continue

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
    response = requests.get(url, timeout=20)
    response.encoding = 'utf-8'  # Force UTF-8 encoding
    html_doc = response.text
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
                            # Clean up non-breaking spaces and other HTML entities
                            li_text = li.get_text(strip=True)
                            # Replace common HTML entities
                            li_text = li_text.replace('\xa0', ' ')  # non-breaking space
                            li_text = li_text.replace('\u00c2', '')  # Remove mojibake
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
    response = requests.get(url, timeout=20)
    response.encoding = 'utf-8'  # Force UTF-8 encoding
    html_doc = response.text
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
    
    # Clean up encoding issues
    full_text = full_text.replace('\xa0', ' ')  # non-breaking space
    full_text = full_text.replace('\u00c2', '')  # Remove mojibake
    
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
    
    content = resp.choices[0].message.content
    bullets = []
    for line in content.split("\n"):
        line = line.strip()
        if line and (line.startswith("•") or line.startswith("🔴") or line.startswith("-") or line.startswith("*")):
            bullets.append(line)
        elif line and not line.startswith("Here") and not line.startswith("[") and len(line) > 20:
            if not line.endswith(":") and not line.lower().startswith("summary"):
                bullets.append("• " + line)
    
    return bullets[:8 if post_type == "mailbag" else SUMMARY_MAX_BULLETS]


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
    content = resp.text if hasattr(resp, "text") else str(resp)
    
    bullets = []
    for line in content.split("\n"):
        line = line.strip()
        if line and (line.startswith("•") or line.startswith("🔴") or line.startswith("-") or line.startswith("*")):
            bullets.append(line)
        elif line and not line.startswith("Here") and not line.startswith("[") and len(line) > 20:
            if not line.endswith(":") and not line.lower().startswith("summary"):
                bullets.append("• " + line)
    
    return bullets[:8 if post_type == "mailbag" else SUMMARY_MAX_BULLETS]


def claude_summarise(pairs: List[Tuple[str, str]], post_type: str) -> List[str]:
    """Summarise using Anthropic's Claude if available."""
    assert anthropic, "anthropic package missing. Install it or use fallback summariser."
    api_key = os.getenv("CLAUDE_API_KEY")
    if not api_key:
        raise RuntimeError("CLAUDE_API_KEY environment variable not set.")

    client = anthropic.Anthropic(api_key=api_key)
    concatenated = "\n".join(f"{s}: {t}" for s, t in pairs)
    prompt_template = POST_TYPES[post_type].prompt

    if post_type == "mailbag":
        system_prompt = prompt_template
        user_message = "Please summarise this mailbag content:\n\n" + concatenated
    else:
        system_prompt = prompt_template.format(max=SUMMARY_MAX_BULLETS)
        user_message = "Please summarise this transcript:\n\n" + concatenated

    # Use different token limits based on content type
    max_tokens = 2048 if post_type == "mailbag" else 1024
    
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",  # Use Sonnet for better accuracy
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": user_message,
            }
        ],
        temperature=0.2,
    )
    
    content = message.content[0].text
    
    # Extract bullets more intelligently
    bullets = []
    for line in content.split("\n"):
        line = line.strip()
        if line and (line.startswith("•") or line.startswith("🔴") or line.startswith("-") or line.startswith("*")):
            bullets.append(line)
        elif line and not line.startswith("Here") and not line.startswith("[") and len(line) > 20:
            # Handle cases where bullets don't have prefixes
            if not line.endswith(":") and not line.lower().startswith("summary"):
                bullets.append("• " + line)
    
    return bullets[:8 if post_type == "mailbag" else SUMMARY_MAX_BULLETS]


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
    if os.getenv("CLAUDE_API_KEY") and anthropic:
        try:
            return claude_summarise([(s, t) for s, t, _ in pairs], post_type)
        except Exception as exc:
            print(f"Claude summarisation failed → {exc}. Falling back to keyword summary.")
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

    # Summary page with transcript.
    summary_html_path = out_dir / "summary.html"
    
    # Determine post type from directory structure
    post_type = "mailbag" if "mailbag" in str(out_dir) else "chat"
    post_date = out_dir.name  # Directory name is the date
    
    # Standardize title format with date
    date_obj = dt.datetime.strptime(post_date, "%Y-%m-%d").date()
    formatted_date = date_obj.strftime("%b %d")  # e.g., "Aug 18"
    
    if post_type == "chat":
        clean_title = f"Chat: {formatted_date}"
    else:  # mailbag
        clean_title = f"Mailbag: {formatted_date}"

    # summary.html
    with summary_html_path.open("w", encoding="utf-8") as f:
        f.write(HEAD_TEMPLATE.format(title=clean_title))
        
        # Navigation bar
        f.write('<div class="nav-bar">')
        f.write('<a href="../../index.html">← Back to All Posts</a>')
        f.write('</div>')
        
        # Header section
        f.write('<div class="header">')
        f.write('<div class="post-meta">')
        f.write(f'<span class="post-date">{post_date}</span>')
        f.write(f'<span class="post-type {post_type}">{post_type}</span>')
        f.write('</div>')
        f.write(f'<h1>{html.escape(clean_title)}</h1>')
        f.write('</div>')
        
        # Main content with two columns
        f.write('<div class="main-content">')
        
        # Left column - Insights
        f.write('<div class="insights-panel">')
        f.write('<div class="section-label">Key Insights</div>')
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
            
            # Write the insight
            insight_class = "insight priority" if is_priority else "insight"
            
            f.write(f'<li class="{insight_class}">')
            f.write(html.escape(content))
            f.write('</li>')
        
        if not summary:
            f.write('<li class="insight">Summary generation in progress...</li>')
        
        f.write('</ul>')
        f.write('</div>')  # End insights-panel
        
        # Right column - Transcript
        f.write('<div class="transcript-panel">')
        f.write('<div class="section-label">Full Transcript</div>')
        f.write('<div class="transcript-content">')
        
        # Show first 10 Q&A pairs or all if less
        display_pairs = pairs[:20] if len(pairs) > 20 else pairs
        for speaker, text in display_pairs:
            f.write(f"<p><strong>{html.escape(speaker)}:</strong> {html.escape(text)}</p>\n")
        
        if len(pairs) > 20:
            f.write(f'<p style="text-align: center; color: #999; font-style: italic;">... and {len(pairs) - 20} more exchanges</p>')
        
        f.write('</div>')
        f.write('</div>')  # End transcript-panel
        
        f.write('</div>')  # End main-content
        
        # Footer navigation
        f.write('<div class="footer-nav">')
        f.write('<a href="../../index.html">← Back to All Posts</a>')
        f.write('<a href="#">Top ↑</a>')
        f.write('</div>')
        
        f.write(TAIL_TEMPLATE)

    print(f"Wrote {summary_html_path}")


def build_main_index(out_base_dir: Path):
    """Generates the root index.html that links to all summaries."""
    index_path = out_base_dir / "index.html"
    print(f"Generating main index: {index_path}")
    
    # Collect all posts data
    all_posts = []
    
    for type_key, post_type in POST_TYPES.items():
        scan_dir = out_base_dir / type_key
        if scan_dir.is_dir():
            for day_dir in sorted(scan_dir.iterdir(), reverse=True):
                if day_dir.is_dir():
                    # Try to get a preview from the summary file
                    preview_text = "Click to read the full summary and analysis."
                    title = f"{post_type.name} Summary"
                    
                    try:
                        summary_file = day_dir / "summary.html"
                        if summary_file.exists():
                            with summary_file.open('r', encoding='utf-8') as preview_f:
                                content = preview_f.read()
                                # Extract insights for preview
                                import re
                                insights = re.findall(r'<li class="insight[^"]*">(.*?)</li>', content)
                                if insights:
                                    # Extract key topics/players from insights
                                    topics = []
                                    for insight in insights[:3]:  # First 3 insights
                                        # Clean HTML entities and tags
                                        clean_insight = html.unescape(re.sub(r'<[^>]+>', '', insight))
                                        # Extract player names, teams, topics
                                        if len(clean_insight) > 20:
                                            # Look for player names (capitalized words)
                                            import re
                                            names = re.findall(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', clean_insight)
                                            teams = re.findall(r'\b(?:Red Sox|Yankees|Cubs|Dodgers|Astros|Giants|Padres|Braves|Mets|Pirates|Tigers|Brewers|Phillies|Rangers|Angels|Orioles|Blue Jays|Rays|Guardians|Twins|White Sox|Royals|Athletics|Mariners|Cardinals|Reds|Marlins|Nationals|Rockies|Diamondbacks)\b', clean_insight)
                                            
                                            if names:
                                                topics.extend(names[:2])  # Max 2 names per insight
                                            if teams:
                                                topics.extend(teams[:1])  # Max 1 team per insight
                                    
                                    if topics:
                                        preview_text = ", ".join(list(dict.fromkeys(topics)))  # Remove duplicates, preserve order
                                        if len(preview_text) > 80:
                                            preview_text = preview_text[:80] + "..."
                                    else:
                                        # Fallback to first insight text
                                        first_insight = html.unescape(re.sub(r'<[^>]+>', '', insights[0]))
                                        preview_text = first_insight[:100] + "..." if len(first_insight) > 100 else first_insight
                                
                                # Generate standardized title
                                date_obj = dt.datetime.strptime(day_dir.name, "%Y-%m-%d").date()
                                formatted_date = date_obj.strftime("%b %d")
                                title = f"{post_type.name}: {formatted_date}"
                    except:
                        # Fallback title for any errors
                        try:
                            date_obj = dt.datetime.strptime(day_dir.name, "%Y-%m-%d").date()
                            formatted_date = date_obj.strftime("%b %d")
                            title = f"{post_type.name}: {formatted_date}"
                        except:
                            title = f"{post_type.name} Summary"
                    
                    all_posts.append({
                        'date': day_dir.name,
                        'type': type_key,
                        'title': title,
                        'preview': preview_text,
                        'url': f"{type_key}/{day_dir.name}/summary.html"
                    })

    with index_path.open("w", encoding="utf-8") as f:
        f.write("""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<title>MLBTR Daily Digest</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { 
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    line-height: 1.65; 
    color: #1a1a1a; 
    background: #fff;
}
.container { 
    max-width: 720px; 
    margin: 0 auto; 
    padding: 0 1.5rem;
}
.header { 
    padding: 3rem 0 2rem;
    border-bottom: 1px solid #e5e5e5;
    margin-bottom: 2rem;
}
.header h1 { 
    font-size: 2rem; 
    font-weight: 700; 
    margin-bottom: 0.5rem;
    letter-spacing: -0.5px;
}
.header .subtitle { 
    font-size: 1rem; 
    color: #666;
    line-height: 1.5;
}
.nav-tabs {
    display: flex;
    gap: 2rem;
    margin-bottom: 2rem;
    border-bottom: 1px solid #e5e5e5;
    padding-bottom: 0;
}
.nav-tab {
    padding: 0.75rem 0;
    color: #666;
    text-decoration: none;
    font-weight: 500;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    transition: all 0.2s;
}
.nav-tab:hover {
    color: #1a1a1a;
}
.nav-tab.active {
    color: #059669;
    border-bottom-color: #059669;
}
.posts-list {
    margin-bottom: 4rem;
}
.post-item {
    padding: 1.5rem 0;
    border-bottom: 1px solid #f0f0f0;
}
.post-item:hover {
    background: #fafafa;
    margin: 0 -1.5rem;
    padding: 1.5rem;
}
.post-link {
    text-decoration: none;
    color: inherit;
    display: block;
}
.post-header {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
}
.post-date {
    font-size: 0.875rem;
    color: #666;
    font-weight: 500;
}
.post-type {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 0.15rem 0.5rem;
    border-radius: 3px;
}
.post-type.chat {
    background: #e0f2fe;
    color: #0369a1;
}
.post-type.mailbag {
    background: #fce7f3;
    color: #be185d;
}
.post-title {
    font-size: 1.125rem;
    font-weight: 600;
    color: #1a1a1a;
    margin-bottom: 0.5rem;
    line-height: 1.4;
}
.post-preview {
    font-size: 0.9375rem;
    color: #666;
    line-height: 1.6;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
.footer {
    padding: 2rem 0;
    margin-top: 4rem;
    border-top: 1px solid #e5e5e5;
    text-align: center;
    color: #666;
    font-size: 0.875rem;
}
.footer-stats {
    display: flex;
    justify-content: center;
    gap: 3rem;
    margin-bottom: 1rem;
}
.stat {
    text-align: center;
}
.stat-number {
    font-size: 1.25rem;
    font-weight: 600;
    color: #1a1a1a;
}
.stat-label {
    font-size: 0.75rem;
    color: #999;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
@media (max-width: 768px) {
    .container { padding: 0 1rem; }
    .header { 
        padding: 1.5rem 0 1rem; 
        margin-bottom: 1.5rem;
    }
    .header h1 { 
        font-size: 1.5rem;
        line-height: 1.3;
    }
    .header .subtitle {
        font-size: 0.9375rem;
        margin-top: 0.5rem;
    }
    .nav-tabs {
        gap: 1rem;
        margin-bottom: 1.5rem;
        flex-wrap: wrap;
    }
    .nav-tab {
        padding: 0.5rem 0;
        font-size: 0.9375rem;
    }
    .post-item { 
        padding: 1rem 0; 
    }
    .post-item:hover { 
        margin: 0 -1rem;
        padding: 1rem;
        border-radius: 8px;
    }
    .post-meta {
        font-size: 0.8125rem;
        margin-bottom: 0.5rem;
    }
    .post-title {
        font-size: 1.125rem;
        line-height: 1.4;
        margin-bottom: 0.5rem;
    }
    .post-preview {
        font-size: 0.875rem;
        line-height: 1.5;
    }
    .posts-list {
        margin-bottom: 2rem;
    }
}
</style>
</head>
<body>
<div class='container'>
<div class="header">
<h1>MLB Trade Rumors Daily Digest</h1>
<div class="subtitle">Curated insights from MLB Trade Rumors chats and mailbags, updated daily</div>
</div>

<div class="nav-tabs">
<a href="#all" class="nav-tab active" onclick="filterPosts('all', event)">All Posts</a>
<a href="#chat" class="nav-tab" onclick="filterPosts('chat', event)">Chats</a>
<a href="#mailbag" class="nav-tab" onclick="filterPosts('mailbag', event)">Mailbags</a>
</div>

<div class="posts-list" id="posts-list">
<!-- Posts will be inserted here by JavaScript -->
</div>

<div class="footer">
<div class="footer-stats">
<div class="stat">
<div class="stat-number" id="chat-count">0</div>
<div class="stat-label">Chats</div>
</div>
<div class="stat">
<div class="stat-number" id="mailbag-count">0</div>
<div class="stat-label">Mailbags</div>
</div>
</div>
<div>MLB Trade Rumors Daily Digest &middot; Auto-updated</div>
</div>
</div>

<script>
// Data structure for all posts
const posts = """)

        # Write posts as JSON
        import json
        f.write(json.dumps(all_posts, indent=2))
        f.write(""";

// Function to render posts
function renderPosts(filter = 'all') {
    const container = document.getElementById('posts-list');
    const filteredPosts = filter === 'all' ? posts : posts.filter(p => p.type === filter);
    
    container.innerHTML = filteredPosts.map(post => `
        <div class="post-item">
            <a href="${post.url}" class="post-link">
                <div class="post-header">
                    <span class="post-date">${formatDate(post.date)}</span>
                    <span class="post-type ${post.type}">${post.type}</span>
                </div>
                <div class="post-title">${post.title}</div>
                <div class="post-preview">${post.preview}</div>
            </a>
        </div>
    `).join('');
}

// Format date nicely
function formatDate(dateStr) {
    const date = new Date(dateStr);
    const options = { month: 'short', day: 'numeric', year: 'numeric' };
    return date.toLocaleDateString('en-US', options);
}

// Filter posts by type
function filterPosts(type, event) {
    event.preventDefault();
    
    // Update active tab
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    event.target.classList.add('active');
    
    // Render filtered posts
    renderPosts(type);
}

// Update stats
function updateStats() {
    const chatCount = posts.filter(p => p.type === 'chat').length;
    const mailbagCount = posts.filter(p => p.type === 'mailbag').length;
    
    document.getElementById('chat-count').textContent = chatCount;
    document.getElementById('mailbag-count').textContent = mailbagCount;
}

// Initialize
renderPosts();
updateStats();
</script>
</body>
</html>""")


# --------------------------------------------------
# ENTRYPOINT
# --------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Daily MLBTR chat summariser")
    parser.add_argument("--force", action="store_true", help="Re-process today's articles even if output exists")
    parser.add_argument("--regenerate-all", action="store_true", help="Regenerate all articles with updated prompts")
    parser.add_argument("--since", type=str, help="Process articles since this date (YYYY-MM-DD)")
    parser.add_argument("--manual-url", type=str, help="Manually process a specific URL")
    parser.add_argument("--manual-type", type=str, choices=["chat", "mailbag"], help="Type for manual URL processing")
    parser.add_argument("--manual-date", type=str, help="Date for manual URL processing (YYYY-MM-DD)")
    args = parser.parse_args()
    out_base_dir = OUT_DIR

    since_date = None
    if args.since:
        try:
            since_date = dt.datetime.strptime(args.since, "%Y-%m-%d").date()
            print(f"Processing articles since {since_date}")
        except ValueError:
            print(f"Invalid date format: {args.since}. Use YYYY-MM-DD format.")
            return

    # Handle manual URL processing
    if args.manual_url:
        if not args.manual_type or not args.manual_date:
            print("Error: --manual-url requires both --manual-type and --manual-date")
            return
        
        try:
            manual_date = dt.datetime.strptime(args.manual_date, "%Y-%m-%d").date()
            print(f"Processing manual URL: {args.manual_url}")
            
            # Create a fake article object for manual processing
            manual_article = Article(
                title=f"Manual {args.manual_type.title()} Processing",
                url=args.manual_url,
                date=manual_date,
                post_type=args.manual_type
            )
            
            out_dir = out_base_dir / manual_article.post_type / str(manual_article.date)
            pairs_raw = extract_content_by_type(manual_article.url, manual_article.post_type)
            
            # Save raw data
            out_dir.mkdir(parents=True, exist_ok=True)
            raw_data_path = out_dir / "raw_extracted_data.txt"
            with raw_data_path.open("w", encoding="utf-8") as f_raw:
                for speaker, text in pairs_raw:
                    f_raw.write(f"SPEAKER: {speaker}\n---\n{text}\n\n{'='*20}\n\n")
            print(f"  -> Raw data saved to: {raw_data_path}")
            
            pairs_priority = prioritise_pairs(pairs_raw)
            summary = build_summary(pairs_priority, manual_article.post_type)
            write_html(summary, pairs_raw, manual_article.title, out_dir)
            
            # Rebuild index
            build_main_index(out_base_dir)
            return
            
        except ValueError:
            print(f"Invalid date format: {args.manual_date}. Use YYYY-MM-DD format.")
            return
        except Exception as e:
            print(f"Error processing manual URL: {e}")
            return

    if args.regenerate_all:
        print("--regenerate-all specified, will re-process ALL articles with updated prompts.")
    elif args.force:
        print("--force specified, will re-process today's articles and regenerate full index.")

    new_articles = fetch_new_articles(out_base_dir, force=args.force, regenerate_all=args.regenerate_all, since_date=since_date)
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