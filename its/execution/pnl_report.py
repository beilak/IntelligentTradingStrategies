from __future__ import annotations

import math
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

BUY_TYPES = {
    "OPERATION_TYPE_BUY",
    "OPERATION_TYPE_BUY_CARD",
    "OPERATION_TYPE_BUY_MARGIN",
    "OPERATION_TYPE_DELIVERY_BUY",
}
SELL_TYPES = {
    "OPERATION_TYPE_SELL",
    "OPERATION_TYPE_SELL_CARD",
    "OPERATION_TYPE_SELL_MARGIN",
    "OPERATION_TYPE_DELIVERY_SELL",
}
EXTERNAL_CASH_TYPES = {
    "OPERATION_TYPE_INPUT",
    "OPERATION_TYPE_OUTPUT",
    "OPERATION_TYPE_OUTPUT_SWIFT",
    "OPERATION_TYPE_INPUT_SWIFT",
    "OPERATION_TYPE_OUTPUT_ACQUIRING",
    "OPERATION_TYPE_INPUT_ACQUIRING",
    "OPERATION_TYPE_OUT_MULTI",
    "OPERATION_TYPE_INP_MULTI",
}
SECURITY_INPUT_TYPES = {
    "OPERATION_TYPE_INPUT_SECURITIES",
    "OPERATION_TYPE_TRANS_IIS_BS",
    "OPERATION_TYPE_TRANS_BS_BS",
}
SECURITY_OUTPUT_TYPES = {"OPERATION_TYPE_OUTPUT_SECURITIES"}
DIVIDEND_TYPES = {
    "OPERATION_TYPE_DIVIDEND",
    "OPERATION_TYPE_DIVIDEND_TRANSFER",
    "OPERATION_TYPE_DIV_EXT",
}
COUPON_TYPES = {"OPERATION_TYPE_COUPON"}
FEE_TYPES = {
    "OPERATION_TYPE_SERVICE_FEE",
    "OPERATION_TYPE_MARGIN_FEE",
    "OPERATION_TYPE_BROKER_FEE",
    "OPERATION_TYPE_SUCCESS_FEE",
    "OPERATION_TYPE_TRACK_MFEE",
    "OPERATION_TYPE_TRACK_PFEE",
    "OPERATION_TYPE_CASH_FEE",
    "OPERATION_TYPE_OUT_FEE",
    "OPERATION_TYPE_OUT_STAMP_DUTY",
    "OPERATION_TYPE_OUTPUT_PENALTY",
    "OPERATION_TYPE_ADVICE_FEE",
    "OPERATION_TYPE_OVER_COM",
    "OPERATION_TYPE_OTHER_FEE",
}
TAX_TYPES = {
    "OPERATION_TYPE_BOND_TAX",
    "OPERATION_TYPE_TAX",
    "OPERATION_TYPE_DIVIDEND_TAX",
    "OPERATION_TYPE_TAX_CORRECTION",
    "OPERATION_TYPE_BENEFIT_TAX",
    "OPERATION_TYPE_TAX_PROGRESSIVE",
    "OPERATION_TYPE_BOND_TAX_PROGRESSIVE",
    "OPERATION_TYPE_DIVIDEND_TAX_PROGRESSIVE",
    "OPERATION_TYPE_BENEFIT_TAX_PROGRESSIVE",
    "OPERATION_TYPE_TAX_CORRECTION_PROGRESSIVE",
    "OPERATION_TYPE_TAX_REPO_PROGRESSIVE",
    "OPERATION_TYPE_TAX_REPO",
    "OPERATION_TYPE_TAX_REPO_HOLD",
    "OPERATION_TYPE_TAX_REPO_REFUND",
    "OPERATION_TYPE_TAX_REPO_HOLD_PROGRESSIVE",
    "OPERATION_TYPE_TAX_REPO_REFUND_PROGRESSIVE",
    "OPERATION_TYPE_TAX_CORRECTION_COUPON",
}
VARIATION_MARGIN_TYPES = {
    "OPERATION_TYPE_ACCRUING_VARMARGIN",
    "OPERATION_TYPE_WRITING_OFF_VARMARGIN",
}
OTHER_INCOME_TYPES = {
    "OPERATION_TYPE_OVERNIGHT",
    "OPERATION_TYPE_OVER_INCOME",
}


@dataclass
class InstrumentState:
    key: str
    figi: str | None = None
    ticker: str | None = None
    name: str | None = None
    currency: str = "rub"
    quantity: float = 0.0
    lots: deque[tuple[float, float]] = field(default_factory=deque)


def build_pnl_report(
    *,
    account_id: str,
    account_name: str,
    from_date: date,
    to_date: date,
    operations: list[dict[str, Any]],
    prices: list[dict[str, Any]],
    strategy_name: str | None = None,
    assigned_strategies: list[str] | None = None,
    current_portfolio_value: float | None = None,
    report_currency: str = "rub",
) -> dict[str, Any]:
    """Build a cash-flow-aware mark-to-market report from broker data.

    Operations are replayed from account inception. Daily prices are only required
    around and inside the requested report period.
    """

    currency = report_currency.lower()
    normalized_operations = sorted(
        (row for row in operations if operation_date(row) is not None),
        key=lambda row: (operation_date(row) or date.min, str(row.get("id") or "")),
    )
    price_history, price_names = normalize_prices(prices)
    operations_by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for operation in normalized_operations:
        current_date = operation_date(operation)
        if current_date is not None:
            operations_by_day[current_date].append(operation)

    timeline = sorted(
        {from_date, to_date}
        | {
            current_date
            for current_date in operations_by_day
            if from_date <= current_date <= to_date
        }
        | {
            current_date
            for history in price_history.values()
            for current_date in history
            if from_date <= current_date <= to_date
        }
    )

    states: dict[str, InstrumentState] = {}
    cash = 0.0
    latest_prices: dict[str, float] = {}
    foreign_currencies: set[str] = set()
    missing_instrument_operations = 0

    for key, history in price_history.items():
        prior = [item for item in history.items() if item[0] < from_date]
        if prior:
            latest_prices[key] = prior[-1][1]

    for operation in normalized_operations:
        current_date = operation_date(operation)
        if current_date is None or current_date >= from_date:
            break
        cash_delta, missing = apply_operation(
            operation,
            states,
            report_currency=currency,
            latest_prices=latest_prices,
        )
        cash += cash_delta
        missing_instrument_operations += missing
        update_price_from_operation(operation, latest_prices, currency)

    # A trade price is a useful fallback, but a later official daily close must win
    # when both are available for the opening valuation.
    for key, history in price_history.items():
        prior = [item for item in history.items() if item[0] < from_date]
        if prior:
            latest_prices[key] = prior[-1][1]

    opening_quantities = {key: state.quantity for key, state in states.items()}
    opening_values = market_values(states, latest_prices, currency)
    opening_nav = cash + sum(opening_values.values())
    previous_nav = opening_nav
    growth_index = 1.0
    growth_high_water = 1.0
    equity_curve: list[dict[str, Any]] = []
    period_returns: list[float] = []
    period_pnl: list[float] = []
    external_flows: list[tuple[date, float]] = []

    period_components = {
        "dividends": 0.0,
        "coupons": 0.0,
        "fees": 0.0,
        "taxes": 0.0,
        "variation_margin": 0.0,
        "other_income": 0.0,
    }
    trade_turnover = 0.0
    trades_count = 0
    buy_count = 0
    sell_count = 0
    realized_pnl = 0.0
    instrument_period_cash: dict[str, float] = defaultdict(float)
    instrument_period_external: dict[str, float] = defaultdict(float)
    instrument_period_turnover: dict[str, float] = defaultdict(float)
    instrument_period_realized: dict[str, float] = defaultdict(float)
    instrument_trade_counts: dict[str, int] = defaultdict(int)

    for current_date in timeline:
        closing_price_keys: set[str] = set()
        for key, history in price_history.items():
            close = history.get(current_date)
            if close is not None:
                latest_prices[key] = close
                closing_price_keys.add(key)

        day_external_flow = 0.0
        for operation in operations_by_day.get(current_date, []):
            operation_type = normalize_operation_type(operation.get("type"))
            key = instrument_key(operation)
            payment = money_value(operation.get("payment"))
            operation_currency = money_currency(operation.get("payment"), operation)
            if operation_currency and operation_currency != currency:
                foreign_currencies.add(operation_currency)

            cash_delta, missing = apply_operation(
                operation,
                states,
                report_currency=currency,
                latest_prices=latest_prices,
            )
            cash += cash_delta
            missing_instrument_operations += missing
            update_price_from_operation(
                operation,
                latest_prices,
                currency,
                protected_keys=closing_price_keys,
            )

            if operation_currency in {None, currency}:
                if operation_type in EXTERNAL_CASH_TYPES:
                    day_external_flow += payment
                    external_flows.append((current_date, payment))
                elif operation_type in SECURITY_INPUT_TYPES | SECURITY_OUTPUT_TYPES:
                    quantity = operation_quantity(operation)
                    price = latest_prices.get(key or "") or money_value(
                        operation.get("price")
                    )
                    sign = 1.0 if operation_type in SECURITY_INPUT_TYPES else -1.0
                    security_flow = sign * quantity * price
                    day_external_flow += security_flow
                    external_flows.append((current_date, security_flow))
                    if key:
                        instrument_period_external[key] += security_flow

                if operation_type in DIVIDEND_TYPES:
                    period_components["dividends"] += payment
                elif operation_type in COUPON_TYPES:
                    period_components["coupons"] += payment
                elif operation_type in FEE_TYPES:
                    period_components["fees"] += payment
                elif operation_type in TAX_TYPES:
                    period_components["taxes"] += payment
                elif operation_type in VARIATION_MARGIN_TYPES:
                    period_components["variation_margin"] += payment
                elif operation_type in OTHER_INCOME_TYPES:
                    period_components["other_income"] += payment

                if key and operation_type not in EXTERNAL_CASH_TYPES:
                    instrument_period_cash[key] += payment

            if operation_type in BUY_TYPES | SELL_TYPES:
                trades_count += 1
                buy_count += int(operation_type in BUY_TYPES)
                sell_count += int(operation_type in SELL_TYPES)
                turnover = (
                    abs(payment) if operation_currency in {None, currency} else 0.0
                )
                trade_turnover += turnover
                realized = money_value(
                    operation.get("yield_")
                    if operation.get("yield_") is not None
                    else operation.get("yield")
                )
                if operation_type in SELL_TYPES:
                    realized_pnl += realized
                if key:
                    instrument_period_turnover[key] += turnover
                    instrument_period_realized[key] += (
                        realized if operation_type in SELL_TYPES else 0.0
                    )
                    instrument_trade_counts[key] += 1

        current_values = market_values(states, latest_prices, currency)
        nav = cash + sum(current_values.values())
        pnl = nav - previous_nav - day_external_flow
        daily_return = pnl / previous_nav if abs(previous_nav) > 1e-12 else 0.0
        if not math.isfinite(daily_return):
            daily_return = 0.0
        growth_index *= 1.0 + daily_return
        growth_high_water = max(growth_high_water, growth_index)
        drawdown = (
            growth_index / growth_high_water - 1.0 if growth_high_water > 0 else 0.0
        )
        equity_curve.append(
            {
                "date": current_date.isoformat(),
                "nav": nav,
                "daily_pnl": pnl,
                "cumulative_pnl": nav
                - opening_nav
                - sum(
                    flow
                    for flow_date, flow in external_flows
                    if flow_date <= current_date
                ),
                "daily_return": daily_return,
                "cumulative_return": growth_index - 1.0,
                "drawdown": drawdown,
                "external_flow": day_external_flow,
            }
        )
        period_returns.append(daily_return)
        period_pnl.append(pnl)
        previous_nav = nav

    ending_values = market_values(states, latest_prices, currency)
    ending_nav = previous_nav
    net_external_flow = sum(flow for _, flow in external_flows)
    total_pnl = ending_nav - opening_nav - net_external_flow
    twr = growth_index - 1.0
    calendar_days = max((to_date - from_date).days, 1)
    annualized_return = (
        (1.0 + twr) ** (365.0 / calendar_days) - 1.0 if 1.0 + twr > 0 else None
    )
    risk = calculate_risk_metrics(
        returns=period_returns,
        daily_pnl=period_pnl,
        annualized_return=annualized_return,
        equity_curve=equity_curve,
        ending_nav=ending_nav,
    )
    mwr = xirr(
        [(from_date, -opening_nav)]
        + [(flow_date, -flow) for flow_date, flow in external_flows]
        + [(to_date, ending_nav)]
    )

    component_total = sum(period_components.values())
    components = [
        {
            "key": "market_and_trading",
            "label": "Рынок и торговый результат",
            "value": total_pnl - component_total,
        },
        {
            "key": "dividends",
            "label": "Дивиденды",
            "value": period_components["dividends"],
        },
        {
            "key": "coupons",
            "label": "Купоны",
            "value": period_components["coupons"],
        },
        {"key": "fees", "label": "Комиссии", "value": period_components["fees"]},
        {"key": "taxes", "label": "Налоги", "value": period_components["taxes"]},
        {
            "key": "variation_margin",
            "label": "Вариационная маржа",
            "value": period_components["variation_margin"],
        },
        {
            "key": "other_income",
            "label": "Прочие доходы",
            "value": period_components["other_income"],
        },
    ]

    attribution: list[dict[str, Any]] = []
    all_keys = set(opening_quantities) | set(states)
    for key in all_keys:
        state = states.get(key) or InstrumentState(key=key)
        opening_value = opening_values.get(key, 0.0)
        ending_value = ending_values.get(key, 0.0)
        contribution = (
            ending_value
            - opening_value
            + instrument_period_cash.get(key, 0.0)
            - instrument_period_external.get(key, 0.0)
        )
        attribution.append(
            {
                "instrument_id": key,
                "figi": state.figi,
                "ticker": state.ticker or price_names.get(key) or state.figi or key,
                "name": state.name or state.ticker or price_names.get(key) or key,
                "opening_quantity": opening_quantities.get(key, 0.0),
                "ending_quantity": state.quantity,
                "opening_value": opening_value,
                "ending_value": ending_value,
                "pnl_contribution": contribution,
                "contribution_pct": (
                    contribution / total_pnl if abs(total_pnl) > 1e-12 else None
                ),
                "realized_pnl_broker": instrument_period_realized.get(key, 0.0),
                "turnover": instrument_period_turnover.get(key, 0.0),
                "trades": instrument_trade_counts.get(key, 0),
            }
        )
    attribution.sort(key=lambda row: abs(float(row["pnl_contribution"])), reverse=True)

    assigned = assigned_strategies or []
    attribution_mode = "account"
    if strategy_name and len(assigned) == 1 and assigned[0] == strategy_name:
        attribution_mode = "dedicated_account_proxy"
    elif strategy_name:
        attribution_mode = "account_context_only"

    warnings: list[str] = []
    if strategy_name:
        warnings.append(
            "Стратегия указана как контекст. T-Invest не предоставляет надежную "
            "историческую связь каждой операции с заявкой стратегии; показатели "
            "рассчитаны по всему брокерскому счету."
        )
    if len(assigned) > 1:
        warnings.append(
            "К счету назначено несколько стратегий. Их PnL нельзя разделить без "
            "отдельного журнала фактических исполнений."
        )
    if foreign_currencies:
        warnings.append(
            "Операции не в базовой валюте не включены в денежный остаток: "
            + ", ".join(sorted(item.upper() for item in foreign_currencies))
            + "."
        )
    priced_keys = {key for key in all_keys if key in price_history}
    missing_price_keys = sorted(all_keys - priced_keys)
    if missing_price_keys:
        warnings.append(
            f"Нет дневной рыночной цены для {len(missing_price_keys)} инструментов; "
            "использована цена последней операции, а при ее отсутствии — 0."
        )
    if missing_instrument_operations:
        warnings.append(
            f"У {missing_instrument_operations} торговых операций нет пригодного "
            "идентификатора инструмента."
        )
    reconciliation_difference = None
    if current_portfolio_value is not None and to_date >= datetime.now(UTC).date():
        reconciliation_difference = ending_nav - current_portfolio_value
        tolerance = max(abs(current_portfolio_value) * 0.01, 1.0)
        if abs(reconciliation_difference) > tolerance:
            warnings.append(
                "Расчетный NAV отличается от текущей оценки брокера. Возможны "
                "неполная история операций, незавершенные расчеты или отсутствующие цены."
            )

    return {
        "account_id": account_id,
        "account_name": account_name,
        "strategy": {
            "name": strategy_name,
            "attribution_mode": attribution_mode,
            "is_exact": not bool(strategy_name),
            "assigned_strategies": assigned,
        },
        "period": {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "calendar_days": calendar_days + 1,
            "observations": len(equity_curve),
        },
        "currency": currency,
        "summary": {
            "opening_nav": opening_nav,
            "ending_nav": ending_nav,
            "total_pnl": total_pnl,
            "twr": twr,
            "mwr": mwr,
            "annualized_return": annualized_return,
            "realized_pnl_broker": realized_pnl,
            "unrealized_pnl_estimate": unrealized_pnl(states, latest_prices, currency),
            "net_external_flow": net_external_flow,
            "inflows": sum(max(flow, 0.0) for _, flow in external_flows),
            "outflows": abs(sum(min(flow, 0.0) for _, flow in external_flows)),
            "dividends": period_components["dividends"],
            "coupons": period_components["coupons"],
            "fees": period_components["fees"],
            "taxes": period_components["taxes"],
            "turnover": trade_turnover,
            "turnover_ratio": (
                trade_turnover / ((opening_nav + ending_nav) / 2.0)
                if opening_nav + ending_nav > 0
                else None
            ),
            "trades": trades_count,
            "buys": buy_count,
            "sells": sell_count,
        },
        "risk": risk,
        "components": components,
        "equity_curve": equity_curve,
        "monthly_returns": build_monthly_returns(equity_curve),
        "attribution": attribution,
        "data_quality": {
            "method": "transaction_replay_mark_to_market",
            "operations_source": "T-Invest GetOperationsByCursor",
            "prices_source": "T-Invest daily candles via ITS DataHub",
            "operations": len(normalized_operations),
            "priced_instruments": len(priced_keys),
            "total_instruments": len(all_keys),
            "price_coverage": len(priced_keys) / len(all_keys) if all_keys else 1.0,
            "missing_price_instruments": missing_price_keys,
            "reconciliation_difference": reconciliation_difference,
            "warnings": warnings,
        },
    }


def apply_operation(
    operation: dict[str, Any],
    states: dict[str, InstrumentState],
    *,
    report_currency: str,
    latest_prices: dict[str, float],
) -> tuple[float, int]:
    operation_type = normalize_operation_type(operation.get("type"))
    operation_currency = money_currency(operation.get("payment"), operation)
    cash_delta = (
        money_value(operation.get("payment"))
        if operation_currency in {None, report_currency}
        else 0.0
    )
    if (
        operation_type
        not in BUY_TYPES | SELL_TYPES | SECURITY_INPUT_TYPES | SECURITY_OUTPUT_TYPES
    ):
        return cash_delta, 0

    key = instrument_key(operation)
    if not key:
        return cash_delta, int(operation_type in BUY_TYPES | SELL_TYPES)
    state = states.setdefault(
        key,
        InstrumentState(
            key=key,
            figi=optional_text(operation.get("figi")),
            ticker=optional_text(operation.get("ticker")),
            name=optional_text(operation.get("name")),
            currency=money_currency(operation.get("price"), operation)
            or report_currency,
        ),
    )
    state.figi = state.figi or optional_text(operation.get("figi"))
    state.ticker = state.ticker or optional_text(operation.get("ticker"))
    state.name = state.name or optional_text(operation.get("name"))
    quantity = operation_quantity(operation)
    price = money_value(operation.get("price")) or latest_prices.get(key, 0.0)
    if operation_type in BUY_TYPES | SECURITY_INPUT_TYPES:
        state.quantity += quantity
        state.lots.append((quantity, max(price, 0.0)))
    elif operation_type in SELL_TYPES | SECURITY_OUTPUT_TYPES:
        state.quantity -= quantity
        consume_fifo(state.lots, quantity)
    if abs(state.quantity) < 1e-10:
        state.quantity = 0.0
    return cash_delta, 0


def consume_fifo(lots: deque[tuple[float, float]], quantity: float) -> None:
    remaining = quantity
    while remaining > 1e-10 and lots:
        lot_quantity, lot_price = lots[0]
        consumed = min(lot_quantity, remaining)
        lot_quantity -= consumed
        remaining -= consumed
        lots.popleft()
        if lot_quantity > 1e-10:
            lots.appendleft((lot_quantity, lot_price))


def normalize_prices(
    prices: list[dict[str, Any]],
) -> tuple[dict[str, dict[date, float]], dict[str, str]]:
    histories: dict[str, dict[date, float]] = defaultdict(dict)
    names: dict[str, str] = {}
    for row in prices:
        key = optional_text(row.get("figi")) or optional_text(row.get("instrument_id"))
        current_date = parse_date(row.get("time") or row.get("date"))
        close = safe_float(row.get("close"))
        if not key or current_date is None or close is None or close <= 0:
            continue
        histories[key][current_date] = close
        ticker = optional_text(row.get("ticker"))
        if ticker:
            names[key] = ticker
    return {
        key: dict(sorted(history.items())) for key, history in histories.items()
    }, names


def market_values(
    states: dict[str, InstrumentState],
    latest_prices: dict[str, float],
    report_currency: str,
) -> dict[str, float]:
    return {
        key: state.quantity * latest_prices.get(key, 0.0)
        for key, state in states.items()
        if state.currency in {"", report_currency}
    }


def unrealized_pnl(
    states: dict[str, InstrumentState],
    latest_prices: dict[str, float],
    report_currency: str,
) -> float:
    result = 0.0
    for key, state in states.items():
        if state.currency not in {"", report_currency}:
            continue
        market_value = state.quantity * latest_prices.get(key, 0.0)
        cost = sum(quantity * price for quantity, price in state.lots)
        result += market_value - cost
    return result


def update_price_from_operation(
    operation: dict[str, Any],
    latest_prices: dict[str, float],
    report_currency: str,
    *,
    protected_keys: set[str] | None = None,
) -> None:
    key = instrument_key(operation)
    price = money_value(operation.get("price"))
    currency = money_currency(operation.get("price"), operation)
    if (
        key
        and key not in (protected_keys or set())
        and price > 0
        and currency in {None, report_currency}
    ):
        latest_prices[key] = price


def calculate_risk_metrics(
    *,
    returns: list[float],
    daily_pnl: list[float],
    annualized_return: float | None,
    equity_curve: list[dict[str, Any]],
    ending_nav: float,
) -> dict[str, Any]:
    finite_returns = [value for value in returns if math.isfinite(value)]
    mean_return = statistics.fmean(finite_returns) if finite_returns else 0.0
    volatility_daily = (
        statistics.stdev(finite_returns) if len(finite_returns) > 1 else 0.0
    )
    volatility = volatility_daily * math.sqrt(252.0)
    downside = [min(value, 0.0) for value in finite_returns]
    downside_deviation = (
        math.sqrt(statistics.fmean(value * value for value in downside))
        if downside
        else 0.0
    )
    sharpe = (
        mean_return / volatility_daily * math.sqrt(252.0)
        if volatility_daily > 1e-12
        else None
    )
    sortino = (
        mean_return / downside_deviation * math.sqrt(252.0)
        if downside_deviation > 1e-12
        else None
    )
    max_drawdown = min(
        (float(row.get("drawdown") or 0.0) for row in equity_curve), default=0.0
    )
    calmar = (
        annualized_return / abs(max_drawdown)
        if annualized_return is not None and max_drawdown < -1e-12
        else None
    )
    positive = [value for value in daily_pnl if value > 1e-10]
    negative = [value for value in daily_pnl if value < -1e-10]
    active_days = len(positive) + len(negative)
    profit_factor = sum(positive) / abs(sum(negative)) if negative else None
    sorted_returns = sorted(finite_returns)
    var_95_return = (
        sorted_returns[max(int(len(sorted_returns) * 0.05) - 1, 0)]
        if sorted_returns
        else None
    )
    return {
        "annualized_volatility": volatility,
        "sharpe_ratio": sharpe,
        "sortino_ratio": sortino,
        "max_drawdown": max_drawdown,
        "calmar_ratio": calmar,
        "profit_factor": profit_factor,
        "positive_days": len(positive),
        "negative_days": len(negative),
        "win_rate": len(positive) / active_days if active_days else None,
        "best_day_pnl": max(daily_pnl, default=0.0),
        "worst_day_pnl": min(daily_pnl, default=0.0),
        "average_day_pnl": statistics.fmean(daily_pnl) if daily_pnl else 0.0,
        "historical_var_95_return": var_95_return,
        "historical_var_95_amount": (
            var_95_return * ending_nav if var_95_return is not None else None
        ),
    }


def build_monthly_returns(equity_curve: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in equity_curve:
        grouped[str(row["date"])[:7]].append(row)
    result: list[dict[str, Any]] = []
    for month, rows in sorted(grouped.items()):
        compounded = 1.0
        for row in rows:
            compounded *= 1.0 + float(row.get("daily_return") or 0.0)
        result.append(
            {
                "month": month,
                "return": compounded - 1.0,
                "pnl": sum(float(row.get("daily_pnl") or 0.0) for row in rows),
                "ending_nav": float(rows[-1].get("nav") or 0.0),
            }
        )
    return result


def xirr(cashflows: list[tuple[date, float]]) -> float | None:
    combined: dict[date, float] = defaultdict(float)
    for flow_date, amount in cashflows:
        if math.isfinite(amount):
            combined[flow_date] += amount
    flows = sorted(
        (flow_date, amount)
        for flow_date, amount in combined.items()
        if abs(amount) > 1e-10
    )
    if (
        not flows
        or not any(amount < 0 for _, amount in flows)
        or not any(amount > 0 for _, amount in flows)
    ):
        return None
    origin = flows[0][0]

    def npv(rate: float) -> float:
        return sum(
            amount / ((1.0 + rate) ** ((flow_date - origin).days / 365.0))
            for flow_date, amount in flows
        )

    low = -0.9999
    high = 1.0
    low_value = npv(low)
    high_value = npv(high)
    while low_value * high_value > 0 and high < 1_000_000:
        high *= 2.0
        high_value = npv(high)
    if low_value * high_value > 0:
        return None
    for _ in range(160):
        middle = (low + high) / 2.0
        middle_value = npv(middle)
        if abs(middle_value) < 1e-8:
            return middle
        if low_value * middle_value <= 0:
            high = middle
        else:
            low = middle
            low_value = middle_value
    return (low + high) / 2.0


def operation_date(operation: dict[str, Any]) -> date | None:
    return parse_date(operation.get("date"))


def parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = optional_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def instrument_key(operation: dict[str, Any]) -> str | None:
    return (
        optional_text(operation.get("figi"))
        or optional_text(operation.get("instrument_uid"))
        or optional_text(operation.get("position_uid"))
        or optional_text(operation.get("ticker"))
    )


def operation_quantity(operation: dict[str, Any]) -> float:
    for key in ("quantity_done", "quantity"):
        value = safe_float(operation.get(key))
        if value is not None and abs(value) > 1e-12:
            return abs(value)
    return 0.0


def money_value(value: Any) -> float:
    if isinstance(value, dict):
        direct = safe_float(value.get("value"))
        if direct is not None:
            return direct
        units = safe_float(value.get("units")) or 0.0
        nano = safe_float(value.get("nano")) or 0.0
        return units + nano / 1_000_000_000.0
    return safe_float(value) or 0.0


def money_currency(value: Any, operation: dict[str, Any]) -> str | None:
    if isinstance(value, dict):
        currency = optional_text(value.get("currency"))
        if currency:
            return currency.lower()
    currency = optional_text(operation.get("currency"))
    return currency.lower() if currency else None


def normalize_operation_type(value: Any) -> str:
    if hasattr(value, "name"):
        return str(value.name)
    return str(value or "").strip().upper()


def optional_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


__all__ = ["build_pnl_report", "xirr"]
