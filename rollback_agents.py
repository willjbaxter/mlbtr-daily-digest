#!/usr/bin/env python3
"""
Emergency rollback script for agent validation system
One-click disable if things go sideways
"""

import os
import sys
from pathlib import Path

def emergency_disable():
    """Immediately disable all agent validation"""
    print("🚨 EMERGENCY ROLLBACK - DISABLING ALL AGENTS")
    
    # Set environment to disable agents
    os.environ['ENABLE_AGENT_VALIDATION'] = 'false'
    os.environ['AGENT_VALIDATION_PERCENTAGE'] = '0'
    
    # Also disable in code if agents are already loaded
    try:
        from agent_validation import disable_agents
        disable_agents()
        print("✅ Agents disabled in running processes")
    except ImportError:
        print("ℹ️  Agents not loaded - environment variables set")
    
    print("✅ Agent validation disabled")
    print("   ENABLE_AGENT_VALIDATION=false")
    print("   AGENT_VALIDATION_PERCENTAGE=0")

def git_rollback():
    """Git rollback to previous version"""
    print("\n🔄 GIT ROLLBACK")
    
    # Check current branch
    import subprocess
    
    try:
        # Get current branch
        result = subprocess.run(['git', 'branch', '--show-current'], 
                              capture_output=True, text=True, check=True)
        current_branch = result.stdout.strip()
        print(f"Current branch: {current_branch}")
        
        if current_branch == 'main':
            print("⚠️  On main branch - rolling back last commit")
            # Show last commit
            result = subprocess.run(['git', 'log', '--oneline', '-1'], 
                                  capture_output=True, text=True, check=True)
            print(f"Last commit: {result.stdout.strip()}")
            
            # Confirm rollback
            response = input("Roll back this commit? (y/N): ").lower()
            if response == 'y':
                subprocess.run(['git', 'revert', 'HEAD', '--no-edit'], check=True)
                print("✅ Commit reverted")
            else:
                print("❌ Rollback cancelled")
        
        else:
            print("⚠️  On feature branch - switching to main")
            response = input("Switch to main branch? (y/N): ").lower()
            if response == 'y':
                subprocess.run(['git', 'checkout', 'main'], check=True)
                print("✅ Switched to main branch")
            else:
                print("❌ Branch switch cancelled")
                
    except subprocess.CalledProcessError as e:
        print(f"❌ Git command failed: {e}")
    except FileNotFoundError:
        print("❌ Git not found - manual rollback required")

def check_system_status():
    """Check if system is working after rollback"""
    print("\n🔍 CHECKING SYSTEM STATUS")
    
    # Test basic functionality
    try:
        # Try to run the main script with a simple command
        import subprocess
        result = subprocess.run([
            sys.executable, 'mlbtr_daily_summary.py', '--help'
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✅ Main script loads successfully")
        else:
            print(f"❌ Main script error: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("⚠️  Script timeout - may be hanging")
    except Exception as e:
        print(f"❌ Test failed: {e}")

def create_incident_report():
    """Create incident report for debugging"""
    print("\n📝 CREATING INCIDENT REPORT")
    
    from datetime import datetime
    
    report_path = Path("incident_reports") / f"rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.parent.mkdir(exist_ok=True)
    
    report_content = f"""# Agent System Rollback Incident Report

**Date**: {datetime.now().isoformat()}
**Triggered by**: {' '.join(sys.argv)}
**User**: {os.getenv('USER', 'unknown')}

## System State
- Branch: {os.popen('git branch --show-current').read().strip()}
- Last Commit: {os.popen('git log --oneline -1').read().strip()}
- Environment: {dict(os.environ)}

## Actions Taken
- [ ] Emergency agent disable
- [ ] Git rollback
- [ ] System status check

## Next Steps
- [ ] Investigate root cause
- [ ] Fix issues in feature branch  
- [ ] Re-test before next deployment

## Logs
```
{os.popen('tail -20 ~/.mlbtr.log 2>/dev/null || echo "No log file found"').read()}
```
"""

    with open(report_path, 'w') as f:
        f.write(report_content)
    
    print(f"📄 Incident report created: {report_path}")

def main():
    print("🚨 AGENT ROLLBACK SYSTEM")
    print("=" * 40)
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python rollback_agents.py emergency    # Disable agents immediately")
        print("  python rollback_agents.py git          # Git rollback")
        print("  python rollback_agents.py full         # Full rollback + incident report")
        print("  python rollback_agents.py status       # Check system status")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'emergency':
        emergency_disable()
    
    elif command == 'git':
        git_rollback()
    
    elif command == 'full':
        print("🚨 FULL ROLLBACK INITIATED")
        emergency_disable()
        git_rollback()
        check_system_status()
        create_incident_report()
        print("\n✅ Full rollback completed")
    
    elif command == 'status':
        check_system_status()
    
    else:
        print(f"Unknown command: {command}")
        return
    
    print("\n🏁 Rollback operations completed")
    print("System should be back to stable state")

if __name__ == "__main__":
    main()