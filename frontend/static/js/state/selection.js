const selections = new Map();

export function getSelection(name, fallback = null) {
  return selections.has(name) ? selections.get(name) : fallback;
}

export function setSelection(name, value) {
  selections.set(name, value);
  return value;
}

export function clearSelection(name) {
  selections.delete(name);
}
