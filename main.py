from contextlib import suppress
from datetime import timedelta
from os import getenv
from time import time

from dotenv import load_dotenv
from flask import Flask, render_template, redirect, request, session, url_for
from requests import HTTPError

import deta_api
import reddit_api
from log_gen import create_logger
from profile import profile
from user_verification import user_verification

load_dotenv('config.env')
app = Flask(__name__)
app.register_blueprint(user_verification, url_prefix="/user_verification")
app.register_blueprint(profile, url_prefix="/user")
app.secret_key = getenv('FLASK_SECRET_KEY')
app.permanent_session_lifetime = timedelta(days=7)
logger = create_logger(__name__)


@app.route('/login/callback')
def reddit_oauth_callback():
    logger.info(request.args)
    if error := request.args.get('error'):
        if error == "access_denied":
            return render_template("error.html", error_title="Access Denied", error_message="We cannot verify your identity from Reddit. "
                                                                                            "Please allow access in order to proceed.")
        else:
            return render_template("error.html", error_title=error, error_message=error)
    else:
        session.permanent = True
        session['code'] = request.args.get('code')
        username = reddit_api.get_username(code=session['code']).lower()
        fetch_res = deta_api.get_item(username)
        logger.info(f"{username}, {session['code']} {fetch_res.items}")
        # If user doesn't exist in db
        if fetch_res.count == 0:
            deta_api.insert_item({"key": username,
                                  "created_at": time(),
                                  "code": session.get('code'),
                                  "refresh_token": session.get('refresh_token'),
                                  "is_blacklisted": False,
                                  "verification_complete": False})
            return render_template("platform.html", enable_warning=False)
        # If user exists but verification is not complete
        elif not fetch_res.items[0].get("verification_complete"):
            deta_api.update_item({"created_at": time(),
                                  "code": session.get('code'),
                                  "refresh_token": session.get('refresh_token'),
                                  "is_blacklisted": fetch_res.items[0].get("is_blacklisted"),
                                  "verification_complete": False}, username)
            return render_template("platform.html", enable_warning=False)
        # If user exists and verification is complete
        elif fetch_res.items[0].get("verification_complete"):
            updated_data = fetch_res.items[0] | {"code": session.get('code'), "refresh_token": session.get('refresh_token')}
            deta_api.update_item(updated_data, username)
            return redirect(url_for("profile.user_profile", user_name=username))
        else:
            return render_template("error.html", error_title="Internal Server Error", error_message="Internal Server Error."
                                                                                                    "Please contact r/Fallout76Marketplace mods")


@app.route('/reddit_oauth', methods=["POST"])
def reddit_oauth():
    return redirect("https://www.reddit.com/api/v1/authorize?"
                    f"client_id={getenv('CLIENT_ID')}&"
                    "response_type=code&"
                    "state=fallout&"
                    f"redirect_uri={getenv('redirect_uri')}&"
                    "duration=permanent&"
                    "scope=identity", code=302)


@app.route('/')
def index():
    # If user is already logged in then redirect to profile page.
    # and the verification is completed
    with suppress(HTTPError):
        username = reddit_api.get_username(refresh_token=session.get('refresh_token'))
        fetch_res = deta_api.get_item(username.lower())
        logger.info(f"{username}, {fetch_res.items}")
        if fetch_res.count > 0 and fetch_res.items[0].get("verification_complete"):
            return redirect(url_for("profile.user_profile", user_name=username))
    return render_template('login.html')


def main():
    app.run()


if __name__ == '__main__':
    main()
