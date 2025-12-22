# 🌿 Automated SEO Article Generator for Natura Parga

An intelligent, automated content generation system that creates SEO-optimized articles for [Natura Parga](https://naturaparga.com) using AI-powered research and content generation.

## 📖 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Obtaining API Keys](#obtaining-api-keys)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Dry Run Mode](#dry-run-mode)
  - [Specific Topic](#specific-topic)
- [Scheduling Automated Runs](#scheduling-automated-runs)
  - [macOS/Linux (cron)](#macoslinux-cron)
  - [Windows (Task Scheduler)](#windows-task-scheduler)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Overview

This project automates the creation and publishing of SEO-optimized articles to WordPress. It uses:

- **Claude (Anthropic)** for intelligent content generation
- **Tavily** for web research and fact-checking
- **WordPress REST API** for automated publishing

The system researches topics, generates high-quality articles with proper SEO structure, and publishes them directly to your WordPress site.

## Features

- 🔍 **Automated Research**: Uses Tavily to gather relevant, up-to-date information
- 🤖 **AI-Powered Writing**: Generates natural, engaging content with Claude
- 📈 **SEO Optimization**: Proper heading structure, meta descriptions, keywords
- 📝 **WordPress Integration**: Direct publishing via REST API
- 🔒 **Secure Authentication**: Uses WordPress Application Passwords
- 🏃 **Dry Run Mode**: Test content generation without publishing
- ⏰ **Schedulable**: Run automatically via cron or Task Scheduler

## Prerequisites

Before setting up this project, ensure you have:

### Required Software

- **Python 3.11 or higher**
  ```bash
  python --version  # Should show 3.11+
  ```

### Required Accounts

1. **WordPress Site** with admin access (e.g., https://naturaparga.com)
2. **Anthropic Account** for Claude API access
3. **Tavily Account** for web search API

### Optional Accounts

4. **OpenAI Account** (optional fallback LLM)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd seo-article-generator
```

### 2. Create a Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate

# On Windows:
.\venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit with your actual values
nano .env  # or use your preferred editor
```

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `WORDPRESS_URL` | ✅ | Your WordPress site URL (e.g., `https://naturaparga.com`) |
| `WORDPRESS_USERNAME` | ✅ | WordPress admin username |
| `WORDPRESS_APP_PASSWORD` | ✅ | WordPress Application Password (see below) |
| `ANTHROPIC_API_KEY` | ✅ | Claude API key for content generation |
| `TAVILY_API_KEY` | ✅ | Tavily API key for web research |
| `OPENAI_API_KEY` | ❌ | Optional fallback LLM |
| `LOG_LEVEL` | ❌ | Logging level (default: `INFO`) |
| `DRY_RUN` | ❌ | Set to `true` to test without publishing |

### Obtaining API Keys

#### WordPress Application Password

WordPress Application Passwords provide secure API access without using your main password.

1. Log in to your WordPress admin dashboard
2. Go to **Users → Profile** (or **Users → Your Profile**)
3. Scroll down to **Application Passwords**
4. Enter a name for the application (e.g., "SEO Article Generator")
5. Click **Add New Application Password**
6. **Copy the generated password immediately** (it won't be shown again!)
7. The password format looks like: `xxxx xxxx xxxx xxxx xxxx xxxx`

> ⚠️ **Important**: Store this password securely. You can revoke it anytime from the same page.

#### Anthropic API Key (Claude)

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in to your account
3. Navigate to **Settings → API Keys**
4. Click **Create Key**
5. Name your key (e.g., "SEO Generator")
6. Copy the key (starts with `sk-ant-api03-`)

> 💡 **Pricing**: Anthropic charges per token. See [pricing page](https://anthropic.com/pricing) for details.

#### Tavily API Key

1. Go to [Tavily](https://tavily.com/)
2. Sign up for an account
3. Navigate to your dashboard
4. Copy your API key (starts with `tvly-`)

> 💡 **Free Tier**: Tavily offers a free tier with limited searches per month.

#### OpenAI API Key (Optional)

1. Go to [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to **API Keys**
4. Click **Create new secret key**
5. Copy the key (starts with `sk-`)

### Validate Configuration

After setting up your `.env` file, validate your configuration:

```bash
python config.py
```

You should see:
```
✅ Configuration loaded successfully!

Configuration summary:
  WordPress URL: https://naturaparga.com
  WordPress User: your_username
  Anthropic API Key: ✓ Configured
  OpenAI API Key: ○ Not configured (optional)
  Tavily API Key: ✓ Configured
  Log Level: INFO
  Dry Run: False
```

## Usage

### Basic Usage

Run the article generator with default settings:

```bash
python run_article.py
```

### Dry Run Mode

Test content generation without publishing to WordPress:

```bash
# Via command line flag
python run_article.py --dry-run

# Or via environment variable
DRY_RUN=true python run_article.py

# Or set in .env file
# DRY_RUN=true
```

### Specific Topic

Generate an article about a specific topic:

```bash
python run_article.py --topic "Valtos Beach"
```

### Additional Options

```bash
# Show help
python run_article.py --help

# Verbose output (debug logging)
python run_article.py --verbose

# Combine options
python run_article.py --dry-run --topic "Parga Castle" --verbose
```

## Scheduling Automated Runs

The article generator can run automatically every 2-3 days to keep your blog fresh with new content. We provide helper scripts for both macOS/Linux and Windows.

### macOS/Linux (cron)

We provide a setup script that automatically configures cron for you.

#### Quick Setup (Recommended)

```bash
# Make the script executable (first time only)
chmod +x scripts/setup_cron.sh

# Install the cron job (runs every 2 days at 9:00 AM)
./scripts/setup_cron.sh

# Or specify a custom time (10:30 AM)
CRON_HOUR=10 CRON_MINUTE=30 ./scripts/setup_cron.sh
```

The script will:
- Detect your Python installation (virtual environment preferred)
- Generate the appropriate crontab entry
- Ask for confirmation before installing
- Create the logs directory if needed

#### Managing the Cron Job

```bash
# Check if the cron job is installed
./scripts/setup_cron.sh status

# Remove the cron job
./scripts/setup_cron.sh remove

# View help
./scripts/setup_cron.sh help
```

#### Manual Setup (Alternative)

If you prefer to set up cron manually:

```bash
# Open crontab editor
crontab -e

# Add this line (customize paths):
0 9 */2 * * cd /path/to/project && /path/to/venv/bin/python run_article.py >> logs/scheduled_runs.log 2>&1
```

> 💡 **Tip**: Use [crontab.guru](https://crontab.guru/) to help create cron expressions.

#### Verify Cron is Working

```bash
# List all cron jobs
crontab -l

# Check the log file after a scheduled run
tail -f logs/scheduled_runs.log

# Test the script manually first
python run_article.py --dry-run
```

### Windows (Task Scheduler)

We provide both a PowerShell script and an XML template for Windows Task Scheduler.

#### Option 1: PowerShell Script (Recommended)

```powershell
# Open PowerShell and navigate to the project directory
cd C:\path\to\seo-article-generator

# Install the scheduled task (runs every 2 days at 9:00 AM)
.\scripts\setup_scheduled_task.ps1

# Or specify a custom time (10:30 AM)
.\scripts\setup_scheduled_task.ps1 -Hour 10 -Minute 30
```

The script will:
- Detect your Python installation (virtual environment preferred)
- Create a wrapper batch script for proper logging
- Register the task with Windows Task Scheduler
- Ask for confirmation before installing

#### Managing the Scheduled Task (PowerShell)

```powershell
# Check if the task is installed
.\scripts\setup_scheduled_task.ps1 -Action Status

# Remove the scheduled task
.\scripts\setup_scheduled_task.ps1 -Action Remove

# View help
.\scripts\setup_scheduled_task.ps1 -Action Help

# Run the task immediately (for testing)
Start-ScheduledTask -TaskName "NaturaPargaArticleGenerator"
```

#### Option 2: Import XML Template (GUI Method)

For users who prefer the graphical interface:

1. **Customize the XML template**:
   - Open `scripts/natura_parga_task.xml` in a text editor
   - Replace `C:\PATH\TO\PROJECT` with your actual project path
   - Replace `C:\PATH\TO\PYTHON` with your Python path
   - Replace `YOUR_USERNAME` with your Windows username

2. **Import the task**:
   - Press `Win + R`, type `taskschd.msc`, press Enter
   - In the Actions panel, click **Import Task...**
   - Select the modified `natura_parga_task.xml` file
   - Review settings and click **OK**

#### Option 3: Manual Setup (GUI)

1. **Open Task Scheduler**:
   - Press `Win + R`, type `taskschd.msc`, press Enter

2. **Create a new task**:
   - Click **Create Task** (not "Create Basic Task")
   
3. **General tab**:
   - Name: `NaturaPargaArticleGenerator`
   - Description: "Generates SEO articles for Natura Parga"
   - Select "Run whether user is logged on or not" (optional)

4. **Triggers tab**:
   - Click **New**
   - Begin the task: "On a schedule"
   - Settings: Daily, recur every **2** days
   - Start time: 9:00 AM (or your preference)

5. **Actions tab**:
   - Click **New**
   - Action: "Start a program"
   - Program/script: `cmd.exe`
   - Arguments: `/c cd /d "C:\path\to\project" && python run_article.py >> logs\scheduled_runs.log 2>&1`

6. **Conditions tab**:
   - ✅ Start only if network connection is available
   - ❌ Uncheck "Start only if the computer is on AC power"

7. **Settings tab**:
   - ✅ Allow task to be run on demand
   - ✅ If the task fails, restart every: 1 hour
   - ✅ Stop the task if it runs longer than: 1 hour

8. Click **OK** and enter your password if prompted

#### Verify Task Scheduler is Working

```powershell
# Check task status
Get-ScheduledTask -TaskName "NaturaPargaArticleGenerator" | Select-Object State, LastRunTime, NextRunTime

# View task details
Get-ScheduledTaskInfo -TaskName "NaturaPargaArticleGenerator"

# Check the log file
Get-Content logs\scheduled_runs.log -Tail 50

# Test manually first
python run_article.py --dry-run
```

### Viewing Logs

Both scheduling methods log output to `logs/scheduled_runs.log`:

```bash
# macOS/Linux - watch log in real-time
tail -f logs/scheduled_runs.log

# macOS/Linux - view last 100 lines
tail -100 logs/scheduled_runs.log
```

```powershell
# Windows - view last 50 lines
Get-Content logs\scheduled_runs.log -Tail 50

# Windows - watch log in real-time (PowerShell 7+)
Get-Content logs\scheduled_runs.log -Wait -Tail 10
```

### Troubleshooting Scheduled Tasks

#### ❌ Cron job doesn't run

**Check these common issues:**

1. **Cron daemon not running**:
   ```bash
   # Check if cron is running
   pgrep cron || pgrep crond
   
   # Start cron (varies by system)
   sudo service cron start
   ```

2. **Path issues**: Cron runs with a minimal environment
   ```bash
   # Always use absolute paths in cron
   # ✅ Good: /home/user/project/venv/bin/python
   # ❌ Bad: python
   ```

3. **Permissions**: Check script permissions
   ```bash
   ls -la run_article.py
   chmod +x run_article.py  # if needed
   ```

#### ❌ Windows Task doesn't run

**Check these common issues:**

1. **View task history**:
   - Open Task Scheduler
   - Select the task
   - Click "History" tab (enable if disabled: Action → Enable All Tasks History)

2. **Common error codes**:
   - `0x1`: Task is running or queued
   - `0x41301`: Task is running
   - `0x80070005`: Access denied (try running as admin)
   - `0x1F`: Network not available

3. **Test manually first**:
   ```powershell
   cd C:\path\to\project
   python run_article.py --dry-run
   ```

#### ❌ Script runs but fails

1. **Check the log file** for error messages
2. **Verify environment variables** are accessible to the scheduled task
3. **Test API connectivity** from the scheduled context

## Troubleshooting

### Common Issues

#### ❌ "Missing required environment variables"

**Problem**: Config validation fails with missing variables.

**Solution**:
1. Ensure `.env` file exists: `cp .env.example .env`
2. Verify all required variables are set
3. Check for typos in variable names
4. Run `python config.py` to validate

#### ❌ "401 Unauthorized" from WordPress

**Problem**: WordPress API returns authentication error.

**Solutions**:
1. Verify `WORDPRESS_USERNAME` is correct (case-sensitive)
2. Regenerate the Application Password in WordPress
3. Ensure no spaces in the password in `.env` (format: `xxxx xxxx xxxx xxxx xxxx xxxx`)
4. Check that Application Passwords are enabled on your WordPress site
5. Verify your user has sufficient permissions (Administrator or Editor role)

#### ❌ "403 Forbidden" from WordPress

**Problem**: WordPress blocks the API request.

**Solutions**:
1. Check if your hosting provider blocks REST API requests
2. Verify no security plugins are blocking the requests
3. Try adding your IP to any firewall whitelist
4. Check `.htaccess` for REST API restrictions

#### ❌ "Invalid API key" from Anthropic

**Problem**: Claude API rejects the API key.

**Solutions**:
1. Verify the key starts with `sk-ant-api03-`
2. Check for leading/trailing whitespace in `.env`
3. Ensure your Anthropic account has billing set up
4. Generate a new key if the current one may be compromised

#### ❌ "Rate limit exceeded"

**Problem**: Too many API requests.

**Solutions**:
1. Wait for the rate limit window to reset (usually 1 minute)
2. Reduce frequency of scheduled runs
3. Upgrade your API plan for higher limits

#### ❌ "Connection timeout"

**Problem**: Network issues when connecting to APIs.

**Solutions**:
1. Check your internet connection
2. Verify the service isn't experiencing an outage
3. Check if a firewall or proxy is blocking connections
4. Try increasing timeout values in the code

### Debug Mode

Run with debug logging for more information:

```bash
# Via command line flag
python run_article.py --verbose

# Or via environment variable
LOG_LEVEL=DEBUG python run_article.py
```

### Getting Help

If you encounter issues not covered here:

1. Check the logs for detailed error messages
2. Run `python config.py` to validate configuration
3. Test API keys individually using their respective dashboards
4. Review WordPress REST API documentation for publishing issues

## Project Structure

```
seo-article-generator/
├── .env.example          # Environment variable template
├── .env                  # Your local configuration (git-ignored)
├── config.py             # Configuration management
├── run_article.py        # Main entry point / orchestrator
├── article_generator.py  # AI content generation
├── topic_manager.py      # Topic selection and tracking
├── wordpress_publisher.py # WordPress API integration
├── requirements.txt      # Python dependencies
├── README.md             # This file
├── logs/                 # Log files (auto-created)
│   ├── article_generator.log
│   └── scheduled_runs.log
└── scripts/              # Scheduling helper scripts
    ├── setup_cron.sh           # macOS/Linux cron setup
    ├── setup_scheduled_task.ps1 # Windows Task Scheduler setup
    └── natura_parga_task.xml   # Windows task XML template
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with 🌿 for Natura Parga**
