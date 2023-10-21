import typing as T

import json
import logging
import time

import requests


_CACHED_TABLE = {}


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
        return _CACHED_TABLE[url]
    logger.debug("Send request to %s", url)
    response = requests.get(url, timeout=timeout)
    assert response.status_code == 200
    result = json.loads(response.text)
    _CACHED_TABLE[url] = result
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
