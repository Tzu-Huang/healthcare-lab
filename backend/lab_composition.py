"""Explicit composition for focused Lab and dashboard use-case services."""

from __future__ import annotations

from backend.services.lab_workflow import (
    DashboardActionService,
    DashboardSnapshotService,
    LabHealthService,
    LabOperationService,
    LabRegistryService,
    LabSmokeService,
    decorate_lab_operation_availability,
    resolve_lab_operator,
    run_dashboard_group_health_check,
)


def lab_server_services(app, store, *, operation_runner, health_checker):
    repository = store.lab_repository
    return (
        LabRegistryService(app, repository, availability_decorator=decorate_lab_operation_availability),
        LabHealthService(app, repository, health_checker=health_checker, availability_decorator=decorate_lab_operation_availability),
        LabOperationService(app, repository, store, operation_runner=operation_runner),
        LabSmokeService(app, repository, store, operation_runner=operation_runner, operator_resolver=resolve_lab_operator),
    )


def dashboard_services(app, store, *, operation_runner, health_checker):
    def health_check(repository, service_id):
        return run_dashboard_group_health_check(
            repository, service_id, health_checker=health_checker
        )

    return (
        DashboardSnapshotService(app, store),
        DashboardActionService(app, store, health_check=health_check, operation_runner=operation_runner),
    )
