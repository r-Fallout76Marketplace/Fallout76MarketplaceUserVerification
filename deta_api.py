from os import getenv

from deta import Deta
from deta.base import FetchResponse


def get_item(key: str) -> FetchResponse:
    deta = Deta(getenv('DETA_PROJECT_KEY'))
    fallout_76_db = deta.Base("fallout_76_db")
    fetch_res = fallout_76_db.fetch({"key": key})
    return fetch_res


def insert_item(data: dict):
    deta = Deta(getenv('DETA_PROJECT_KEY'))
    fallout_76_db = deta.Base("fallout_76_db")
    fallout_76_db.insert(data)


def update_item(data: dict, key: str):
    deta = Deta(getenv('DETA_PROJECT_KEY'))
    fallout_76_db = deta.Base("fallout_76_db")
    fallout_76_db.put(data, key)
