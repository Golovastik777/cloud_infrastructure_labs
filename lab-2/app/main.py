"""NeoShop API — заглушка API-бэкенда для Лабы 2 (мониторинг).

Эндпоинты названы по предметной области NeoShop:
  GET  /api/products              — каталог (быстро)
  GET  /api/products/{product_id} — карточка товара (быстро)
  POST /api/cart/items            — добавить в корзину (быстро)
  GET  /api/products/search       — поиск через OpenSearch: кнопка «Создать задержку»
  POST /api/payments              — оплата через внешний шлюз: кнопка «Создать ошибку»
  POST /api/load                  — сервис сам шлёт себе запросы: кнопка «Нагрузка»
  GET  /metrics                   — метрики Prometheus (RED)
"""

import asyncio
import contextvars
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Status, StatusCode
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "neoshop-api")
PORT = int(os.getenv("PORT", "8080"))


# --- Логи: JSON в stdout, в каждой строке trace_id текущего спана -------------

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ctx = trace.get_current_span().get_span_context()
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname.lower(),
            "service": SERVICE_NAME,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": format(ctx.trace_id, "032x") if ctx.is_valid else None,
            "span_id": format(ctx.span_id, "016x") if ctx.is_valid else None,
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
log = logging.getLogger("neoshop.api")


# --- Трейсы: OpenTelemetry SDK, экспорт по OTLP ------------------------------
# Адрес коллектора/Jaeger берётся из OTEL_EXPORTER_OTLP_ENDPOINT (OTLP/HTTP).
# Пока переменная не задана, спаны всё равно создаются (trace_id попадает в логи),
# просто никуда не отправляются.

provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("neoshop.api")


# --- Метрики RED --------------------------------------------------------------
# Лейбл route — шаблон пути (/api/products/{product_id}), а не сам путь:
# иначе каждый id товара стал бы отдельным временным рядом.

REQUESTS = Counter(
    "http_requests_total", "Число HTTP-запросов", ["method", "route", "status"]
)
ERRORS = Counter(
    "http_request_errors_total", "Число HTTP-запросов, завершившихся 5xx", ["method", "route"]
)
LATENCY = Histogram(
    "http_request_duration_seconds",
    "Время обработки HTTP-запроса",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 1.5, 2, 2.5, 3, 5),
)


app = FastAPI(title="NeoShop API (stub)")


@app.middleware("http")
async def observe(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:
        log.exception("unhandled error")
        response = JSONResponse({"error": "internal"}, status_code=500)
        status = 500
    elapsed = time.perf_counter() - start

    route_obj = request.scope.get("route")
    route = getattr(route_obj, "path", "unmatched")
    if route != "/metrics":
        REQUESTS.labels(request.method, route, str(status)).inc()
        LATENCY.labels(request.method, route).observe(elapsed)
        if status >= 500:
            ERRORS.labels(request.method, route).inc()

        ctx = trace.get_current_span().get_span_context()
        if ctx.is_valid:
            response.headers["X-Trace-Id"] = format(ctx.trace_id, "032x")
        level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
        log.log(level, "request handled", extra={"fields": {
            "method": request.method,
            "route": route,
            "path": request.url.path,
            "status": status,
            "duration_ms": round(elapsed * 1000, 1),
        }})
    return response


# --- Обычные эндпоинты магазина ----------------------------------------------

PRODUCTS = [
    {"id": 1, "name": "Смартфон Neo X", "price": 49990},
    {"id": 2, "name": "Робот-пылесос Clean 3", "price": 21990},
    {"id": 3, "name": "Чайник Steel 1.7 л", "price": 3490},
    {"id": 4, "name": "Наушники Air Pro", "price": 12990},
]


@app.get("/api/products")
async def list_products():
    await asyncio.sleep(random.uniform(0.01, 0.06))
    return {"items": PRODUCTS}


@app.get("/api/products/search")
async def search_products(q: str = "чайник"):
    """«Создать задержку»: медленный запрос в OpenSearch — вложенный спан."""
    with tracer.start_as_current_span("slow-dependency") as span:
        span.set_attribute("peer.service", "opensearch")
        span.set_attribute("db.system", "opensearch")
        span.set_attribute("search.query", q)
        delay = random.uniform(1.0, 3.0)
        span.set_attribute("delay_seconds", round(delay, 2))
        log.warning("opensearch is slow", extra={"fields": {"query": q, "delay_s": round(delay, 2)}})
        await asyncio.sleep(delay)
    hits = [p for p in PRODUCTS if q.lower() in p["name"].lower()]
    return {"query": q, "hits": hits, "took_ms": round(delay * 1000)}


@app.get("/api/products/{product_id}")
async def get_product(product_id: int):
    await asyncio.sleep(random.uniform(0.005, 0.03))
    for p in PRODUCTS:
        if p["id"] == product_id:
            return p
    return JSONResponse({"error": "product not found"}, status_code=404)


@app.post("/api/cart/items")
async def add_to_cart():
    await asyncio.sleep(random.uniform(0.01, 0.04))
    return {"cart_id": f"c-{random.randint(1000, 9999)}", "items": 1}


@app.post("/api/payments")
async def create_payment():
    """«Создать ошибку»: платёжный шлюз отвечает ошибкой, отдаём 502."""
    order_id = random.randint(100000, 999999)
    span = trace.get_current_span()
    with tracer.start_as_current_span("payment-gateway.charge") as gw:
        gw.set_attribute("peer.service", "payment-gateway")
        gw.set_attribute("order.id", order_id)
        await asyncio.sleep(random.uniform(0.05, 0.2))
        err = RuntimeError("payment gateway returned 503: provider unavailable")
        gw.record_exception(err)
        gw.set_status(Status(StatusCode.ERROR, str(err)))
    span.set_status(Status(StatusCode.ERROR, "payment failed"))
    log.error("payment failed", extra={"fields": {"order_id": order_id, "reason": str(err)}})
    return JSONResponse({"error": "payment failed", "order_id": order_id}, status_code=502)


# --- «Нагрузка»: сервис сам шлёт себе запросы -------------------------------

async def _generate_load(seconds: int, rps: int) -> None:
    targets = [
        ("GET", "/api/products"),
        ("GET", "/api/products/1"),
        ("GET", "/api/products/2"),
        ("GET", "/api/products/3"),
        ("POST", "/api/cart/items"),
    ]
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{PORT}", timeout=10) as client:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            tick = time.monotonic()
            batch = [client.request(*random.choice(targets)) for _ in range(rps)]
            await asyncio.gather(*batch, return_exceptions=True)
            await asyncio.sleep(max(0.0, 1.0 - (time.monotonic() - tick)))
    log.info("load finished", extra={"fields": {"seconds": seconds, "rps": rps}})


@app.post("/api/load", status_code=202)
async def start_load(seconds: int = 60, rps: int = 30):
    seconds, rps = min(seconds, 300), min(rps, 200)
    # Пустой контекст: запросы нагрузки — отдельные трейсы, а не один гигантский.
    asyncio.create_task(_generate_load(seconds, rps), context=contextvars.Context())
    log.info("load started", extra={"fields": {"seconds": seconds, "rps": rps}})
    return {"status": "started", "seconds": seconds, "rps": rps}


# --- Служебное ----------------------------------------------------------------

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index():
    return INDEX_HTML


INDEX_HTML = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8"><title>NeoShop API — стенд мониторинга</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 16px;color:#222}
 button{font-size:16px;padding:12px 18px;margin:6px 6px 6px 0;border:0;border-radius:8px;cursor:pointer;color:#fff}
 .err{background:#c62828}.slow{background:#ef6c00}.load{background:#1565c0}.ok{background:#2e7d32}
 pre{background:#f4f4f4;padding:12px;border-radius:8px;white-space:pre-wrap;min-height:60px}
 a{margin-right:14px}
</style></head><body>
<h1>NeoShop API</h1>
<p>Заглушка API-бэкенда. Кнопки провоцируют ситуации для мониторинга.</p>
<button class="err"  onclick="call('POST','/api/payments')">Создать ошибку</button>
<button class="slow" onclick="call('GET','/api/products/search?q=чайник')">Создать задержку</button>
<button class="load" onclick="call('POST','/api/load?seconds=60&rps=30')">Нагрузка</button>
<button class="ok"   onclick="call('GET','/api/products')">Обычный запрос</button>
<pre id="out">—</pre>
<p>
 <a href="/metrics" target="_blank">/metrics</a>
 <a href="http://localhost:9090" target="_blank">Prometheus</a>
 <a href="http://localhost:3000" target="_blank">Grafana</a>
 <a href="http://localhost:16686" target="_blank">Jaeger</a>
 <a href="http://localhost:9093" target="_blank">Alertmanager</a>
</p>
<script>
async function call(method, url){
  const out = document.getElementById('out');
  out.textContent = method + ' ' + url + ' …';
  const t0 = performance.now();
  const r = await fetch(url, {method});
  const ms = Math.round(performance.now() - t0);
  const body = await r.text();
  out.textContent = `${method} ${url}\\nstatus: ${r.status}   time: ${ms} ms\\ntrace_id: ${r.headers.get('X-Trace-Id') || '—'}\\n\\n${body}`;
}
</script>
</body></html>"""


# exclude_spans: без служебных спанов «http send/receive» на каждый кусок ответа.
FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics,/healthz", exclude_spans=["send", "receive"])


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT, access_log=False, log_config=None)
