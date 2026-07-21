# healthcare-lab-oie-runtime-diagnostics Specification

## Purpose
TBD - created by archiving change harden-oie-hlab-runtime-delivery-diagnostics. Update Purpose after archive.
## Requirements
### Requirement: Runtime diagnostics identify each delivery layer

Healthcare Lab SHALL return a diagnostic report with independent checks for OIE Management API reachability, HLAB listener runtime, managed Channel deployment, runtime port contracts, and OIE destination delivery state.

#### Scenario: One layer fails
- **WHEN** a diagnostic probe fails while other probes succeed
- **THEN** the report identifies the failing layer with a stable category and bounded recovery guidance
- **AND** preserves successful evidence from the other layers

#### Scenario: Diagnostics are refreshed
- **WHEN** an operator requests runtime diagnostics
- **THEN** each check includes its state and observation time without claiming that an untested external firewall path is healthy

### Requirement: Delivery statistics degrade honestly

Healthcare Lab SHALL report queued and error destination counts when supported by the connected OIE API and SHALL report the statistic as unavailable when it cannot be obtained.

#### Scenario: Queue statistics are supported
- **WHEN** OIE returns bounded message statistics for the managed ORU destination
- **THEN** diagnostics display queued and error counts associated with that managed Channel

#### Scenario: Queue statistics are unsupported
- **WHEN** the OIE version or endpoint cannot provide bounded delivery statistics
- **THEN** diagnostics report `unavailable` with safe guidance
- **AND** do not report a fabricated zero

### Requirement: Diagnostics exclude credentials and PHI

Diagnostic responses, routine logs, and stored diagnostic evidence MUST NOT contain configured passwords, cookies, authorization values, complete Channel payloads, or complete PHI-bearing HL7 messages.

#### Scenario: Upstream diagnostic failure contains sensitive content
- **WHEN** OIE or a transport exception includes headers, credentials, or message content
- **THEN** Healthcare Lab maps it to an allowlisted category and safe summary
- **AND** omits the sensitive upstream content from the response and routine logs
