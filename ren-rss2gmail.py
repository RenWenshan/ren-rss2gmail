#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# ren-rss2gmail.py --- parse RSS feeds and send them to via email

# Copyright (C) 2013 Ren Wenshan

# Author: 任文山 (Ren Wenshan) <renws1990@gmail.com>
# URL:

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import smtplib
from email.MIMEMultipart import MIMEMultipart
from email.MIMEText import MIMEText
import feedparser
import json
import os
import os.path
import logging
import time

# debugging flag
DEBUG = False


# logging level
if DEBUG:
    logging_level = logging.DEBUG
else:
    logging_level = logging.INFO

# basic config
FORMAT = '%(asctime)-15s %(message)s'
logging.basicConfig(filename=os.getenv("HOME") + "/ren-rss2gmail.log",
                    level=logging_level,
                    format=FORMAT)

# get logger
logger = logging.getLogger("ren-rss2gmail")


def send_feeds(receivers, feeds, gmail_username, gmail_password, config):
    # gmail login
    logger.info("starting email server connection")
    mail_server = smtplib.SMTP("smtp.gmail.com", 587)
    mail_server.ehlo()
    mail_server.starttls()
    logger.info("login: " + gmail_username)
    mail_server.login(gmail_username, gmail_password)

    for feed in feeds:
        # feed[0] is the blog title
        subject = "[%s] " % feed[0]

        # feed[1] is the entries list
        for entry in feed[1]:
            for to in receivers:
                msg = compose_email(
                    gmail_username,
                    to,
                    subject + entry[1],  # entry[1] is the entry title
                    (entry[0] + "\n" +   # link
                     entry[3] + "\n"))   # content

                # update the last update time
                # feed[2] is the url, entry[2] is parsed published date
                config["feeds"][feed[2]]["last_update"] = {
                    'tm_year': entry[2].tm_year,
                    'tm_mon': entry[2].tm_mon,
                    'tm_mday': entry[2].tm_mday,
                    'tm_hour': entry[2].tm_hour,
                    'tm_min': entry[2].tm_min,
                    'tm_sec': entry[2].tm_sec,
                    'tm_wday': entry[2].tm_wday,
                    'tm_yday': entry[2].tm_yday,
                    'tm_isdst': entry[2].tm_isdst
                }
                # send email
                mail_server.sendmail(gmail_username, to, msg.as_string())
                logger.info("sent " + subject + entry[1] + " to " + to)

    # close mail server
    logger.info("closing email server connection")
    mail_server.close()

    return config


def compose_email(gmail_username, to, subject, content):
    # compose email
    msg = MIMEMultipart()
    msg['From'] = gmail_username
    msg['To'] = to
    msg['Subject'] = subject
    msg.attach(MIMEText(content, 'html', "utf-8"))
    return msg


def parse_feed(url, last_parse_time):
    # retrieve feed data
    data = feedparser.parse(url)
    logger.info("data parsed")

    # get the title of the blog
    blog_title = data.feed.title

    # `res' is a list [blog_title, entries, blog_url], `entries' is a list of
    # entries, each entry is also a list [link, title, date, content]
    res = [blog_title, [], url]

    # convert the last_parse_time dict to a struct_time object
    if last_parse_time:
        last_parse_time_parsed = time.struct_time((
            last_parse_time['tm_year'],
            last_parse_time['tm_mon'],
            last_parse_time['tm_mday'],
            last_parse_time['tm_hour'],
            last_parse_time['tm_min'],
            last_parse_time['tm_sec'],
            last_parse_time['tm_wday'],
            last_parse_time['tm_yday'],
            last_parse_time['tm_isdst']))
    else:
        # do not read the blogs of Confucius
        last_parse_time_parsed = time.struct_time((0, 0, 0, 0, 0, 0, 0, 0, 0))

    # do not parse if no new items
    if data.entries[0].updated_parsed:
        # some feeds use `updated_parsed' to indicate the last updated time
        last_update_key = "updated_parsed"
    else:
        # while some other use `published_parsed'
        last_update_key = "published_parsed"

    if data.entries[0][last_update_key] <= last_parse_time_parsed:
        logger.info(blog_title + ": no new entries")
        return res

    for blog in data.entries:
        if blog[last_update_key] <= last_parse_time_parsed:
            logger.info(blog_title + ": finished")
            break

        if "content" in blog:
            content = blog.content[0].value
        elif "summary" in blog:
            # some blogs do not support full text RSS, shame on these blogs
            content = blog.summary
        else:
            content = ""

        # res[1] is the entries list
        res[1].insert(0, [
            blog.link,      # 0 link
            blog.title,     # 1 title
            blog[last_update_key],  # 2 published date
            content                 # 3 content
        ])

    return res


def main():
    # check if configuration file exists
    config_file_path = os.getenv("HOME") + "/.ren-rss2gmail"

    if not os.path.isfile(config_file_path):
        logger.error("Cannot find " + config_file_path)
        exit

    # read in configurations

    # open the configuration file
    try:
        config_file = open(config_file_path, "r+")
    except IOError:
        logger.error("Cannot open " + config_file_path)
        exit

    # load in the json expression
    try:
        config = json.load(config_file)
    except:
        logger.error(
            "Cannot parse the JSON expression in " + config_file_path)
        exit

    # close the configuration file
    config_file.close()

    # get username for the sender
    try:
        gmail_username = config['username']
    except:
        logger.error("Cannot read in Gmail username")
        exit

    # get password for the sender
    try:
        gmail_password = config['password']
    except:
        logger.error("Cannot read in Gmail password")
        exit

    # get the receivers list
    try:
        receivers = config['receivers']
    except:
        logger.error("Cannot read in receivers list")
        exit

    # read in the RSS list, each item is a tuple (name, url, last_update)
    logger.info("start reading in the RSS list")
    rss_list = []
    for url, info in config["feeds"].iteritems():
        rss_list.append([info["name"], url, info["last_update"]])

    # read in latest feeds
    logger.info("start parsing feeds")
    feeds = []
    for rss in rss_list:
        feeds.append(parse_feed(rss[1], rss[2]))

    # send feeds to receivers
    logger.info("start sending Emails")
    new_config = send_feeds(
        receivers, feeds, gmail_username, gmail_password, config)

    # save configuration
    json.dump(new_config, open(config_file_path, 'w'))
    logger.info("configuration saved")


if __name__ == "__main__":
    main()
