# Resource Current

Resource Current presents clinical interoperability as a set of restful currents moving between a control plane, a canonical FHIR surface, and an external application platform. The container boundary should feel architectural and precise, holding the local dashboard and FHIR service as a deliberate runtime domain while the AP remains clearly outside.

FHIR resources are the visual language. Labels should name the resource families, not explain the whole implementation. ServiceRequest and Task form the order current; DiagnosticReport, Observation, DocumentReference, and Binary form the result current. The diagram must be meticulously crafted so those two currents are distinct at presentation distance.

The local database appears as a quiet ledger, not a major integration endpoint. Its role is persistence, audit, retry, and local workflow state, so it should be visible but secondary. This balance requires painstaking attention to scale and hierarchy.

The final image should be calm, exact, and presentation-ready. Every arrow, port, and label must feel intentionally placed, with master-level execution and enough breathing room that the workflow is understood without narration.
