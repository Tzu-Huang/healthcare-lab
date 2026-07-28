import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import vm from "node:vm";
import { fileURLToPath, pathToFileURL } from "node:url";

const ROOT = path.resolve(import.meta.dirname, "..", "..");

class FakeElement {
  constructor(tagName = "div", text = "") {
    this.tagName = tagName.toUpperCase();
    this.textContent = text;
    this.className = "";
    this.hidden = false;
    this.children = [];
    this.listeners = new Map();
    this.attributes = new Map();
    this.onload = null;
    this.onerror = null;
    this._src = "";
    this.srcOutcome = "load";
  }

  appendChild(child) {
    this.children.push(child);
    return child;
  }

  append(...children) {
    this.children.push(...children);
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  dispatch(type) {
    this.listeners.get(type)?.({
      currentTarget: this,
      target: this,
      stopPropagation() {},
    });
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === "src") this._src = "";
  }

  set src(value) {
    this._src = value;
    queueMicrotask(() => {
      if (this.srcOutcome === "error") this.onerror?.();
      else this.onload?.();
    });
  }

  get src() {
    return this._src;
  }

  get childElementCount() {
    return this.children.length;
  }
}

function createDom(pathname = "/viewer/ecg/42") {
  const ids = [
    "ecg-viewer-status",
    "ecg-viewer-loading",
    "ecg-viewer-content",
    "ecg-viewer-error",
    "ecg-viewer-error-message",
    "ecg-viewer-retry",
    "ecg-viewer-graph",
    "ecg-viewer-graph-error",
    "ecg-viewer-leads",
    "ecg-viewer-sample-rate",
    "ecg-viewer-unit",
    "ecg-viewer-duration",
  ];
  const elements = Object.fromEntries(ids.map((id) => [id, new FakeElement()]));
  return {
    elements,
    document: {
      createElement: (tagName) => new FakeElement(tagName),
      getElementById: (id) => elements[id] ?? null,
    },
    window: {
      location: { pathname },
      openCalls: [],
      open(...args) {
        this.openCalls.push(args);
      },
    },
  };
}

async function loadModule(relativePath, globals = {}) {
  const context = vm.createContext({
    console,
    Date,
    Error,
    Intl,
    Map,
    Number,
    Object,
    Promise,
    RegExp,
    Set,
    String,
    URLSearchParams,
    encodeURIComponent,
    queueMicrotask,
    ...globals,
  });
  const cache = new Map();

  async function compile(filename) {
    const absolute = path.resolve(ROOT, filename);
    if (cache.has(absolute)) return cache.get(absolute);
    const source = await fs.readFile(absolute, "utf8");
    const module = new vm.SourceTextModule(source, {
      context,
      identifier: pathToFileURL(absolute).href,
    });
    cache.set(absolute, module);
    await module.link(async (specifier, referencingModule) => {
      const parent = path.dirname(fileURLToPath(referencingModule.identifier));
      return compile(path.resolve(parent, specifier));
    });
    return module;
  }

  const module = await compile(relativePath);
  await module.evaluate();
  return { namespace: module.namespace, context };
}

function jsonResponse(item, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() {
      return status < 400
        ? { success: true, item }
        : { success: false, error: item };
    },
  };
}

function nextTurn() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

test("result action executes capability gating, URL construction, and noopener", async () => {
  const dom = createDom();
  const { namespace } = await loadModule("frontend/static/js/views/dcm4chee.js", {
    document: dom.document,
    window: dom.window,
    navigator: { clipboard: { writeText() {} } },
  });

  assert.equal(
    namespace.dcm4cheeEcgViewerUrl(
      { id: 42, capabilities: { ecgGraph: true } },
      "instance",
    ),
    "/viewer/ecg/42",
  );
  assert.equal(
    namespace.dcm4cheeEcgViewerUrl(
      { id: 42, modality: "ECG", capabilities: { ecgGraph: false } },
      "instance",
    ),
    "",
  );

  const supported = namespace.dcm4cheeActionsForResult(
    {
      id: 42,
      capabilities: { ecgGraph: true },
      viewerUrl: "/generic-viewer",
      instanceRetrieveUrl: "/retrieve",
    },
    "instance",
  );
  assert.deepEqual(
    supported.children.map((child) => child.textContent),
    ["Open Viewer", "View ECG Graph", "Copy Retrieve"],
  );
  supported.children[1].dispatch("click");
  assert.deepEqual(dom.window.openCalls, [["/viewer/ecg/42", "_blank", "noopener"]]);

  const unsupported = namespace.dcm4cheeActionsForResult(
    { id: 43, modality: "ECG", capabilities: { ecgGraph: false } },
    "instance",
  );
  assert.equal(unsupported.children.some((child) => child.textContent === "View ECG Graph"), false);
});

test("viewer executes loading, successful metadata, graph, and reload initialization", async () => {
  const dom = createDom("/viewer/ecg/42");
  let resolveFetch;
  const fetch = () => new Promise((resolve) => {
    resolveFetch = resolve;
  });
  const { namespace } = await loadModule("frontend/static/js/views/ecg-viewer.js", {
    document: dom.document,
    window: dom.window,
    fetch,
    setTimeout,
  });

  assert.equal(namespace.resultIdFromPath(), "42");
  assert.equal(dom.elements["ecg-viewer-loading"].hidden, false);
  assert.equal(dom.elements["ecg-viewer-content"].hidden, true);
  assert.equal(dom.elements["ecg-viewer-status"].textContent, "Loading ECG metadata...");

  resolveFetch(jsonResponse({
    waveform: {
      leads: ["I", "II", "III"],
      samplingFrequencyHz: 500,
      unit: "mV",
      durationSeconds: 10,
    },
  }));
  await nextTurn();
  await nextTurn();

  assert.equal(dom.elements["ecg-viewer-loading"].hidden, true);
  assert.equal(dom.elements["ecg-viewer-content"].hidden, false);
  assert.equal(dom.elements["ecg-viewer-leads"].textContent, "I, II, III");
  assert.equal(dom.elements["ecg-viewer-sample-rate"].textContent, "500 Hz");
  assert.equal(dom.elements["ecg-viewer-unit"].textContent, "mV");
  assert.equal(dom.elements["ecg-viewer-duration"].textContent, "10 seconds");
  assert.equal(dom.elements["ecg-viewer-status"].textContent, "ECG graph loaded.");
  assert.match(dom.elements["ecg-viewer-graph"].src, /\/api\/dcm4chee\/results\/42\/ecg\/render\.svg\?v=/);
});

test("viewer executes controlled metadata failure", async () => {
  const dom = createDom("/viewer/ecg/404");
  await loadModule("frontend/static/js/views/ecg-viewer.js", {
    document: dom.document,
    window: dom.window,
    fetch: async () => jsonResponse(
      { code: "dcm4chee_ecg_result_not_found", message: "safe" },
      404,
    ),
    setTimeout,
  });
  await nextTurn();

  assert.equal(dom.elements["ecg-viewer-loading"].hidden, true);
  assert.equal(dom.elements["ecg-viewer-error"].hidden, false);
  assert.match(dom.elements["ecg-viewer-error-message"].textContent, /not found/i);
  assert.equal(dom.elements["ecg-viewer-status"].textContent, "ECG graph unavailable.");
});

test("viewer executes independent SVG load failure", async () => {
  const dom = createDom("/viewer/ecg/42");
  dom.elements["ecg-viewer-graph"].srcOutcome = "error";
  await loadModule("frontend/static/js/views/ecg-viewer.js", {
    document: dom.document,
    window: dom.window,
    fetch: async () => jsonResponse({
      waveform: {
        leads: ["I"],
        samplingFrequencyHz: 250,
        unit: "mV",
        durationSeconds: 5,
      },
    }),
    setTimeout,
  });
  await nextTurn();
  await nextTurn();

  assert.equal(dom.elements["ecg-viewer-content"].hidden, false);
  assert.equal(dom.elements["ecg-viewer-error"].hidden, true);
  assert.equal(dom.elements["ecg-viewer-graph-error"].hidden, false);
  assert.equal(
    dom.elements["ecg-viewer-status"].textContent,
    "ECG summary loaded, but the graph is unavailable.",
  );
});
