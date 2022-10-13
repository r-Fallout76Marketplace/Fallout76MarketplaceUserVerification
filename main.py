from contextlib import suppress
from datetime import timedelta
from os import getenv
from time import time

from deta import Deta
from flask import Flask, render_template, redirect, request, session, url_for

import reddit_api
from profile import profile
from user_verification import user_verification

app = Flask(__name__)
app.register_blueprint(user_verification, url_prefix="/user_verification")
app.register_blueprint(profile, url_prefix="/user")
app.secret_key = getenv('FLASK_SECRET_KEY')
app.permanent_session_lifetime = timedelta(days=7)


@app.route('/login/callback')
def reddit_oauth_callback():
    if error := request.args.get('error'):
        if error == "access_denied":
            return render_template("error.html", error_title="Access Denied", error_message="We cannot verify your identity from Reddit. "
                                                                                            "Please allow access in order to proceed.")
        else:
            return render_template("error.html", error_title=error, error_message=error)
    else:
        session['code'] = request.args.get('code')
        username = reddit_api.get_username().lower()
        deta = Deta(getenv('DETA_PROJECT_KEY'))
        fallout_76_db = deta.Base("fallout_76_db")
        fetch_res = fallout_76_db.fetch({"key": username})
        # If user doesn't exist in db
        if fetch_res.count == 0:
            fallout_76_db.insert({"key": username,
                                  "created_at": time(),
                                  "code": session.get('code'),
                                  "refresh_token": session.get('refresh_token'),
                                  "verification_complete": False})
            return render_template("platform.html", enable_warning=False)
        # If user exists but verification is not complete
        elif not fetch_res.items[0].get("verification_complete"):
            fallout_76_db.put({"created_at": time(),
                               "code": session.get('code'),
                               "refresh_token": session.get('refresh_token'),
                               "verification_complete": False}, username)
            return render_template("platform.html", enable_warning=False)
        # If user exists and verification is complete
        elif fetch_res.items[0].get("verification_complete"):
            updated_data = fetch_res.items[0]
            updated_data |= {"code": session.get('code'), "refresh_token": session.get('refresh_token')}
            fallout_76_db.put(updated_data, username.lower())
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
    with suppress(KeyError, ValueError):
        username = reddit_api.get_username()
        deta = Deta(getenv('DETA_PROJECT_KEY'))
        fallout_76_db = deta.Base("fallout_76_db")
        fetch_res = fallout_76_db.fetch({"key": session['username']})
        if fetch_res.count > 0 and fetch_res.items[0].get("verification_complete"):
            return redirect(url_for("profile.user_profile", user_name=username))
    return render_template('login.html')


def main():
    session.permanent = True
    app.run()


if __name__ == '__main__':
    main()
