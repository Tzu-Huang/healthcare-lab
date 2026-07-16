# OIE 4.5.2 Management API Evidence

This implementation is pinned to the official NextGen Connect `4.5.2` tag.
The authoritative sources are the JAX-RS servlet interfaces and server request
filters below; paths are relative to `/api`.

## Sources

- [`UserServletInterface.java`](https://github.com/nextgenhealthcare/connect/blob/4.5.2/server/src/com/mirth/connect/client/core/api/servlets/UserServletInterface.java)
- [`ConfigurationServletInterface.java`](https://github.com/nextgenhealthcare/connect/blob/4.5.2/server/src/com/mirth/connect/client/core/api/servlets/ConfigurationServletInterface.java)
- [`SystemServletInterface.java`](https://github.com/nextgenhealthcare/connect/blob/4.5.2/server/src/com/mirth/connect/client/core/api/servlets/SystemServletInterface.java)
- [`ChannelServletInterface.java`](https://github.com/nextgenhealthcare/connect/blob/4.5.2/server/src/com/mirth/connect/client/core/api/servlets/ChannelServletInterface.java)
- [`EngineServletInterface.java`](https://github.com/nextgenhealthcare/connect/blob/4.5.2/server/src/com/mirth/connect/client/core/api/servlets/EngineServletInterface.java)
- [`ChannelStatusServletInterface.java`](https://github.com/nextgenhealthcare/connect/blob/4.5.2/server/src/com/mirth/connect/client/core/api/servlets/ChannelStatusServletInterface.java)
- [`RequestedWithFilter.java`](https://github.com/nextgenhealthcare/connect/blob/4.5.2/server/src/com/mirth/connect/server/api/providers/RequestedWithFilter.java)
- [`ResponseCodeFilter.java`](https://github.com/nextgenhealthcare/connect/blob/4.5.2/server/src/com/mirth/connect/server/api/providers/ResponseCodeFilter.java)

## Verified request contracts

| Operation | Request | Encoding | Declared response |
|---|---|---|---|
| Login | `POST /users/_login` | form fields `username`, `password` | `LoginStatus`, XML or JSON |
| Logout | `POST /users/_logout` | none | void |
| Current user | `GET /users/current` | none | `User`, XML or JSON |
| Server version | `GET /server/version` | none | plain-text `String` |
| System info | `GET /system/info` | none | `SystemInfo`, XML or JSON |
| List channels | `GET /channels` | query options from servlet interface | `List<Channel>`, XML or JSON |
| Get channel | `GET /channels/{channelId}` | query `includeCodeTemplateLibraries` | `Channel`, XML or JSON |
| Create channel | `POST /channels/` | `Channel`, XML or JSON | boolean, JSON or plain text |
| Update channel | `PUT /channels/{channelId}` | `Channel`, XML or JSON; query `override` and `startEdit` | boolean, JSON or plain text |
| Delete channel | `DELETE /channels/{channelId}` | none | void |
| Deploy channel | `POST /channels/{channelId}/_deploy` | query `returnErrors`, `debugOptions` | void |
| Redeploy all | `POST /channels/_redeployAll` | query `returnErrors` | void |
| Undeploy channel | `POST /channels/{channelId}/_undeploy` | query `returnErrors` | void |
| Channel status | `GET /channels/{channelId}/status` | none | `DashboardStatus`, XML or JSON |
| Ports in use | `GET /channels/portsInUse` | none | `List<Ports>`, XML or JSON |

The channel servlet also declares bulk deploy and undeploy operations using an
XML/JSON `Set<String>`. ZAC-46 exposes exact single-channel primitives and the
declared redeploy-all primitive; it does not invent lifecycle sequencing.

`RequestedWithFilter` requires a nonblank `X-Requested-With` header when the
default `server.api.require-requested-with=true` setting is active. The filter
does not constrain the nonblank value. The client consistently sends
`X-Requested-With: XMLHttpRequest` and requests JSON where the interface
declares JSON support.

## Deliberately unasserted details

The tagged static interfaces do not establish the session-cookie name or
attributes, complete serialized fields for the declared Java models, a stable
error entity schema, or every successful HTTP status after
`ResponseCodeFilter` processing. The client therefore retains cookies without
depending on their names, returns bounded normalized mappings rather than raw
responses, accepts documented 2xx success statuses, and maps failures by HTTP
class plus caller context. Tests must not claim undocumented wire details.
