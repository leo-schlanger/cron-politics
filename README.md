# Cron Politics

A professional news aggregator focused on politics, controversies, conflicts, and natural disasters. Cron Politics monitors over 50 RSS feeds across multiple regions and categories, utilizing a keyword-based scoring system to prioritize the most relevant news.

## Features

- **Multi-Source Monitoring:** Tracks over 54 RSS feeds across 6 categories (Portugal, Brazil, World, Controversies, Conflicts, and Disasters).
- **Intelligent Prioritization:** Uses a keyword-based scoring system to calculate a priority score for each news item.
- **Smart Deduplication:** Implements title hashing to prevent duplicate news entries from multiple sources or repeat fetches.
- **Automated Workflows:** Fully integrated with GitHub Actions for hourly news fetching, weekly database cleanup, and periodic newsletters.
- **Newsletter System:** Generates and sends a comprehensive Excel report and HTML summary via Resend API.
- **Database Backend:** Scalable storage using Supabase (PostgreSQL).

## Tech Stack

- **Python 3.11+**
- **Supabase** (PostgreSQL cloud)
- **GitHub Actions** (Automation & Scheduling)
- **Resend API** (Transactional Email)
- **OpenPyXL** (Excel Generation)

## Project Structure

```text
cron_politics/
├── main.py              # Main CLI Entrypoint
├── fetcher.py           # RSS Collection & Processing Logic
├── database.py          # Database Interface (Supabase/PostgreSQL)
├── deduplication.py     # Content Deduplication Logic
├── newsletter.py        # Newsletter Generation & Emailing
├── sources.json         # RSS Feed Definitions by Category
├── requirements.txt     # Python Dependencies
└── .github/workflows/
    ├── fetch_news.yml   # Hourly Fetch Cron Jobs
    ├── cleanup.yml      # Weekly Database Cleanup
    └── newsletter.yml   # Newsletter Trigger
```

## Categories Covered

| Category | Description | Key Sources |
|-----------|-----------|--------|
| `politics_pt` | Portuguese Politics | Observador, RTP, ECO, SIC Notícias, etc. |
| `politics_br` | Brazilian Politics | G1, Folha, Poder360, Agência Brasil, etc. |
| `politics_world`| International News | BBC, Guardian, NY Post, Al Jazeera, etc. |
| `controversies` | Scandals & Celebs | Daily Mail, TMZ, Fox News, Page Six |
| `conflicts` | Wars & Tensions | Times of Israel, Ukrinform, Defense News |
| `disasters` | Environment & Disasters | USGS, NOAA, ReliefWeb, Mongabay |

## Setup Guide

### 1. Database Setup (Supabase)

1. Create a free project at [supabase.com](https://supabase.com).
2. Go to **Settings > Database > Connection string > URI**.
3. Copy the connection string for later use.

### 2. GitHub Configuration

Add the following Secrets to your repository (**Settings > Secrets and variables > Actions**):

| Secret | Value Description |
|--------|-------|
| `DATABASE_URL` | Your Supabase Postgres URI |
| `RESEND_API_KEY` | Your Resend API key (for newsletter) |
| `RECIPIENTS` | Comma-separated list of email addresses |
| `FROM_EMAIL` | The verified email address to send from |

### 3. Initialize Database

You can run the initial setup manually or via GitHub Actions:
- **Local:** `python main.py setup-db`
- **GitHub Actions:** Go to **Actions > Setup Database > Run workflow**.

## CLI Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Environment Variable
export DATABASE_URL="postgresql://user:pass@host:5432/postgres"

# Command Line Interface
python main.py fetch                # Fetch news for all categories
python main.py fetch --cat [name]    # Fetch specific category
python main.py stats                # Show database statistics
python main.py sources              # List all configured sources
python main.py cleanup --days 60    # Delete news older than X days
python main.py newsletter           # Trigger manual newsletter send
```

## Keywords & Prioritization

The system calculates a "Priority Score" based on matched keywords:
- **High Weight (+2.0):** Matches in the title.
- **Standard Weight (+1.0):** Matches in the description.
- **Exclusion (-1.0):** Items containing ignored keywords (horoscopes, promotions, crypto-prices) are automatically skipped.

## Cost Efficiency

Designed to run entirely on free-tier services:
- **Supabase:** Free up to 500MB database storage.
- **GitHub Actions:** Free for public repositories.
- **Resend:** Free tier available for transactional emails.

**Total Operating Cost: $0/month**

---

## Support the Project

If you find this project useful, consider supporting its development!

[![Donate with PayPal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/donate/?hosted_button_id=UAB9LYC87EVBC)

[Donate via PayPal](https://www.paypal.com/donate/?hosted_button_id=UAB9LYC87EVBC)
