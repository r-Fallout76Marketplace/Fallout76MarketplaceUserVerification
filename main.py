import os
from os import getenv

from flask import Flask, render_template, redirect, request

app = Flask(__name__)


@app.route('/login/callback', methods=["GET"])
def reddit_oauth_callback():
    if error := request.args.get('error'):
        if error == "access_denied":
            return redirect("https://http.cat/403")
        else:
            return error
    else:
        return redirect("https://www.google.com/")


@app.route('/reddit_oauth', methods=["GET"])
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
    return render_template('index.html')


def main():
    app.run()


if __name__ == '__main__':
    main()
