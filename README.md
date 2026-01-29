# Prometheus Practice based on Flask  App Demo

## 目标

由于理解Prometheus的监控指标需要数学统计学基础，本demo侧重于Prometheus的学习实践，体验Prometheus ，而不仅仅是了解概念。关于gitops部署流程参照[apidemo/README.md at main · shenzheke/apidemo](https://github.com/shenzheke/apidemo/blob/main/README.md)

## 实验前须知

- 要复现我的场景还需要在K8s集群能访问apiserver的节点执行：

```
[root@m01 devops]# cat << "EOF" | kubectl apply -f -
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: flask-prom-demo
  namespace: argocd
spec:
  project: default

  source:
    repoURL: http://10.0.0.200/gitops/flask-prom-demo
    targetRevision: main
    path: deploy/overlays/prod

  destination:
    server: https://kubernetes.default.svc
    namespace: monitoring

  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF

```

- 在进行Prometheus测试之前，要完成Prometheus已经部署在K8s集群，并和以下类似：

```
[root@m01 ~]# kubectl get pod -n monitoring -o wide
NAME                                             READY   STATUS    RESTARTS       AGE     IP              NODE       NOMINATED NODE   READINESS GATES

flask-prom-5464f764cd-bqr9p                      1/1     Running   1 (23h ago)    2d1h    10.244.5.27     worker01   <none>           <none>
flask-prom-5464f764cd-ndd4c                      1/1     Running   1 (23h ago)    2d1h    10.244.19.119   worker03   <none>           <none>
[root@m01 ~]# kubectl get svc -n monitoring -o wide
NAME                                  TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)                      AGE     SELECTOR

flask-prom                            ClusterIP   10.104.160.163   <none>        80/TCP                       2d17h   app=flask-prom
[root@m01 ~]# kubectl get servicemonitors.monitoring.coreos.com -n monitoring -o wide 
NAME                                  AGE
flask-prom                            2d17h

```

![image-20260129154034446](<img width="1610" height="713" alt="image" src="https://github.com/user-attachments/assets/957a8a55-d879-481e-aa0d-2e04ed77acd9" />
)

![image-20260129172437154](<img width="1907" height="646" alt="image" src="https://github.com/user-attachments/assets/9acce005-4fbb-4be6-803b-4d3d57bb127d" />
)

## 开始实验

- 确定库存正常：product_inventory 100.0

```
[root@m01 devops]# curl http://10.104.160.163/metrics | grep product_inventory
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed
  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0# HELP product_inventory Current product inventory
100  5069  100  5069    0     0  1237k      0 --:--:-- --:--:-- --:--:-- 1650k
# TYPE product_inventory gauge
product_inventory 100.0

```

测试正常：

```
[root@m01 devops]# curl -s -X POST http://10.104.160.163/order
{"order_id":4234,"status":"success"}
```

- 执行压测(二选一即可)：

  ```
  for i in {1..200}; do   curl -X POST http://10.104.160.163/order & done
  
  ```

  ```
  for i in {1..300}
  do
    curl -s -o /dev/null -w "%{http_code}\n" \
         -X POST http://10.104.160.163/order \
         -H "Content-Type: application/json" \
         -d "{\"order_id\": $i, \"user_id\": 10086, \"amount\": 99.9}" &
  done
  ```

  连续执行上述压测两次，观察图像：注意以下图的时间，**正确理解是Prometheus显示的时间+8h等于你的真实时间。**

```
rate(http_request_latency_seconds_bucket[5m])
```

![原始直方图桶（histogram buckets）](<img width="1889" height="1020" alt="image" src="https://github.com/user-attachments/assets/2feed478-9b36-42fe-9f83-cbe585e85e2a" />

)

<span style="color:red">原始直方图桶（histogram buckets）</span>

例如，单击“le=0.1“的条目，发现对应的Y轴值为0.5，意思是过去5分钟的http请求延迟低于0.1s的请求速率，合计每秒0.5个。例如le=”+Inf“的条目对应Y轴值大约为1，即为5分钟内收到的所有请求大约为1x5x60=300个，和测试相符。



```
histogram_quantile(
  0.95,
  sum by (le)(
    rate(http_request_latency_seconds_bucket[5m])
  )
)
```

![P95 延迟](<img width="1904" height="996" alt="image" src="https://github.com/user-attachments/assets/34e0b371-c0a3-4baf-a118-6bcbe4b37e72" />
)

**计算 HTTP 请求延迟的 95% 分位数（即 P95 延迟）  **：**过去 5 分钟内，95% 的 HTTP 请求响应时间 ≤ 1.7xx 秒，**



```
rate(http_request_latency_seconds_sum[5m])
/
rate(http_request_latency_seconds_count[5m])
```

![该时间窗口内的平均延迟](<img width="1893" height="987" alt="image" src="https://github.com/user-attachments/assets/dd6b5dd3-871e-447d-809d-cb473f750879" />
)

rate(sum[5m]) / rate(count[5m])= (总延迟增量 / 时间窗口) / (请求数增量 / 时间窗口)= 总延迟增量 / 请求数增量= 过去 5 分钟内的 **平均请求延迟（秒）**



```
sum(rate(orders_total{result="success"}[5m]))
/
sum(rate(orders_total[5m]))
```

![image-20260129160906983](<img width="1870" height="811" alt="image" src="https://github.com/user-attachments/assets/be590168-a43c-4e3c-8836-3e43ea0b0403" />
)

过去 5 分钟内所有成功的订单数 / 过去 5 分钟内所有订单总数，也就是订单成功率（Success Rate）

```
max_over_time(http_requests_in_progress[1m])

```

![ 并发峰值（生产常用）](<img width="1876" height="975" alt="image" src="https://github.com/user-attachments/assets/542c1a13-3c1a-4f6b-8a77-709ed71725e0" />
)

看并发 Gauge(容量规划 / HPA 的重要依据)

- <span style="color:red">搞了几轮压测，会把库存打爆，要及时恢复，否则总是返回409</span>

  ```
  [root@m01 devops]# curl http://10.104.160.163/metrics | grep product_inventory
    % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                   Dload  Upload   Total   Spent    Left  Speed
  100 11470  100 11470    0     0  2240k      0 --:--:-- --:--:-- --:--:-- 2240k
  # HELP product_inventory Current product inventory
  # TYPE product_inventory gauge
  product_inventory -28.0
  [root@m01 devops]# curl -X POST http://10.104.160.163/inventory/reset
  {"inventory":100}
  [root@m01 devops]# curl http://10.104.160.163/metrics | grep product_inventory
    % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                   Dload  Upload   Total   Spent    Left  Speed
  100 13449  100 13449    0     0  2626k      0 --:--:-- --:--:-- --:--:-- 2626k
  # HELP product_inventory Current product inventory
  # TYPE product_inventory gauge
  product_inventory 100.0
  
  ```

