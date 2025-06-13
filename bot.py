import os
import logging
from datetime import datetime
from typing import Optional, Union
from threading import Thread
from flask import Flask
import asyncio
from pyrogram import (
    Client,
    filters,
    enums,
    types
)
from pyrogram.errors import (
    BadRequest,
    ChannelInvalid,
    ChatAdminRequired,
    FloodWait,
    PeerIdInvalid,
    UserNotParticipant
)
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from config import *


# --- Logging ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.WARNING
)
logger = logging.getLogger(__name__)

# --- Flask Keep-Alive Server ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run_flask).start()

# --- Database Setup ---
try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client["uploaderfiles"]
    users_collection = db["users"]
    files_collection = db["files"]
    file_access_collection = db["file_access"]
except PyMongoError as e:
    logger.error(f"MongoDB connection error: {e}")
    raise

# --- Pyrogram Client ---
bot = Client(
    "file_share_bot",
    bot_token=BOT_TOKEN,
    api_id=api_id,  # Replace with your API ID
    api_hash=api_hash  # Replace with your API hash
)

# --- Helper Functions ---
async def save_user_to_db(user_id: int, username: Optional[str], first_name: Optional[str]) -> bool:
    """Save user data to MongoDB with error handling."""
    try:
        existing_user = users_collection.find_one({"user_id": user_id})
        if not existing_user:
            users_collection.insert_one({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "join_date": datetime.utcnow()
            })
            logger.info(f"User {user_id} saved to database")
            return True
        return False
    except PyMongoError as e:
        logger.error(f"Error saving user to DB: {e}")
        return False

async def save_file_to_db(file_id: int, uploader_id: int, uploader_name: str, file_type: str) -> bool:
    """Save file metadata to MongoDB with error handling."""
    try:
        existing_file = files_collection.find_one({"file_id": file_id})
        if not existing_file:
            files_collection.insert_one({
                "file_id": file_id,
                "uploader_id": uploader_id,
                "uploader_name": uploader_name,
                "file_type": file_type,
                "upload_date": datetime.utcnow(),
                "access_count": 0
            })
            logger.info(f"File {file_id} saved to database")
            return True
        return False
    except PyMongoError as e:
        logger.error(f"Error saving file to DB: {e}")
        return False

async def log_file_access(file_id: int, user_id: int, username: Optional[str], first_name: Optional[str]) -> bool:
    """Log file access with error handling."""
    try:
        # Update access count
        files_collection.update_one(
            {"file_id": file_id},
            {"$inc": {"access_count": 1}}
        )
        
        # Create access log
        file_access_collection.insert_one({
            "file_id": file_id,
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
            "access_time": datetime.utcnow()
        })
        logger.info(f"File {file_id} accessed by {user_id}")
        return True
    except PyMongoError as e:
        logger.error(f"Error logging file access: {e}")
        return False

async def is_member(user_id: int, channel: str) -> bool:
    """Check if user is member of a channel with error handling."""
    try:
        chat_member = await bot.get_chat_member(channel, user_id)
        return chat_member.status in [
            enums.ChatMemberStatus.MEMBER,
            enums.ChatMemberStatus.ADMINISTRATOR,
            enums.ChatMemberStatus.OWNER
        ]
    except UserNotParticipant:
        return False
    except (ChannelInvalid, PeerIdInvalid):
        logger.error(f"Invalid channel: {channel}")
        return False
    except Exception as e:
        logger.error(f"Error checking membership for {channel}: {e}")
        return False

async def check_all_channels(user_id: int) -> bool:
    """Check if user is member of all required channels."""
    for channel in REQUIRED_CHANNELS:
        if not await is_member(user_id, channel):
            return False
    return True

async def send_notification(text: str, parse_mode: enums.ParseMode = enums.ParseMode.MARKDOWN) -> bool:
    """Send notification to admin channel with error handling."""
    try:
        await bot.send_message(
            chat_id=NOTIFY_CHANNEL,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        logger.error(f"Error sending notification: {e}")
        return False

# --- Handlers ---
@bot.on_message(filters.command("start"))
async def start_handler(client: Client, message: types.Message):
    """Handle /start command with file links and new users."""
    user = message.from_user
    args = message.command
    
    # Save user to DB
    await save_user_to_db(user.id, user.username, user.first_name)
    
    # Handle file links (e.g., /start file_123)
    if len(args) > 1 and args[1].startswith("file_"):
        file_id = args[1].split("_")[-1]
        await handle_file_link(user, file_id,message=message)
        return
    
    # Check channel membership
    if not await check_all_channels(user.id):
        buttons = []
        for channel in REQUIRED_CHANNELS:
            buttons.append([types.InlineKeyboardButton(
                f"Join {channel}",
                url=f"https://t.me/{channel}"
            )])
        
        buttons.append([types.InlineKeyboardButton(
            "✅ I've Joined",
            callback_data="check_joined"
        )])
        
        await message.reply_text(
            f"👋 Hello {user.first_name},\n\n"
            "You need to join our channels to use this bot:\nPlease join first\n\n"

            "After joining, click the button below.",
            reply_markup=types.InlineKeyboardMarkup(buttons)
        )
        return
    
    # Main menu for verified users
    buttons = types.InlineKeyboardMarkup([
        [
            types.InlineKeyboardButton("📢 Channel", url=f"https://t.me/{Main_channel}"),
            types.InlineKeyboardButton("👤 Developer", url=f"https://t.me/shishyapy")
        ],
        [
            types.InlineKeyboardButton("📤 Upload File", callback_data="upload_file")
        ]
    ])
    
    await message.reply_text(
        f"👋 Welcome {user.first_name}!\n\n"
        "This bot helps you share files easily.\n\n"
        "• Just send me any file\n"
        "• I'll generate a shareable link\n"
        "• Share the link with anyone\n\n"
        "Click 'Upload File' to get started!",
        reply_markup=buttons
    )
    
    # Send new user notification
    await send_notification(
        f"📢 New user started the bot!\n\n"
        f"Name: {user.first_name}\n"
        f"ID: {user.id}\n"
        f"Username: @{user.username if user.username else 'N/A'}"
    )

async def handle_file_link(user: types.User, file_id: str, message: types.Message):
    """Handle file access via shared link."""
    try:
        file_id = int(file_id)
    except ValueError:
        return  # Invalid file ID
    
    if not await check_all_channels(user.id):
        buttons = []
        for channel in REQUIRED_CHANNELS:
            buttons.append([types.InlineKeyboardButton(
                f"Join {channel}",
                url=f"https://t.me/{channel}"
            )])
        
        buttons.append([types.InlineKeyboardButton(
            "✅ I've Joined",
            callback_data="check_joined"
        )])
        
        await message.reply_text(
            f"👋 Hello {user.first_name},\n\n"
            "You need to join our channels to use this bot:\nPlease join first\n\n"

            "After joining, click the button below.",
            reply_markup=types.InlineKeyboardMarkup(buttons)
        )
        return
    # Log the access
    await log_file_access(file_id, user.id, user.username, user.first_name)
    
    try:
        # Forward the file to user
        await bot.copy_message(
            chat_id=user.id,
            from_chat_id=CHANNEL_ID,
            message_id=file_id
        )
        
        # Send access notification
        file_info = files_collection.find_one({"file_id": file_id})
        if file_info:
            await send_notification(
                f"📥 File Accessed!\n\n"
                f"📄 File ID: `{file_id}`\n"
                f"📂 Type: {file_info.get('file_type', 'Unknown')}\n"
                f"⬆️ Uploaded by: {file_info.get('uploader_name', 'Unknown')}\n\n"
                f"👤 Accessed by:\n"
                f"Name: {user.first_name}\n"
                f"ID: {user.id}\n"
                f"Username: @{user.username if user.username else 'N/A'}\n\n"
                f"🔗 [View File](https://t.me/c/{str(CHANNEL_ID)[4:]}/{file_id})"
            )
    except Exception as e:
        logger.error(f"Error sending file {file_id}: {e}")

@bot.on_callback_query(filters.regex("^check_joined$"))
async def check_joined_handler(client: Client, callback_query: types.CallbackQuery):
    """Handle 'I've Joined' button press."""
    user = callback_query.from_user
    
    if await check_all_channels(user.id):
        await callback_query.edit_message_text(
            "✅ Thanks for joining! Now you can use the bot.\n-- Please start with your link again",
            reply_markup=None
        )
        await start_handler(client, callback_query.message)
    else:
        await callback_query.answer(
            "You haven't joined all channels yet!",
            show_alert=True
        )

@bot.on_callback_query(filters.regex("^upload_file$"))
async def upload_file_handler(client: Client, callback_query: types.CallbackQuery):
    """Prompt user to upload a file."""
    await callback_query.edit_message_text(
        "⬆️ Please send me the file you want to upload",
        reply_markup=None
    )
    await callback_query.answer()

@bot.on_message(filters.document | filters.photo | filters.video | filters.audio)
async def file_handler(client: Client, message: types.Message):
    """Handle file uploads."""
    user = message.from_user
    
    # Check channel membership
    if not await check_all_channels(user.id):
        return
    
    # Determine file type
    if message.document:
        file_type = message.document.mime_type
    elif message.photo:
        file_type = "photo"
    elif message.video:
        file_type = message.video.mime_type
    elif message.audio:
        file_type = message.audio.mime_type
    else:
        file_type = "unknown"
    
    try:
        # Forward file to channel
        forwarded = await message.forward(CHANNEL_ID)
        
        # Save to database
        await save_file_to_db(
            forwarded.id,
            user.id,
            user.first_name or "Unknown",
            file_type
        )
        
        # Create shareable link
        bot_username = (await bot.get_me()).username
        file_link = f"https://t.me/{bot_username}?start=file_{forwarded.id}"
        
        await message.reply_text(
            f"✅ File uploaded successfully!\n\n"
            f"🔗 Share this link:\n`{file_link}`\n\n"
            f"📊 Use /check {forwarded.id} to view stats (admin only)",
            parse_mode=enums.ParseMode.MARKDOWN
        )
        
        # Send upload notification
        await send_notification(
            f"📤 New File Uploaded!\n\n"
            f"📄 File ID: `{forwarded.id}`\n"
            f"📂 Type: {file_type}\n"
            f"👤 Uploaded by: {user.first_name}\n"
            f"🆔 User ID: {user.id}\n\n"
            f"🔗 [View File](https://t.me/c/{str(CHANNEL_ID)[4:]}/{forwarded.id})"
        )
    except Exception as e:
        logger.error(f"Error handling file upload: {e}")
        await message.reply_text("❌ Failed to upload file. Please try again.")

@bot.on_message(filters.command("feedback"))
async def feedback_handler(client: Client, message: types.Message):
    """Handle user feedback."""
    if len(message.command) < 2:
        await message.reply_text(
            "Please provide your feedback after the command.\n"
            "Example: /feedback This bot is great!"
        )
        return
    
    feedback = " ".join(message.command[1:])
    user = message.from_user
    
    await send_notification(
        f"💬 New Feedback Received\n\n"
        f"👤 User: {user.first_name}\n"
        f"🆔 ID: {user.id}\n"
        f"📝 Feedback: {feedback}"
    )
    
    await message.reply_text("✅ Thank you for your feedback!")

@bot.on_message(filters.command("stats") & filters.user(ADMIN_IDS))
async def users_handler(client: Client, message: types.Message):
    """Show total user count (admin only)."""
    try:
        count = users_collection.count_documents({})
        await message.reply_text(f"📊 Total users: {count}")
    except PyMongoError as e:
        logger.error(f"Error counting users: {e}")
        await message.reply_text("❌ Error fetching user count")

@bot.on_message(filters.command("broad") & filters.user(ADMIN_IDS))
async def broadcast_handler(client: Client, message: types.Message):
    """Broadcast message to all users (admin only)."""
    if len(message.command) < 2:
        await message.reply_text("Usage: /broadcast Your message here")
        return
    
    broadcast_text = " ".join(message.command[1:])
    formatted_text = f"📢 Announcement:\n\n{broadcast_text}"
    
    try:
        users = users_collection.find({}, {"user_id": 1})
        user_ids = [user["user_id"] for user in users]
    except PyMongoError as e:
        logger.error(f"Error fetching users for broadcast: {e}")
        await message.reply_text("❌ Error fetching users")
        return
    
    success = 0
    failed = 0
    blocked = []
    
    for user_id in user_ids:
        try:
            await bot.send_message(user_id, formatted_text)
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except BadRequest as e:
            if "blocked" in str(e).lower():
                blocked.append(user_id)
            failed += 1
        except Exception as e:
            logger.error(f"Error sending to {user_id}: {e}")
            failed += 1
    
    await message.reply_text(
        f"📢 Broadcast Results:\n\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"⛔ Blocked: {len(blocked)}\n\n"
        f"Blocked users: {', '.join(map(str, blocked)) if blocked else 'None'}"
    )

@bot.on_message(filters.command("check") & filters.user(ADMIN_IDS))
async def check_handler(client: Client, message: types.Message):
    """Check file stats (admin only)."""
    if len(message.command) < 2:
        await message.reply_text("Usage: /check <file_id>")
        return
    
    try:
        file_id = int(message.command[1])
    except ValueError:
        await message.reply_text("Invalid file ID. Must be a number.")
        return
    
    try:
        file_info = files_collection.find_one({"file_id": file_id})
        if not file_info:
            await message.reply_text("File not found in database.")
            return
        
        access_count = file_info.get("access_count", 0)
        uploader = file_info.get("uploader_name", "Unknown")
        upload_date = file_info.get("upload_date", datetime.utcnow())
        
        await message.reply_text(
            f"📊 File Stats\n\n"
            f"🆔 ID: {file_id}\n"
            f"👤 Uploader: {uploader}\n"
            f"📅 Uploaded: {upload_date.strftime('%Y-%m-%d %H:%M')}\n"
            f"🔢 Accesses: {access_count}\n\n"
            f"🔗 [View File](https://t.me/c/{str(CHANNEL_ID)[4:]}/{file_id})",
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
    except PyMongoError as e:
        logger.error(f"Error checking file stats: {e}")
        await message.reply_text("❌ Database error")





@bot.on_message(filters.command("help"))
async def help_handler(client: Client, message: types.Message):
    """Send the bot's help message with all commands and instructions."""
    
    help_text = """
    **📂 Welcome to the TG File Uploader Bot!** 
    
    This bot allows you to upload files and retrieve them via links.

    **🔑 Commands:**
    
    1. **/start** - Start the bot and initialize the connection.  
    2. **/help** - Show this help message.  
    3. **/stats** - (Admin only) Check the total number of users.  
    4. **/check <file_id>** - (Admin only) Check file stats using the file ID.  
    5. **/broadcast <message>** - (Admin only) Send a message to all users.  
    6. **/feedback <your feedback>** - Send feedback to the bot creator.  
   
    **📌 Important Notes:**
    - You must join all the required channels to use the bot.
    - After uploading a file, you will receive a unique file link.
    - Share the file link with anyone to allow them to download the file.

    **📝 To get the source code:**
    Get this bot's source code from [@Shishyacode](https://github.com/shishyacode)
    
    **⚠️ Feedback:**
    If you encounter any issues or have suggestions, send your feedback using `/feedback <your message>`.

    **🎯 Admin Commands:**
    - `/stats`: Check the total number of users.  
    - `/check <file_id>`: View file details (admin only).  
    - `/broadcast <message>`: Broadcast a message to all users (admin only).
    """

    await message.reply_text(help_text)


# --- Run Bot ---
if __name__ == "__main__":
    keep_alive()
    logger.info("Starting bot...")
    bot.run()