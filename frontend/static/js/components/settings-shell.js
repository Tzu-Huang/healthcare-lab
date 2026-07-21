export function listenerReloadMessage() {
  return "Listener settings were saved but are not active. Stop and Retry the listener, or restart lab-app.";
}
export function settingsUnavailableMessage() { return "Settings are temporarily unavailable."; }
export function listenerPortWarning() {
  return "Changing this port may also require applying the managed ORU route, updating Docker/runtime port exposure and firewall rules, then Retry or restart of lab-app.";
}
export function safeConnectionResult(item = {}) {
  const status = item.status || (item.connected ? "Connected" : "Not connected");
  return [status, item.version && `OIE ${item.version}`, item.currentUser && `User ${item.currentUser}`,
    item.tlsMode && `TLS ${item.tlsMode}`, item.testedAt && `Tested ${item.testedAt}`].filter(Boolean).join(" · ");
}
