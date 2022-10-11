from __future__ import annotations

import re
from os import getenv
from urllib.parse import urlsplit, urljoin

import praw
import requests
import yaml
from flask import session
from requests.auth import HTTPBasicAuth


def save_data_to_session(username, refresh_token):
    session['username'] = username.lower()
    session['refresh_token'] = refresh_token


def access_token_from_refresh_token():
    # Gets access token from refresh token
    auth = HTTPBasicAuth(getenv('CLIENT_ID'), getenv('CLIENT_SECRET'))
    header = {'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}
    data = {'grant_type': 'refresh_token', 'refresh_token': session.get('refresh_token')}
    res = requests.post('https://www.reddit.com/api/v1/access_token', auth=auth, headers=header, data=data)
    json_data = res.json()
    return res.status_code, json_data


def access_token_from_code():
    # Gets access token from code
    auth = HTTPBasicAuth(getenv('CLIENT_ID'), getenv('CLIENT_SECRET'))
    header = {'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}
    data = {'grant_type': 'authorization_code', 'code': session.get('code'), 'redirect_uri': getenv('redirect_uri')}
    res = requests.post('https://www.reddit.com/api/v1/access_token', auth=auth, headers=header, data=data)
    json_data = res.json()
    return res.status_code, json_data


def get_access_token():
    # If access token is not expired
    if session.get('refresh_token'):
        status_code, json_data = access_token_from_refresh_token()
        if status_code != 200:
            status_code, json_data = access_token_from_code()
    else:
        status_code, json_data = access_token_from_code()
    return status_code, json_data


def get_username():
    try:
        status_code, tokens = get_access_token()
    except KeyError:
        raise KeyError("No session information available.")

    if status_code == 200:
        header = {'Authorization': f"bearer {tokens['access_token']}", 'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}
        res = requests.get('https://oauth.reddit.com/api/v1/me', headers=header)
        save_data_to_session(res.json()['name'], tokens['refresh_token'])
        return res.json()['name']
    else:
        raise ValueError(f"Got HTTPS Error {status_code}.")


def display_stats(stat: int | float) -> str:
    magnitude = 0
    if stat < 1_000:
        pretty_stat = stat
        return f"{pretty_stat}"
    else:
        while abs(stat) >= 1000:
            magnitude += 1
            stat /= 1000.0
    return f"{stat:.2f}{['', 'K', 'M', 'G', 'T', 'P'][magnitude]}"


def check_if_courier(username):
    with open("couriers.yaml", 'r') as fp:
        courier_list = yaml.safe_load(fp)
        courier_list = courier_list.get('couriers', [])
    if username.lower() in courier_list:
        return True
    else:
        return False


def get_trading_karma(username):
    reddit = praw.Reddit(
        client_id=getenv('PRAW_CLIENT_ID'),
        client_secret=getenv('PRAW_CLIENT_SECRET'),
        password=getenv('PRAW_PASSWORD'),
        user_agent="Fallout76MarketplaceUserVerification v0.0.1",
        username=getenv('PRAW_USERNAME'),
    )

    subreddit = reddit.subreddit("Fallout76Marketplace")
    flair = next(subreddit.flair(username))
    flair_text = flair.get('flair_text')
    if not flair_text:
        return 0
    else:
        if res := re.search(r"(?<=: )\d+\b", flair_text):
            return res.group()
        else:
            return flair_text.split(' ')[-1]


def get_reddit_profile_info(user_name):
    reddit_profile_info = requests.get(f"https://www.reddit.com/user/{user_name}/about.json",
                                       headers={'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}).json()

    if reddit_profile_info['data']['subreddit'].get("over_18"):
        profile_pic_uri = "/static/images/76_logo.png"
    else:
        profile_pic_uri = reddit_profile_info['data'].get('icon_img', "https://avatarfiles.alphacoders.com/917/91786.jpg")
    reddit_karma = display_stats(reddit_profile_info['data'].get('total_karma'))
    profile_pic_uri = urljoin(profile_pic_uri, urlsplit(profile_pic_uri).path)

    trading_karma = get_trading_karma(user_name)
    is_courier = check_if_courier(user_name)

    profile_info = {
        "display_name": reddit_profile_info['data'].get('name', user_name),
        "profile_pic_uri": profile_pic_uri,
        "reddit_karma": reddit_karma,
        "trading_karma": trading_karma,
        "is_courier": is_courier
    }
    return profile_info
