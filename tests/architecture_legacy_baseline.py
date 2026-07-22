"""Reviewed legacy surface allowed only while bounded-context extraction proceeds."""

BACKEND_LEGACY_BASELINE: frozenset[tuple[str, str, str, str]] = frozenset(
    tuple(line.split("|", 3))
    for line in """
catch-all|backend/dashboard_services.py|DockerSocketHttpConnection|a7b166a5ae8204a9
catch-all|backend/dashboard_services.py|DockerSocketHttpConnection.__init__|eb833d43bcd1941b
catch-all|backend/dashboard_services.py|DockerSocketHttpConnection.connect|31bc0f15a6bfcadb
catch-all|backend/dashboard_services.py|collect_dashboard_resource_snapshot|4507029a254ccbcf
catch-all|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_cli|1b42e5af8d10ee3f
catch-all|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_socket|50701cdf6e9c93b5
catch-all|backend/dashboard_services.py|collect_docker_socket_container_stats|951ca6bf0005af7f
catch-all|backend/dashboard_services.py|current_dashboard_timestamp|5414e4e3a22c0671
catch-all|backend/dashboard_services.py|dashboard_action_for_group|140c8b06fdd48188
catch-all|backend/dashboard_services.py|dashboard_child_for_group|3fa7fa402dcf8cae
catch-all|backend/dashboard_services.py|dashboard_health_rank|f52d8c617d08b482
catch-all|backend/dashboard_services.py|dashboard_operation_services|eeb8a4e762de6843
catch-all|backend/dashboard_services.py|dashboard_resource_fallback|b10e912b7158a34f
catch-all|backend/dashboard_services.py|dashboard_servers_for_group|eed4c6f1d63de146
catch-all|backend/dashboard_services.py|derive_dashboard_group_status|bd2f38a640196eb6
catch-all|backend/dashboard_services.py|docker_socket_available|7c917b803c455f42
catch-all|backend/dashboard_services.py|docker_socket_json_request|de36d1301bfb75c8
catch-all|backend/dashboard_services.py|parse_docker_memory_usage|28249d66d3d0bed9
catch-all|backend/dashboard_services.py|parse_docker_socket_cpu_percent|7db41ad87ee19068
catch-all|backend/dashboard_services.py|parse_docker_socket_memory_usage|c5c0ecf71ba0d79b
catch-all|backend/dashboard_services.py|parse_docker_stats_percent|1389e8b406a74af3
catch-all|backend/dashboard_services.py|parse_size_to_mib|1a91bb9c65771691
catch-all|backend/lab_operations.py|DockerComposeLabOperationAdapter|9dddf280cbf28f37
catch-all|backend/lab_operations.py|DockerComposeLabOperationAdapter.__init__|b341f1e137c24724
catch-all|backend/lab_operations.py|DockerComposeLabOperationAdapter.build_command|63e9e0c73576eb49
catch-all|backend/lab_operations.py|DockerComposeLabOperationAdapter.inspect|ab58bf8d93bd603a
catch-all|backend/lab_operations.py|DockerComposeLabOperationAdapter.parse_compose_ps_json|c765fdcc1d9c01b8
catch-all|backend/lab_operations.py|DockerComposeLabOperationAdapter.run|42d780eeb000c326
catch-all|backend/lab_operations.py|DockerComposeLabOperationAdapter.unavailable_reason|33822d8082ef6da0
catch-all|backend/lab_operations.py|DockerSocketHttpConnection|e0c11fde0161025e
catch-all|backend/lab_operations.py|DockerSocketHttpConnection.__init__|2b37ce35fad25f45
catch-all|backend/lab_operations.py|DockerSocketHttpConnection.connect|31bc0f15a6bfcadb
catch-all|backend/lab_operations.py|DockerSocketLabOperationAdapter|9deb614a904857f4
catch-all|backend/lab_operations.py|DockerSocketLabOperationAdapter.__init__|ab12acb30b2e8307
catch-all|backend/lab_operations.py|DockerSocketLabOperationAdapter.containers_for_service|8c40d23041668fa8
catch-all|backend/lab_operations.py|DockerSocketLabOperationAdapter.inspect|cabbffffed167f02
catch-all|backend/lab_operations.py|DockerSocketLabOperationAdapter.is_available|e826e37d83b3258f
catch-all|backend/lab_operations.py|DockerSocketLabOperationAdapter.request|ea583b15ddc107fa
catch-all|backend/lab_operations.py|DockerSocketLabOperationAdapter.run|febe223fac88622c
payload|backend/dashboard_services.py|collect_dashboard_resource_snapshot|4507029a254ccbcf
payload|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_cli|1b42e5af8d10ee3f
payload|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_socket|50701cdf6e9c93b5
payload|backend/dashboard_services.py|dashboard_resource_fallback|b10e912b7158a34f
sql|backend/dashboard_services.py|docker_socket_json_request|7ab3778776cde4fa
sql|backend/lab_operations.py|DockerComposeLabOperationAdapter.inspect|7ab3778776cde4fa
sql|backend/lab_operations.py|DockerComposeLabOperationAdapter.run|7ab3778776cde4fa
sql|backend/lab_operations.py|DockerSocketLabOperationAdapter.run|7ab3778776cde4fa
transport|backend/dashboard_services.py|DockerSocketHttpConnection|a7b166a5ae8204a9
transport|backend/dashboard_services.py|DockerSocketHttpConnection.connect|31bc0f15a6bfcadb
transport|backend/dashboard_services.py|collect_dashboard_resource_snapshot|4507029a254ccbcf
transport|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_cli|1b42e5af8d10ee3f
transport|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_socket|50701cdf6e9c93b5
transport|backend/lab_operations.py|DockerComposeLabOperationAdapter|9dddf280cbf28f37
transport|backend/lab_operations.py|DockerComposeLabOperationAdapter.inspect|ab58bf8d93bd603a
transport|backend/lab_operations.py|DockerComposeLabOperationAdapter.run|42d780eeb000c326
transport|backend/lab_operations.py|DockerSocketHttpConnection|e0c11fde0161025e
transport|backend/lab_operations.py|DockerSocketHttpConnection.connect|31bc0f15a6bfcadb
transport|backend/lab_operations.py|DockerSocketLabOperationAdapter|9deb614a904857f4
transport|backend/lab_operations.py|DockerSocketLabOperationAdapter.containers_for_service|8c40d23041668fa8
workflow|backend/dashboard_services.py|collect_dashboard_resource_snapshot|4507029a254ccbcf
workflow|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_cli|1b42e5af8d10ee3f
workflow|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_socket|50701cdf6e9c93b5
workflow|backend/dashboard_services.py|collect_docker_socket_container_stats|951ca6bf0005af7f
catch-all|backend/dashboard_services.py|<module>.DOCKER_COMPOSE_PROJECT|8aae4c1613a1fbc1
catch-all|backend/dashboard_services.py|<module>.DOCKER_SOCKET_PATH|ff29a28315e0502b
catch-all|backend/dashboard_services.py|<module>.LAB_DASHBOARD_SERVICE_GROUPS|74cad3d77344ec20
catch-all|backend/dashboard_services.py|<module>.RESOURCE_SNAPSHOT_CACHE_SECONDS|58f5db5da0fd94ed
catch-all|backend/dashboard_services.py|<module>.RESOURCE_SNAPSHOT_MAX_WORKERS|2d8aa4e8726094ba
catch-all|backend/dashboard_services.py|<module>._RESOURCE_SNAPSHOT_CACHE|8c4e05c60f5f19ed
catch-all|backend/dashboard_services.py|<module>._RESOURCE_SNAPSHOT_CACHE_LOCK|c3b68e86eddd30a8
catch-all|backend/lab_operations.py|<module>.DOCKER_COMPOSE_PROJECT|8aae4c1613a1fbc1
catch-all|backend/lab_operations.py|<module>.DOCKER_SOCKET_PATH|ff29a28315e0502b
catch-all|backend/lab_operations.py|<module>.DOCKER_SOCKET_STOP_GRACE_SECONDS|2e843a750486e0e9
payload|backend/dashboard_services.py|<module>.LAB_DASHBOARD_SERVICE_GROUPS|74cad3d77344ec20
payload|backend/dashboard_services.py|<module>._RESOURCE_SNAPSHOT_CACHE|8c4e05c60f5f19ed
workflow|backend/dashboard_services.py|<module>._RESOURCE_SNAPSHOT_CACHE_LOCK|c3b68e86eddd30a8
""".strip().splitlines()
)
FRONTEND_FUNCTION_NAME_INVENTORY: frozenset[str] = frozenset()

FRONTEND_FUNCTION_BASELINE: frozenset[tuple[str, str]] = frozenset(
    tuple(line.split("|", 1))
    for line in """
<module-prefix>|e3b0c44298fc1c14
""".strip().splitlines()
)

FRONTEND_SELECTOR_FAMILY_BASELINE: frozenset[str] = frozenset()

CONCRETE_REPOSITORY_IMPORT_BASELINE: frozenset[tuple[str, str]] = frozenset(
    {
        (
            "backend/runtime/gdt_bridge_watcher.py",
            "backend.repositories.gdt_bridge_health",
        ),
        (
            "backend/services/lab_workflow.py",
            "backend.repositories.gdt_bridge_health",
        ),
    }
)

COMPATIBILITY_FACADE_CALLER_BASELINE: frozenset[tuple[str, str]] = frozenset(
    {
        ("backend/app_factory.py", "backend.dashboard_services"),
        ("backend/app_factory.py", "backend.lab_operations"),
        ("backend/services/lab_workflow.py", "backend.dashboard_services"),
        ("backend/services/lab_workflow.py", "backend.lab_operations"),
    }
)
