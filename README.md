# MLBTR Daily Digest

A Python-powered tool that automatically generates clean, insightful summaries from MLB Trade Rumors chat transcripts and mailbag columns. Transform lengthy Q&A sessions into digestible insights perfect for staying up-to-date with baseball's trade deadline buzz.

## 🚀 Features

- **🤖 AI-Powered Quality Control**: Multi-agent validation system ensures every post is accurate, well-formatted, and insightful
- **Automated Content Extraction**: Pulls the latest chat transcripts and mailbag columns from MLB Trade Rumors RSS feed
- **Smart Insight Generation**: Converts raw Q&A content into meaningful, specific insights rather than generic summaries  
- **Intelligent Previews**: Auto-generated previews with player names and team mentions (e.g., "Red Sox, Tanner Houck, Yankees")
- **Priority Team Highlighting**: Automatically highlights content related to Red Sox, Yankees, AL East teams, and Cubs
- **Clean, Professional Design**: Modern web interface inspired by top sports journalism sites
- **Responsive Layout**: Works perfectly on desktop and mobile devices
- **Expert-Focused**: Prioritizes analysis from MLB Trade Rumors experts over fan questions
- **Production-Safe**: Circuit breaker patterns and graceful degradation prevent system failures

## 📱 Live Demo

Check out the live version: [MLBTR Daily Digest](https://mlbtr.willbaxter.info)

![MLBTR Daily Digest Screenshot](screenshot.png)

## 🛠 How It Works

1. **RSS Monitoring**: Scans MLB Trade Rumors RSS feed for new chat transcripts and mailbags
2. **Content Parsing**: Extracts clean speaker-text pairs from HTML using BeautifulSoup
3. **Insight Generation**: Analyzes content to create specific, actionable insights
4. **🤖 Agent Validation**: 4-agent pipeline validates and improves content quality:
   - **Extraction Agent**: Validates content extraction and formatting
   - **Editorial Agent**: Fixes team assignments, standardizes titles, improves quality
   - **Preview Agent**: Generates intelligent previews with player/team extraction  
   - **Publisher Agent**: Final validation before publication
5. **Web Generation**: Produces clean HTML summaries with full transcript access
6. **Index Creation**: Maintains a central index of all generated summaries

## 📋 Sample Output

Instead of generic bullets like "Trade deadline activity discussed", you get specific insights like:

- 🔴 **Dodgers expected to add notable reliever; Bednar and Helsley both likely to be traded, though Clase less likely to move**
- **Players who exercise opt-out clauses can receive qualifying offers if they haven't previously received one and spent full season with the team**
- **Sandy Leon called up to Braves, reinforcing expectation that Marcell Ozuna will be traded**

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Virtual environment (recommended)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/willjbaxter/mlbtr-daily-digest.git
cd mlbtr-daily-digest
```

2. Create and activate virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

### Usage

#### Generate Today's Summaries
```bash
./mlbtr_daily_summary.py
```

#### Force Regenerate Today's Content
```bash
./mlbtr_daily_summary.py --force
```

#### Regenerate All Historical Content (with Agent Validation)
```bash
ENABLE_AGENT_VALIDATION=true AGENT_VALIDATION_PERCENTAGE=100 GEMINI_API_KEY=your_key ./mlbtr_daily_summary.py --regenerate-all
```

#### Agent Validation Commands
```bash
# Full agent validation (recommended)
ENABLE_AGENT_VALIDATION=true AGENT_VALIDATION_PERCENTAGE=100 GEMINI_API_KEY=your_key ./mlbtr_daily_summary.py

# Test in shadow mode (agents run but don't affect output)
ENABLE_AGENT_VALIDATION=true AGENT_SHADOW_MODE=true GEMINI_API_KEY=your_key ./mlbtr_daily_summary.py

# Emergency: disable agents
ENABLE_AGENT_VALIDATION=false ./mlbtr_daily_summary.py
```

#### Custom Output Directory
```bash
./mlbtr_daily_summary.py --out /path/to/output
```

### Automated Daily Runs

Set up a daily cron job to automatically generate summaries:

```bash
# Run daily at 6 PM
0 18 * * * /usr/bin/python3 /path/to/mlbtr_daily_summary.py
```

## 🎨 Design Philosophy

The interface draws inspiration from professional sports journalism sites like The Ringer and The Athletic:

- **Clean Typography**: System fonts for maximum readability
- **Minimal Color Palette**: Focus on content over flashy design  
- **Subtle Highlighting**: Red accent for priority team content
- **Responsive Grid**: Works seamlessly across all device sizes
- **Fast Loading**: Lightweight HTML with embedded CSS

## 🔧 Configuration

### Team Priorities

Edit the `KEYWORDS_PRIMARY` set in `mlbtr_daily_summary.py` to customize which teams get priority highlighting:

```python
KEYWORDS_PRIMARY = {
    "red sox", "boston", "yankees", "new york", 
    "rays", "tampa", "orioles", "baltimore",
    "blue jays", "toronto", "cubs", "chicago cubs"
}
```

### LLM Integration

For enhanced summarization and agent validation:

```bash
export CLAUDE_API_KEY="your-claude-key"     # Primary LLM for summarization
export OPENAI_API_KEY="your-openai-key"     # Secondary LLM fallback
export GEMINI_API_KEY="your-gemini-key"     # Tertiary fallback + agent system
```

**Agent Validation Environment Variables:**
```bash
export ENABLE_AGENT_VALIDATION=true          # Enable agent validation system
export AGENT_VALIDATION_PERCENTAGE=100       # Percentage of content to validate (0-100)
export AGENT_SHADOW_MODE=false               # Set to true for testing without affecting output
```

Without API keys, the tool uses a smart fallback that still produces excellent results, but without agent validation.

## 📁 Project Structure

```
mlbtr-daily-digest/
├── mlbtr_daily_summary.py    # Main application
├── agent_validation.py       # Multi-agent content validation system
├── test_agents.py           # Agent testing suite
├── rollback_agents.py       # Emergency agent rollback system
├── requirements.txt          # Python dependencies  
├── run_daily.sh             # Shell script for automation
├── env.example              # Environment variables template
├── .github/workflows/       # GitHub Actions automation
├── out/                     # Generated HTML files
│   ├── index.html          # Main navigation page  
│   ├── chat/               # Chat transcript summaries
│   └── mailbag/           # Mailbag summaries
├── chat/                    # Root chat files (GitHub Pages)
├── mailbag/                 # Root mailbag files (GitHub Pages)
├── index.html               # Root index (GitHub Pages)
└── README.md               # This file
```

## 🤝 Contributing

This is a personal project, but suggestions and improvements are welcome! Feel free to:

- Report bugs via GitHub issues
- Suggest new features
- Submit pull requests for improvements

## 📄 License

MIT License - feel free to use this code for your own projects!

## 🏗 Built With

- **Python 3** - Core application logic
- **BeautifulSoup4** - HTML parsing and content extraction
- **Requests** - HTTP requests for content fetching
- **Feedparser** - RSS feed processing
- **Claude/OpenAI/Gemini APIs** - LLM integration with fallback hierarchy
- **Google Gemini** - Multi-agent validation system
- **LangGraph** - Agent orchestration framework
- **GitHub Actions** - Automated daily deployment
- **GitHub Pages** - Static site hosting

## 👨‍💻 About

Created by [Will Baxter](https://willbaxter.info) as a showcase project demonstrating:
- Web scraping and content extraction
- Multi-agent AI system architecture
- Production-safe AI deployment patterns
- Natural language processing and content validation
- Clean web design principles  
- Python automation and scheduling
- Modern development practices
- Circuit breaker patterns and graceful degradation

---

*Stay up-to-date with MLB trade rumors without the noise. Get the insights that matter.* 