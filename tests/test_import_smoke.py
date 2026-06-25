def test_backend_main_imports_without_starting_network_services():
    import backend.main as main

    assert main.app.title == "Guarded AI Agent"


def test_policy_module_imports_without_opening_mongo_connection():
    import backend.policy as policy

    assert hasattr(policy.PolicyEngine, "evaluate_tool")
