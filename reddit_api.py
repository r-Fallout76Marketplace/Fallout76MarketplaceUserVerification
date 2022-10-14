from __future__ import annotations

import re
from os import getenv
from typing import Optional
from urllib.parse import urlsplit, urljoin

import praw
import requests
import yaml
from flask import session
from requests import HTTPError
from requests.auth import HTTPBasicAuth


def save_data_to_session(username: str, refresh_token: str) -> None:
    session['username'] = username.lower()
    session['refresh_token'] = refresh_token


def access_token_from_refresh_token(refresh_token: str) -> (int, dict):
    """
    Gets access token from refresh token

    :param refresh_token: Reddit Refresh Token
    :return: Dict with access_token and status code
    :raises HTTPError: If an HTTP Error occurs
    """
    auth = HTTPBasicAuth(getenv('CLIENT_ID'), getenv('CLIENT_SECRET'))
    header = {'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}
    data = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
    res = requests.post('https://www.reddit.com/api/v1/access_token', auth=auth, headers=header, data=data)
    res.raise_for_status()
    json_data = res.json() | {"refresh_token": refresh_token}  # Adding refresh token back for consistency
    return res.status_code, json_data


def access_token_from_code(code: str) -> (int, dict):
    """
    Gets access token from oauth code

    :param code: Reddit oauth code
    :return: Dict with access_token and status code
    :raises HTTPError: If an HTTP Error occurs
    """
    auth = HTTPBasicAuth(getenv('CLIENT_ID'), getenv('CLIENT_SECRET'))
    header = {'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}
    data = {'grant_type': 'authorization_code', 'code': code, 'redirect_uri': getenv('redirect_uri')}
    res = requests.post('https://www.reddit.com/api/v1/access_token', auth=auth, headers=header, data=data)
    res.raise_for_status()
    json_data = res.json()
    return res.status_code, json_data


def get_access_token(tokens: dict) -> (int, dict):
    """
    Gets the access token either from refresh_token or code.

    :param tokens: Contains the refresh token or code
    :return: status code and access_token
    """
    if tokens.get('refresh_token'):
        status_code, json_data = access_token_from_refresh_token(tokens.get('refresh_token'))
    elif tokens.get('code'):
        status_code, json_data = access_token_from_code(tokens.get('code'))
    else:
        raise HTTPError("402 Client Error: Unauthorized.")
    return status_code, json_data


def get_username(*, code: Optional[str] = None, refresh_token: Optional[str] = None) -> str:
    """
    Gets username from code or refresh token passed as an argument

    :param refresh_token: Refresh Token from oauth
    :param code: oauth code
    :return: Reddit username
    """
    status_code, tokens = get_access_token({'code': code, 'refresh_token': refresh_token})
    if status_code == 200:
        header = {'Authorization': f"bearer {tokens['access_token']}", 'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}
        res = requests.get('https://oauth.reddit.com/api/v1/me', headers=header)
        save_data_to_session(res.json()['name'], tokens['refresh_token'])
        return res.json()['name']
    else:
        raise HTTPError(f"{status_code}")


def display_stats(stat: int | float) -> str:
    """
    Takes float or int and returns the number in human-readable form.

    :param stat: Number
    :return: Human-readable number
    """
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
    """
    Checks if a reddit user is a courier

    :param username: Reddit username
    :return: True if user is courier else False
    """
    with open("couriers.yaml", 'r') as fp:
        courier_list = yaml.safe_load(fp)
        courier_list = courier_list.get('couriers', [])
    if username.lower() in courier_list:
        return True
    else:
        return False


def get_trading_karma(username: str) -> str:
    """
    Gets the trading karma of a user by grabbing their flair info in r/Fallout76Marketplace

    :param username: Reddit username
    :return: Trading Karma of the user
    """
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
        return "0"
    else:
        if res := re.search(r"(?<=: )\d+\b", flair_text):
            return res.group()
        else:
            return flair_text.split(' ')[-1]


def get_reddit_profile_info(user_name: str) -> dict:
    """
    Gathers all the information on a reddit user such as profile pic, reddit karma, trading karma, courier status, etc.

    :param user_name: Reddit username
    :return: dict object containing all information
    """
    reddit_profile_info = requests.get(f"https://www.reddit.com/user/{user_name}/about.json",
                                       headers={'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}).json()

    if reddit_profile_info.get("error"):
        return reddit_profile_info

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
