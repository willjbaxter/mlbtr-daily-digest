# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Development and Testing
```bash
# Run main application to process new articles
.venv/bin/python3 mlbtr_daily_summary.py

# Force regenerate today's articles (useful during development)
.venv/bin/python3 mlbtr_daily_summary.py --force

# Regenerate all articles with updated prompts
.venv/bin/python3 mlbtr_daily_summary.py --regenerate-all

# Process articles since a specific date
.venv/bin/python3 mlbtr_daily_summary.py --since 2025-08-01

# Manually process a specific URL (for testing/debugging)
.venv/bin/python3 mlbtr_daily_summary.py --manual-url "https://example.com" --manual-type chat --manual-date 2025-08-11

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Deployment
The site uses GitHub Pages for hosting. Files from `out/` directory are automatically synced to the root by GitHub Actions for GitHub Pages compatibility.

## Architecture Overview

### Core Application Flow
The system operates as a content aggregation and summarization pipeline:

1. **RSS Feed Monitoring** (`fetch_new_articles()`) - Scans MLB Trade Rumors RSS for new chat transcripts and mailbags
2. **Content Extraction** (`extract_transcript()`, `extract_mailbag_content()`) - Parses HTML to extract speaker-text pairs from chat transcripts and full content from mailbags
3. **Content Processing** (`prioritise_pairs()`) - Identifies priority content based on team keywords (Red Sox, Yankees, AL East, Cubs)
4. **Summarization** (`build_summary()`) - Uses Claude 3.5 Sonnet API to generate structured insights, with fallback to keyword-based extraction
5. **HTML Generation** (`write_html()`) - Creates summary pages with two-column layout (insights + transcript)
6. **Index Generation** (`build_main_index()`) - Maintains central index with JavaScript-driven filtering

### Data Processing Pipeline
- **Input**: MLB Trade Rumors RSS feed entries
- **Parsing**: BeautifulSoup extracts content from specific div classes (`live-chat-archive`, `entry-content`)
- **Encoding**: UTF-8 handling with mojibake cleanup (removes `\u00c2` characters)
- **Output**: Structured HTML files in `out/` directory organized by type and date

### Content Types
The system handles two distinct content types with different parsing strategies:

1. **Chat Transcripts**: Structured Q&A format with speaker identification
   - Extracts `<p class="moderator">` and `<p class="user">` elements
   - Processes corresponding `<ul><li>` content blocks
   - Prioritizes expert responses over fan questions

2. **Mailbags**: Long-form analysis content
   - Extracts full text content from article body
   - Removes promotional content automatically
   - Generates comprehensive topic-based summaries

### LLM Integration
Uses hierarchical LLM fallback system:
1. **Primary**: Claude 3.5 Sonnet (via `CLAUDE_API_KEY`)
2. **Secondary**: OpenAI GPT-4 (via `OPENAI_API_KEY`) 
3. **Tertiary**: Google Gemini (via `GEMINI_API_KEY`)
4. **Fallback**: Keyword-based extraction without LLM

Critical prompting includes explicit date preservation instructions to prevent temporal confusion (e.g., 2025 → 2023 substitutions).

### UI Design System
- **Main Index**: Blog-style list with JavaScript filtering and date-based sorting
- **Individual Pages**: Two-column layout with insights panel (left) and scrollable transcript (right)
- **Responsive**: CSS Grid with mobile-first breakpoints at 768px, single-column layout on mobile
- **Typography**: Inter font with consistent spacing and color hierarchy
- **Navigation**: Breadcrumb navigation and footer links between pages
- **Mobile Optimizations**: Viewport meta tag, improved touch targets, reduced font sizes, better spacing

### File Structure
```
out/
├── index.html                    # Main navigation page
├── chat/YYYY-MM-DD/
│   ├── summary.html             # Two-column summary page
│   ├── transcript.html          # Full transcript (legacy)
│   └── raw_extracted_data.txt   # Debug/inspection data
└── mailbag/YYYY-MM-DD/
    ├── summary.html
    ├── transcript.html
    └── raw_extracted_data.txt
```

## Configuration

### Team Priority Keywords
Modify `KEYWORDS_PRIMARY` set in `mlbtr_daily_summary.py` to change which teams get highlighted with red arrows (→) instead of green bullets (•).

### Post Type Configuration
The `POST_TYPES` dictionary defines content matching patterns and LLM prompts for each content type. Each post type includes:
- `match_keywords`: RSS title patterns for content detection (e.g., `["chat transcript", "live chat", "subscriber chat"]`)
- `prompt`: Specific LLM instructions for that content type

Current keywords:
- **Chat**: `["chat transcript", "live chat", "subscriber chat"]`
- **Mailbag**: `["mailbag"]`

### Environment Variables
- `CLAUDE_API_KEY`: Primary LLM for summarization
- `OPENAI_API_KEY`: Secondary LLM fallback  
- `GEMINI_API_KEY`: Tertiary LLM fallback

## Common Development Patterns

### Adding New Content Types
1. Add entry to `POST_TYPES` dictionary with match keywords and prompt
2. Implement extraction function if needed (following `extract_transcript` pattern)
3. Update `extract_content_by_type()` dispatcher
4. Test with `--manual-url` flag

### Debugging Content Extraction
- Use `raw_extracted_data.txt` files to inspect extracted content before summarization
- Enable manual URL processing with `--manual-url` for specific articles
- Check encoding issues by examining raw text output

### UI Updates
- Main index template is generated dynamically in `build_main_index()`
- Individual page template is in `HEAD_TEMPLATE` and `write_html()` function
- CSS is embedded in templates for performance and simplicity

## Content Management

### Title Standardization
All articles use consistent title format:
- **Chat articles**: `"Chat: Aug 18"` (MMM DD format)
- **Mailbag articles**: `"Mailbag: Aug 13"` (MMM DD format)

### Preview Generation
The system automatically generates intelligent previews by:
1. Extracting player names using regex pattern `\b[A-Z][a-z]+ [A-Z][a-z]+\b`
2. Identifying team mentions from comprehensive team list (30 MLB teams)
3. Combining up to 2 players and 1 team per insight for concise previews
4. Fallback to first insight text if no names/teams found

Examples:
- `"Red Sox, Tanner Houck, Trent Grisham, Yankees"`
- `"Spencer Jones, Mason Miller, Yankees"`
- `"Jarren Duran, Mitch Keller, Pirates"`

### Automation Status
- **Daily Pipeline**: Runs at 10 PM UTC via GitHub Actions
- **Content Detection**: Enhanced with "subscriber chat" keyword for broader coverage
- **Title/Preview System**: Automatically applied to all new and regenerated content
- **Mobile Layout**: Fully responsive with dedicated mobile breakpoints