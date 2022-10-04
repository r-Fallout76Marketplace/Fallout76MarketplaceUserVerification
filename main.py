from datetime import timedelta
from os import getenv

from deta import Deta
from flask import Flask, render_template, redirect, request, session, url_for

import reddit_api
from user_verification import user_verification

app = Flask(__name__)
app.register_blueprint(user_verification)
app.secret_key = getenv('FLASK_SECRET_KEY')
app.permanent_session_lifetime = timedelta(days=7)


@app.route('/login/callback')
def reddit_oauth_callback():
    if error := request.args.get('error'):
        if error == "access_denied":
            return redirect("https://http.cat/403")
        else:
            return error
    else:
        session['code'] = request.args.get('code')
        username = reddit_api.get_username()
        deta = Deta(getenv('PROJECT_KEY'))
        fallout_76_db = deta.Base("fallout_76_db")
        fetch_res = fallout_76_db.fetch({"key": username})
        # If user doesn't exist in db
        if fetch_res.count == 0:
            fallout_76_db.insert({"key": username,
                                  "code": request.args.get('code'),
                                  "refresh_token": session.get('refresh_token'),
                                  "verification_complete": False})
            return render_template("platform.html", enable_warning=False)
        # If user exists but verification is not complete
        elif not fetch_res.items[0].get("verification_complete"):
            fallout_76_db.put({"code": request.args.get('code'),
                               "refresh_token": session.get('refresh_token'),
                               "verification_complete": False}, username)
            return render_template("platform.html", enable_warning=False)
        # If user exists and verification is complete
        elif fetch_res.items[0].get("verification_complete"):
            updated_data = fetch_res.items[0]
            updated_data["code"] = request.args.get('code')
            updated_data["refresh_token"] = session.get('refresh_token')
            fallout_76_db.put(updated_data, username)
            return render_template("profile.html")
        else:
            return redirect("https://http.cat/500")


@app.route('/reddit_login', methods=["POST"])
def reddit_login():
    username = session.get('username')
    if username is not None:
        return f"Logged in as {username}"
    else:
        return redirect(url_for("reddit_oauth"), code=307)


@app.route('/reddit_oauth', methods=["POST"])
def reddit_oauth():
    return redirect("https://www.reddit.com/api/v1/authorize?"
                    f"client_id={getenv('CLIENT_ID')}&"
                    "response_type=code&"
                    "state=fallout&"
                    "redirect_uri=http://localhost:5000/login/callback&"
                    "duration=permanent&"
                    "scope=identity", code=302)


@app.route('/')
def index():
    return render_template('login.html')


def main():
    app.run()


if __name__ == '__main__':
    main()
