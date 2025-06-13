# telegram-file-uploader-bot

# 📂 Telegram File Uploader Bot

A powerful and easy-to-use **Telegram File Uploader Bot** built with [Pyrogram](https://github.com/pyrogram/pyrogram) and [MongoDB](https://www.mongodb.com/). This bot allows users to **upload files**, store them securely, and **generate unique links** to retrieve them anytime. 🎯

---

## 🚀 Features

✅ Upload any file directly to the bot  
✅ Get a permanent shareable download link for each file  
✅ Automatically stores file metadata in MongoDB  
✅ Requires users to join specific channels before using the bot  
✅ Admin-only tools: user statistics, file stats, and broadcast messaging  
✅ Feedback system for users to send suggestions  
✅ Built with asynchronous architecture using Pyrogram

---

## 🔧 Commands

| Command | Description |
|--------|-------------|
| `/start` | Start the bot and register the user |
| `/help` | Show detailed help and instructions |
| `/feedback <message>` | Send feedback to the bot admin |
| `/stats` | 📊 View total users (admin only) |
| `/check <file_id>` | 🔎 Check stats for a specific file (admin only) |
| `/broadcast <message>` | 📢 Send message to all users (admin only) |

---

## 🛡️ Requirements to Use

🔐 You **must join all required Telegram channels** before uploading or downloading files. This helps control access and engagement.

---

## 🧠 How It Works

1. Upload a file to the bot  
2. Receive a unique file link  
3. Share the link — anyone with it can retrieve the file  
4. Admins can monitor usage and send broadcasts

---

## 🛠️ Built With

- **Python 3**
- **[Pyrogram](https://docs.pyrogram.org/)**
- **[MongoDB](https://www.mongodb.com/)**
- **Flask** (for optional web dashboard or uptime)

---

## 🧩 Installation & Deployment

### 1. Clone the repository

```bash
git clone https://github.com/shishyacode/telegram-file-uploader-bot.git
cd telegram-file-uploader-bot
