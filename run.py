# Alternative way to run the bot
# এই ফাইল তৈরি করে Run বাটন দিয়ে চালাতে পারেন

import subprocess
import sys
import os

def install_requirements():
    """Install required packages."""
    print("📦 Installing requirements...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ Requirements installed successfully!")

def run_bot():
    """Run the main bot."""
    print("🚀 Starting META GHOST Bot...")
    import main
    
if __name__ == "__main__":
    try:
        install_requirements()
        run_bot()
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check your setup and try again.")