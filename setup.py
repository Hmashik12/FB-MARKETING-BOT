#!/usr/bin/env python3
import os
import subprocess
import sys

def setup_environment():
    """Set up the environment for the bot."""
    print("🔧 Setting up environment...")

    # Create virtual environment if it doesn't exist
    if not os.path.exists("venv"):
        print("🔨 Creating virtual environment...")
        subprocess.check_call([sys.executable, "-m", "venv", "venv"])

    # Determine the pip path
    pip_path = os.path.join("venv", "bin", "pip") if os.path.exists(os.path.join("venv", "bin", "pip")) else os.path.join("venv", "Scripts", "pip")

    # Install requirements
    print("📦 Installing requirements...")
    subprocess.check_call([pip_path, "install", "--upgrade", "pip"])
    subprocess.check_call([pip_path, "install", "-r", "requirements.txt"])

    print("✅ Setup complete! You can now run the bot with: python3 main.py")

if __name__ == "__main__":
    setup_environment()
