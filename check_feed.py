#!/usr/bin/env python3
"""
Quick script to check MLBTR RSS feed for new chat/mailbag content.
Usage: python check_feed.py
"""

import feedparser
import datetime as dt

RSS_FEED = "https://www.mlbtraderumors.com/feed"

def check_for_new_content():
    """Check RSS feed for chat transcripts and mailbags."""
    print(f"Checking MLBTR RSS feed at {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Feed URL: {RSS_FEED}")
    print("-" * 50)
    
    try:
        feed = feedparser.parse(RSS_FEED)
        
        if not feed.entries:
            print("❌ No entries found in RSS feed")
            return
            
        print(f"✅ Found {len(feed.entries)} total articles in feed")
        print()
        
        # Check for chats and mailbags
        chats = []
        mailbags = []
        
        for entry in feed.entries:
            title_lower = entry.title.lower()
            published_date = None
            
            try:
                if hasattr(entry, 'published'):
                    published_date = dt.datetime.strptime(entry.published[:16], "%a, %d %b %Y").date()
            except:
                pass
            
            # Check for chat transcripts
            if any(kw in title_lower for kw in ["chat transcript", "live chat"]):
                chats.append((entry.title, published_date, entry.link))
            
            # Check for mailbags
            elif "mailbag" in title_lower:
                mailbags.append((entry.title, published_date, entry.link))
        
        print(f"🗣️  Chat Transcripts Found: {len(chats)}")
        for title, date, url in sorted(chats, key=lambda x: x[1] or dt.date.min, reverse=True)[:5]:
            date_str = str(date) if date else "Unknown date"
            print(f"   • {date_str}: {title}")
        
        print()
        print(f"📧 Mailbags Found: {len(mailbags)}")
        for title, date, url in sorted(mailbags, key=lambda x: x[1] or dt.date.min, reverse=True)[:5]:
            date_str = str(date) if date else "Unknown date"
            print(f"   • {date_str}: {title}")
        
        if not chats and not mailbags:
            print("ℹ️  No chat transcripts or mailbags found in current RSS feed")
            print("   This is normal - MLBTR doesn't publish chats/mailbags every day")
        
        print()
        print("🔄 Most recent 5 articles of any type:")
        for i, entry in enumerate(feed.entries[:5]):
            try:
                published_date = dt.datetime.strptime(entry.published[:16], "%a, %d %b %Y").date()
                date_str = str(published_date)
            except:
                date_str = "Unknown date"
            print(f"   {i+1}. {date_str}: {entry.title}")
        
    except Exception as e:
        print(f"❌ Error checking RSS feed: {e}")

if __name__ == "__main__":
    check_for_new_content()