from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics
import time
import random

app = Flask(__name__)
metrics = PrometheusMetrics(app)

# =========================
# 1️⃣ 通用请求级指标
# =========================

REQUEST_COUNT = metrics.counter(
    "http_requests_total",
    "Total HTTP requests",
    labels={
        "method": lambda: request.method,
        "path": lambda: request.path,
        "status": lambda r: r.status_code
    }
)

REQUEST_LATENCY = metrics.histogram(
    "http_request_latency_seconds",
    "HTTP request latency",
    buckets=(0.1, 0.3, 0.5, 1, 2, 3, 5)
)

IN_PROGRESS = metrics.gauge(
    "http_requests_in_progress",
    "In progress HTTP requests"
)

# =========================
# 2️⃣ 业务级指标（订单）
# =========================

ORDER_TOTAL = metrics.counter(
    "orders_total",
    "Total orders created",
    labels={"result": lambda r: r.json.get("status", "unknown")}
)

ORDER_LATENCY = metrics.histogram(
    "order_processing_seconds",
    "Order processing latency",
    buckets=(0.2, 0.5, 1, 2, 3, 5)
)

# =========================
# 3️⃣ 状态型指标（库存）
# =========================

INVENTORY = metrics.gauge(
    "product_inventory",
    "Current product inventory"
)

# 初始化库存
INVENTORY.set(100)

# =========================
# 4️⃣ 外部依赖模拟
# =========================

DEPENDENCY_LATENCY = metrics.histogram(
    "dependency_call_seconds",
    "External dependency latency",
    buckets=(0.05, 0.1, 0.3, 0.5, 1, 2)
)

DEPENDENCY_ERRORS = metrics.counter(
    "dependency_errors_total",
    "External dependency errors"
)


def call_external_service():
    """模拟支付 / 库存中心 / 第三方 API"""
    latency = random.uniform(0.05, 1.5)
    time.sleep(latency)

    # 10% 概率失败
    if random.random() < 0.1:
        DEPENDENCY_ERRORS.inc()
        raise Exception("External service error")

    return latency


# =========================
# 5️⃣ 路由定义
# =========================

@app.route("/")
def index():
    return "Order Service with Prometheus Metrics"


@app.route("/order", methods=["POST"])
@IN_PROGRESS.track_inprogress()
@REQUEST_LATENCY.time()
@ORDER_LATENCY.time()
def create_order():
    # 库存检查
    current_inventory = INVENTORY._value.get()
    if current_inventory <= 0:
        response = jsonify({"status": "failed", "reason": "out_of_stock"})
        response.status_code = 409
        ORDER_TOTAL.labels(result="failed").inc()
        return response

    # 调用外部依赖
    try:
        with DEPENDENCY_LATENCY.time():
            call_external_service()
    except Exception:
        response = jsonify({"status": "failed", "reason": "dependency_error"})
        response.status_code = 502
        ORDER_TOTAL.labels(result="failed").inc()
        return response

    # 模拟业务处理
    time.sleep(random.uniform(0.1, 0.5))

    # 扣减库存
    INVENTORY.dec()

    ORDER_TOTAL.labels(result="success").inc()

    return jsonify({
        "status": "success",
        "order_id": random.randint(10000, 99999)
    })


@app.route("/inventory/reset", methods=["POST"])
def reset_inventory():
    INVENTORY.set(100)
    return {"inventory": 100}

