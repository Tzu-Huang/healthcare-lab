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


class LabApplicationRepository:
    """Exact Lab workflow view over Lab persistence plus GDT inventory."""

    def __init__(self, repository, *, gdt_inventory):
        self._repository = repository
        self._gdt_inventory = gdt_inventory

    def get_lab_server(self, server_id): return self._repository.get_server(server_id)
    def list_lab_servers(self): return self._repository.list_servers()
    def create_lab_server(self, payload): return self._repository.create_server(payload)
    def update_lab_server(self, server_id, payload): return self._repository.update_server(server_id, payload)
    def update_lab_server_health(self, server_id, **values): return self._repository.update_health(server_id, **values)
    def record_lab_operation(self, server_id, **values): return self._repository.record_operation(server_id, **values)
    def get_lab_operation(self, operation_id): return self._repository.get_operation(operation_id)
    def list_lab_operations(self, server_id=None, *, limit=20): return self._repository.list_operations(server_id, limit=limit)
    def list_gdt_orders(self): return self._gdt_inventory()


def lab_server_services(app, repository, *, operation_runner, health_checker):
    return (
        LabRegistryService(app, repository, availability_decorator=decorate_lab_operation_availability),
        LabHealthService(app, repository, health_checker=health_checker, availability_decorator=decorate_lab_operation_availability),
        LabOperationService(app, repository, repository, operation_runner=operation_runner),
        LabSmokeService(app, repository, repository, operation_runner=operation_runner, operator_resolver=resolve_lab_operator),
    )


def dashboard_services(app, repository, *, operation_runner, health_checker):
    def health_check(repository, service_id):
        return run_dashboard_group_health_check(
            repository, service_id, health_checker=health_checker
        )

    return (
        DashboardSnapshotService(app, repository),
        DashboardActionService(app, repository, health_check=health_check, operation_runner=operation_runner),
    )
