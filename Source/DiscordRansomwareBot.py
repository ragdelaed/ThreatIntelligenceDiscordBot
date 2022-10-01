import json
import os
import requests
import time
from enum import Enum

import signal
import sys
import atexit
import smtplib
import ssl
import feedparser
from configparser import ConfigParser, NoOptionError
from discord import SyncWebhook # Import SyncWebhook
from Formatting import format_single_article

# expects the configuration file in the same directory as this script by default, replace if desired otherwise
configuration_file_path = os.path.join(
    os.path.split(os.path.abspath(__file__))[0], "Config.txt"
)

# put the discord hook urls to the channels you want to receive feeds in here
ransomware_feed = SyncWebhook.from_url('https://discord.com/api/webhooks/1010159571685359657/6yF3L71zgh62QMLVa6Og3wLzWd9gjA1LpcjAuEWfZuwzCqzmoydun1-Cdgqk2PRpK8rE/github')
# this one is logging of moniotring status only
status_messages = SyncWebhook.from_url('https://discord.com/api/webhooks/1010160699684700242/WlCdmqE7mIL3q8xuN45Pk_DqkLb8LYZrWLekFHH33P3N3YXRnGZX8tZSmXABRNlc_CFb/github')

FeedTypes = Enum("FeedTypes", "RSS JSON")

source_details = {
    "Ransomware News": {
        "source": "https://raw.githubusercontent.com/joshhighet/ransomwatch/main/posts.json",
        "hook": ransomware_feed,
        "type": FeedTypes.JSON,
    },
}


config_file = ConfigParser()
config_file.read(configuration_file_path)

def send_email(string):

    smtp_server = "smtp.gmail.com"
    port = 587  # For starttls
    sender_email = "ragdelaed@gmail.com"
    password = "ubjpcdiiivpwling"
    
    import smtplib
    from email.mime.text import MIMEText
    import email.utils

    subject="Ransomware_Discord_Bot_Alert"
    sender="ragdelaed@gmail.com"
    to="edgar.deal@bms.com"
    msg = MIMEText(string, _charset='UTF-8')
    msg['Subject'] = subject
    msg['Message-ID'] = email.utils.make_msgid()
    msg['Date'] = email.utils.formatdate(localtime=1)
    msg['From'] = sender
    msg['To'] = to   
    msg.add_header('Precedence', 'bulk')
    # Create a secure SSL context
    context = ssl.create_default_context()
    try:
        s = smtplib.SMTP(smtp_server,port)
        s.starttls(context=context) # Secure the connection
        s.login(sender_email, password)        
        s.sendmail(msg['From'], {msg['To'], sender }, msg.as_string())
    except Exception as e:
        # Print any error messages to stdout
        print(e)
    finally:
        s.quit()

def get_ransomware_news(source):
    posts = requests.get(source).json()
    for post in posts:
        post["publish_date"] = post["discovered"]
        post["title"] = "Post: " + post["post_title"]
        post["source"] = post["group_name"]

    return posts

def proccess_articles(articles):
    messages, new_articles = [], []
    articles.sort(key=lambda article: article["publish_date"])

    for article in articles:
        t=article['post_title']
        g=article["group_name"]
        d=article["discovered"]
        string="Source^Discord\r\n"+"Threat_Actor_Group^"+g+"\r\n"+"Timestamp^"+d+"\r\n"+"Alleged_Victim^"+t
        try:
            config_entry = config_file.get("main", article["source"])
        except NoOptionError:  # automatically add newly discovered groups to config
            config_file.set("main", article["source"], " = ?")
            config_entry = config_file.get("main", article["source"])

        if config_entry.endswith("?"):
            config_file.set("main", article["source"], article["publish_date"])
        else:
            if config_entry >= article["publish_date"]:
                continue
        send_email(string)
        messages.append(format_single_article(article))
        new_articles.append(article)

    return messages, new_articles

def send_messages(hook, messages, articles, batch_size=10):
    for i in range(0, len(messages), batch_size):
        #hook.send(embeds=messages[i : i + batch_size])

        for article in articles[i : i + batch_size]:
            config_file.set(
                "main", article["source"], article["publish_date"]
            )

        time.sleep(3)

def process_source(post_gathering_func, source, hook):
    raw_articles = post_gathering_func(source)
    processed_articles, new_raw_articles = proccess_articles(raw_articles)
    send_messages(hook, processed_articles, new_raw_articles)

def handle_rss_feed_list(rss_feed_list, hook):
    for rss_feed in rss_feed_list:
        status_messages.send(f"> {rss_feed[1]}")
        process_source(get_news_from_rss, rss_feed, hook)

def write_status_messages_to_discord(message):
    status_messages.send(f"**{time.ctime()}**: *{message}*")
    time.sleep(3)

@atexit.register
def clean_up_and_close():
    with open(configuration_file_path, "w") as f:
        config_file.write(f)

    sys.exit(0)

def main():
    while True:
        for detail_name, details in source_details.items():
            write_status_messages_to_discord(f"Checking {detail_name}")
            process_source(get_ransomware_news, details["source"], details["hook"])

        write_status_messages_to_discord("All done")
        with open(configuration_file_path, "w") as f:
            config_file.write(f)

        time.sleep(1800)

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda num, frame: clean_up_and_close())
    main()
