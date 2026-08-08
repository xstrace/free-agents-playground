#!/usr/bin/env python3
"""LLM 网关(边车容器): agent 的唯一模型入口。

- key 只存在于本进程的环境变量 ZEN_KEY 里, agent 容器内没有任何 key
- OpenAI 兼容协议转发到 opencode zen, 支持 SSE 流式透传
- 忽略客户端带来的任何 Authorization(永远用自己的 key)
"""
import http.client
import http.server
import json
import os

ZEN_HOST = os.environ.get("ZEN_HOST", "opencode.ai")
# 注意: 传入路径自带 /v1/..., 所以基准是 /zen, 拼成 /zen/v1/chat/completions
ZEN_BASE = os.environ.get("ZEN_BASE", "/zen")
KEY = os.environ.get("ZEN_KEY", "")
PORT = int(os.environ.get("GATEWAY_PORT", "8787"))


def forward(method, path, body, wfile):
    conn = http.client.HTTPSConnection(ZEN_HOST, timeout=300)
    conn.request(method, ZEN_BASE + path, body=body, headers={
        "Authorization": "Bearer " + KEY,
        "Content-Type": "application/json",
        "Accept": "*/*",
    })
    resp = conn.getresponse()
    status = resp.status
    wfile.write(f"HTTP/1.1 {status} {resp.reason}\r\n".encode())
    for k, v in resp.getheaders():
        if k.lower() not in ("connection", "transfer-encoding", "content-length", "keep-alive"):
            wfile.write(f"{k}: {v}\r\n".encode())
    wfile.write(b"Connection: close\r\n")
    wfile.write(b"Transfer-Encoding: chunked\r\n\r\n")
    while True:
        chunk = resp.read(16384)
        if not chunk:
            break
        wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
        wfile.flush()
    wfile.write(b"0\r\n\r\n")
    wfile.flush()
    conn.close()
    return status


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _handle(self):
        import time
        t0 = time.time()
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        status = 502
        try:
            status = forward(self.command, self.path, body, self.wfile)
        except Exception as e:
            try:
                msg = json.dumps({"error": {"message": str(e), "type": "gateway_error"}}).encode()
                self.send_response(502)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(msg)))
                self.end_headers()
                self.wfile.write(msg)
            except Exception:
                pass
        print(f"[gateway] {self.command} {self.path} -> {status} ({time.time()-t0:.2f}s)", flush=True)

    do_GET = _handle
    do_POST = _handle


if __name__ == "__main__":
    print(f"[gateway] :{PORT} → {ZEN_HOST}{ZEN_BASE} (key: {'set' if KEY else 'MISSING'})", flush=True)
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
