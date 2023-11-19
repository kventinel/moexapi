import typing as T

import collections
import json
import logging
import time

import requests


_CACHE_SIZE = 1000
_CACHED_TABLE = collections.OrderedDict()


def initialize_logging(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    log.setLevel(logging.INFO)
    _stream_handler = logging.StreamHandler()
    _stream_handler.setLevel(logging.DEBUG)
    _stream_handler.setFormatter(logging.Formatter(
        '%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s'
    ))
    log.addHandler(_stream_handler)
    log.propagate = False
    return log


logger = initialize_logging(__file__)


def _cached_request(url: str, timeout: int = 10) -> T.Any:
    if url in _CACHED_TABLE:
        _CACHED_TABLE.move_to_end(url)
        return _CACHED_TABLE[url]
    logger.debug("Send request to %s", url)
    response = requests.get(url, timeout=timeout)
    assert response.status_code == 200
    result = json.loads(response.text)
    _CACHED_TABLE[url] = result
    if len(_CACHED_TABLE) > _CACHE_SIZE:
        _CACHED_TABLE.popitem(last=False)
    return result


def json_api_call(url: str, retries: int = 10, timeout: int = 10, wait: int = 10) -> T.Any:
    last_ex = None
    for _ in range(retries):
        try:
            return _cached_request(url, timeout=timeout)
        except Exception as ex:
            last_ex = ex
            time.sleep(wait)
    logger.error(f"Can't parse results from {url}")
    assert last_ex is not None
    raise last_ex


def prepare_dict(response: T.Any, name: str) -> list[list[dict[str, T.Any]]]:
    return [{key: value for key, value in zip(response[name]["columns"], line)} for line in response[name]["data"]]
