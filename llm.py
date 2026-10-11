"""Minimal OpenAI-compatible chat client, stdlib only. Works against llama-server and mlx_lm.server.

The `model` field is omitted unless given: single-model servers ignore it or default sensibly.
"""
import json
import urllib.error
import urllib.request


class ServerDown(Exception):
    """Nothing is listening at the endpoint."""


def get(url, timeout=3):
    """GET a JSON endpoint; None if unreachable or not 200. Used for health probes."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return None


def _post(url, body, timeout):
    req = urllib.request.Request(
        f"{url.rstrip('/')}/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        return urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{url}: HTTP {e.code}: {e.read().decode(errors='replace')[:500]}") from None
    except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
        raise ServerDown(f"no server at {url} ({getattr(e, 'reason', e)})") from None


def chat(url, messages, tools=None, timeout=600, **gen):
    """One non-streaming completion. Returns the parsed response JSON."""
    body = {"messages": messages, **gen}
    if tools:
        body["tools"] = tools
    with _post(url, body, timeout) as r:
        return json.load(r)


def stream(url, messages, timeout=600, **gen):
    """Yield {'text': ..} and {'reasoning': ..} deltas, plus {'usage': ..} if the server sends one."""
    body = {"messages": messages, "stream": True, "stream_options": {"include_usage": True}, **gen}
    with _post(url, body, timeout) as r:
        for line in r:
            line = line.decode().strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            chunk = json.loads(data)
            if chunk.get("usage"):
                yield {"usage": chunk["usage"]}
            if chunk.get("timings"):
                yield {"timings": chunk["timings"]}  # llama-server: server-side prompt and decode rates
            for choice in chunk.get("choices", []):
                delta = choice.get("delta", {})
                reasoning = delta.get("reasoning_content") or delta.get("reasoning")  # llama-server / mlx_lm.server
                if reasoning:
                    yield {"reasoning": reasoning}
                if delta.get("content"):
                    yield {"text": delta["content"]}
