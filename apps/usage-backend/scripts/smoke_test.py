"""Exercise a running backend against its configured upstream, including a saved-record reread."""

import argparse
import json
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:41873")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    browser = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(path, *, method="GET", token=None, payload=None, expected=200):
        headers = {"Accept": "application/json"}
        if token:
            headers["X-CSRFToken"] = token
        if payload is not None:
            headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode() if payload is not None else None
        req = Request(base_url + path, data=body, headers=headers, method=method)
        try:
            response = browser.open(req, timeout=15)
        except HTTPError as exc:
            response = exc
        with response:
            assert response.status == expected, (path, response.status, expected)
            assert response.headers.get("X-Request-ID")
            return json.load(response)

    assert request("/health") == {"status": "healthy"}
    assert request("/health/ready") == {"status": "ready"}
    assert "name" in request("/api/user/info")
    assert "error" in request(
        "/api/user/actions", method="POST", payload={"usage": 42.7}, expected=403
    )
    token = request("/api/csrf")["csrfToken"]
    created = request(
        "/api/user/actions", method="POST", token=token, payload={"usage": 42.7}, expected=201
    )
    assert created["usage"] == 42.7
    history = request("/api/user/actions?timeframe=15m")
    identifiers = {record["usage_id"] for record in history}
    assert created["usage_id"] in identifiers
    exact_range = urlencode({"start_date": created["timestamp"], "end_date": created["timestamp"]})
    assert created in request("/api/user/actions?" + exact_range)
    assert "error" in request(
        "/api/user/actions", method="POST", token=token, payload={"usage": 101}, expected=400
    )
    print("PASS: health, user info, CSRF, creation, filters, validation, reread")


if __name__ == "__main__":
    main()
