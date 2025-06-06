import os
import time
import json
import random
import string
import pyotp
import requests
import asyncio
import logging
import re
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from keep_alive import keep_alive

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token
BOT_TOKEN = "7366992515:AAE7hR-dLQsqiLV9lTDRBsswv9ssPOne5yg"

# Dictionary to store user data
user_data = {}

# Dictionary to store email checking tasks
email_tasks = {}

# Dictionary to store received emails for each user
user_emails = {}

# Mail.tm API endpoints
MAIL_TM_API = "https://api.mail.tm"
MAIL_TM_DOMAINS_URL = f"{MAIL_TM_API}/domains"
MAIL_TM_ACCOUNTS_URL = f"{MAIL_TM_API}/accounts"
MAIL_TM_MESSAGES_URL = f"{MAIL_TM_API}/messages"
MAIL_TM_TOKEN_URL = f"{MAIL_TM_API}/token"

# Alternative APIs
GUERRILLA_API = "https://www.guerrillamail.com/ajax.php"
TEMP_MAIL_API = "https://api.temp-mail.org/request"

# Reduced Bangladeshi Male First Names (20)
male_first_names = [
    "Abdullah", "Ahmed", "Ali", "Amir", "Anwar", "Arif", "Asif", "Aziz", 
    "Farid", "Farhan", "Faisal", "Habib", "Hasan", "Ibrahim", "Imran", 
    "Karim", "Khalid", "Mohammad", "Omar", "Rashid"
]

# Reduced Bangladeshi Male Last Names (20)
male_last_names = [
    "Ahmed", "Khan", "Rahman", "Hossain", "Islam", "Chowdhury", "Ali", "Uddin", 
    "Miah", "Sheikh", "Sarkar", "Molla", "Siddique", "Haque", "Alam", "Karim",
    "Hassan", "Hussain", "Mahmud", "Bhuiyan"
]

# Reduced Bangladeshi Female First Names (20)
female_first_names = [
    "Fatima", "Aisha", "Nusrat", "Sabina", "Taslima", "Nasrin", "Rahima", "Salma", 
    "Amina", "Farida", "Jasmine", "Roksana", "Sadia", "Tania", "Zara", "Nadia",
    "Farzana", "Rabeya", "Sharmin", "Tahmina"
]

# Reduced Bangladeshi Female Last Names (20)
female_last_names = [
    "Begum", "Khatun", "Akter", "Sultana", "Jahan", "Rahman", "Ahmed", "Khan", 
    "Hossain", "Islam", "Chowdhury", "Ali", "Uddin", "Miah", "Sheikh", "Sarkar",
    "Molla", "Siddique", "Haque", "Parveen"
]

# Helper functions
async def generate_random_password(length=12):
    """Generate a random password."""
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))

async def generate_random_username():
    """Generate a random username."""
    letters = string.ascii_lowercase
    digits = string.digits
    username = ''.join(random.choice(letters) for _ in range(random.randint(6, 10)))
    username += ''.join(random.choice(digits) for _ in range(random.randint(2, 4)))
    return username

def extract_codes_from_text(text):
    """Extract verification codes from email text."""
    if not text:
        return []

    # Common patterns for verification codes
    patterns = [
        r'\b(\d{4,8})\b',  # 4-8 digit codes
        r'\b([A-Z0-9]{4,8})\b',  # 4-8 character alphanumeric codes
        r'code[:\s]+(\d{4,8})',  # "code: 123456"
        r'verification[:\s]+(\d{4,8})',  # "verification: 123456"
        r'confirm[:\s]+(\d{4,8})',  # "confirm: 123456"
        r'OTP[:\s]+(\d{4,8})',  # "OTP: 123456"
    ]

    codes = []
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        codes.extend(matches)

    # Remove duplicates and filter reasonable codes
    unique_codes = []
    for code in codes:
        if code not in unique_codes and len(code) >= 4 and len(code) <= 8:
            unique_codes.append(code)

    return unique_codes[:3]  # Return max 3 codes

def format_email_notification(message, email_address):
    """Format email notification in beautiful style like the image."""
    try:
        # Extract email details
        subject = message.get('subject', 'No Subject')
        from_info = message.get('from', {})

        # Get sender name and email
        if isinstance(from_info, dict):
            sender_name = from_info.get('name', 'Unknown')
            sender_email = from_info.get('address', 'unknown@email.com')
        else:
            sender_name = 'Unknown'
            sender_email = str(from_info) if from_info else 'unknown@email.com'

        # Get email content for code extraction
        intro = message.get('intro', '')
        text = message.get('text', '')
        content = f"{subject} {intro} {text}"

        # Extract codes
        codes = extract_codes_from_text(content)

        # Get current time
        current_time = datetime.now().strftime("%I:%M %p")

        # Format the beautiful notification
        notification = f"📧 **NEW EMAIL ARRIVED!** 📧\n"
        notification += f"{'═' * 35}\n\n"

        # From section
        notification += f"📨 **From:** \"{sender_name}\"\n"
        notification += f"`{sender_email}`\n\n"

        # Subject section
        notification += f"📄 **Subject:** {subject}\n"
        notification += f"{'═' * 35}\n\n"

        # Codes section (if any codes found)
        if codes:
            notification += f"🔑 **Codes:** {' | '.join(codes)}\n\n"

            # Copyable codes section
            for i, code in enumerate(codes):
                notification += f"📋 `{code}`\n"

        notification += f"\n⏰ {current_time}"

        return notification, codes

    except Exception as e:
        logger.error(f"Error formatting email notification: {str(e)}")
        return f"📧 **NEW EMAIL ARRIVED!**\n\n📄 **Subject:** {subject}\n\n⏰ {datetime.now().strftime('%I:%M %p')}", []

async def create_mail_tm_account():
    """Create a new account on mail.tm with enhanced error handling and multiple fallbacks."""
    try:
        # Headers for requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

        # Try to get domains from mail.tm
        domain = None

        try:
            logger.info("Attempting to get domains from mail.tm...")
            response = requests.get(MAIL_TM_DOMAINS_URL, headers=headers, timeout=30)
            logger.info(f"Domains response status: {response.status_code}")

            if response.status_code == 200:
                domains_data = response.json()
                logger.info(f"Domains data: {domains_data}")

                # Handle different response structures
                if isinstance(domains_data, dict) and 'hydra:member' in domains_data:
                    members = domains_data['hydra:member']
                    if isinstance(members, list) and len(members) > 0:
                        domain = members[0].get('domain')
                elif isinstance(domains_data, list) and len(domains_data) > 0:
                    domain = domains_data[0].get('domain') if isinstance(domains_data[0], dict) else domains_data[0]

                logger.info(f"Extracted domain: {domain}")
        except Exception as e:
            logger.error(f"Error getting domains: {str(e)}")

        # If no domain found, use fallback domains
        if not domain:
            fallback_domains = [
                'mailgw.com', 'guerrillamail.info', 'guerrillamail.biz', 
                'guerrillamail.com', 'guerrillamail.de', 'guerrillamail.net',
                'guerrillamail.org', 'sharklasers.com', 'grr.la', 'pokemail.net'
            ]
            domain = random.choice(fallback_domains)
            logger.info(f"Using fallback domain: {domain}")

        # Generate random address and password
        username = await generate_random_username()
        email = f"{username}@{domain}"
        password = await generate_random_password()

        logger.info(f"Generated email: {email}")

        # Try to create account on mail.tm
        account_data = {
            "address": email,
            "password": password
        }

        token = None
        account_id = "generated"

        try:
            logger.info("Attempting to create account...")
            response = requests.post(MAIL_TM_ACCOUNTS_URL, json=account_data, headers=headers, timeout=30)
            logger.info(f"Account creation response: {response.status_code}")

            if response.status_code == 201:
                try:
                    created_account = response.json()
                    account_id = created_account.get('id', 'generated')
                    logger.info(f"Account created with ID: {account_id}")
                except:
                    pass

                # Try to get auth token
                auth_data = {
                    "address": email,
                    "password": password
                }

                try:
                    logger.info("Attempting to get token...")
                    token_response = requests.post(MAIL_TM_TOKEN_URL, json=auth_data, headers=headers, timeout=30)
                    logger.info(f"Token response: {token_response.status_code}")

                    if token_response.status_code == 200:
                        token_data = token_response.json()
                        token = token_data.get('token')
                        logger.info(f"Token obtained: {token[:20] if token else 'None'}...")
                except Exception as e:
                    logger.error(f"Error getting token: {str(e)}")
        except Exception as e:
            logger.error(f"Error creating account: {str(e)}")

        # Return email data (with or without working API)
        return {
            "email": email,
            "password": password,
            "token": token or "no_token",
            "account_id": account_id,
            "domain": domain,
            "has_api": token is not None
        }, None

    except Exception as e:
        logger.error(f"Error in create_mail_tm_account: {str(e)}")
        return None, f"Error creating email: {str(e)}"

async def check_mail_tm_messages(email_data):
    """Check messages for a mail.tm account with robust error handling."""
    try:
        # If no API access, return empty
        if not email_data.get('has_api', False) or email_data.get('token') == "no_token":
            return [], None

        token = email_data.get('token')
        if not token:
            return [], None

        headers = {
            "Authorization": f"Bearer {token}",
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9'
        }

        logger.info("Checking for messages...")
        response = requests.get(MAIL_TM_MESSAGES_URL, headers=headers, timeout=20)
        logger.info(f"Messages response status: {response.status_code}")

        if response.status_code == 401:
            logger.warning("Token expired")
            return [], "Token expired"
        elif response.status_code != 200:
            logger.warning(f"Messages API returned: {response.status_code}")
            return [], None

        try:
            messages_data = response.json()
            logger.info(f"Messages data type: {type(messages_data)}")

            # Handle different response structures
            messages = []

            if isinstance(messages_data, dict):
                if 'hydra:member' in messages_data:
                    messages = messages_data['hydra:member']
                elif 'messages' in messages_data:
                    messages = messages_data['messages']
                elif 'data' in messages_data:
                    messages = messages_data['data']
                else:
                    # If it's a dict but no known structure, check if it has message-like properties
                    if 'subject' in messages_data or 'from' in messages_data:
                        messages = [messages_data]
            elif isinstance(messages_data, list):
                messages = messages_data

            logger.info(f"Extracted {len(messages)} messages")
            return messages, None

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return [], None
        except Exception as e:
            logger.error(f"Error parsing messages: {str(e)}")
            return [], None

    except requests.exceptions.Timeout:
        logger.warning("Request timeout while checking messages")
        return [], None
    except requests.exceptions.RequestException as e:
        logger.warning(f"Request error while checking messages: {str(e)}")
        return [], None
    except Exception as e:
        logger.error(f"Unexpected error checking messages: {str(e)}")
        return [], None

# Command handlers
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    try:
        user_id = update.effective_user.id

        # Initialize user data
        if user_id not in user_data:
            user_data[user_id] = {}

        # Initialize user emails storage
        if user_id not in user_emails:
            user_emails[user_id] = []

        # Create main menu keyboard
        keyboard = [
            [
                InlineKeyboardButton("📧 Temp Email", callback_data="temp_email"),
                InlineKeyboardButton("🥷 Name Gen", callback_data="name_gen")
            ],
            [
                InlineKeyboardButton("🔑 2FA Code", callback_data="2fa_code"),
                InlineKeyboardButton("👨‍💻 Developer", callback_data="developer")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send welcome message
        await update.message.reply_text(
            "🔮 META GHOST\n📱 Mobile Optimized\n\n💬 Need help? DM @hmashik_420\n\n🎯 Choose an option:",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in start_command: {str(e)}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    try:
        help_text = (
            "🔮 *META GHOST BOT HELP* 📱\n\n"
            "*Available Commands:*\n"
            "/start - Start the bot and show main menu\n"
            "/help - Show this help message\n"
            "/menu - Show main menu\n\n"
            "*Available Features:*\n"
            "📧 *Temp Email* - Generate temporary disposable email\n"
            "🥷 *Name Gen* - Generate random names\n"
            "🔑 *2FA Code* - Generate 2FA authentication codes\n"
            "👨‍💻 *Developer* - Developer information\n\n"
            "For support, contact @hmashik_420"
        )

        await update.message.reply_text(help_text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error in help_command: {str(e)}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show the main menu."""
    try:
        keyboard = [
            [
                InlineKeyboardButton("📧 Temp Email", callback_data="temp_email"),
                InlineKeyboardButton("🥷 Name Gen", callback_data="name_gen")
            ],
            [
                InlineKeyboardButton("🔑 2FA Code", callback_data="2fa_code"),
                InlineKeyboardButton("👨‍💻 Developer", callback_data="developer")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text("🏠 Menu", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in menu_command: {str(e)}")
        await update.message.reply_text("❌ An error occurred. Please try again.")

# Callback query handlers
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button clicks."""
    try:
        query = update.callback_query
        user_id = query.from_user.id

        # Initialize user data if not exists
        if user_id not in user_data:
            user_data[user_id] = {}

        # Initialize user emails storage
        if user_id not in user_emails:
            user_emails[user_id] = []

        await query.answer()

        logger.info(f"Button clicked: {query.data} by user {user_id}")

        if query.data == "temp_email":
            await handle_temp_email(query, context)
        elif query.data == "name_gen":
            await handle_name_gen(query, context)
        elif query.data == "2fa_code":
            await handle_2fa_code(query, context)
        elif query.data == "developer":
            await handle_developer(query, context)
        elif query.data == "menu":
            await show_main_menu(query)
        elif query.data == "male":
            await generate_name(query, "male")
        elif query.data == "female":
            await generate_name(query, "female")
        elif query.data == "change_email":
            await change_email(query, context)
        elif query.data == "show_current_email":
            await show_current_email(query, context)
        elif query.data.startswith("delete_email_"):
            await delete_email(query, context)
    except Exception as e:
        logger.error(f"Error in button_click: {str(e)}")
        try:
            await query.answer("❌ An error occurred. Please try again.")
        except:
            pass

async def show_main_menu(query):
    """Show the main menu."""
    try:
        keyboard = [
            [
                InlineKeyboardButton("📧 Temp Email", callback_data="temp_email"),
                InlineKeyboardButton("🥷 Name Gen", callback_data="name_gen")
            ],
            [
                InlineKeyboardButton("🔑 2FA Code", callback_data="2fa_code"),
                InlineKeyboardButton("👨‍💻 Developer", callback_data="developer")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🏠 Menu", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in show_main_menu: {str(e)}")

async def generate_name(query, gender):
    """Generate a name based on gender with mono text formatting."""
    try:
        user_id = query.from_user.id

        if gender == "male":
            first_name = random.choice(male_first_names)
            last_name = random.choice(male_last_names)
            emoji = "♂️"
            callback_data = "male"
        else:
            first_name = random.choice(female_first_names)
            last_name = random.choice(female_last_names)
            emoji = "♀️"
            callback_data = "female"

        full_name = f"{first_name} {last_name}"

        # Store the generated name
        user_data[user_id]['generated_name'] = full_name

        # Create keyboard
        keyboard = [
            [
                InlineKeyboardButton("🔄 Generate", callback_data=callback_data)
            ],
            [
                InlineKeyboardButton("🏠 Menu", callback_data="menu")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Use mono text formatting for easy copying
        await query.edit_message_text(
            f"{emoji} {gender.title()} Name:\n\n`{full_name}`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in generate_name: {str(e)}")
        await query.answer("❌ Error generating name. Please try again.")

# Feature handlers
async def handle_temp_email(query, context):
    """Handle temp email - show current email or generate new one."""
    try:
        user_id = query.from_user.id

        # Check if user already has an active email
        if user_id in user_data and 'email_data' in user_data[user_id]:
            await show_current_email(query, context)
        else:
            await generate_new_email(query, context)
    except Exception as e:
        logger.error(f"Error in handle_temp_email: {str(e)}")
        await query.answer("❌ Error. Please try again.")

async def show_current_email(query, context):
    """Show current email with change option only."""
    try:
        user_id = query.from_user.id
        email_data = user_data[user_id]['email_data']

        # Create keyboard with only change button
        keyboard = [
            [
                InlineKeyboardButton("🔄 Change Email", callback_data="change_email")
            ],
            [
                InlineKeyboardButton("🏠 Menu", callback_data="menu")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Show current email
        status_text = "🔄 Auto-checking for new emails" if email_data.get('has_api') else "📧 Email ready"

        await query.edit_message_text(
            f"📧 Your Temp Email\n\n`{email_data['email']}`\n\n{status_text}\n\n💡 New emails will appear automatically\n💡 Use Change to get a new email",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in show_current_email: {str(e)}")
        await query.answer("❌ Error showing email. Please try again.")

async def generate_new_email(query, context):
    """Generate a new temp email."""
    try:
        user_id = query.from_user.id

        # Show loading message
        await query.edit_message_text("🔄 Generating temporary email...")

        # Cancel any existing email checking task
        if user_id in email_tasks and not email_tasks[user_id].done():
            email_tasks[user_id].cancel()

        # Clear previous emails
        user_emails[user_id] = []

        # Create a new mail.tm account
        email_data, error = await create_mail_tm_account()

        if error:
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Try Again", callback_data="change_email")
                ],
                [
                    InlineKeyboardButton("🏠 Menu", callback_data="menu")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(f"❌ Error: {error}", reply_markup=reply_markup)
            return

        # Store email data
        user_data[user_id]['email_data'] = email_data

        # Create keyboard with only change button
        keyboard = [
            [
                InlineKeyboardButton("🔄 Change Email", callback_data="change_email")
            ],
            [
                InlineKeyboardButton("🏠 Menu", callback_data="menu")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send email info with mono text formatting
        status_text = "🔄 Auto-checking for new emails" if email_data.get('has_api') else "📧 Email ready"

        await query.edit_message_text(
            f"📧 Temp Email Generated\n\n`{email_data['email']}`\n\n{status_text}\n\n💡 New emails will appear automatically\n💡 Use Change to get a new email",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        # Start checking for emails if API is available
        if email_data.get('has_api'):
            email_tasks[user_id] = asyncio.create_task(
                check_emails_periodically(query.message.chat_id, context, email_data, user_id)
            )
    except Exception as e:
        logger.error(f"Error in generate_new_email: {str(e)}")
        try:
            await query.edit_message_text("❌ Error generating email. Please try again.")
        except:
            pass

async def change_email(query, context):
    """Change to a new email address."""
    try:
        user_id = query.from_user.id

        # Cancel existing email checking task
        if user_id in email_tasks and not email_tasks[user_id].done():
            email_tasks[user_id].cancel()

        # Generate new email
        await generate_new_email(query, context)
    except Exception as e:
        logger.error(f"Error in change_email: {str(e)}")
        await query.answer("❌ Error changing email. Please try again.")

async def delete_email(query, context):
    """Delete a specific email."""
    try:
        user_id = query.from_user.id
        email_index = int(query.data.split("_")[-1])

        if user_id in user_emails and 0 <= email_index < len(user_emails[user_id]):
            # Remove the email
            del user_emails[user_id][email_index]
            await query.answer("🗑️ Email deleted!")

            # Edit message to show deletion
            await query.edit_message_text(
                "🗑️ **EMAIL DELETED**\n\nThis email has been removed from your inbox.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Menu", callback_data="menu")]]),
                parse_mode="Markdown"
            )
        else:
            await query.answer("❌ Email not found.")
    except Exception as e:
        logger.error(f"Error in delete_email: {str(e)}")
        await query.answer("❌ Error deleting email.")

async def check_emails_periodically(chat_id, context, email_data, user_id):
    """Check emails periodically and send beautiful notifications."""
    try:
        checked_messages = set()
        consecutive_errors = 0
        max_consecutive_errors = 5
        check_count = 0
        max_checks = 120  # Check for 30 minutes (120 * 15 seconds)

        # If no API access, don't check
        if not email_data.get('has_api', False):
            logger.info("No API access, skipping email checking")
            return

        logger.info(f"Starting email checking for user {user_id}")

        while check_count < max_checks:
            try:
                # Check if user still has this email data
                if user_id not in user_data or 'email_data' not in user_data[user_id]:
                    logger.info("User data no longer exists, stopping email checking")
                    break

                # Check if this is still the current email
                if user_data[user_id]['email_data'] != email_data:
                    logger.info("Email data changed, stopping email checking")
                    break

                messages, error = await check_mail_tm_messages(email_data)

                if error:
                    consecutive_errors += 1
                    logger.warning(f"Error checking emails (attempt {consecutive_errors}): {error}")

                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("Too many consecutive errors, stopping email checking")
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text="❌ Email checking stopped due to repeated errors.\n\nPlease generate a new email."
                        )
                        break
                    else:
                        # Wait longer before retrying
                        await asyncio.sleep(30)
                        continue
                else:
                    consecutive_errors = 0  # Reset error count on success

                # Check for new messages
                new_message_count = 0
                for msg in messages:
                    msg_id = msg.get('id', str(hash(str(msg))))
                    if msg_id not in checked_messages:
                        checked_messages.add(msg_id)
                        new_message_count += 1

                        # Store email for user
                        if user_id not in user_emails:
                            user_emails[user_id] = []
                        user_emails[user_id].append(msg)

                        # Format beautiful notification
                        notification, codes = format_email_notification(msg, email_data['email'])

                        # Create keyboard with delete and menu buttons
                        email_index = len(user_emails[user_id]) - 1
                        keyboard = [
                            [
                                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_email_{email_index}"),
                                InlineKeyboardButton("🏠 Menu", callback_data="menu")
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)

                        # Send beautiful notification
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=notification,
                            reply_markup=reply_markup,
                            parse_mode="Markdown"
                        )

                if new_message_count > 0:
                    logger.info(f"Sent {new_message_count} new email notifications to user {user_id}")

                check_count += 1
                # Wait for 15 seconds
                await asyncio.sleep(15)

            except asyncio.CancelledError:
                logger.info("Email checking task cancelled")
                raise
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"Unexpected error in email checking: {str(e)}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors, stopping email checking")
                    break

                await asyncio.sleep(30)

        # Notify that auto-checking stopped
        if user_id in user_data and 'email_data' in user_data[user_id] and user_data[user_id]['email_data'] == email_data:
            await context.bot.send_message(
                chat_id=chat_id,
                text="⏰ Auto email checking stopped after 30 minutes.\n\nGenerate a new email to continue receiving notifications."
            )

    except asyncio.CancelledError:
        logger.info("Email checking task was cancelled")
    except Exception as e:
        logger.error(f"Fatal error in check_emails_periodically: {str(e)}")
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Email checking stopped due to an error.\n\nPlease generate a new email."
            )
        except:
            pass
    finally:
        # Clean up
        if user_id in email_tasks:
            del email_tasks[user_id]
        logger.info(f"Email checking cleanup completed for user {user_id}")

async def handle_name_gen(query, context):
    """Handle name generation."""
    try:
        # Create keyboard for gender selection
        keyboard = [
            [
                InlineKeyboardButton("♂️ Male", callback_data="male"),
                InlineKeyboardButton("♀️ Female", callback_data="female")
            ],
            [
                InlineKeyboardButton("🏠 Menu", callback_data="menu")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text("👤 Select gender:", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error in handle_name_gen: {str(e)}")
        await query.answer("❌ Error. Please try again.")

async def handle_2fa_code(query, context):
    """Handle 2FA code generation."""
    try:
        user_id = query.from_user.id

        # Create keyboard
        keyboard = [
            [
                InlineKeyboardButton("🏠 Menu", callback_data="menu")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Set user state to waiting for 2FA secret
        user_data[user_id]['state'] = '2fa_waiting_secret'

        await query.edit_message_text(
            "🔢 Enter 2FA Secret:\n\n📝 Example:\n`S6W0 BQXK HV0V EQR6`\n\nJust send the secret key as a message.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error in handle_2fa_code: {str(e)}")
        await query.answer("❌ Error. Please try again.")

async def handle_developer(query, context):
    """Handle developer information display with enhanced error handling."""
    try:
        logger.info(f"Developer button clicked by user {query.from_user.id}")

        # Create keyboard with developer contact links
        keyboard = [
            [
                InlineKeyboardButton("🔗 Telegram", url="https://t.me/hmashik_420")
            ],
            [
                InlineKeyboardButton("🔗 WhatsApp", url="https://wa.me/8801621185512")
            ],
            [
                InlineKeyboardButton("🔗 Email", url="mailto:hmashik0001@gmail.com")
            ],
            [
                InlineKeyboardButton("🏠 Menu", callback_data="menu")
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        # Developer info text
        developer_text = (
            "👨‍💻 *Developer Information*\n\n"
            "*NAME:* HM ASHIK\n\n"
            "Contact me through any of the links below:"
        )

        # Send developer info
        await query.edit_message_text(
            developer_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

        logger.info("Developer info sent successfully")

    except Exception as e:
        logger.error(f"Error in handle_developer: {str(e)}")
        try:
            # Fallback response
            fallback_keyboard = [[InlineKeyboardButton("🏠 Menu", callback_data="menu")]]
            fallback_markup = InlineKeyboardMarkup(fallback_keyboard)

            await query.edit_message_text(
                "👨‍💻 Developer: HM ASHIK\n\nTelegram: @hmashik_420\nWhatsApp: +8801621185512\nEmail: hmashik0001@gmail.com",
                reply_markup=fallback_markup
            )
        except Exception as fallback_error:
            logger.error(f"Fallback also failed: {str(fallback_error)}")
            await query.answer("❌ Error showing developer info. Please try /menu command.")

# Message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming messages."""
    try:
        user_id = update.effective_user.id
        message_text = update.message.text

        # Initialize user data if not exists
        if user_id not in user_data:
            user_data[user_id] = {}

        # Check if user has an active state
        if 'state' in user_data[user_id]:
            state = user_data[user_id]['state']

            if state == '2fa_waiting_secret':
                # Process 2FA secret
                secret = message_text.replace(' ', '').replace('-', '').upper()

                try:
                    # Validate secret length
                    if len(secret) < 16:
                        await update.message.reply_text(
                            "❌ Invalid 2FA secret. Please enter a valid secret key.\n\n"
                            "Example: `S6W0 BQXK HV0V EQR6`",
                            parse_mode="Markdown"
                        )
                        return

                    # Create TOTP object
                    totp = pyotp.TOTP(secret)

                    # Generate current code
                    code = totp.now()

                    # Calculate remaining seconds
                    remaining_seconds = 30 - int(time.time()) % 30

                    # Create keyboard
                    keyboard = [
                        [
                            InlineKeyboardButton("🔑 New 2FA", callback_data="2fa_code")
                        ],
                        [
                            InlineKeyboardButton("🏠 Menu", callback_data="menu")
                        ]
                    ]

                    reply_markup = InlineKeyboardMarkup(keyboard)

                    # Send the code
                    await update.message.reply_text(
                        f"✅ 2FA Code ({remaining_seconds}s remaining)\n\n`{code}`",
                        reply_markup=reply_markup,
                        parse_mode="Markdown"
                    )

                    # Clear state
                    del user_data[user_id]['state']

                except Exception as e:
                    logger.error(f"Error generating 2FA code: {str(e)}")
                    await update.message.reply_text(
                        f"❌ Error generating 2FA code: {str(e)}\n\n"
                        "Please enter a valid 2FA secret key."
                    )

            else:
                # Unknown state, show menu
                await menu_command(update, context)

        else:
            # No active state, show menu
            await menu_command(update, context)
    except Exception as e:
        logger.error(f"Error in handle_message: {str(e)}")
        try:
            await update.message.reply_text("❌ An error occurred. Please try again.")
        except:
            pass

# Error handler
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    """Start the bot."""
    print("🔮 Starting META GHOST Bot...")

    # Start keep_alive server
    keep_alive()
    print("✅ Keep-alive server started!")

    try:
        # Create the Application
        application = Application.builder().token(BOT_TOKEN).build()

        # Add error handler
        application.add_error_handler(error_handler)

        # Add command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("menu", menu_command))

        # Add callback query handler
        application.add_handler(CallbackQueryHandler(button_click))

        # Add message handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        print("✅ Bot handlers registered successfully!")
        print("🚀 Bot is now running and will stay alive 24/7...")

        # Run the bot
        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.error(f"Failed to start bot: {str(e)}")
        print(f"❌ Failed to start bot: {str(e)}")
        print("💡 Please check your BOT_TOKEN and internet connection")

if __name__ == "__main__":
    main()
