"""Приёмник webhook от Alertmanager: пишет каждый алерт JSON-строкой в stdout.

Без зависимостей (только stdlib). Логи видно в `docker compose logs alert-receiver`
и в Grafana → Loki: {service="alert-receiver"}.
"""

import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        payload = json.loads(body or b"{}")
        for alert in payload.get("alerts", []):
            print(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                "level": "error" if alert.get("status") == "firing" else "info",
                "message": f"alert {alert.get('status')}: {alert['labels'].get('alertname')}",
                "status": alert.get("status"),
                "alertname": alert["labels"].get("alertname"),
                "severity": alert["labels"].get("severity"),
                "summary": alert.get("annotations", {}).get("summary"),
                "starts_at": alert.get("startsAt"),
                "ends_at": alert.get("endsAt"),
            }, ensure_ascii=False), flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass  # без стандартного access-лога http.server


if __name__ == "__main__":
    print(json.dumps({"level": "info", "message": "alert-receiver listening on :9000"}), flush=True)
    HTTPServer(("0.0.0.0", 9000), Handler).serve_forever()
