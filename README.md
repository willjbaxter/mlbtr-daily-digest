# MLBTR Daily Digest

A Python-powered tool that automatically generates clean, insightful summaries from MLB Trade Rumors chat transcripts and mailbag columns. Transform lengthy Q&A sessions into digestible insights perfect for staying up-to-date with baseball's trade deadline buzz.

## 🚀 Features

- **Automated Content Extraction**: Pulls the latest chat transcripts and mailbag columns from MLB Trade Rumors RSS feed
- **Smart Insight Generation**: Converts raw Q&A content into meaningful, specific insights rather than generic summaries  
- **Priority Team Highlighting**: Automatically highlights content related to Red Sox, Yankees, AL East teams, and Cubs
- **Clean, Professional Design**: Modern web interface inspired by top sports journalism sites
- **Responsive Layout**: Works perfectly on desktop and mobile devices
- **Expert-Focused**: Prioritizes analysis from MLB Trade Rumors experts over fan questions

## 📱 Live Demo

Check out the live version: [MLBTR Daily Digest](https://willjbaxter.github.io/mlbtr-daily-digest/)

![MLBTR Daily Digest Screenshot](screenshot.png)

## 🛠 How It Works

1. **RSS Monitoring**: Scans MLB Trade Rumors RSS feed for new chat transcripts and mailbags
2. **Content Parsing**: Extracts clean speaker-text pairs from HTML using BeautifulSoup
3. **Insight Generation**: Analyzes content to create specific, actionable insights
4. **Web Generation**: Produces clean HTML summaries with full transcript access
5. **Index Creation**: Maintains a central index of all generated summaries

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

#### Regenerate All Historical Content
```bash
./mlbtr_daily_summary.py --regenerate-all
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

### LLM Integration (Optional)

For enhanced summarization, set environment variables:

```bash
export OPENAI_API_KEY="your-key-here"
# or
export GEMINI_API_KEY="your-key-here"
```

Without API keys, the tool uses a smart fallback that still produces excellent results.

## 📁 Project Structure

```
mlbtr-daily-digest/
├── mlbtr_daily_summary.py    # Main application
├── requirements.txt          # Python dependencies  
├── run_daily.sh             # Shell script for automation
├── env.example              # Environment variables template
├── out/                     # Generated HTML files
│   ├── index.html          # Main navigation page
│   ├── chat/               # Chat transcript summaries
│   └── mailbag/           # Mailbag summaries
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
- **OpenAI/Gemini APIs** - Optional enhanced summarization

## 👨‍💻 About

Created by [Will Baxter](https://willbaxter.info) as a showcase project demonstrating:
- Web scraping and content extraction
- Natural language processing
- Clean web design principles  
- Python automation and scheduling
- Modern development practices

---

*Stay up-to-date with MLB trade rumors without the noise. Get the insights that matter.* 