from flask import Flask, request, jsonify
from prometheus_flask_exporter import PrometheusMetrics
# 全部从原生库导入
from prometheus_client import Counter, Gauge, Histogram
import time
import random

app = Flask(__name__)
# 仅用于自动生成 /metrics 接口和基础 HTTP 指标
metrics = PrometheusMetrics(app)

# =========================
# 1️⃣ 业务/通用指标 (全部使用原生定义)
# =========================

# 对应之前的 REQUEST_LATENCY
HTTP_REQ_LATENCY = Histogram(
    "http_request_latency_seconds",
    "HTTP request latency",
    buckets=(0.1, 0.3, 0.5, 1, 2, 3, 5)
)

# 对应之前的 IN_PROGRESS
IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "In progress HTTP requests"
)

ORDER_TOTAL = Counter(
    "orders_total",
    "Total orders created",
    ["result"]
)

ORDER_LATENCY = Histogram(
    "order_processing_seconds",
    "Order processing latency",
    buckets=(0.2, 0.5, 1, 2, 3, 5)
)

INVENTORY = Gauge(
    "product_inventory",
    "Current product inventory"
)

# 外部依赖指标
DEPENDENCY_LATENCY = Histogram(
    "dependency_call_seconds",
    "External dependency latency",
    buckets=(0.05, 0.1, 0.3, 0.5, 1, 2)
)

DEPENDENCY_ERRORS = Counter(
    "dependency_errors_total",
    "External dependency errors"
)

# 初始化库存
INVENTORY.set(100)

# =========================
# 2️⃣ 业务逻辑
# =========================

def call_external_service():
    latency = random.uniform(0.05, 1.5)
    time.sleep(latency)
    if random.random() < 0.1:
        DEPENDENCY_ERRORS.inc()
        raise Exception("External service error")
    return latency

# =========================
# 3️⃣ 路由定义
# =========================

@app.route("/")
def index():
    return "Order Service with Prometheus Metrics"

@app.route("/order", methods=["POST"])
@IN_PROGRESS.track_inprogress() # 现在原生 Gauge 支持这个方法了
@HTTP_REQ_LATENCY.time()        # 原生 Histogram 支持这个方法
@ORDER_LATENCY.time()           # 原生 Histogram 支持这个方法
def create_order():
    # 注意：原生 Gauge 获取值建议用 INVENTORY._value.get() 
    # 或者直接进行逻辑判断
    if INVENTORY._value.get() <= 0:
        ORDER_TOTAL.labels(result="failed").inc()
        return jsonify({"status": "failed", "reason": "out_of_stock"}), 409

    try:
        with DEPENDENCY_LATENCY.time():
            call_external_service()
    except Exception:
        ORDER_TOTAL.labels(result="failed").inc()
        return jsonify({"status": "failed", "reason": "dependency_error"}), 502

    time.sleep(random.uniform(0.1, 0.3))
    
    INVENTORY.dec() # 正常扣减
    ORDER_TOTAL.labels(result="success").inc()

    return jsonify({"status": "success", "order_id": random.randint(1000, 9999)})

@app.route("/inventory/reset", methods=["POST"])
def reset_inventory():
    INVENTORY.set(100)
    return {"inventory": 100}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
