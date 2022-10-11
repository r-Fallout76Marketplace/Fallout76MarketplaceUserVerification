from os import getenv

import requests
from deta import Deta
from flask import Blueprint, render_template, redirect, session, url_for
from psnawp_api import PSNAWP
from psnawp_api.core.psnawp_exceptions import PSNAWPNotFound, PSNAWPAuthenticationError

from reddit_api import get_reddit_profile_info

profile = Blueprint("profile", __name__)

WINDOWS_LOGO_URI = "/static/images/windows.webp"
XBOX_LOGO_URI = "/static/images/xbox_logo.webp"
PLAYSTATION_LOGO_URI = "/static/images/playstation_logo.webp"


@profile.route('/<user_name>', methods=['GET'])
def user_profile(user_name: str):
    user_name = user_name.lower()
    deta = Deta(getenv('PROJECT_KEY'))
    fallout_76_db = deta.Base("fallout_76_db")
    fetch_res = fallout_76_db.fetch({"key": user_name})
    # If user doesn't exist in db
    if fetch_res.count == 0 or not fetch_res.items[0].get("verification_complete"):
        return redirect("https://http.cat/404")

    profile_info = get_reddit_profile_info(user_name)
    pc_gt = (WINDOWS_LOGO_URI, fetch_res.items[0].get("Fallout 76"), "PC")
    ps_gt = (PLAYSTATION_LOGO_URI, fetch_res.items[0].get("PlayStation"), "PlayStation")
    xbox_gt = (XBOX_LOGO_URI, fetch_res.items[0].get("XBOX"), "XBOX")
    gamer_tags = list(filter(lambda gt: gt[1] is not None, [xbox_gt, ps_gt, pc_gt]))
    profile_info["gamer_tags"] = gamer_tags
    profile_info["is_logged_in"] = 'username' in session.keys()
    profile_info["is_own_profile"] = session.get('username') == user_name.lower()
    return render_template('profile.html', profile_info=profile_info)


def xuid_to_gamer_tag(xuid):
    auth_headers = {"X-Authorization": getenv("XBOX_API")}
    resp = requests.get(f'https://xbl.io/api/v2/account/{xuid}', headers=auth_headers).json()
    profile = resp.get('profileUsers')[0]
    try:
        gamer_tag = profile['settings'][2]['value']
        return gamer_tag
    except KeyError:
        return None


@profile.route('/update_info')
def update_user_info():
    if session.get('username'):
        deta = Deta(getenv('PROJECT_KEY'))
        fallout_76_db = deta.Base("fallout_76_db")
        fetch_res = fallout_76_db.fetch({"key": session.get('username')}).items[0]

        if xuid := fetch_res.get('XBOX_ID'):
            new_gt = "Failed to fetch the XBOX GamerTag"
            for i in range(2):
                gt = xuid_to_gamer_tag(xuid)
                if gt is not None:
                    new_gt = gt
                    break

            fetch_res["XBOX"] = new_gt
            fallout_76_db.put(fetch_res, session.get('username'))

        if psnid := fetch_res.get("PlayStation_ID"):
            try:
                psnawp = PSNAWP(getenv('NPSSO'))
                user = psnawp.user(account_id=f"{psnid}")
                new_gt = user.online_id
            except PSNAWPNotFound:
                new_gt = "Failed to fetch the PSN GamerTag. The Account does not exist."
            except PSNAWPAuthenticationError:
                new_gt = fetch_res.get("PlayStation")

            fetch_res["PlayStation"] = new_gt
            fallout_76_db.put(fetch_res, session.get('username'))

        return redirect(url_for("profile.user_profile", user_name=session['username']))
    else:
        return redirect("https://http.cat/401")


@profile.route('/logout')
def log_out_user():
    session.clear()
    return redirect(url_for('index'))
