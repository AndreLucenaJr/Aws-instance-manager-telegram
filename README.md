
<p align="center">
  <img width="208" height="168" alt="AWS EC2 Manager Bot" src="https://github.com/user-attachments/assets/2bb1cf71-b342-4fc2-b743-deb747225a73">
</p>



# AWS EC2 Manager Bot

Telegram bot for managing AWS EC2 instances with automatic scheduling.

## Quick Installation

```bash
git clone git@github.com:AndreLucenaJr/Aws-instance-manager-telegram.git
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```
## Docker

```bash
docker-compose up -d
docker logs aws-ec2-manager-bot -f
```
## Configuration (.env)

Use env-example as a base

```env
TELEGRAM_BOT_TOKEN= ## Add your telegram bot token
AWS_ACCESS_KEY_ID=  ## Add your user aws acces key id
AWS_SECRET_ACCESS_KEY= ## Add your user aws secret access key
AWS_REGION= ## Add your aws region
POSTGRES_URL= postgresql://[user]:[password]@[host]:[port]/[db]
AUTHORIZED_GROUP_ID= ## ID of the Telegram group in which the bot will be active and respond to messages.
INSTANCES_TO_IGNORE= ## Comma-separated list of AWS instance IDs that the bot should ignore during processing.
TZ_TIMEZONE= ## A timezone from pytz list. Example: America/New_York
```

##  How to Get Credentials

    Bot Token: Create with @BotFather on Telegram

    Group ID: Add @RawDataBot to the group and send /start

    AWS Credentials: AWS Console → IAM → Create user with EC2 permissions

## Commands

    /start - Main menu

    Interactive buttons for:

        Manage instances

        Schedule tasks

        View schedules

