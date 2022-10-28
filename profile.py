from os import getenv

import requests
from flask import Blueprint, render_template, redirect, session, url_for, request
from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFound, PSNAWPAuthenticationError

import deta_api
from log_gen import create_logger
from reddit_api import get_reddit_profile_info
from user_verification import add_gamer_tag_to_db

profile = Blueprint("profile", __name__)
logger = create_logger()
WINDOWS_LOGO_URI = "/static/images/windows.webp"
XBOX_LOGO_URI = "/static/images/xbox_logo.webp"
PLAYSTATION_LOGO_URI = "/static/images/playstation_logo.webp"


def user_not_found(username):
    msg = f"The user does not exist or has not fully completed verification process. If you are {username}, please sign up again and finish the process."
    return render_template("error.html", error_title=f"Could not find {username}", error_message=msg)


@profile.route('/search_username', methods=['GET'])
def search_user():
    user_name = request.args.get('search_box')
    if user_name.startswith("u/"):
        user_name = user_name[2:]
    return redirect(url_for("profile.user_profile", user_name=user_name))


@profile.route('/<user_name>', methods=['GET'])
def user_profile(user_name: str):
    user_name = user_name.lower()
    fetch_res = deta_api.get_item(user_name)

    logger.info(f"{user_name} profile visited by {session.get('username', '!NotLoggedIn')}.")
    # If user doesn't exist in db
    if fetch_res.count == 0 or not fetch_res.items[0].get("verification_complete"):
        return render_template("error.html", error_title=f"Could not find {user_name}", error_message=f"The user does not exist or has not fully completed "
                                                                                                      f"verification process. If you are {user_name}, please "
                                                                                                      f"sign up again and finish the process.")
    # If reddit account is deleted later
    profile_info = get_reddit_profile_info(user_name)
    if profile_info.get("error"):
        return user_not_found(user_name)

    pc_gt = (WINDOWS_LOGO_URI, fetch_res.items[0].get("Fallout 76"), "PC")
    ps_gt = (PLAYSTATION_LOGO_URI, fetch_res.items[0].get("PlayStation"), "PlayStation")
    xbox_gt = (XBOX_LOGO_URI, fetch_res.items[0].get("XBOX"), "XBOX")
    gamer_tags = list(filter(lambda gt: gt[1] is not None, [xbox_gt, ps_gt, pc_gt]))
    profile_info["gamer_tags"] = gamer_tags
    profile_info["is_logged_in"] = 'username' in session.keys()
    profile_info["is_own_profile"] = session.get('username') == user_name.lower()
    profile_info["is_blacklisted"] = fetch_res.items[0].get("is_blacklisted")
    return render_template('profile.html', profile_info=profile_info)


@profile.route('/<user_name>/pc/update/', methods=["POST"])
def update_pc_gamer_tag(user_name: str):
    gamer_tag = request.form.get('gamertag')
    session['gt'] = gamer_tag
    session['gt_id'] = "0"
    session['platform'] = "Fallout 76"
    add_gamer_tag_to_db(verification_complete=True)
    logger.info(f"{user_name} changed gamertag to {gamer_tag}")
    session.pop('gt', None)
    session.pop('gt_id', None)
    session.pop('platform', None)
    return redirect(url_for("profile.user_profile", user_name=session['username']))


@profile.route('/<user_name>/pc/edit/')
def edit_pc_gamer_tag(user_name: str):
    return render_template("edit_pc_gamertag.html", user_name=user_name)


def xuid_to_gamer_tag(xuid):
    auth_headers = {"X-Authorization": getenv("XBOX_API")}
    resp = requests.get(f'https://xbl.io/api/v2/account/{xuid}', headers=auth_headers).json()
    xbox_profile = resp.get('profileUsers')[0]
    try:
        gamer_tag = xbox_profile['settings'][2]['value']
        return gamer_tag
    except KeyError:
        return None


@profile.route('/update_info')
def update_user_info():
    if session.get('username'):
        fetch_res = deta_api.get_item(session.get('username')).items[0]

        if xuid := fetch_res.get('XBOX_ID'):
            new_gt = "Failed to fetch the XBOX GamerTag."
            for i in range(2):
                # Sometimes XBOX api returns empty results so have to try twice
                gt = xuid_to_gamer_tag(xuid)
                if gt is not None:
                    new_gt = gt
                    break

            fetch_res["XBOX"] = new_gt
            deta_api.update_item(fetch_res, session.get('username'))

        if psnid := fetch_res.get("PlayStation_ID"):
            try:
                psnawp = PSNAWP(getenv('NPSSO'))
                user = psnawp.user(account_id=f"{psnid}")
                new_gt = user.online_id
            except (PSNAWPNotFound, PSNAWPAuthenticationError):
                new_gt = "Failed to fetch the PSN GamerTag."

            fetch_res["PlayStation"] = new_gt
            deta_api.update_item(fetch_res, session.get('username'))

        return redirect(url_for("profile.user_profile", user_name=session['username']))
    else:
        # Doubt this will reach but just in case if the session expires at right time.
        return redirect("https://http.cat/401")


@profile.route('/logout')
def log_out_user():
    session.clear()
    return redirect(url_for('index'))
