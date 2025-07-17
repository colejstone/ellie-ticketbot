# ellie-ticketbot

A Telegram bot that monitors chat messages and creates Linear tickets via n8n workflow when issues are detected.

## New Architecture (v2.0)

🔄 **The bot now uses n8n workflow for OpenAI analysis and Linear integration!**

### How It Works
1. **Message Monitoring**: Bot stores recent messages from whitelisted chats
2. **Reaction Trigger**: Whitelisted users react with 👍 to trigger issue analysis
3. **Context Collection**: Bot collects trigger message + recent context
4. **n8n Processing**: Raw context sent to n8n webhook for OpenAI analysis
5. **Linear Integration**: n8n creates Linear tickets if valid issues are detected
6. **Response**: Bot receives confirmation and notifies user via DM

## Setup Instructions

### 1. Environment Variables
Create a `.env` file with the following variables:

**Required Variables:**
```env
# Telegram Configuration
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash

# Security Configuration (REQUIRED)
WHITELISTED_CHATS=chat1,chat2,chat3    # Required for security
WHITELISTED_USERS=user1,user2,user3    # Required for emoji reactions

# n8n Webhook Configuration (REQUIRED)
N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/telegram-bot
WEBHOOK_SECRET=your_webhook_secret_key  # Required for HMAC authentication
```

**Optional Variables:**
```env
# Legacy OpenAI (Optional - handled by n8n now)
OPENAI_API_KEY=your_openai_key          # Optional - for direct bot processing

# Advanced Security (Optional)
CHAT_ID=your_primary_chat_id            # Primary chat for testing
ANONYMIZE_USERNAMES=true                # Anonymize usernames (default: true)
MAX_CONTEXT_MESSAGES=25                 # Limit context size (default: 25)
RATE_LIMIT_REQUESTS=5                   # Max requests per user/min (default: 5)
ENCRYPT_SESSION_FILES=true              # Encrypt session files (default: true)
```

### 2. n8n Workflow Setup
1. Set up n8n instance (cloud or self-hosted)
2. Import the workflow (see `n8n_workflow_design.md`)
3. Configure environment variables in n8n:
   - `WEBHOOK_SECRET`
   - `OPENAI_API_KEY`
   - `LINEAR_API_KEY`
   - `LINEAR_TEAM_ID`
4. Test the webhook endpoint

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

**Note**: OpenAI is now optional since processing happens in n8n.

### 4. Run the Bot
```bash
# Activate virtual environment
source venv/bin/activate

# Run the bot
python3 bot.py
```

## New Workflow Architecture

```
Telegram Bot → n8n Webhook → OpenAI Analysis → Linear Issue Creation → Response
```

### Benefits of n8n Architecture
- **Separation of Concerns**: Bot handles Telegram, n8n handles AI/Linear
- **Scalability**: n8n can handle multiple bots and integrations
- **Flexibility**: Easy to modify workflow without touching bot code
- **Monitoring**: Built-in n8n monitoring and error handling
- **Security**: Centralized API key management in n8n

## Security Features

- 🔒 **Maximum Security**: Never discovers or accesses non-whitelisted chats
- 🔒 **User Whitelisting**: Only authorized users can trigger emoji reactions
- 🔒 **HMAC Authentication**: Webhook requests signed with secret key
- 🔒 **Message Sanitization**: Removes sensitive data before processing
- 🔒 **Rate Limiting**: Prevents abuse with configurable limits
- 🔒 **Session Encryption**: AES-256 encryption for Telegram session files
- 🔒 **Private Responses**: Bot DMs users instead of messaging groups

## Files Structure

```
ellie-ticketbot/
├── bot/                          # Main bot package
│   ├── core/                     # Core bot functionality
│   ├── handlers/                 # Message and reaction handlers
│   ├── integrations/             # External integrations
│   ├── security/                 # Security components
│   ├── storage/                  # Data persistence
│   └── utils/                    # Utility functions
├── n8n_workflow_design.md        # N8N workflow documentation
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Migration from v1.0

If you're upgrading from the old version:

1. **Update Environment Variables**: Add `N8N_WEBHOOK_URL` and `WEBHOOK_SECRET`
2. **Set Up n8n**: Follow the n8n workflow setup guide
3. **Optional**: Remove `OPENAI_API_KEY` from bot environment (handled by n8n)
4. **Test**: Verify webhook integration works correctly

## Troubleshooting

### Common Issues

1. **Webhook Authentication Failed**
   - Verify `WEBHOOK_SECRET` matches in bot and n8n
   - Check webhook URL is correct

2. **n8n Workflow Not Triggering**
   - Verify n8n webhook endpoint is accessible
   - Check n8n logs for errors
   - Ensure n8n environment variables are set

3. **OpenAI Analysis Not Working**
   - Check OpenAI API key in n8n environment
   - Verify OpenAI node configuration in n8n
   - Monitor OpenAI rate limits

4. **Linear Issues Not Created**
   - Check Linear API key in n8n environment
   - Verify Linear team ID is correct
   - Check Linear node configuration

### Debug Mode
Enable debug logging for 5 minutes on startup to help identify issues:
```python
# Automatically enabled in bot startup
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Update documentation
5. Submit a pull request

## License

MIT License - see LICENSE file for details.