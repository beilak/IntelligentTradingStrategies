from dataclasses import dataclass

from google.protobuf import descriptor_pb2
from t_tech.invest import AccountStatus

from its.execution.serialization import serialize_sdk_value


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
