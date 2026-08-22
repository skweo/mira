# ARIMA 时间序列预测

## 一句话

ARIMA = 数据**有趋势、有季节性、点数够多（>30）**时的首选预测工具。把时间序列拆成自回归（AR）+ 差分（I）+ 移动平均（MA）三步。

## 何时用

| 条件 | 适合 |
|------|------|
| 数据量 | > 30 个时间点 |
| 数据特点 | 有趋势（上升/下降）、可能有季节性波动 |
| 不适合 | 4–10 个点 → 用 GM(1,1)；纯随机白噪声 → 无可预测性 |

## ARIMA(p, d, q)——三个参数

| 参数 | 含义 | 怎么选 |
|------|------|------|
| **p** (AR 阶数) | 用前 p 个时刻的值预测现在 | 看 PACF 图——最后一个显著的滞后 |
| **d** (差分次数) | 差分几次后序列平稳 | 一般 d=0 或 d=1。看 ADF 检验 |
| **q** (MA 阶数) | 用前 q 个时刻的预测误差修正 | 看 ACF 图——最后一个显著的滞后 |

## 数学模型

**AR(p)——自回归：**
$$x_t = c + \phi_1 x_{t-1} + \phi_2 x_{t-2} + ... + \phi_p x_{t-p} + \varepsilon_t$$

**MA(q)——移动平均：**
$$x_t = \mu + \varepsilon_t + \theta_1 \varepsilon_{t-1} + ... + \theta_q \varepsilon_{t-q}$$

**I(d)——差分：** 不平稳就差分一次——$\nabla x_t = x_t - x_{t-1}$，直到平稳为止。

## Python 实现

```python
from statsmodels.tsa.arima.model import ARIMA
import pandas as pd
import numpy as np

data = np.array([...])  # 你的时间序列

# 自动选择参数（也可以用 auto_arima）
# pip install pmdarima
from pmdarima import auto_arima
model_auto = auto_arima(data, seasonal=False, trace=True)
print(model_auto.summary())

# 或手动指定
model = ARIMA(data, order=(2, 1, 1))
fitted = model.fit()
forecast = fitted.forecast(steps=10)  # 预测未来 10 步
```

## 检验残差

好的 ARIMA 模型——残差是**白噪声**（没有可预测的模式）：

```python
residuals = fitted.resid
# Ljung-Box 检验——p > 0.05 → 残差是白噪声 → 模型合格
from statsmodels.stats.diagnostic import acorr_ljungbox
lb = acorr_ljungbox(residuals, lags=[10])
print(f'Ljung-Box p-value: {lb["lb_pvalue"].values[0]:.4f}')
```

## 常见陷阱

- 忘记检验平稳性——非平稳序列直接 ARIMA 会伪回归
- d > 2——很少有序列需要差分 3 次
- 预测步数太长——预测 10 步的置信区间已经宽到没什么用
