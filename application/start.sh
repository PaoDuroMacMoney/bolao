#!/bin/sh


# please do not change this file...please!

echo _Starting...

echo _    Running Crawler...
python GloboEsporteCrawler.py
echo _    Running Crawler...OK!

echo _    Starting Cron...
crontab crawler_cron
service cron start
echo _    Starting Cron...OK!

echo "Environment variables..."
export
echo "Environment variables...OK!"

echo _Starting...OK!
gunicorn -w 1 -b :8000 app:app
