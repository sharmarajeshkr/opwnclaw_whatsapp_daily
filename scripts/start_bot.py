"""
scripts/start_bot.py
--------------------
Convenience alias to launch the main bot daemon from the project root.
Usage: python scripts/start_bot.py [--phone <phone>]
"""
import sys
import os
import subprocess

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

def main():
    cmd = [sys.executable, "main.py"] + sys.argv[1:]
    print(f"[*] Launching Interview Bot Daemon from {PROJECT_ROOT}...")
    try:
        # Use subprocess.run to keep it simple for this script
        subprocess.run(cmd, cwd=PROJECT_ROOT)
    except KeyboardInterrupt:
        print("\n[!] Bot daemon stopped.")

if __name__ == "__main__":
    main()
