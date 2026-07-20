from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLIENT = ROOT / "frontend/static/js/api/client.js"
OIE_API = ROOT / "frontend/static/js/api/oie.js"


class ApiClientModuleTests(unittest.TestCase):
    def test_shared_client_executes_complete_failure_matrix(self):
        script = r"""
import assert from "node:assert/strict";
const client = await import(process.argv[1]);
const response = (ok, payload, statusText = "") => ({
  ok,
  statusText,
  json: async () => {
    if (payload instanceof Error) throw payload;
    return payload;
  },
});

globalThis.fetch = async () => response(true, { success: true, item: { id: "ok" } });
assert.equal((await client.requestJson("/success")).item.id, "ok");

globalThis.fetch = async () => response(false, { error: "HTTP failed" }, "Bad Gateway");
await assert.rejects(client.requestJson("/http"), /HTTP failed/);

globalThis.fetch = async () => response(true, { success: false, error: "Business failed" });
await assert.rejects(client.requestJson("/business"), /Business failed/);
assert.equal((await client.requestJsonAllowBusinessFailure("/business")).success, false);

globalThis.fetch = async () => response(false, new Error("not JSON"), "Invalid response");
await assert.rejects(client.requestJson("/non-json"), /Invalid response/);

globalThis.fetch = async () => { throw new Error("Network failed"); };
await assert.rejects(client.requestJsonEnvelope("/network"), /Network failed/);

globalThis.fetch = async () => response(false, { success: false, error: "OIE rejected" }, "Rejected");
const envelope = await client.requestJsonEnvelope("/envelope");
assert.equal(envelope.response.ok, false);
assert.equal(envelope.payload.error, "OIE rejected");
"""
        result = subprocess.run(
            ["node", "--input-type=module", "-e", script, CLIENT.as_uri()],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_oie_adapter_uses_shared_response_envelope(self):
        source = OIE_API.read_text(encoding="utf-8")
        self.assertIn("requestJsonEnvelope", source)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("response.json()", source)


if __name__ == "__main__":
    unittest.main()
