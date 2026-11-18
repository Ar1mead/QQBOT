const DEFAULTS = Object.freeze({
  enabled: false,
  private: Object.freeze({ enabled: false, conversationAllowlist: Object.freeze([]) }),
  groups: Object.freeze({ enabled: false, conversationAllowlist: Object.freeze([]) }),
  maxRecordChars: 16000,
});

function plainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function validIdentifier(value) {
  return (typeof value === "string" && value.trim() !== "")
    || (typeof value === "number" && Number.isSafeInteger(value));
}

function normalizeIds(value, field) {
  if (!Array.isArray(value)) throw new TypeError(`${field} must be an array`);
  const ids = value.map((item) => {
    if ((typeof item !== "string" && typeof item !== "number")
        || (typeof item === "number" && !Number.isSafeInteger(item))
        || String(item).trim() === "") {
      throw new TypeError(`${field} contains an invalid identifier`);
    }
    return String(item);
  });
  return [...new Set(ids)];
}

/** Normalize only the dedicated observation policy; never inherit chat allowAll behavior. */
export function normalizeObservationIngressConfig(raw = {}) {
  if (!plainObject(raw)) throw new TypeError("observationIngress must be an object");
  const allowed = new Set(["enabled", "private", "groups", "maxRecordChars"]);
  for (const key of Object.keys(raw)) {
    if (!allowed.has(key)) throw new TypeError(`unknown observationIngress field: ${key}`);
  }
  const normalizeKind = (value, name) => {
    if (value === undefined) value = {};
    if (!plainObject(value)) throw new TypeError(`observationIngress.${name} must be an object`);
    for (const key of Object.keys(value)) {
      if (!["enabled", "conversationAllowlist"].includes(key)) {
        throw new TypeError(`unknown observationIngress.${name} field: ${key}`);
      }
    }
    return {
      enabled: value.enabled === true,
      conversationAllowlist: normalizeIds(value.conversationAllowlist ?? [], `${name}.conversationAllowlist`),
    };
  };
  const maxRecordChars = raw.maxRecordChars ?? DEFAULTS.maxRecordChars;
  if (!Number.isInteger(maxRecordChars) || maxRecordChars < 1 || maxRecordChars > 16000) {
    throw new RangeError("maxRecordChars must be an integer from 1 to 16000");
  }
  return Object.freeze({
    enabled: raw.enabled === true,
    private: Object.freeze(normalizeKind(raw.private, "private")),
    groups: Object.freeze(normalizeKind(raw.groups, "groups")),
    maxRecordChars,
  });
}

export function evaluateIncomingObservation({
  config,
  conversationKind,
  conversationId,
  senderId,
  selfId,
  event,
  denyUsers = [],
  denyConversations = [],
}) {
  if (!config?.enabled) return { allowed: false, reason: "ingress_disabled" };
  if (conversationKind !== "private" && conversationKind !== "group") {
    return { allowed: false, reason: "unsupported_conversation_kind" };
  }
  const kindConfig = conversationKind === "private" ? config.private : config.groups;
  if (!kindConfig?.enabled || !Array.isArray(kindConfig.conversationAllowlist)
      || kindConfig.conversationAllowlist.length === 0) {
    return { allowed: false, reason: "kind_not_explicitly_allowed" };
  }
  if (event?.post_type !== "message") {
    return { allowed: false, reason: "not_message_event" };
  }
  if (event?.message_type !== conversationKind) {
    return { allowed: false, reason: "conversation_kind_mismatch" };
  }
  if (!validIdentifier(conversationId) || !validIdentifier(senderId)) {
    return { allowed: false, reason: "missing_source_identity" };
  }
  if (selfId != null && String(senderId) === String(selfId)) {
    return { allowed: false, reason: "self_authored" };
  }
  const conversation = String(conversationId);
  const sender = String(senderId);
  if (!kindConfig.conversationAllowlist.includes(conversation)) {
    return { allowed: false, reason: "conversation_not_allowlisted" };
  }
  if (normalizeIds(denyUsers, "denyUsers").includes(sender)) {
    return { allowed: false, reason: "sender_denied" };
  }
  if (normalizeIds(denyConversations, "denyConversations").includes(conversation)) {
    return { allowed: false, reason: "conversation_denied" };
  }
  return { allowed: true, reason: "allowed" };
}

/** Extract only OneBot text segments; unsupported segments are explicitly marked partial. */
export function extractIncomingText(message, maxChars = 16000) {
  if (!Number.isInteger(maxChars) || maxChars < 1 || maxChars > 16000) {
    throw new RangeError("maxChars must be an integer from 1 to 16000");
  }
  const segments = typeof message === "string" ? [{ type: "text", data: { text: message } }]
    : Array.isArray(message) ? message : [];
  let content = "";
  const omitted = new Set();
  for (const segment of segments) {
    if (segment?.type === "text" && typeof segment?.data?.text === "string") {
      content += segment.data.text;
    } else {
      const type = typeof segment?.type === "string" ? segment.type.slice(0, 40) : "unknown";
      omitted.add(type);
    }
  }
  if (!content.trim()) return { accepted: false, reason: "no_text_content" };
  const codePoints = Array.from(content);
  const truncated = codePoints.length > maxChars;
  if (truncated) content = codePoints.slice(0, maxChars).join("");
  const notes = [];
  if (omitted.size) notes.push(`unsupported_segments_omitted:${[...omitted].sort().join(",")}`);
  if (truncated) notes.push("text_truncated_at_configured_limit");
  return {
    accepted: true,
    content,
    complete: !omitted.size && !truncated,
    notes,
  };
}
