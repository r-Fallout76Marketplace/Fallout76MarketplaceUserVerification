from os import getenv

import requests
from flask import session
from requests.auth import HTTPBasicAuth


def get_access_token():
    # If access token is not expired
    if session.get('refresh_token'):
        # Gets access token from refresh token
        auth = HTTPBasicAuth(getenv('CLIENT_ID'), getenv('CLIENT_SECRET'))
        header = {'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}
        data = {'grant_type': 'refresh_token', 'refresh_token': session.get('refresh_token')}
        res = requests.post('https://www.reddit.com/api/v1/access_token', auth=auth, headers=header, data=data)
        json_data = res.json()
        return json_data
    else:
        # Gets access token from code
        auth = HTTPBasicAuth(getenv('CLIENT_ID'), getenv('CLIENT_SECRET'))
        header = {'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}
        data = {'grant_type': 'authorization_code', 'code': session.get('code'), 'redirect_uri': getenv('redirect_uri')}
        res = requests.post('https://www.reddit.com/api/v1/access_token', auth=auth, headers=header, data=data)
        json_data = res.json()
        session['refresh_token'] = json_data['refresh_token']
        return json_data


def get_username():
    tokens = get_access_token()
    header = {'Authorization': f"bearer {tokens['access_token']}", 'User-agent': 'Fallout76MarketplaceUserVerification v0.0.1'}
    res = requests.get('https://oauth.reddit.com/api/v1/me', headers=header)
    session['username'] = res.json()['name']
    return res.json()['name']
