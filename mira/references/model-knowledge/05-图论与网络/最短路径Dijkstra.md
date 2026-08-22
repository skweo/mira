# 最短路径——Dijkstra 与 Floyd

## 一句话

Dijkstra = 从一个起点出发，贪心扩展，找到到所有其他点的最短距离。Floyd = 一次性算出所有点对之间的最短距离。

## Dijkstra 算法

### 适用条件

- 边权**非负**（有负权边 → 用 Bellman-Ford）
- 稀疏图（边数远小于 $n^2$）→ 优先队列版 O((n+m) log n)

### 算法步骤

```
1. 初始化：起点距离 = 0，其他点 = ∞
2. 选未访问点距离最小的点 u
3. 对 u 的每个邻居 v：如果 dist[u] + w(u,v) < dist[v]，更新 dist[v]
4. 标记 u 已访问
5. 重复 2–4 直到所有点已访问
```

### Python 实现

```python
import heapq

def dijkstra(graph, start):
    """graph: {node: [(neighbor, weight), ...]}, start: 起点"""
    dist = {node: float('inf') for node in graph}
    dist[start] = 0
    pq = [(0, start)]  # (距离, 节点)
    prev = {}  # 记录路径

    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue

        for v, w in graph[u]:
            new_dist = dist[u] + w
            if new_dist < dist[v]:
                dist[v] = new_dist
                prev[v] = u
                heapq.heappush(pq, (new_dist, v))

    return dist, prev
```

## Floyd 算法——所有点对最短路径

三重循环，O(n³)——适合 n < 500 的情况：

```python
def floyd(dist):
    """dist: n×n 邻接矩阵，dist[i][j] = i 到 j 的距离（不直接相连 = ∞）"""
    n = len(dist)
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if dist[i][k] + dist[k][j] < dist[i][j]:
                    dist[i][j] = dist[i][k] + dist[k][j]
    return dist
```

> k 在最外层——"经过 k 的路径去更新 i 到 j"。不能把 k 放内层。

## Dijkstra vs Floyd 怎么选

| 条件 | 用 |
|------|------|
| 单一起点到其他所有点 | Dijkstra O(m log n) |
| 所有点对之间（n < 500） | Floyd O(n³) |
| 所有点对之间（n > 500） | n 次 Dijkstra O(n m log n) |
| 有负权边 | Bellman-Ford 或 SPFA |
| 需要最短路径的具体路线 | 都支持——用 prev 回溯 |

## 数学建模中的常见变体

| 题目 | 怎么建模 |
|------|------|
| "最短配送路线" | 标准最短路径 |
| "经过多个指定点的最短路径" | TSP——不是最短路径！不要用 Dijkstra |
| "有时间窗口的配送" | VRP——带约束的路径规划 |
| "每条路有容量限制" | 网络流——最大流/最小费用流 |
