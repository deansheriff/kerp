import inspect


def test_ap_payment_web_service_has_workflow_methods():
    """
    Regression test: AP payment routes call these methods on the modular web service.
    Missing them results in runtime 500s on approve/post/void actions.
    """
    from app.services.finance.ap.web import ap_web_service

    for name in [
        "approve_payment_response",
        "post_payment_response",
        "void_payment_response",
    ]:
        assert hasattr(ap_web_service, name), name

    sig = inspect.signature(ap_web_service.approve_payment_response)
    assert "payment_id" in sig.parameters
