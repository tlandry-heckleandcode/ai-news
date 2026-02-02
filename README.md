# AI Trends Reporter

Automated overnight scraper that finds trending YouTube videos and news articles about AI coding tools (Cursor AI, Claude Code, Google Antigravity AI), and delivers a morning report to Slack.

## Features

- Fetches trending YouTube videos from the last 7 days
- Fetches trending news articles from Google News
- Ranks content by engagement metrics and recency
- Sends formatted reports to Slack
- Runs automatically overnight via cron or launchd
- Reports top 3 videos and top 3 articles (or indicates if none found)

## Quick Start

```bash
# 1. Clone/navigate to the project
cd SlackAIUpdate

# 2. Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up credentials (see sections below)
cp config/.env.example .env
# Edit .env with your API keys

# 5. Test the setup
python src/main.py --dry-run

# 6. Install scheduled job
./setup_cron.sh --launchd
```

## Setup Instructions

### 1. YouTube Data API Setup

The YouTube API is used to search for videos and get view/engagement statistics.

#### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name it something like "AI Trends Reporter"
4. Click "Create"

#### Step 2: Enable YouTube Data API

1. In your project, go to "APIs & Services" → "Library"
2. Search for "YouTube Data API v3"
3. Click on it and press "Enable"

#### Step 3: Create API Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "API Key"
3. Copy the generated API key
4. (Optional) Click "Restrict Key" to limit it to YouTube Data API only

#### Step 4: Add to Environment

Add the API key to your `.env` file:

```
YOUTUBE_API_KEY=AIzaSy...your_key_here
```

**API Quotas:** The free tier provides 10,000 units/day. A typical run uses ~100-200 units, so you have plenty of headroom.

---

### 2. Slack Webhook Setup

Slack webhooks allow the script to post messages to a channel.

#### Step 1: Create a Slack App

1. Go to [Slack API Apps](https://api.slack.com/apps)
2. Click "Create New App"
3. Choose "From scratch"
4. Name it "AI Trends Reporter" and select your workspace
5. Click "Create App"

#### Step 2: Enable Incoming Webhooks

1. In your app settings, go to "Incoming Webhooks"
2. Toggle "Activate Incoming Webhooks" to ON
3. Click "Add New Webhook to Workspace"
4. Select the channel where you want reports posted
5. Click "Allow"

#### Step 3: Copy Webhook URL

1. Copy the Webhook URL (starts with `https://hooks.slack.com/services/...`)
2. Add it to your `.env` file:

```
SLACK_WEBHOOK_URL=your_slack_webhook_url_here
```

#### Step 4: Test the Integration

```bash
python src/main.py --test
```

You should see a test message appear in your Slack channel.

---

### 3. Environment Configuration

Copy the example environment file and fill in your credentials:

```bash
cp config/.env.example .env
```

Edit `.env` with your values:

```bash
# Required
YOUTUBE_API_KEY=your_youtube_api_key_here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Optional customization
SEARCH_TERMS=Cursor AI,Claude Code,Google Antigravity AI
MAX_RESULTS_PER_TERM=10
DAYS_LOOKBACK=7
```

---

### 4. Schedule Automatic Runs

The `setup_cron.sh` script helps you configure automatic overnight runs.

#### macOS (Recommended: launchd)

```bash
chmod +x setup_cron.sh
./setup_cron.sh --launchd
```

This creates a launchd job that runs at midnight daily.

**Useful commands:**
```bash
# Run immediately
launchctl start com.aitrends.reporter

# Stop/disable
launchctl unload ~/Library/LaunchAgents/com.aitrends.reporter.plist

# View logs
tail -f logs/output.log
```

#### Linux/Other (cron)

```bash
./setup_cron.sh --cron
```

**Useful commands:**
```bash
# View cron jobs
crontab -l

# Edit cron jobs
crontab -e
```

---

## Usage

### Command Line Options

```bash
# Full report (fetch data and send to Slack)
python src/main.py

# Test Slack connection
python src/main.py --test

# Dry run (fetch data, print to console, don't send to Slack)
python src/main.py --dry-run

# Only fetch videos
python src/main.py --videos --dry-run

# Only fetch articles
python src/main.py --articles --dry-run
```

### Manual Run

To run the report manually:

```bash
cd SlackAIUpdate
source venv/bin/activate  # if using virtual environment
python src/main.py
```

---

## Report Format

The Slack report includes:

```
AI Trends Report - Monday, February 2, 2026

Good morning! Here's your daily roundup of trending AI content.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📺 TRENDING YOUTUBE VIDEOS (Last 7 Days)

1. [Video Title]
   Channel: Channel Name
   Views: 50,000 | Published: 2 days ago
   Watch on YouTube

2. ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📰 TRENDING ARTICLES (Last 7 Days)

1. [Article Title]
   Source: TechCrunch
   Published: 12 hours ago
   Read Article

2. ...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Report generated at 6:00 AM
```

---

## Project Structure

```
SlackAIUpdate/
├── src/
│   ├── __init__.py
│   ├── youtube_fetcher.py    # YouTube API integration
│   ├── news_fetcher.py       # Google News RSS parsing
│   ├── slack_reporter.py     # Slack message formatting/sending
│   └── main.py               # Orchestration script
├── config/
│   └── .env.example          # Template for API keys
├── logs/                     # Log files (created automatically)
├── requirements.txt
├── setup_cron.sh             # Scheduler setup script
└── README.md
```

---

## Troubleshooting

### "YouTube API key is required"

Make sure your `.env` file exists and contains `YOUTUBE_API_KEY`.

### "Slack webhook URL is required"

Make sure your `.env` file contains `SLACK_WEBHOOK_URL`.

### No videos/articles found

- Check that the search terms are correct
- The content must be from the last 7 days
- Try running with `--dry-run` to see debug output

### launchd job not running

1. Check if the job is loaded: `launchctl list | grep aitrends`
2. Check logs: `cat logs/error.log`
3. Make sure Python path is correct in the plist

### Rate limiting

- YouTube API: 10,000 units/day (plenty for daily runs)
- Google News RSS: No rate limit, but don't abuse

---

## Customization

### Change Search Terms

Edit `SEARCH_TERMS` in your `.env` file:

```
SEARCH_TERMS=Cursor AI,Claude Code,Copilot,Windsurf
```

### Change Schedule Time

For launchd, edit `~/Library/LaunchAgents/com.aitrends.reporter.plist` and modify:

```xml
<key>StartCalendarInterval</key>
<dict>
    <key>Hour</key>
    <integer>6</integer>  <!-- 6 AM -->
    <key>Minute</key>
    <integer>0</integer>
</dict>
```

Then reload: `launchctl unload ~/Library/LaunchAgents/com.aitrends.reporter.plist && launchctl load ~/Library/LaunchAgents/com.aitrends.reporter.plist`

For cron, edit with `crontab -e` and change the schedule.

---

## License

MIT License - Feel free to modify and use as needed.
