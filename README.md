# 🔮 META GHOST Telegram Bot

A powerful Telegram bot with multiple features including temporary email generation, name generation, and 2FA code generation.

## 🚀 Features

### 📧 Temporary Email
- Generate disposable email addresses using mail.tm API
- Auto-check for new emails every 5 seconds
- Real-time email notifications
- Copy email to clipboard functionality

### 🥷 Name Generator
- Generate random male and female names
- Bangladeshi/South Asian name database
- Copy generated names to clipboard
- Regenerate names with one click

### 🔑 2FA Code Generator
- Generate TOTP codes for two-factor authentication
- Support for Google Authenticator format
- Real-time countdown timer
- Secure secret key processing

### 🎯 User Interface
- Clean inline keyboard interface
- Mobile-optimized design
- Easy navigation with menu system
- Stop functionality for all operations

## 📱 Commands

- `/start` - Start the bot and show main menu
- `/help` - Show help message with all features
- `/menu` - Display the main menu

## 🛠️ Setup Instructions

### For Replit:

1. Create a new Python Replit project
2. Copy all files to your project
3. Install dependencies: `pip install -r requirements.txt`
4. Run the bot: `python main.py`

### Bot Token
Your bot token is already configured in the code.

## 🔧 Technical Details

- **Framework**: python-telegram-bot 20.6
- **2FA Library**: pyotp 2.9.0
- **HTTP Requests**: requests 2.31.0
- **Email Service**: mail.tm API
- **Architecture**: Async/await pattern for better performance

## 📞 Support

For support and questions, contact @ghost_cipher on Telegram.

## 🔒 Security

- Bot token is securely embedded
- No user data is permanently stored
- All operations are session-based
- Secure API communication with mail.tm

## 🎨 Interface Preview

The bot features a dark-themed interface with:
- 🔮 META GHOST branding
- 📱 Mobile Optimized design
- Inline buttons for all features
- Real-time status updates

Enjoy using META GHOST Bot! 🚀