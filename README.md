# Telegram Link Sender Bot

A Telegram bot that manages channel invites and generates unique invite links.

## Features
- Generate unique invite links for channels
- Admin-only commands for managing channels
- Automatic invite link renewal
- Backup system for data persistence

## Deployment to Heroku

1. Create a new Heroku app
2. Set up the following environment variables in Heroku:
   - `BOT_TOKEN`: Your Telegram bot token from @BotFather
   - `ADMIN_ID`: Your Telegram user ID (already set in the code)

3. Deploy using Heroku CLI:
```bash
heroku login
heroku git:remote -a your-app-name
git add .
git commit -m "Initial commit"
git push heroku main
```

4. Scale the worker dyno:
```bash
heroku ps:scale worker=1
```

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with:
```
BOT_TOKEN=your_telegram_bot_token_here
```

3. Run the bot:
```bash
python Bot.py
```

## Commands
- `/start` - Start the bot
- `/add` - Add a new channel (Admin only)
- `/del` - Delete a channel (Admin only)
- `/delall` - Delete all channels (Admin only)
- `/list` - List all channels (Admin only)
- `/help` - Show help menu (Admin only)
- `/cancel` - Cancel current operation 