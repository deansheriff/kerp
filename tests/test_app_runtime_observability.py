import app.main as main_module


def test_bootstrap_runtime_observability_is_idempotent_per_process(
    monkeypatch,
) -> None:
    calls: list[str] = []

    monkeypatch.setattr(
        main_module, "configure_logging", lambda: calls.append("logging")
    )
    monkeypatch.setattr(
        main_module, "setup_monitoring", lambda: calls.append("monitoring")
    )
    monkeypatch.setattr(
        main_module, "setup_otel", lambda app=None: calls.append("otel")
    )
    monkeypatch.setattr(main_module.os, "getpid", lambda: 5151)
    monkeypatch.setattr(main_module, "_runtime_observability_pid", None)

    main_module.bootstrap_runtime_observability(main_module.app)
    main_module.bootstrap_runtime_observability(main_module.app)

    assert calls == ["logging", "monitoring", "otel"]
    assert main_module._runtime_observability_pid == 5151


def test_bootstrap_runtime_observability_reinitializes_after_fork(
    monkeypatch,
) -> None:
    calls: list[str] = []
    pids = iter((5151, 6262))

    monkeypatch.setattr(
        main_module, "configure_logging", lambda: calls.append("logging")
    )
    monkeypatch.setattr(
        main_module, "setup_monitoring", lambda: calls.append("monitoring")
    )
    monkeypatch.setattr(
        main_module, "setup_otel", lambda app=None: calls.append("otel")
    )
    monkeypatch.setattr(main_module.os, "getpid", lambda: next(pids))
    monkeypatch.setattr(main_module, "_runtime_observability_pid", None)

    main_module.bootstrap_runtime_observability(main_module.app)
    main_module.bootstrap_runtime_observability(main_module.app)

    assert calls == ["logging", "monitoring", "otel", "logging", "monitoring", "otel"]
    assert main_module._runtime_observability_pid == 6262
