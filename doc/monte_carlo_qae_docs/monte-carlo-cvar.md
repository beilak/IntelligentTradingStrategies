# Monte Carlo CVaR

## 1. Что решает метод

Monte Carlo CVaR оценивает средний убыток в худших сценариях.

CVaR также называют:

- Conditional Value at Risk;
- Expected Shortfall;
- Tail Value at Risk.

Если VaR отвечает на вопрос:

```text
Где начинается хвост плохих сценариев?
```

то CVaR отвечает:

```text
Насколько плохой хвост в среднем?
```

Например:

```text
VaR95 = 320 000 RUB
CVaR95 = 510 000 RUB
```

Это означает:

```text
В 5% худших сценариев средний убыток составляет 510 000 RUB.
```

---

## 2. Почему CVaR важнее VaR

VaR показывает только границу.

Допустим, есть два портфеля:

| Портфель | VaR95 | CVaR95 |
|---|---:|---:|
| A | 300 000 RUB | 380 000 RUB |
| B | 300 000 RUB | 1 500 000 RUB |

По VaR они выглядят одинаково.

Но портфель B намного опаснее, потому что его хвост тяжелее.

Поэтому CVaR часто лучше отражает реальный риск.

---

## 3. Математическая идея

Пусть:

- \(L\) — случайный убыток;
- \(\alpha\) — уровень доверия, например \(0.95\);
- \(VaR_{\alpha}\) — квантиль убытков.

Тогда:

\[
CVaR_{\alpha} = E[L \mid L \ge VaR_{\alpha}]
\]

То есть:

```text
CVaR = средний убыток среди сценариев, где убыток не меньше VaR.
```

Для уровня 95% это среднее по худшим 5% сценариев.

---

## 4. Типовой пайплайн

```text
Исторические цены
↓
Доходности акций
↓
Monte Carlo сценарии
↓
Убытки портфеля
↓
VaR как квантиль
↓
Среднее по убыткам выше VaR
↓
CVaR
```

---

## 5. Пример с российскими акциями

Портфель:

| Акция | Вес |
|---|---:|
| SBER | 30% |
| LKOH | 25% |
| YDEX | 20% |
| T | 15% |
| VKCO | 10% |

Стоимость:

```text
10 000 000 RUB
```

Нужно оценить:

```text
VaR95
CVaR95
```

---

## 6. Реализация на Python

```python
import numpy as np


def monte_carlo_var_cvar(
    returns: np.ndarray,
    weights: np.ndarray,
    portfolio_value: float,
    confidence_level: float = 0.95,
    n_simulations: int = 100_000,
    random_state: int = 42,
) -> tuple[float, float]:
    """
    Monte Carlo оценка VaR и CVaR.

    returns:
        Исторические дневные доходности.
        Shape: [n_days, n_assets]

    weights:
        Веса активов.
        Shape: [n_assets]

    portfolio_value:
        Стоимость портфеля.
    """

    rng = np.random.default_rng(random_state)

    mean = returns.mean(axis=0)
    cov = np.cov(returns.T)

    simulated_asset_returns = rng.multivariate_normal(
        mean=mean,
        cov=cov,
        size=n_simulations,
    )

    portfolio_returns = simulated_asset_returns @ weights

    losses = -portfolio_returns * portfolio_value

    var = np.quantile(losses, confidence_level)

    tail_losses = losses[losses >= var]

    cvar = tail_losses.mean()

    return float(var), float(cvar)


if __name__ == "__main__":
    np.random.seed(42)

    tickers = ["SBER", "LKOH", "YDEX", "T", "VKCO"]
    n_days = 1500
    n_assets = len(tickers)

    returns = np.random.normal(
        loc=0.0004,
        scale=0.025,
        size=(n_days, n_assets),
    )

    weights = np.array([0.30, 0.25, 0.20, 0.15, 0.10])
    portfolio_value = 10_000_000

    var_95, cvar_95 = monte_carlo_var_cvar(
        returns=returns,
        weights=weights,
        portfolio_value=portfolio_value,
        confidence_level=0.95,
        n_simulations=100_000,
    )

    print(f"VaR95:  {var_95:,.0f} RUB")
    print(f"CVaR95: {cvar_95:,.0f} RUB")
```

---

## 7. Historical bootstrap версия

Для акций часто полезно начать именно с bootstrap, потому что он использует реальные совместные движения активов.

```python
import numpy as np


def historical_bootstrap_var_cvar(
    returns: np.ndarray,
    weights: np.ndarray,
    portfolio_value: float,
    confidence_level: float = 0.95,
    n_simulations: int = 100_000,
    random_state: int = 42,
) -> tuple[float, float]:
    rng = np.random.default_rng(random_state)

    n_days = returns.shape[0]

    sampled_indices = rng.integers(
        low=0,
        high=n_days,
        size=n_simulations,
    )

    sampled_returns = returns[sampled_indices]

    portfolio_returns = sampled_returns @ weights

    losses = -portfolio_returns * portfolio_value

    var = np.quantile(losses, confidence_level)

    tail_losses = losses[losses >= var]

    cvar = tail_losses.mean()

    return float(var), float(cvar)
```

---

## 8. Важная деталь: знак убытка

В риск-менеджменте удобно работать с положительными убытками:

```python
losses = -returns * portfolio_value
```

Если доходность портфеля:

```text
-3%
```

и стоимость портфеля:

```text
10 000 000 RUB
```

то:

```text
loss = 300 000 RUB
```

Если доходность:

```text
+2%
```

то:

```text
loss = -200 000 RUB
```

То есть отрицательный loss означает прибыль.

---

## 9. Как интерпретировать CVaR

Если:

```text
VaR95 = 320 000 RUB
CVaR95 = 520 000 RUB
```

То:

```text
5% худших сценариев начинаются примерно после 320 000 RUB убытка.
Средний убыток внутри этих 5% сценариев равен 520 000 RUB.
```

CVaR обычно больше VaR:

\[
CVaR_{\alpha} \ge VaR_{\alpha}
\]

---

## 10. Почему CVaR удобен для оптимизации

CVaR часто используют в портфельной оптимизации, потому что он лучше учитывает хвостовые риски.

Например, можно ставить задачу:

```text
Максимизировать доходность
при ограничении CVaR95 <= 500 000 RUB
```

Или:

```text
Минимизировать CVaR95
при заданной ожидаемой доходности
```

В отличие от VaR, CVaR обычно более удобен математически для оптимизации.

---

## 11. Ошибка Monte Carlo

CVaR часто требует больше сценариев, чем VaR, потому что оценивается только по хвосту.

Например:

```text
N = 100 000 сценариев
CVaR95 использует только худшие 5% = 5 000 сценариев
CVaR99 использует только худший 1% = 1 000 сценариев
```

Поэтому CVaR99 может быть шумным, если сценариев мало.

Классическая сходимость Monte Carlo:

\[
\epsilon \sim O\left(\frac{1}{\sqrt{N}}\right)
\]

Для хвостовых метрик это особенно болезненно.

---

## 12. Практические проверки

Для промышленного расчета нужно проверять:

1. Backtesting VaR.
2. Стабильность CVaR по окнам.
3. Чувствительность к кризисным периодам.
4. Чувствительность к числу сценариев.
5. Корректность adjusted prices.
6. Наличие выбросов и гэпов.
7. Учет валюты, если есть валютные активы.
8. Учет ликвидности, если портфель большой.

---

## 13. Минимальный план реализации

1. Загрузить цены.
2. Посчитать adjusted returns.
3. Сформировать веса портфеля.
4. Сгенерировать сценарии.
5. Посчитать P&L.
6. Перевести P&L в убытки.
7. Найти VaR-квантиль.
8. Отобрать сценарии `loss >= VaR`.
9. Посчитать среднее.
10. Получить CVaR.

---

## 14. Краткий вывод

Monte Carlo CVaR — это естественное расширение Monte Carlo VaR. Если VaR показывает границу худших сценариев, то CVaR показывает средний ущерб за этой границей.

Для риск-анализа портфеля российских акций CVaR обычно полезнее VaR, потому что российский рынок может иметь резкие гэпы, кризисные периоды и тяжелые хвосты.

