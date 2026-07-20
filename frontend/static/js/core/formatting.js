export function hl7Escape(value) {
  return String(value ?? "")
    .replaceAll("\\", "\\E\\")
    .replaceAll("|", "\\F\\")
    .replaceAll("&", "\\T\\")
    .replaceAll("~", "\\R\\")
    .replaceAll("\r\n", "\n")
    .replaceAll("\r", "\n")
    .replaceAll("\n", "\\.br\\");
}

export function hl7EscapeComposite(value) {
  return String(value ?? "").split("^").map(hl7Escape).join("^");
}

export function pad(value) {
  return String(value).padStart(2, "0");
}

export function hl7Timestamp(date = new Date()) {
  return [date.getFullYear(), pad(date.getMonth() + 1), pad(date.getDate()), pad(date.getHours()), pad(date.getMinutes()), pad(date.getSeconds())].join("");
}

export function localDatetimeValue(date = new Date()) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function taipeiTimestamp(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(date).replace(",", " TPE");
}

export function gdtTaipeiTimestamp(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).formatToParts(date).reduce((acc, part) => {
    acc[part.type] = part.value;
    return acc;
  }, {});
  return `${parts.year}-${parts.month}-${parts.day} TPE ${parts.hour}:${parts.minute}:${parts.second}`;
}

export function fhirBirthDate(dob) {
  return `${dob.slice(0, 4)}-${dob.slice(4, 6)}-${dob.slice(6)}`;
}

export function fhirGender(sex) {
  return { M: "male", F: "female", O: "other", U: "unknown" }[sex] || "unknown";
}
