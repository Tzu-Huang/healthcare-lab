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
catch-all|backend/dashboard_services.py|dashboard_summary|5252ce23fd250e67
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
catch-all|backend/lab_store.py|DemoStore._order_account_number|5c3609a4356a2182
catch-all|backend/lab_store.py|DemoStore._order_record_number|0f9145d6e6b83de5
catch-all|backend/lab_store.py|DemoStore._order_visit_id|a9ee8493af05f2d2
catch-all|backend/lab_store.py|DemoStore._result_record_dict|4ad87223c2d4f7cf
catch-all|backend/lab_store.py|DemoStore.connect|db95eb9c330f888d
catch-all|backend/lab_store.py|DemoStore.initialize|1ec55384df4f5277
catch-all|backend/lab_store.py|DemoStore.list_oie_local_adt_inventory|a08d55ca7a0e3b85
catch-all|backend/lab_store.py|DemoStore.list_oie_local_order_inventory|436e0fbb175ab391
catch-all|backend/lab_store.py|_hl7_escape|b062236ad3ab289a
catch-all|backend/lab_store.py|_hl7_escape_composite|98f1ff43d8ec015b
catch-all|backend/lab_store.py|first_gdt_field|d8f033c133a3a034
catch-all|backend/lab_store.py|hl7_timestamp|c0a425769b5ad627
catch-all|backend/lab_store.py|now_iso|b2c98c9253a55daf
catch-all|backend/lab_store.py|parse_gdt_message|57b74ee66d8c12b4
catch-all|backend/lab_store.py|render_gdt_message|d49763cdbf85bae8
catch-all|backend/lab_store.py|render_gdt_record|19b9104452bbd723
catch-all|backend/lab_store.py|urllib_quote_safe|8a0318c50c4a8c59
payload|backend/dashboard_services.py|collect_dashboard_resource_snapshot|4507029a254ccbcf
payload|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_cli|1b42e5af8d10ee3f
payload|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_socket|50701cdf6e9c93b5
payload|backend/dashboard_services.py|dashboard_resource_fallback|b10e912b7158a34f
payload|backend/lab_store.py|DemoStore._result_record_dict|4ad87223c2d4f7cf
payload|backend/lab_store.py|_hl7_escape|b062236ad3ab289a
payload|backend/lab_store.py|_hl7_escape_composite|98f1ff43d8ec015b
payload|backend/lab_store.py|first_gdt_field|d8f033c133a3a034
payload|backend/lab_store.py|hl7_timestamp|c0a425769b5ad627
payload|backend/lab_store.py|parse_gdt_message|57b74ee66d8c12b4
payload|backend/lab_store.py|render_gdt_message|d49763cdbf85bae8
payload|backend/lab_store.py|render_gdt_record|19b9104452bbd723
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
transport|backend/lab_store.py|urllib_quote_safe|8a0318c50c4a8c59
workflow|backend/dashboard_services.py|collect_dashboard_resource_snapshot|4507029a254ccbcf
workflow|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_cli|1b42e5af8d10ee3f
workflow|backend/dashboard_services.py|collect_dashboard_resource_snapshot_from_socket|50701cdf6e9c93b5
workflow|backend/dashboard_services.py|collect_docker_socket_container_stats|951ca6bf0005af7f
catch-all|backend/dashboard_services.py|<module>.DOCKER_COMPOSE_PROJECT|8aae4c1613a1fbc1
catch-all|backend/dashboard_services.py|<module>.DOCKER_SOCKET_PATH|ff29a28315e0502b
catch-all|backend/dashboard_services.py|<module>.LAB_DASHBOARD_SERVICE_GROUPS|5613527314933370
catch-all|backend/dashboard_services.py|<module>.RESOURCE_SNAPSHOT_CACHE_SECONDS|58f5db5da0fd94ed
catch-all|backend/dashboard_services.py|<module>.RESOURCE_SNAPSHOT_MAX_WORKERS|2d8aa4e8726094ba
catch-all|backend/dashboard_services.py|<module>._RESOURCE_SNAPSHOT_CACHE|8c4e05c60f5f19ed
catch-all|backend/dashboard_services.py|<module>._RESOURCE_SNAPSHOT_CACHE_LOCK|c3b68e86eddd30a8
catch-all|backend/lab_operations.py|<module>.DOCKER_COMPOSE_PROJECT|8aae4c1613a1fbc1
catch-all|backend/lab_operations.py|<module>.DOCKER_SOCKET_PATH|ff29a28315e0502b
catch-all|backend/lab_operations.py|<module>.DOCKER_SOCKET_STOP_GRACE_SECONDS|2e843a750486e0e9
catch-all|backend/lab_store.py|<module>.DEFAULT_LAB_OPERATION_METADATA|800846a541107f50
catch-all|backend/lab_store.py|<module>.DEFAULT_LAB_SERVERS|60052052e562f266
catch-all|backend/lab_store.py|<module>.FHIR_ORDER_DEFAULT_CATEGORY|acb004473bb6dfad
catch-all|backend/lab_store.py|<module>.FHIR_ORDER_DEFAULT_INTENT|0ee7bd9c43650ef3
catch-all|backend/lab_store.py|<module>.FHIR_ORDER_DEFAULT_PRIORITY|3bff8d06e7ba5dc1
catch-all|backend/lab_store.py|<module>.FHIR_ORDER_DEFAULT_STATUS|742c1af33109ee20
catch-all|backend/lab_store.py|<module>.FHIR_ORDER_MESSAGE_TYPE|c69c50ccf0b6899c
catch-all|backend/lab_store.py|<module>.FHIR_ORDER_PROTOCOL_VERSION|1fc0ae067338c7dd
catch-all|backend/lab_store.py|<module>.FHIR_ORDER_STATUS_CREATED|e277bcc9dd7eabf7
catch-all|backend/lab_store.py|<module>.FHIR_SUPPORTED_RESOURCE_TYPES|e79371c6bca8f26f
catch-all|backend/lab_store.py|<module>.FHIR_SYNC_STATUSES|8e0e57cb882b4a00
catch-all|backend/lab_store.py|<module>.GDT_ORDER_PROTOCOL_VERSION|d14622425d0b39c0
catch-all|backend/lab_store.py|<module>.GDT_ORDER_STATUS_CREATED|a7cfe8e27baa8f82
catch-all|backend/lab_store.py|<module>.GDT_ORDER_STATUS_ERROR|6f3d0a19240387aa
catch-all|backend/lab_store.py|<module>.GDT_ORDER_STATUS_RESULT_RECEIVED|626052f6379af963
catch-all|backend/lab_store.py|<module>.GDT_ORDER_TEST_LABEL|dea8b0ba0337ef6c
catch-all|backend/lab_store.py|<module>.GDT_PATIENT_SEX_CODES|7d77248b82f06158
catch-all|backend/lab_store.py|<module>.HL7_V2_CHARSET|4b92910cc9435735
catch-all|backend/lab_store.py|<module>.HL7_V2_MSH_SUFFIX|e3e0b999087a0591
catch-all|backend/lab_store.py|<module>.HL7_V2_VERSION|2fda8a6e9ddfa9a4
catch-all|backend/lab_store.py|<module>.OIE_MANAGEMENT_API_BASE_URL|96b562d91f5b8b5b
catch-all|backend/lab_store.py|<module>.OIE_MANAGEMENT_API_PASSWORD|890a4b27f86f5421
catch-all|backend/lab_store.py|<module>.OIE_MANAGEMENT_API_TIMEOUT_SECONDS|4f94612fda7c4007
catch-all|backend/lab_store.py|<module>.OIE_MANAGEMENT_API_USERNAME|6fc70b5d6edf16ec
catch-all|backend/lab_store.py|<module>.OIE_RESULT_LISTENER_HOST|db94348b03364756
catch-all|backend/lab_store.py|<module>.OIE_RESULT_LISTENER_PORT|9ab16e65e012c4de
catch-all|backend/lab_store.py|<module>.OIE_SETTINGS_PROFILE_NAME|307bf9238c05ade8
catch-all|backend/lab_store.py|<module>.ORDER_ALLOWED_PRIORITIES|3e58cbf19a55705d
catch-all|backend/lab_store.py|<module>.ORDER_DEFAULT_ALT_CODE|2807ffff7dbd5e15
catch-all|backend/lab_store.py|<module>.ORDER_DEFAULT_ALT_SYSTEM|08f04e82bc7ec416
catch-all|backend/lab_store.py|<module>.ORDER_DEFAULT_ALT_TEXT|4cd02092534d1d95
catch-all|backend/lab_store.py|<module>.ORDER_DEFAULT_CODE|a6315e482d9f9ebf
catch-all|backend/lab_store.py|<module>.ORDER_DEFAULT_PROVIDER|e1c1fe9e0ae146a3
catch-all|backend/lab_store.py|<module>.ORDER_DEFAULT_TEXT|f460ea084c92ac40
catch-all|backend/lab_store.py|<module>.ORDER_MESSAGE_TYPE|96a37ff4b1acd80c
catch-all|backend/lab_store.py|<module>.ORDER_PROTOCOL_VERSION|d8291434e8635462
catch-all|backend/lab_store.py|<module>.PATIENT_CLASS_DEFAULT|e77e6dbf0ca32b83
catch-all|backend/lab_store.py|<module>.PATIENT_MESSAGE_TYPE|b090bc2ba1e88382
catch-all|backend/lab_store.py|<module>.PATIENT_MODES|49210b84d1feae78
catch-all|backend/lab_store.py|<module>.PATIENT_PROTOCOL_VERSION|ddf3ae35d7e181c4
payload|backend/dashboard_services.py|<module>.LAB_DASHBOARD_SERVICE_GROUPS|5613527314933370
payload|backend/dashboard_services.py|<module>._RESOURCE_SNAPSHOT_CACHE|8c4e05c60f5f19ed
payload|backend/lab_store.py|<module>.DEFAULT_LAB_OPERATION_METADATA|800846a541107f50
payload|backend/lab_store.py|<module>.DEFAULT_LAB_SERVERS|60052052e562f266
payload|backend/lab_store.py|<module>.GDT_PATIENT_SEX_CODES|7d77248b82f06158
payload|backend/lab_store.py|<module>.PATIENT_MODES|49210b84d1feae78
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
        ("backend/app_factory.py", "backend.lab_store"),
        ("backend/services/lab_workflow.py", "backend.dashboard_services"),
        ("backend/services/lab_workflow.py", "backend.lab_operations"),
    }
)
