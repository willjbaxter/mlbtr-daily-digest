#!/usr/bin/env python3
"""
MLBTR Daily Digest Monitoring and Management Script

This script helps you:
1. Monitor for new content that might not be in RSS
2. Manually add content when needed
3. Check system health
4. View recent activity

Usage:
    python monitor_and_fix.py status       # Check current status
    python monitor_and_fix.py feed         # Check RSS feed
    python monitor_and_fix.py add <url> <type> <date>  # Manually add content
    python monitor_and_fix.py history      # Show recent activity
"""

import sys
import subprocess
import datetime as dt
from pathlib import Path

def run_command(cmd, description):
    """Run a shell command and return output."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Success")
            return result.stdout.strip()
        else:
            print(f"❌ Failed: {result.stderr.strip()}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def check_status():
    """Check the overall system status."""
    print("🔍 MLBTR Daily Digest System Status")
    print("=" * 50)
    
    # Check virtual environment
    venv_path = Path("venv/bin/python")
    if venv_path.exists():
        print("✅ Virtual environment found")
    else:
        print("❌ Virtual environment missing")
        return
    
    # Check dependencies
    result = run_command("source venv/bin/activate && python -c 'import feedparser, requests, bs4; print(\"All dependencies available\")'", "Checking dependencies")
    
    # Check GitHub Actions status
    print("\n📊 Recent GitHub Actions runs:")
    run_command("gh run list --limit 5", "Checking recent workflow runs")
    
    # Check output directory
    out_dir = Path("out")
    if out_dir.exists():
        chat_dirs = list((out_dir / "chat").glob("*")) if (out_dir / "chat").exists() else []
        mailbag_dirs = list((out_dir / "mailbag").glob("*")) if (out_dir / "mailbag").exists() else []
        
        print(f"\n📁 Output directory status:")
        print(f"   Chat summaries: {len(chat_dirs)}")
        print(f"   Mailbag summaries: {len(mailbag_dirs)}")
        
        if chat_dirs or mailbag_dirs:
            all_dirs = chat_dirs + mailbag_dirs
            latest = max(all_dirs, key=lambda x: x.name)
            print(f"   Latest summary: {latest.name}")
    
    # Test script execution
    print(f"\n🧪 Testing script execution:")
    run_command("source venv/bin/activate && python check_feed.py", "Running feed check")

def check_feed():
    """Check RSS feed for new content."""
    run_command("source venv/bin/activate && python check_feed.py", "Checking RSS feed")

def add_manual_content(url, content_type, date_str):
    """Manually add content from a URL."""
    if content_type not in ["chat", "mailbag"]:
        print("❌ Error: type must be 'chat' or 'mailbag'")
        return
    
    try:
        dt.datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print("❌ Error: date must be in YYYY-MM-DD format")
        return
    
    print(f"🔄 Manually processing {content_type} from {date_str}...")
    cmd = f"source venv/bin/activate && python mlbtr_daily_summary.py --manual-url '{url}' --manual-type {content_type} --manual-date {date_str}"
    run_command(cmd, f"Processing {content_type}")
    
    print(f"\n✅ Manual processing complete!")
    print(f"📂 Check out/{content_type}/{date_str}/ for results")

def show_history():
    """Show recent activity and summaries."""
    print("📈 Recent Activity History")
    print("=" * 50)
    
    # Show recent summaries
    out_dir = Path("out")
    if not out_dir.exists():
        print("❌ No output directory found")
        return
    
    all_summaries = []
    
    # Collect all summaries with dates
    for content_type in ["chat", "mailbag"]:
        type_dir = out_dir / content_type
        if type_dir.exists():
            for date_dir in type_dir.iterdir():
                if date_dir.is_dir() and (date_dir / "summary.html").exists():
                    try:
                        date_obj = dt.datetime.strptime(date_dir.name, "%Y-%m-%d").date()
                        all_summaries.append((date_obj, content_type, date_dir.name))
                    except ValueError:
                        continue
    
    # Sort by date (newest first)
    all_summaries.sort(key=lambda x: x[0], reverse=True)
    
    if not all_summaries:
        print("❌ No summaries found")
        return
    
    print(f"📊 Found {len(all_summaries)} total summaries:")
    print()
    
    for date_obj, content_type, date_str in all_summaries[:10]:  # Show last 10
        days_ago = (dt.date.today() - date_obj).days
        if days_ago == 0:
            age_str = "today"
        elif days_ago == 1:
            age_str = "yesterday"
        else:
            age_str = f"{days_ago} days ago"
        
        icon = "🗣️" if content_type == "chat" else "📧"
        print(f"   {icon} {date_str} ({age_str}) - {content_type.title()}")
    
    # Show gap analysis
    if len(all_summaries) > 1:
        print(f"\n📅 Gap Analysis:")
        latest_date = all_summaries[0][0]
        days_since_latest = (dt.date.today() - latest_date).days
        
        if days_since_latest > 3:
            print(f"⚠️  Warning: {days_since_latest} days since last summary")
            print("   Consider checking for missed content or RSS feed issues")
        else:
            print(f"✅ Latest summary was {days_since_latest} days ago (normal)")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1].lower()
    
    if command == "status":
        check_status()
    elif command == "feed":
        check_feed()
    elif command == "add":
        if len(sys.argv) != 5:
            print("Usage: python monitor_and_fix.py add <url> <type> <date>")
            print("Example: python monitor_and_fix.py add 'https://...' chat 2025-08-01")
            return
        add_manual_content(sys.argv[2], sys.argv[3], sys.argv[4])
    elif command == "history":
        show_history()
    else:
        print(f"Unknown command: {command}")
        print(__doc__)

if __name__ == "__main__":
    main()