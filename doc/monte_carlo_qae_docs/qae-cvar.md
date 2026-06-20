# QAE CVaR

## 1. Что решает метод

QAE CVaR использует Quantum Amplitude Estimation для оценки среднего убытка в хвосте распределения.

CVaR:

\[
CVaR_{\alpha} = E[L \mid L \ge VaR_{\alpha}]
\]

Для VaR95 хвост — это худшие 5% сценариев.

QAE CVaR обычно делается в два этапа:

```text
1. Найти или задать VaR threshold.
2. Оценить средний убыток в сценариях, где loss >= VaR.
```

---

## 2. Почему CVaR сложнее, чем VaR

Для VaR нужно оценивать вероятность события:

```text
P(loss > X)
```

Это естественно ложится на QAE.

Для CVaR нужно оценить условное математическое ожидание:

```text
E[loss | loss > VaR]
```

Это можно переписать как отношение:

\[
CVaR_{\alpha} =
\frac{E[L \cdot I(L \ge VaR_{\alpha})]}{P(L \ge VaR_{\alpha})}
\]

где:

- \(I(\cdot)\) — индикатор события;
- числитель — ожидаемый убыток только в хвосте;
- знаменатель — вероятность хвоста.

Для уровня \(\alpha = 0.95\):

\[
P(L \ge VaR_{0.95}) \approx 0.05
\]

---

## 3. Что именно оценивает QAE

QAE умеет оценивать амплитуду, то есть вероятность `good state`.

Чтобы оценить CVaR, нужно закодировать не только факт попадания в хвост, но и величину убытка.

Есть два практических подхода.

---

## 4. Подход A: дискретный tail average

Если распределение убытков уже дискретизировано:

| Bucket | Loss | Probability |
|---:|---:|---:|
| 0 | -100 000 | 0.10 |
| 1 | 0 | 0.20 |
| 2 | 100 000 | 0.30 |
| 3 | 300 000 | 0.25 |
| 4 | 600 000 | 0.10 |
| 5 | 1 000 000 | 0.05 |

и VaR95 примерно:

```text
600 000 RUB
```

то CVaR95:

\[
\frac{600000 \cdot 0.10 + 1000000 \cdot 0.05}{0.10 + 0.05}
\]

Этот расчет можно сделать классически после того, как QAE оценил:

```text
P(loss >= VaR)
```

Но это не полноценный QAE CVaR, потому что числитель считается классически.

---

## 5. Подход B: QAE для tail expectation

Более квантовая схема:

1. Подготовить распределение сценариев:

\[
\sum_i \sqrt{p_i}|i\rangle
\]

2. Для каждого сценария вычислить масштабированный tail loss:

\[
g(i) =
\begin{cases}
\frac{L_i}{L_{max}}, & L_i \ge VaR \\
0, & L_i < VaR
\end{cases}
\]

3. Через controlled rotation закодировать \(g(i)\) в амплитуду дополнительного qubit:

\[
|i\rangle|0\rangle
\rightarrow
|i\rangle
\left(
\sqrt{1-g(i)}|0\rangle +
\sqrt{g(i)}|1\rangle
\right)
\]

4. QAE оценивает:

\[
a = E[g(i)]
\]

5. Возвращаем масштаб:

\[
E[L \cdot I(L \ge VaR)] = a \cdot L_{max}
\]

6. Делим на вероятность хвоста:

\[
CVaR = \frac{E[L \cdot I(L \ge VaR)]}{P(L \ge VaR)}
\]

---

## 6. Практичная архитектура для российских акций

Для 100 российских акций на CPU-симуляторе лучше делать так:

```text
100 stocks
↓
classical portfolio loss distribution
↓
discretize into 32/64/128 buckets
↓
QAE #1: estimate P(loss >= VaR)
↓
QAE #2: estimate E[loss * I(loss >= VaR)]
↓
CVaR = numerator / denominator
```

Не стоит пытаться кодировать все 100 акций напрямую в квантовую схему.

---

## 7. Упрощенный Qiskit/NumPy skeleton

Полноценная реализация QAE CVaR требует controlled rotations для функции убытка. Ниже skeleton показывает архитектуру: где классическая часть, где QAE для вероятности хвоста, где QAE для ожидания.

Установка:

```bash
pip install qiskit qiskit-aer qiskit-algorithms numpy
```

```python
import numpy as np


def classical_loss_distribution(
    returns: np.ndarray,
    weights: np.ndarray,
    portfolio_value: float,
    n_buckets: int = 64,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Возвращает:
    - probabilities: вероятность каждого bucket;
    - losses_by_bucket: representative loss для каждого bucket.
    """

    portfolio_returns = returns @ weights
    portfolio_losses = -portfolio_returns * portfolio_value

    hist, bin_edges = np.histogram(
        portfolio_losses,
        bins=n_buckets,
        density=False,
    )

    probabilities = hist / hist.sum()
    losses_by_bucket = (bin_edges[:-1] + bin_edges[1:]) / 2

    return probabilities, losses_by_bucket


def classical_var_from_distribution(
    probabilities: np.ndarray,
    losses_by_bucket: np.ndarray,
    confidence_level: float,
) -> float:
    order = np.argsort(losses_by_bucket)
    sorted_losses = losses_by_bucket[order]
    sorted_probabilities = probabilities[order]

    cdf = np.cumsum(sorted_probabilities)

    index = np.searchsorted(cdf, confidence_level)

    return float(sorted_losses[index])


def classical_cvar_from_distribution(
    probabilities: np.ndarray,
    losses_by_bucket: np.ndarray,
    var_threshold: float,
) -> float:
    mask = losses_by_bucket >= var_threshold

    tail_probability = probabilities[mask].sum()

    if tail_probability == 0:
        raise ValueError("Tail probability is zero.")

    tail_expectation = np.sum(
        probabilities[mask] * losses_by_bucket[mask]
    )

    return float(tail_expectation / tail_probability)


def qae_tail_probability_placeholder(
    probabilities: np.ndarray,
    losses_by_bucket: np.ndarray,
    var_threshold: float,
) -> float:
    """
    Здесь должна быть QAE-оценка:

        P(loss >= var_threshold)

    Реализация почти такая же, как в документе qae-var.md:
    - StatePreparation(sqrt(probabilities))
    - threshold oracle
    - IterativeAmplitudeEstimation

    Для skeleton возвращаем классическое значение.
    """

    return float(probabilities[losses_by_bucket >= var_threshold].sum())


def qae_tail_expectation_placeholder(
    probabilities: np.ndarray,
    losses_by_bucket: np.ndarray,
    var_threshold: float,
) -> float:
    """
    Здесь должна быть QAE-оценка:

        E[loss * I(loss >= var_threshold)]

    Для полноценной квантовой реализации нужно:
    - подготовить |i> с вероятностями p_i;
    - добавить ancilla qubit;
    - сделать controlled rotation по величине scaled_tail_loss_i;
    - через QAE оценить вероятность ancilla=1;
    - домножить результат на L_max.

    Для skeleton возвращаем классическое значение.
    """

    mask = losses_by_bucket >= var_threshold

    return float(np.sum(probabilities[mask] * losses_by_bucket[mask]))


if __name__ == "__main__":
    rng = np.random.default_rng(42)

    n_stocks = 100
    n_days = 1500
    portfolio_value = 10_000_000

    returns = rng.normal(
        loc=0.0003,
        scale=0.025,
        size=(n_days, n_stocks),
    )

    weights = np.ones(n_stocks) / n_stocks

    probabilities, losses_by_bucket = classical_loss_distribution(
        returns=returns,
        weights=weights,
        portfolio_value=portfolio_value,
        n_buckets=64,
    )

    var_95 = classical_var_from_distribution(
        probabilities=probabilities,
        losses_by_bucket=losses_by_bucket,
        confidence_level=0.95,
    )

    tail_probability = qae_tail_probability_placeholder(
        probabilities=probabilities,
        losses_by_bucket=losses_by_bucket,
        var_threshold=var_95,
    )

    tail_expectation = qae_tail_expectation_placeholder(
        probabilities=probabilities,
        losses_by_bucket=losses_by_bucket,
        var_threshold=var_95,
    )

    cvar_95 = tail_expectation / tail_probability

    classical_cvar_95 = classical_cvar_from_distribution(
        probabilities=probabilities,
        losses_by_bucket=losses_by_bucket,
        var_threshold=var_95,
    )

    print(f"VaR95:                {var_95:,.0f} RUB")
    print(f"QAE-style CVaR95:     {cvar_95:,.0f} RUB")
    print(f"Classical CVaR95:     {classical_cvar_95:,.0f} RUB")
```

---

## 8. Как реализовать controlled rotation

Для каждого bucket \(i\) нужно иметь значение:

\[
g_i = \frac{L_i \cdot I(L_i \ge VaR)}{L_{max}}
\]

где:

\[
0 \le g_i \le 1
\]

Затем нужно сделать поворот ancilla:

\[
R_y(\theta_i)
\]

такой, чтобы:

\[
\sin^2(\theta_i / 2) = g_i
\]

Отсюда:

\[
\theta_i = 2 \arcsin(\sqrt{g_i})
\]

В учебной реализации можно пройти по всем bucket и для каждого состояния сделать controlled rotation.

Идея:

```python
theta_i = 2 * np.arcsin(np.sqrt(g_i))
controlled_ry(theta_i, condition_state=i)
```

Это неэффективно для больших схем, но нормально для:

```text
5-7 qubits
32-128 buckets
CPU simulator
```

---

## 9. Почему QAE CVaR тяжелее QAE VaR

QAE VaR требует только oracle:

```text
loss > X?
```

QAE CVaR требует:

```text
loss > VaR?
если да, насколько большой loss?
```

То есть нужно кодировать функцию убытка в амплитуду.

Это делает схему:

- глубже;
- сложнее;
- чувствительнее к ошибкам;
- сложнее для объяснения;
- тяжелее для симулятора.

---

## 10. Что можно исследовать

Хорошая исследовательская постановка:

```text
Monte Carlo CVaR
vs
QAE-style CVaR
```

Сравнивать:

1. Точность CVaR.
2. Число сценариев / shots.
3. Число bucket.
4. Ошибку из-за дискретизации.
5. Ошибку VaR threshold.
6. Ошибку tail probability.
7. Ошибку tail expectation.
8. Общее накопление ошибки.

---

## 11. Важная проблема ошибки VaR

CVaR зависит от VaR.

Если VaR оценен с ошибкой, то хвост выбран неправильно.

Пример:

```text
Истинный VaR95 = 300 000
Оцененный VaR95 = 330 000
```

Тогда часть сценариев между 300 000 и 330 000 будет ошибочно исключена из хвоста.

Поэтому QAE CVaR фактически имеет две ошибки:

```text
ошибка VaR
+
ошибка оценки tail expectation
```

---

## 12. Минимальный план реализации

1. Получить доходности портфеля.
2. Построить распределение убытков.
3. Дискретизировать убытки в \(2^n\) bucket.
4. Найти VaR threshold:
   - классически;
   - или через QAE VaR.
5. Оценить tail probability:

\[
P(L \ge VaR)
\]

6. Оценить tail expectation:

\[
E[L \cdot I(L \ge VaR)]
\]

7. Посчитать:

\[
CVaR = \frac{tail\ expectation}{tail\ probability}
\]

8. Сравнить с классическим Monte Carlo CVaR.

---

## 13. Что писать честно в выводах

Корректный вывод для CPU-симулятора:

```text
QAE CVaR демонстрирует теоретическую возможность квадратичного ускорения
для оценки хвостового ожидания, но практическая эффективность зависит от
стоимости state preparation и сложности кодирования функции убытка.
```

Некорректный вывод:

```text
QAE CVaR уже быстрее классического Monte Carlo на ноутбуке.
```

На обычном CPU-симуляторе это почти наверняка будет неверно.

---

## 14. Полезные источники

- Qiskit Algorithms: `IterativeAmplitudeEstimation`.
- Qiskit Finance tutorial: Credit Risk Analysis.
- Woerner, Egger: Quantum Risk Analysis.
- Grinko et al.: Iterative Quantum Amplitude Estimation.
- Исследования по quantum subgradient / CVaR optimization через amplitude estimation.

---

## 15. Краткий вывод

QAE CVaR — более сложная, но более содержательная задача, чем QAE VaR. Для VaR достаточно оценивать вероятность превышения порога. Для CVaR нужно оценивать условное математическое ожидание убытка в хвосте.

Практически на CPU лучше начинать с агрегированного распределения убытков портфеля, дискретизировать его в 32–128 bucket и затем реализовывать два QAE-блока:

```text
tail probability
tail expectation
```

После этого:

\[
CVaR = \frac{tail\ expectation}{tail\ probability}
\]

