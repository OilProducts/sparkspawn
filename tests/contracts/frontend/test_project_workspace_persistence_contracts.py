from tests.contracts.frontend.frontend_behavior_runner import assert_frontend_behavior_contract_passed


def test_project_registry_persists_across_sessions_with_unique_directory_enforcement_item_11_5_01() -> None:
    assert_frontend_behavior_contract_passed("11.5.01")


def test_project_scoped_conversation_spec_plan_linkage_persists_by_project_item_11_5_02() -> None:
    assert_frontend_behavior_contract_passed("11.5.02")
