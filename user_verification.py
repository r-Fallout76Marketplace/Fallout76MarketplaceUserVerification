import json
from contextlib import suppress
from os import getenv
from random import randint

import requests
from deta import Deta
from flask import render_template, Blueprint, request, session, redirect, url_for
from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFound

user_verification = Blueprint("user_verification", __name__)


def get_xuid(gamer_tag):
    auth_headers = {"X-Authorization": getenv("XBOX_API")}
    params = {'gt': gamer_tag}
    for i in range(2):
        with suppress(requests.JSONDecodeError, KeyError):
            resp = requests.get('https://xbl.io/api/v2/friends/search', headers=auth_headers, params=params)
            json_resp = resp.json()
            profile_list = json_resp.get('profileUsers')[0]
            return profile_list['settings'][2]['value'], profile_list['id']
    raise ValueError("Gamertag is not correct.")


def send_message_xbox(xuid):
    auth_headers = {"X-Authorization": getenv("XBOX_API")}
    verification_code = randint(100000, 999999)
    session['verification_code'] = verification_code
    msg = json.dumps({"xuid": xuid, "message": verification_code})
    resp = requests.post("https://xbl.io/api/v2/conversations", headers=auth_headers, data=msg)
    if resp.status_code != 200:
        raise ValueError("Could not send the message.")


def add_gamertag_to_db(*, verification_complete):
    deta = Deta(getenv('PROJECT_KEY'))
    fallout_76_db = deta.Base("fallout_76_db")
    fetch_res = fallout_76_db.fetch({"key": session['username']}).items[0]
    updated_data = {**fetch_res, "verification_complete": verification_complete, session['platform']: session['gt'],
                    f"{session['platform']}_ID": session['gt_id']}
    fallout_76_db.put(updated_data, session['username'])


@user_verification.route('/user_profile', methods=['POST'])
def redirect_to_profile():
    add_gamertag_to_db(verification_complete=True)
    username = session['username']
    refresh_token = session['refresh_token']
    session.clear()
    session.permanent = True
    session['username'] = username
    session['refresh_token'] = refresh_token
    return "Verification Completed"


@user_verification.route('/user_verification/verify_code', methods=['POST'])
def verify_identity():
    verification_code = request.form.get('verification_code')[:6]
    if session['verification_code'] == int(verification_code):
        add_gamertag_to_db(verification_complete=False)
        return redirect(url_for('user_verification.platform_verification', warning_message=""))
    else:
        return render_template("verification_code.html", platform=session['platform'], warning_message="Verification Code incorrect. Please try again.")


@user_verification.route('/user_verification/gamertag', methods=['POST'])
def get_gamertag():
    platform = session['platform']
    gamertag = request.form.get('gamertag')
    try:
        if platform == "XBOX":
            gamertag, xuid = get_xuid(gamertag)
            send_message_xbox(xuid)
            session['gt'] = gamertag
            session['gt_id'] = xuid
            return render_template("verification_code.html", platform=platform, warning_message="")
        elif platform == "PlayStation":
            psnawp = PSNAWP(getenv('NPSSO'))
            try:
                user = psnawp.user(online_id=gamertag)
                group = psnawp.group(users_list=[user])
                verification_code = randint(100000, 999999)
                session['verification_code'] = verification_code
                group.send_message(f"{verification_code}")
                session['gt'] = user.online_id
                session['gt_id'] = user.account_id
                return render_template("verification_code.html", platform=platform, warning_message="")
            except PSNAWPNotFound:
                raise ValueError("Online ID not found")
        else:
            session['gt'] = gamertag
            session['gt_id'] = "0"
            add_gamertag_to_db(verification_complete=False)
            return redirect(url_for('user_verification.platform_verification', warning_message=""))
    except ValueError:
        selected_platforms = session['selected_platforms']
        selected_platforms.insert(0, platform)
        session['selected_platforms'] = selected_platforms
        return redirect(url_for('user_verification.platform_verification', warning_message="Could not find the Gamertag. Please check the spelling."))


@user_verification.route('/user_verification/')
def platform_verification():
    selected_platforms = session['selected_platforms']
    if selected_platforms:
        platform = selected_platforms.pop(0)
        session['platform'] = platform
        return render_template("gamer_tag.html", platform=platform, warning_message=request.args['warning_message'])
    else:
        return render_template("subreddit_rules.html")


@user_verification.route('/user_verification_redirect', methods=['POST'])
def get_platforms():
    selected_platforms = request.form.getlist('platform_checkbox')
    if len(selected_platforms) == 0:
        return render_template("platform.html", enable_warning=True)
    session['selected_platforms'] = selected_platforms
    return redirect(url_for('user_verification.platform_verification', warning_message=""))
