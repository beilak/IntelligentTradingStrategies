from its.execution.config import parse_account_configs, parse_order_submission_mode


def test_parse_account_configs_from_list_and_legacy_keys() -> None:
    configs = parse_account_configs(
        {
            "EXECUTION_TINVEST_ACCOUNTS": "111:Main,222:IIS",
            "tinvest_account_id": "333",
            "tinvest_account_id_": "444:Backup",
        }
    )

    assert [(config.account_id, config.name) for config in configs] == [
        ("111", "Main"),
        ("222", "IIS"),
        ("333", None),
        ("444", "Backup"),
    ]


def test_parse_account_configs_from_json() -> None:
    configs = parse_account_configs(
        {
            "EXECUTION_TINVEST_ACCOUNTS": (
                '[{"account_id": "111", "name": "Main"}, "222:Second"]'
            ),
        }
    )

    assert [(config.account_id, config.name) for config in configs] == [
        ("111", "Main"),
        ("222", "Second"),
    ]


def test_parse_order_submission_mode_defaults_to_real() -> None:
    assert parse_order_submission_mode({}) == "real"
    assert parse_order_submission_mode({"EXECUTION_ORDER_SUBMISSION_MODE": "stub"}) == "stub"
    assert parse_order_submission_mode({"EXECUTION_ORDER_SUBMISSION_MODE": "live"}) == "real"
