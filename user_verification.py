import json
from contextlib import suppress
from os import getenv
from random import randint
from threading import Thread
from typing import NamedTuple, Optional

import requests
from flask import render_template, Blueprint, request, session, redirect, url_for
from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFound, PSNAWPAuthenticationError, PSNAWPForbidden, PSNAWPBadRequest, PSNAWPException
from requests import HTTPError

import deta_api
from log_gen import create_logger
from trello_api import search_multiple_items_blacklist

user_verification = Blueprint("user_verification", __name__)
logger = create_logger()


class Platform(NamedTuple):
    platform_type: str
    value: Optional[str]


def send_message_to_discord(msg):
    """
    Sends the message to discord channel via webhook url.

    :param msg: message content.
    """

    webhook = getenv("USER_VERIFICATION_CHANNEL")
    data = {"content": msg, "username": "User Verification"}
    with suppress(Exception):
        requests.post(webhook, data=json.dumps(data), headers={"Content-Type": "application/json"})


def check_user_in_blacklist(updated_data: dict):
    user_data: list[Platform] = [Platform("Reddit", updated_data['key']),
                                 Platform("PC", updated_data.get('Fallout 76')),
                                 Platform("PS4", updated_data.get('PlayStation')),
                                 Platform("PS4", updated_data.get('PlayStation_ID')),
                                 Platform("XB1", updated_data.get('XBOX')),
                                 Platform("XB1", updated_data.get('XBOX_ID'))]
    result = search_multiple_items_blacklist([data for data in user_data if data.value is not None])
    if result:
        blacklist_urls = '\n'.join([x.short_url for x in result])
        msg = f"Blacklisted u/{updated_data['key']} registered. See https://fallout76marketplace.com/user/{updated_data['key']}\n" \
              f"Blacklist cards:\n{blacklist_urls}"
        send_message_to_discord(msg)

        updated_data["is_blacklisted"] = True
        deta_api.update_item(updated_data, updated_data['key'])


def add_gamer_tag_to_db(*, verification_complete, check_blacklist: bool = False):
    updated_data = deta_api.get_item(session['username']).items[0]
    if check_blacklist:
        black_list_check_thread = Thread(target=check_user_in_blacklist, args=(updated_data,))
        black_list_check_thread.daemon = True
        black_list_check_thread.start()
    updated_data |= {"verification_complete": verification_complete, session['platform']: session['gt'], f"{session['platform']}_ID": session['gt_id']}
    deta_api.update_item(updated_data, session['username'])


@user_verification.route('/user_profile', methods=['POST'])
def redirect_to_profile():
    logger.info(f"{session['username']} accepted the agreement.")
    add_gamer_tag_to_db(verification_complete=True, check_blacklist=True)
    username = session['username']
    refresh_token = session['refresh_token']
    session.clear()
    session['username'] = username
    session['refresh_token'] = refresh_token
    return redirect(url_for("profile.user_profile", user_name=session['username']))


@user_verification.route('/verify_code', methods=['POST'])
def verify_identity():
    verification_code = request.form.get('verification_code')[:6]
    logger.info(f"{session['username']}, Actual code {session['verification_code']} vs user input {verification_code}")
    if session['verification_code'] == int(verification_code):
        add_gamer_tag_to_db(verification_complete=False)
        return redirect(url_for('user_verification.platform_verification', warning_message=""))
    else:
        return render_template("verification_code.html", platform=session['platform'], warning_message="Verification Code incorrect. Please try again.")


def get_xuid(gamer_tag):
    auth_headers = {"X-Authorization": getenv('XBOX_API'), "Content-Type": "application/json"}
    params = {'gt': gamer_tag}
    # Sometimes XBOX api returns empty results so have to try twice
    try:
        for i in range(2):
            resp = requests.get('https://xbl.io/api/v2/friends/search', headers=auth_headers, params=params)
            json_resp = resp.json()
            logger.info(json_resp)
            if json_resp.get('code') == 28:
                raise HTTPError(json_resp.get('description'))
            resp.raise_for_status()
            profile_list = json_resp.get('profileUsers')[0]
            return profile_list['settings'][2]['value'], profile_list['id']
    except (requests.JSONDecodeError, KeyError, HTTPError) as err:
        raise HTTPError(f"Could not find the GamerTag {gamer_tag}. Please check the spelling.") from err


def send_message_xbox(gamer_tag):
    gamer_tag, xuid = get_xuid(gamer_tag)
    auth_headers = {"X-Authorization": getenv("XBOX_API"), "Content-Type": "application/json"}
    verification_code = randint(100000, 999999)
    session['verification_code'] = verification_code
    msg = json.dumps({"xuid": xuid, "message": f"Your verification code is {verification_code}. Please do not share this with anyone."})
    logger.info(f"{session['username']}, {gamer_tag} Verification Code {verification_code}")
    try:
        resp = requests.post("https://xbl.io/api/v2/conversations", headers=auth_headers, data=msg)
        resp.raise_for_status()
        session['gt'] = gamer_tag
        session['gt_id'] = xuid
    except requests.HTTPError as err:
        raise HTTPError(f"Could not send the message to {gamer_tag}. Please make sure your profile is not private.") from err


def send_message_psnid(gamer_tag):
    try:
        psnawp = PSNAWP(getenv('NPSSO'))
        user = psnawp.user(online_id=gamer_tag)
        group = psnawp.group(users_list=[user])
        verification_code = randint(100000, 999999)
        session['verification_code'] = verification_code
        group.send_message(f"Your verification code is {verification_code}. Please do not share this with anyone.")
        session['gt'] = user.online_id
        session['gt_id'] = user.account_id
        logger.info(f"{session['username']}, {user.online_id} Verification code {verification_code}")
    except (PSNAWPNotFound, PSNAWPBadRequest) as not_found:
        raise PSNAWPException(f"Could not find the GamerTag {gamer_tag}. Please check the spelling.") from not_found
    except PSNAWPForbidden as forbidden:
        raise PSNAWPException(f"Could not send the message to {gamer_tag} because the profile is either private or you have blocked the bot account. "
                              f"See the <a href=\"https://imgur.com/a/ZNC9kFU\">PlayStation Message Settings</a> and make sure your settings are similar") \
            from forbidden
    except PSNAWPAuthenticationError as auth_error:
        send_message_to_discord("NPSSO code for user verification has expired.")
        raise PSNAWPException("NPSSO Code Expired. Please message moderators.") from auth_error


@user_verification.route('/gamertag', methods=['POST'])
def get_gamer_tag():
    platform = session['platform']
    gamer_tag = request.form.get('gamertag').strip()
    logger.info(f"{session['username']}, {platform} {gamer_tag}")
    try:
        if platform == "XBOX":
            send_message_xbox(gamer_tag)
            return render_template("verification_code.html", platform=platform, warning_message="")
        elif platform == "PlayStation":
            send_message_psnid(gamer_tag)
            return render_template("verification_code.html", platform=platform, warning_message="")
        else:
            session['gt'] = gamer_tag
            session['gt_id'] = "0"
            add_gamer_tag_to_db(verification_complete=False)
            # For PC, we do not need message verification.
            return redirect(url_for('user_verification.platform_verification', warning_message=""))
    except Exception as e:
        logger.exception(str(e), exc_info=True)
        # This needs to be done otherwise flask doesn't like it
        selected_platforms = session['selected_platforms']
        selected_platforms.insert(0, platform)
        session['selected_platforms'] = selected_platforms
        return redirect(url_for('user_verification.platform_verification', warning_message=str(e)))


@user_verification.route('/')
def platform_verification():
    selected_platforms = session['selected_platforms']
    if selected_platforms:
        session['platform'] = selected_platforms.pop(0)
        return render_template("gamer_tag.html", platform=session['platform'], warning_message=request.args['warning_message'])
    else:
        return render_template("subreddit_rules.html")


@user_verification.route('/redirect', methods=['POST'])
def verification_redirect():
    selected_platforms = request.form.getlist('platform_checkbox')
    logger.info(f"{session['username']}, {selected_platforms}")
    if len(selected_platforms) == 0:
        return render_template("platform.html", enable_warning=True)
    session['selected_platforms'] = selected_platforms
    return redirect(url_for('user_verification.platform_verification', warning_message=""))
