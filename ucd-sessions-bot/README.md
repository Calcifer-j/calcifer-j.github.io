# UCD Sessions Bot

A simple GitHub Action that runs every Thursday to manage UCD playback sessions.

## What it does

**Every Thursday:**
1. Checks if this Monday's session has a presenter
   - Yes → does nothing (Linear's Slack integration already announced it)
   - No → posts to Slack asking for volunteers
2. Checks if next Monday's session exists
   - No → creates it in Linear (Linear's Slack integration announces it)

## Setup

### 1. Create a Linear API key
- Go to Linear → Settings → API → Personal API keys
- Create a new key, copy it

### 2. Create a Slack webhook
- Go to https://api.slack.com/apps
- Create an app (or use existing)
- Add "Incoming Webhooks" feature
- Create a webhook for your #ucd channel
- Copy the webhook URL

### 3. Add GitHub secrets
In your repo → Settings → Secrets and variables → Actions:
- `LINEAR_API_KEY` - your Linear API key
- `SLACK_WEBHOOK_URL` - your Slack webhook URL

### 4. Update config
Edit `config.py`:
- `LINEAR_TEAM_ID` - your UCD team ID
- `LINEAR_PROJECT_ID` - your UCD Team Sessions project ID
- `SLACK_CHANNEL_NAME` - for display in messages

## Manual run
You can trigger the action manually from the Actions tab in GitHub.

## Local testing
```bash
export LINEAR_API_KEY="your-key"
export SLACK_WEBHOOK_URL="your-webhook"
python bot.py
```
