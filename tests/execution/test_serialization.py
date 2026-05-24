from dataclasses import dataclass
from datetime import UTC, datetime

from google.protobuf import descriptor_pb2
from t_tech.invest import AccountStatus, Order, OrderBook, Quotation

from its.execution.serialization import serialize_sdk_value
from its.execution.service import is_missing_sdk_value, normalize_order_book


@dataclass
class SDKLikePayload:
    values: object


def test_serialize_repeated_scalar_container() -> None:
    proto = descriptor_pb2.FileDescriptorProto()
    proto.dependency.append("first")
    proto.dependency.append("second")

    assert serialize_sdk_value(SDKLikePayload(values=proto.dependency)) == {
        "values": ["first", "second"]
    }


def test_serialize_t_invest_int_enum_as_name() -> None:
    assert serialize_sdk_value(AccountStatus.ACCOUNT_STATUS_OPEN) == "ACCOUNT_STATUS_OPEN"


def test_empty_stream_payload_is_treated_as_missing() -> None:
    assert is_missing_sdk_value(None) is True


def test_normalize_order_book_to_plain_json_numbers() -> None:
    order_book = OrderBook(
        figi="figi-1",
        depth=2,
        is_consistent=True,
        bids=[
            Order(price=Quotation(units=99, nano=500000000), quantity=10),
            Order(price=Quotation(units=100, nano=0), quantity=5),
        ],
        asks=[
            Order(price=Quotation(units=101, nano=0), quantity=7),
            Order(price=Quotation(units=100, nano=500000000), quantity=9),
        ],
        time=datetime(2026, 5, 23, tzinfo=UTC),
        limit_up=Quotation(units=110, nano=0),
        limit_down=Quotation(units=90, nano=0),
        instrument_uid="uid-1",
    )

    payload = normalize_order_book(order_book, requested_instrument_id="uid-1")

    assert payload["type"] == "orderbook"
    assert payload["bids"] == [
        {"price": 100.0, "quantity": 5},
        {"price": 99.5, "quantity": 10},
    ]
    assert payload["asks"] == [
        {"price": 100.5, "quantity": 9},
        {"price": 101.0, "quantity": 7},
    ]
    assert payload["limit_up"] == 110.0
    assert payload["limit_down"] == 90.0
