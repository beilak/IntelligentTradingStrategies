# QAE VaR

## 1. Что решает метод

QAE VaR использует Quantum Amplitude Estimation для оценки вероятности хвостового события:

```text
P(loss > X)
```

После этого VaR находится через поиск такого порога \(X\), при котором:

\[
P(L > X) \approx 1 - \alpha
\]

Например, для VaR95:

\[
P(L > VaR_{0.95}) \approx 0.05
\]

Важно:

```text
QAE не выдает VaR напрямую.
QAE оценивает вероятность превышения заданного порога.
VaR находится через серию таких оценок.
```

---

## 2. Зачем здесь квантовый алгоритм

Классический Monte Carlo оценивает вероятность события с ошибкой:

\[
\epsilon \sim O\left(\frac{1}{\sqrt{N}}\right)
\]

Quantum Amplitude Estimation теоретически дает:

\[
\epsilon \sim O\left(\frac{1}{N}\right)
\]

То есть QAE дает квадратичное ускорение по числу обращений к модели.

Это не означает, что на ноутбуке Qiskit-симулятор будет быстрее классического NumPy. На CPU-симуляторе квантовая схема обычно медленнее.

Смысл исследования на симуляторе:

```text
Показать алгоритмическую схему.
Сравнить точность.
Оценить число запросов.
Понять ограничения state preparation.
```

---

## 3. Как VaR превращается в QAE-задачу

Допустим, есть распределение убытков:

| Сценарий | Убыток |
|---:|---:|
| 0 | -100 000 |
| 1 | 0 |
| 2 | 100 000 |
| 3 | 200 000 |
| 4 | 300 000 |
| 5 | 400 000 |
| 6 | 700 000 |
| 7 | 1 000 000 |

Для порога:

```text
X = 300 000 RUB
```

интересующее событие:

```text
loss > 300 000
```

Плохие сценарии:

```text
400 000
700 000
1 000 000
```

В QAE они называются `good states`, потому что это состояния, вероятность которых мы хотим оценить.

---

## 4. Квантовая формулировка

Нужен оператор подготовки состояния \(A\):

\[
A|0\rangle = \sum_i \sqrt{p_i}|i\rangle
\]

где:

- \(i\) — номер сценария или loss bucket;
- \(p_i\) — вероятность сценария.

Oracle помечает состояния, где:

\[
L_i > X
\]

QAE оценивает амплитуду:

\[
a = \sum_{i: L_i > X} p_i
\]

То есть:

\[
a = P(L > X)
\]

---

## 5. Практичная архитектура для 100 российских акций

Нереалистичный путь:

```text
100 акций
↓
кодировать каждую акцию отдельным квантовым регистром
↓
строить корреляции внутри квантовой схемы
```

На CPU-симуляторе это почти сразу становится непрактичным.

Практичный путь:

```text
100 акций
↓
классическая модель доходности портфеля
↓
агрегированное распределение убытков портфеля
↓
дискретизация в 32/64/128 bucket
↓
QAE оценивает P(loss > X)
```

То есть квантовая часть не знает про SBER, LKOH, YDEX и другие тикеры. Она получает уже готовое одномерное распределение потерь портфеля.

---

## 6. Qiskit CPU пример

Установка:

```bash
pip install qiskit qiskit-aer qiskit-algorithms numpy
```

Пример ниже:

- генерирует синтетические доходности 100 акций;
- строит портфельное распределение убытков;
- дискретизирует его в 64 bucket;
- кодирует распределение в квантовое состояние;
- оценивает \(P(loss > X)\) через Iterative Amplitude Estimation.

```python
import numpy as np

from qiskit import QuantumCircuit
from qiskit.circuit.library import StatePreparation, GroverOperator
from qiskit_aer.primitives import Sampler
from qiskit_algorithms import IterativeAmplitudeEstimation, EstimationProblem


def build_threshold_oracle(
    n_qubits: int,
    good_states: set[int],
) -> QuantumCircuit:
    """
    Oracle помечает фазой -1 состояния из good_states.

    Для учебного примера строим multi-controlled phase flip
    отдельно для каждого good state.
    """

    oracle = QuantumCircuit(n_qubits)

    for state in good_states:
        bitstring = format(state, f"0{n_qubits}b")[::-1]

        zero_qubits = []

        for q, bit in enumerate(bitstring):
            if bit == "0":
                oracle.x(q)
                zero_qubits.append(q)

        oracle.h(n_qubits - 1)
        oracle.mcx(list(range(n_qubits - 1)), n_qubits - 1)
        oracle.h(n_qubits - 1)

        for q in zero_qubits:
            oracle.x(q)

    return oracle


def qae_probability_loss_exceeds_threshold(
    probabilities: np.ndarray,
    losses_by_bucket: np.ndarray,
    threshold: float,
    epsilon_target: float = 0.01,
    alpha: float = 0.05,
    shots: int = 2000,
) -> float:
    n_buckets = len(probabilities)
    n_qubits = int(np.log2(n_buckets))

    if 2**n_qubits != n_buckets:
        raise ValueError("Number of buckets must be power of two.")

    amplitudes = np.sqrt(probabilities)
    amplitudes = amplitudes / np.linalg.norm(amplitudes)

    good_states = {
        i for i, loss in enumerate(losses_by_bucket)
        if loss > threshold
    }

    state_preparation = QuantumCircuit(n_qubits)
    state_preparation.append(StatePreparation(amplitudes), range(n_qubits))

    oracle = build_threshold_oracle(
        n_qubits=n_qubits,
        good_states=good_states,
    )

    grover_operator = GroverOperator(
        oracle=oracle,
        state_preparation=state_preparation,
    )

    def is_good_state(bitstring: str) -> bool:
        # Qiskit returns bitstrings in classical display order.
        return int(bitstring, 2) in good_states

    problem = EstimationProblem(
        state_preparation=state_preparation,
        grover_operator=grover_operator,
        objective_qubits=list(range(n_qubits)),
        is_good_state=is_good_state,
    )

    sampler = Sampler(run_options={"shots": shots})

    iae = IterativeAmplitudeEstimation(
        epsilon_target=epsilon_target,
        alpha=alpha,
        sampler=sampler,
    )

    result = iae.estimate(problem)

    return float(result.estimation)


if __name__ == "__main__":
    rng = np.random.default_rng(42)

    n_stocks = 100
    n_days = 1500
    portfolio_value = 10_000_000

    # Синтетика. В реальном проекте заменить на MOEX adjusted returns.
    returns = rng.normal(
        loc=0.0003,
        scale=0.025,
        size=(n_days, n_stocks),
    )

    weights = np.ones(n_stocks) / n_stocks

    portfolio_returns = returns @ weights
    portfolio_losses = -portfolio_returns * portfolio_value

    n_qubits = 6
    n_buckets = 2**n_qubits

    hist, bin_edges = np.histogram(
        portfolio_losses,
        bins=n_buckets,
        density=False,
    )

    probabilities = hist / hist.sum()
    losses_by_bucket = (bin_edges[:-1] + bin_edges[1:]) / 2

    threshold = 300_000

    classical_probability = probabilities[
        losses_by_bucket > threshold
    ].sum()

    qae_probability = qae_probability_loss_exceeds_threshold(
        probabilities=probabilities,
        losses_by_bucket=losses_by_bucket,
        threshold=threshold,
        epsilon_target=0.01,
        alpha=0.05,
        shots=2000,
    )

    print(f"Classical P(loss > {threshold:,.0f}): {classical_probability:.4f}")
    print(f"QAE P(loss > {threshold:,.0f}):       {qae_probability:.4f}")
```

---

## 7. Как получить VaR через бинарный поиск

QAE дает функцию:

```python
qae_probability_loss_exceeds_threshold(X)
```

Нужно найти такой \(X\), что:

```text
P(loss > X) ≈ 1 - confidence_level
```

Для VaR95:

```text
target_probability = 0.05
```

Псевдокод:

```python
def qae_var_binary_search(
    min_loss: float,
    max_loss: float,
    confidence_level: float,
    n_iterations: int = 12,
) -> float:
    target_tail_probability = 1.0 - confidence_level

    left = min_loss
    right = max_loss

    for _ in range(n_iterations):
        middle = (left + right) / 2

        p_tail = qae_probability_loss_exceeds_threshold(middle)

        if p_tail > target_tail_probability:
            # Порог слишком низкий:
            # слишком много сценариев превышают его.
            left = middle
        else:
            # Порог слишком высокий:
            # слишком мало сценариев превышают его.
            right = middle

    return (left + right) / 2
```

---

## 8. Ограничения на CPU-симуляторе

Главное ограничение:

```text
Количество qubits растет как log2(number_of_buckets).
Но симуляция statevector растет как 2^n.
```

Пример:

| Bucket | Qubits |
|---:|---:|
| 32 | 5 |
| 64 | 6 |
| 128 | 7 |
| 256 | 8 |
| 1024 | 10 |

Для одномерного loss distribution это нормально.

Но если попытаться кодировать 100 акций напрямую, размерность взорвется.

Поэтому для CPU-симулятора лучше:

```text
100 stocks → classical loss distribution → 64 buckets → QAE
```

---

## 9. Главная проблема QAE в финансах

Главная проблема — не сама amplitude estimation.

Главная проблема:

```text
State preparation
```

Нужно подготовить квантовое состояние:

\[
\sum_i \sqrt{p_i}|i\rangle
\]

Для учебного распределения это легко.

Для реальной многомерной финансовой модели это может быть сложнее, чем сама классическая оценка риска.

Поэтому честная исследовательская постановка должна явно сказать:

```text
Мы используем классическую модель для получения агрегированного loss distribution,
а QAE применяем к дискретизированному распределению убытков.
```

---

## 10. Что сравнивать с Monte Carlo

Для исследования можно сравнить:

1. Classical Monte Carlo VaR.
2. Historical VaR.
3. Bootstrap VaR.
4. QAE VaR на дискретизированном распределении.
5. Ошибку оценки \(P(loss > X)\).
6. Чувствительность к числу bucket.
7. Чувствительность к `epsilon_target`.
8. Чувствительность к `shots`.

---

## 11. Минимальный план реализации

1. Получить доходности российских акций.
2. Задать веса портфеля.
3. Построить сценарии портфельного P&L.
4. Перевести P&L в loss.
5. Дискретизировать loss в \(2^n\) bucket.
6. Подготовить вектор вероятностей.
7. Создать `StatePreparation`.
8. Создать threshold oracle.
9. Запустить `IterativeAmplitudeEstimation`.
10. Получить \(P(loss > X)\).
11. Через бинарный поиск найти VaR.

---

## 12. Полезные источники

- Qiskit Algorithms: `IterativeAmplitudeEstimation`.
- Qiskit Finance tutorial: Quantum Amplitude Estimation.
- Qiskit Finance tutorial: Credit Risk Analysis.
- Woerner, Egger: Quantum Risk Analysis.
- Grinko et al.: Iterative Quantum Amplitude Estimation.

---

## 13. Краткий вывод

QAE VaR — это не магический способ сразу получить VaR. Это способ быстрее оценивать вероятность:

```text
P(loss > X)
```

VaR получается через поиск порога \(X\). На CPU-симуляторе QAE не будет быстрее NumPy, но как исследовательская и архитектурная схема он хорошо показывает, как gate-based quantum algorithms могут применяться к реальной задаче риск-менеджмента.

