"""Bounded JSON reads between the public API, search proxy and private index."""

import json
from time import monotonic

MAX_SEARCH_RESPONSE_BYTES = 16 * 1024 * 1024
IDENTITY_ENCODING = {"Accept-Encoding": "identity"}


def read_search_json(response, *, deadline):
    response.raise_for_status()
    if response.headers.get("content-encoding", "identity").lower() != "identity":
        raise ValueError("Unexpected search response encoding")
    length = response.headers.get("content-length")
    if length is not None and not 0 <= int(length) <= MAX_SEARCH_RESPONSE_BYTES:
        raise ValueError("Search response exceeds the byte limit")
    payload = bytearray()
    # Do not aggregate small chunks before checking the wall-clock deadline.
    # Test adapters can supply an already materialized Response; actual HTTPX
    # stream responses reach this boundary unconsumed.
    chunks = (response.content,) if response.is_stream_consumed else response.iter_raw()
    for chunk in chunks:
        if monotonic() >= deadline or len(payload) + len(chunk) > MAX_SEARCH_RESPONSE_BYTES:
            raise ValueError("Search response exceeds the read budget")
        payload.extend(chunk)
    return json.loads(payload)
