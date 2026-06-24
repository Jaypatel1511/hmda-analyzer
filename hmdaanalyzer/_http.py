"""
Extractable HTTP fetch layer for the CFPB HMDA Data Browser API.

This module is intentionally self-contained — it imports only ``requests`` and the
package ``__version__`` — so it can later move to a shared package unchanged.

Why these headers: a live probe reproduced an HTTP 403 "Access Denied" from the
CFPB API's Akamai edge when requests came from cloud/datacenter environments (e.g.
Google Colab) with a bare default library client. The configuration that CLEARED
the reproduced cloud 403 was a non-default *identifying* User-Agent plus explicit
``Accept`` and ``Accept-Language`` headers. The probe did not isolate which of the
three is the lever, so we send the whole verified-passing bundle. A spoofed browser
User-Agent is deliberately NOT used — it 403s on residential connections (TLS
fingerprint mismatch).
"""
import requests

from hmdaanalyzer import __version__

# Cap stored error bodies so a pathological response can't balloon the exception.
_MAX_BODY = 2048


class CFPBAPIError(RuntimeError):
    """
    Raised when the CFPB HMDA Data Browser API returns an HTTP error status.

    Subclasses :class:`RuntimeError` deliberately, so existing ``except RuntimeError``
    callers keep working unchanged (the same back-compat philosophy as
    :class:`hmdaanalyzer.MissingColumnError` subclassing ``ValueError``).

    Attributes:
        status_code:   The HTTP status code the API returned (e.g. 403, 400).
        response_body: The raw response body text (truncated to ~2 KB).
        url:           The request URL that failed.
    """

    def __init__(self, message, *, status_code=None, response_body=None, url=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.url = url


def _build_headers(accept=None, extra_headers=None):
    """Build the verified-passing request headers; ``extra_headers`` override last."""
    headers = {
        "User-Agent": f"hmda-analyzer/{__version__} (+https://github.com/Jaypatel1511/hmda-analyzer)",
        "Accept": accept or "text/csv, application/json;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if extra_headers:
        headers.update(extra_headers)
    return headers


def fetch(url, *, params=None, timeout=120, stream=True, accept=None, extra_headers=None):
    """
    GET ``url`` with the verified-passing CFPB header bundle and raise for status.

    On an HTTP error status this raises :class:`CFPBAPIError` with a status-branched,
    accurate message and the response body attached. Only ``requests.HTTPError`` is
    wrapped here — connection and timeout errors (``ConnectionError``, ``Timeout``)
    propagate unwrapped so callers can handle them as they always have.

    Returns the live :class:`requests.Response` on success; the caller is responsible
    for consuming/closing it (it may still be streaming when ``stream=True``).
    """
    headers = _build_headers(accept=accept, extra_headers=extra_headers)
    r = requests.get(url, params=params, headers=headers, timeout=timeout, stream=stream)
    try:
        r.raise_for_status()
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        body = ""
        if e.response is not None:
            try:
                body = (e.response.text or "")[:_MAX_BODY]
            except Exception:
                body = ""
        r.close()
        raise CFPBAPIError(
            _message_for(status, body),
            status_code=status,
            response_body=body,
            url=url,
        ) from e
    return r


def _message_for(status, body):
    """Status-branched, honest error text — a 403 is an edge block, not a bad query."""
    if status == 403:
        return (
            "The CFPB HMDA API edge (Akamai) refused this request (HTTP 403). "
            "This commonly happens from cloud/datacenter environments such as "
            "Google Colab, even when the query is valid. Try running locally, or "
            "download the CSV from the HMDA Data Browser "
            "(https://ffiec.cfpb.gov/data-browser/). This is an access/network "
            "block, NOT a problem with your year/state/county values."
        )
    if status == 400:
        return f"The CFPB HMDA API rejected the query (HTTP 400). API response: {body}"
    return f"The CFPB HMDA API returned HTTP {status}. {body}"


__all__ = ["CFPBAPIError", "fetch"]
