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

FRONTEND_FUNCTION_NAME_INVENTORY: frozenset[str] = frozenset("""

 buildFhirOrderPreviewPayload buildGdtOrderPreviewPayload
buildOrderPreviewPayload byId
  createGdtPatientFromOrderFlow
createOrderRecord createPatientRecord currentOrderMode
 dcm4cheeActionsForResult dcm4cheeConsoleOrders dcm4cheeConsolePatients
dcm4cheeCopyButton dcm4cheeDetailBlock dcm4cheeDisplayStatus dcm4cheeFirstArtifact
dcm4cheeFirstValue dcm4cheeNestedTable dcm4cheeOpenButton dcm4cheeOrderActionButtons
dcm4cheeOrderLabel dcm4cheeOrderPatient dcm4cheeOrderPreviewPayload dcm4cheeOrderResultRecords
dcm4cheeOrderStatus dcm4cheeOrderVerificationStatus dcm4cheePatientLabel dcm4cheePatientSection
dcm4cheeResultKey dcm4cheeResultStatusClass dcm4cheeWorkflowStatusClass dcm4cheeWorkflowSummary
 ensureDcm4cheeSelection
fhirConcept fhirOrderField
fhirOrderPayload fhirReferenceList fhirSyncStatusClass
gdtPatientFormPayload
groupDcm4cheeResultsForBrowser
loadDcm4cheeAttemptHistory






 openGdtOrderFlow orderAccountNumber orderFormPayload orderListKey
orderModeLabel orderPatientModeLabel orderPatientProtocolForMode orderPatientRecordsForMode
orderRecordMode orderStateLabel orderVisitId orderVisitNumber
refreshDcm4cheeConsole

 refreshOrderPreview refreshOrderWorkspace refreshOrders
refreshPatientDcm4cheeResults refreshPatientPreview refreshPatients
renderDcm4cheeAttemptHistory renderDcm4cheeConsole renderDcm4cheeExpandedOrders
renderDcm4cheeExpandedResults renderDcm4cheeInstanceTable renderDcm4cheeOrderActions
renderDcm4cheePatientList renderDcm4cheePreview renderDcm4cheeProfileSummary
renderDcm4cheeResultGroup renderDcm4cheeResultTable renderDcm4cheeResultsBrowser
renderDcm4cheeSelectedOrder renderDcm4cheeSelectedPatient renderDcm4cheeSelectors
renderDcm4cheeSeriesDetails renderDcm4cheeStudyDetails renderDcm4cheeWorkflowStrip

renderGdtMessage renderGdtRecord






renderOrderPatientOptions renderOrderRecordList
renderOrderSummary renderOrderValidation renderPatientDcm4cheeResults renderPatientRecords
renderPatientSummaryFromRecord


retryDcm4cheeOrder retryPatientFhirSync
 selectDcm4cheeOrder
selectDcm4cheePatient
 selectOrderRecord selectedDcm4cheeOrder selectedDcm4cheePatient


 selectedOrderPatient selectedOrderPatientReference selectedOrderPayloadPreview
sendDcm4cheeOrder setFhirOrderForm setOrderForm
simulateDcm4cheeApReturn splitFhirList
 summarizeDcm4cheeResultGroup updateOrderModeFields
validateOrderPayload verifyDcm4cheeOrder

""".split())

FRONTEND_FUNCTION_BASELINE: frozenset[tuple[str, str]] = frozenset(
    tuple(line.split("|", 1))
    for line in """
<module-prefix>|e3b0c44298fc1c14
byId|c6f086e09f1c6f6a
buildFhirOrderPreviewPayload|f74813ed4a5d3994
buildGdtOrderPreviewPayload|2ce27ec95d4cb1fb
buildOrderPreviewPayload|29c39842e5808a98
createGdtPatientFromOrderFlow|86197c052f7ec659
createOrderRecord|3b67aea5840bbf2c
createPatientRecord|fa6b4ca4ec407373
currentOrderMode|bf23a42fec967e1c
dcm4cheeActionsForResult|49b20326dcc6f71e
dcm4cheeConsoleOrders|9b947ad007af173f
dcm4cheeConsolePatients|760e34b4bd1c54ec
dcm4cheeCopyButton|736f0e34985463f6
dcm4cheeDetailBlock|4a6e094bb57aa8f4
dcm4cheeDisplayStatus|6c26216213ae3126
dcm4cheeFirstArtifact|3b4a91a2813a5947
dcm4cheeFirstValue|f5fce9e8fac63438
dcm4cheeNestedTable|5e2b2a349e4002c8
dcm4cheeOpenButton|b80f02137f5cb1c8
dcm4cheeOrderActionButtons|e48d5545d6458417
dcm4cheeOrderLabel|433f50db054c372a
dcm4cheeOrderPatient|5cf4764b22475a80
dcm4cheeOrderPreviewPayload|11afddbbf15a4270
dcm4cheeOrderResultRecords|daf2319bdfe89a15
dcm4cheeOrderStatus|545b290bfb295396
dcm4cheeOrderVerificationStatus|a842575584b2482f
dcm4cheePatientLabel|ceb0cb90cb19b848
dcm4cheePatientSection|6b4cf5ce12c25323
dcm4cheeResultKey|23fa043503dc1eab
dcm4cheeResultStatusClass|d5a75ef7659d061a
dcm4cheeWorkflowStatusClass|ddaeab2efb1f6853
dcm4cheeWorkflowSummary|d4891b00848e1520
ensureDcm4cheeSelection|9ffd3778b6cc2d6c
fhirConcept|95bfe7b4e5a4bd57
fhirOrderField|c74c765b0ac4aedc
fhirOrderPayload|550ee8fdfd94902e
fhirReferenceList|10ec74c08ba5dd99
fhirSyncStatusClass|d8f2fca5e3492941
gdtPatientFormPayload|c64195a464e6f026
groupDcm4cheeResultsForBrowser|66f107b0638fc2f9
loadDcm4cheeAttemptHistory|56952e5737f25a7b
openGdtOrderFlow|9d2a252ce82f8051
orderAccountNumber|6a917d4b155cda08
orderFormPayload|7b3529715e75b2ee
orderListKey|a3ec6dbb96876e80
orderModeLabel|bd5864e4fcc7dc43
orderPatientModeLabel|bd28abe98cd5f32a
orderPatientProtocolForMode|553df2f5ae1bd187
orderPatientRecordsForMode|fe87e38283861f56
orderRecordMode|b5bfa84fae5b63ab
orderStateLabel|99e85e8413f1a79b
orderVisitId|926611e93a737933
orderVisitNumber|e5e3d9608612cbee
refreshDcm4cheeConsole|1554e14716400d7f
refreshOrderPreview|4279f76d09a5d2f4
refreshOrderWorkspace|e764382daebb7625
refreshOrders|bda9a1532b277c9f
refreshPatientDcm4cheeResults|7347aee84021fe70
refreshPatientPreview|bb365f6a379d2f4d
refreshPatients|cd301ef45155b179
renderDcm4cheeAttemptHistory|108e4210ed93c5fb
renderDcm4cheeConsole|d6e893288e1d6cc8
renderDcm4cheeExpandedOrders|5ed6c4844d9b2c77
renderDcm4cheeExpandedResults|a41f8a270f011de7
renderDcm4cheeInstanceTable|02b79fdec934fe77
renderDcm4cheeOrderActions|0942e99e4988827e
renderDcm4cheePatientList|e461f7c84f1b898d
renderDcm4cheePreview|36146c3dac20f1b2
renderDcm4cheeProfileSummary|9f959acc8d65d264
renderDcm4cheeResultGroup|731e7ab92cd5ccd0
renderDcm4cheeResultTable|481457348f928423
renderDcm4cheeResultsBrowser|5eff0dafad8e017a
renderDcm4cheeSelectedOrder|bd251e3b4dc5cf5a
renderDcm4cheeSelectedPatient|4e28c8f646936b18
renderDcm4cheeSelectors|db369d99146866b4
renderDcm4cheeSeriesDetails|fad0178408929d40
renderDcm4cheeStudyDetails|cf29969b2cc86df6
renderDcm4cheeWorkflowStrip|4fbead145a5ae548
renderGdtMessage|3c00507446576905
renderGdtRecord|1b9f17ffdfa1c5fc
renderOrderPatientOptions|b8dd40339441b14e
renderOrderRecordList|cd11a6d17cd764f9
renderOrderSummary|97f03a710b8a6181
renderOrderValidation|b86c7af4719aff91
renderPatientDcm4cheeResults|3dd8c0f6e08e3c3e
renderPatientRecords|eda80d0a31656925
renderPatientSummaryFromRecord|2bd38af1fb047a06
retryDcm4cheeOrder|11a506272f8fdf47
retryPatientFhirSync|ee82c5029fb0bf81
selectDcm4cheeOrder|3705ba0cbe46d211
selectDcm4cheePatient|d791a29ae0d23328
selectOrderRecord|ae83db87e6186815
selectedDcm4cheeOrder|6f36805ede93772b
selectedDcm4cheePatient|d54a2251e79b80e9
selectedOrderPatient|c2da2cf765e2a4f7
selectedOrderPatientReference|f4816d13973441f3
selectedOrderPayloadPreview|05d63ddcf629ccc1
sendDcm4cheeOrder|b9681a0fa79516b3
setFhirOrderForm|0f05f464d96dcb55
setOrderForm|1f5ce669e5fe820c
simulateDcm4cheeApReturn|336c8cfbc8354f2e
splitFhirList|40c983243807ca21
summarizeDcm4cheeResultGroup|4c6ce8b2862bada6
updateOrderModeFields|dc3285a88f82d6c1
validateOrderPayload|f38aab922de8c8c1
verifyDcm4cheeOrder|9712bbd6ecd623a3
""".strip().splitlines()
)

FRONTEND_SELECTOR_FAMILY_BASELINE: frozenset[str] = frozenset("""
#fhir-token
#gdt-bridge-config-summary
#gdt-payload-preview
#gdt-watcher-summary
.action-menu
.action-row
.actions-cell
.advanced-card
.advanced-tools
.app-shell
.app-sidebar
.app-view
.artifact-reference
.artifact-reference-list
.attempt-list
.back-button
.brand-mark
.button
.button-row
.card
.card-title
.category-grid
.category-tile
.checkbox-row
.code-area
.compact-actions
.compact-output
.danger
.dashboard-cell-subtext
.dashboard-child-identity
.dashboard-child-row
.dashboard-main-grid
.dashboard-primary-identity
.dashboard-resource-panel
.dashboard-search
.dashboard-service-toggle
.dashboard-services-panel
.dcm4chee-browser-metadata
.dcm4chee-browser-row
.dcm4chee-console-grid
.dcm4chee-diagnostic-check
.dcm4chee-diagnostic-checks
.dcm4chee-empty-result
.dcm4chee-nested-table
.dcm4chee-nested-table-wrap
.dcm4chee-order-actions
.dcm4chee-patient-detail-row
.dcm4chee-patient-panel
.dcm4chee-patient-preview
.dcm4chee-patient-preview-heading
.dcm4chee-patient-rollup-content
.dcm4chee-patient-section
.dcm4chee-patient-section-heading
.dcm4chee-patient-sync-card
.dcm4chee-patient-table
.dcm4chee-patient-table-wrap
.dcm4chee-patient-toggle
.dcm4chee-preview-heading
.dcm4chee-preview-output
.dcm4chee-profile-panel
.dcm4chee-result-actions
.dcm4chee-result-browser
.dcm4chee-result-browser-viewport
.dcm4chee-result-group
.dcm4chee-result-table-wrap
.dcm4chee-row-kind
.dcm4chee-selected-order-bar
.dcm4chee-send-selection-grid
.dcm4chee-series-row
.dcm4chee-series-table-wrap
.dcm4chee-study-table-wrap
.dcm4chee-workflow-label
.dcm4chee-workflow-panel
.dcm4chee-workflow-step
.dcm4chee-workflow-strip
.dcm4chee-workspace
.detail-block
.detail-list
.detail-workbench
.direction-banner
.eyebrow
.feature-header
.fhir-selection-toolbar
.field-grid
.form-grid
.four-columns
.full-width
.full-width-field
.gdt-advanced-tools
.gdt-bridge-actions
.gdt-bridge-config-grid
.gdt-config-details
.gdt-console
.gdt-console-grid
.gdt-nested-table
.gdt-patient-detail-row
.gdt-patient-rollup-content
.gdt-patient-section
.gdt-patient-section-heading
.gdt-patient-table
.gdt-patient-table-wrap
.gdt-patient-toggle
.gdt-primary-actions
.gdt-selected-patient-panel
.gdt-selected-patient-raw
.gdt-shared-folder-panel
.gdt-watcher-bar
.gdt-workflow-strip
.hint
.inline-check
.is-running
.lab-card-facts
.lab-console
.lab-console-header
.lab-empty-state
.lab-enabled-row
.lab-operation-output
.lab-panel
.lab-server-card
.lab-server-grid
.lab-summary-label
.lab-summary-strip
.lab-summary-tile
.lab-summary-value
.lab-workbench
.level
.log-entry
.log-output
.log-panel
.loopback-diagram
.medplum-console-grid
.medplum-context-column
.medplum-diagnostic-report-group
.medplum-diagnostic-report-rollup
.medplum-diagnostic-report-section
.medplum-diagnostic-report-table
.medplum-diagnostic-report-table-wrap
.medplum-json-console
.medplum-json-preview
.medplum-nested-table
.medplum-nested-table-wrap
.medplum-patient-detail-row
.medplum-patient-panel
.medplum-patient-rollup-content
.medplum-patient-section
.medplum-patient-section-heading
.medplum-patient-table
.medplum-patient-table-wrap
.medplum-patient-toggle
.medplum-related-group
.medplum-related-list
.medplum-related-row
.medplum-related-section
.medplum-selected-patient-panel
.medplum-workflow-controls
.medplum-workflow-panel
.medplum-workspace
.menu-panel
.mode-selector
.muted
.nav-icon
.oie-connection-grid
.oie-console-grid
.oie-inventory-grid
.oie-nested-table
.oie-patient-detail-row
.oie-patient-panel
.oie-patient-rollup-content
.oie-patient-section
.oie-patient-section-heading
.oie-patient-table
.oie-patient-table-wrap
.oie-patient-toggle
.oie-preview-heading
.oie-preview-output
.oie-selected-order-bar
.oie-send-connection-grid
.oie-subsection-heading
.oie-transmission-panel
.operation-buttons
.operation-error
.operation-history
.operation-history-item
.operation-meta
.operation-progress
.order-local-table-wrap
.order-workspace
.orders-workbench
.output-panel
.page-header
.page-shell
.panel-head
.patient-grid
.patient-local-table-wrap
.payload-grid
.primary
.progress
.queue-actions
.raw-details
.recently-updated
.record-detail
.resource-item
.resource-usage-list
.secondary-action
.section-heading
.section-index
.selected
.selected-row
.sidebar-brand
.sidebar-link
.sidebar-nav
.small-button
.small-panel
.sop-card
.sop-copy
.status
.status-pill
.step-label
.subtitle
.table-wrap
.tall-panel
.three-columns
.timeline-item
.timeline-list
.timestamp-cell
.timestamp-date
.timestamp-time
.token-detail-list
.token-inspector
.token-toolbar
.topbar
.two-column
.two-columns-grid
.upload-grid
.view-heading
.warning-box
.workbench-detail-grid
.workbench-filter-grid
.workbench-header
.workbench-layout
.workbench-table-wrap
.workflow-strip
.active
.compact
.compact-detail
.critical
.danger-action
.disabled
.error
.expanded
.healthy
.inbound
.info
.lower-grid
.neutral
.outbound
.patient-focused-grid
.pending
.secondary
.status-error
.status-neutral
.status-pending
.status-success
.success
.text-button
.token-masked
.warn
.warning
.warning-action
""".split())

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
