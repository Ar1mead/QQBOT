import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { TextDecoder } from "node:util";
import { evaluateIncomingObservation, extractIncomingText, normalizeObservationIngressConfig } from "./observation-policy.mjs";

const RECORD_FIELDS = new Set([
  "schema_version", "platform", "record_id", "cursor", "external_ref",
  "observation_kind", "account_ref", "conversation_kind", "conversation_ref",
  "sender_ref", "actor_role", "content_origin", "modality", "content",
  "source_ref", "observed_at", "received_at", "extraction_method",
  "historical", "coverage",
]);
const COVERAGE_FIELDS = new Set([
  "modality", "extraction_method", "complete", "start_ms", "end_ms",
  "missing_ranges_ms", "notes",
]);
const EXTRACTION_METHOD = "surfcore_onebot_v11_text_v1";

function requireString(value, field) {
  if (typeof value !== "string" || !value.trim()) throw new TypeError(`${field} must be a non-empty string`);
  return value;
}

function isIsoDate(value) {
  if (typeof value !== "string") return false;
  const date = new Date(value);
  return Number.isFinite(date.getTime()) && date.toISOString() === value;
}

function opaqueRef(key, domain, value) {
  const digest = crypto.createHmac("sha256", key).update(domain).update("\0").update(String(value)).digest("hex");
  return `hmac:v1:${digest}`;
}

function validateRecord(record, expectedStreamRef, expectedCursor) {
  if (!record || typeof record !== "object" || Array.isArray(record)) throw new Error("record_not_object");
  const keys = Object.keys(record);
  if (keys.length !== RECORD_FIELDS.size || keys.some((key) => !RECORD_FIELDS.has(key))) {
    throw new Error("record_schema_mismatch");
  }
  if (record.schema_version !== 1 || record.platform !== "qq"
      || record.observation_kind !== "qq.message.incoming"
      || record.account_ref !== expectedStreamRef
      || record.cursor !== expectedCursor
      || !Number.isSafeInteger(record.cursor) || record.cursor < 1
      || record.conversation_kind !== "private" && record.conversation_kind !== "group"
      || record.actor_role !== "sender" || record.modality !== "text"
      || record.content_origin !== "source_provided" || record.historical !== false) {
    throw new Error("record_invariant_failed");
  }
  for (const field of ["record_id", "external_ref", "account_ref", "conversation_ref", "sender_ref",
    "content", "source_ref", "extraction_method"]) requireString(record[field], field);
  const opaquePattern = /^hmac:v1:[a-f0-9]{64}$/;
  for (const field of ["record_id", "external_ref", "account_ref", "conversation_ref", "sender_ref"]) {
    if (!opaquePattern.test(record[field])) throw new Error("record_opaque_reference_invalid");
  }
  if (record.source_ref !== `surfcore://qq/message/${record.external_ref}`) {
    throw new Error("record_source_reference_invalid");
  }
  if (!isIsoDate(record.observed_at) || !isIsoDate(record.received_at)) throw new Error("record_timestamp_invalid");
  if (record.extraction_method !== EXTRACTION_METHOD || record.content.length > 16000) {
    throw new Error("record_content_limit_invalid");
  }
  const coverage = record.coverage;
  if (!coverage || typeof coverage !== "object" || Array.isArray(coverage)
      || Object.keys(coverage).length !== COVERAGE_FIELDS.size
      || Object.keys(coverage).some((key) => !COVERAGE_FIELDS.has(key))
      || coverage.modality !== "text" || coverage.extraction_method !== EXTRACTION_METHOD
      || typeof coverage.complete !== "boolean"
      || coverage.start_ms !== null || coverage.end_ms !== null
      || !Array.isArray(coverage.missing_ranges_ms) || coverage.missing_ranges_ms.length !== 0
      || !Array.isArray(coverage.notes) || coverage.notes.some((note) => typeof note !== "string")) {
    throw new Error("record_coverage_invalid");
  }
  return record;
}

function toIsoTime(value, fallback) {
  if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
    const date = new Date(value * 1000);
    if (Number.isFinite(date.getTime())) return date.toISOString();
  }
  return fallback;
}

/**
 * A conservative reference journal. The host must supply a Windows/Linux ACL
 * hardening callback and a dedicated random HMAC key. It does not provision
 * secrets or claim OS-level isolation itself.
 */
export function createObservationJournal({
  directory,
  accountId,
  hmacKey,
  config,
  secureDirectory,
  now = () => new Date(),
  maxBytes = 64 * 1024 * 1024,
  log = () => {},
}) {
  requireString(directory, "directory");
  requireString(accountId, "accountId");
  if (!Buffer.isBuffer(hmacKey) || hmacKey.length < 32) throw new TypeError("hmacKey must be a 32-byte random Buffer");
  if (typeof secureDirectory !== "function") throw new TypeError("secureDirectory ACL callback is required");
  if (!Number.isSafeInteger(maxBytes) || maxBytes < 1024) throw new RangeError("maxBytes must be at least 1024");
  const filePath = path.join(directory, "qq-observations-v1.jsonl");
  const normalizedConfig = normalizeObservationIngressConfig(config);
  const streamRef = opaqueRef(hmacKey, "qq-account", accountId);
  const state = { opened: false, healthy: true, writable: true, appended: 0, failures: 0, latestCursor: 0, bytes: 0 };
  let handle = null;
  let queue = Promise.resolve();
  let lastFailureLogAt = 0;

  function reportFailure(reason) {
    state.failures += 1;
    state.healthy = false;
    state.writable = false;
    const time = now().getTime();
    if (time - lastFailureLogAt >= 60000) {
      lastFailureLogAt = time;
      try { log(`QQ observation journal degraded: ${reason}`); } catch { /* diagnostics must not affect QQ */ }
    }
  }

  async function recover() {
    let data;
    try { data = await fs.readFile(filePath); }
    catch (error) {
      if (error?.code !== "ENOENT") throw error;
      data = Buffer.alloc(0);
    }
    const lastNewline = data.lastIndexOf(0x0a);
    if (data.length && lastNewline !== data.length - 1) {
      const safeLength = lastNewline + 1;
      const repair = await fs.open(filePath, "r+");
      try { await repair.truncate(safeLength); await repair.sync(); }
      finally { await repair.close(); }
      data = data.subarray(0, safeLength);
    }
    let decoded;
    try { decoded = new TextDecoder("utf-8", { fatal: true }).decode(data); }
    catch { throw new Error("journal_utf8_corrupt"); }
    const lines = data.length ? decoded.slice(0, -1).split("\n") : [];
    let cursor = 0;
    for (const line of lines) {
      let record;
      try {
        record = JSON.parse(line);
        if (JSON.stringify(record) !== line) throw new Error("non_canonical_json");
      } catch { throw new Error("journal_complete_line_corrupt"); }
      validateRecord(record, streamRef, cursor + 1);
      cursor = record.cursor;
    }
    state.latestCursor = cursor;
    state.bytes = data.length;
  }

  async function open() {
    if (state.opened) return;
    await fs.mkdir(directory, { recursive: true });
    await secureDirectory(directory);
    await recover();
    handle = await fs.open(filePath, "a+");
    state.opened = true;
    state.healthy = true;
    state.writable = state.bytes < maxBytes;
  }

  function capture(event, { conversationKind, denyUsers = [], denyConversations = [] } = {}) {
    const operation = queue.then(async () => {
      if (!state.opened || !state.healthy || !state.writable) {
        return { captured: false, reason: "journal_unavailable" };
      }
      const conversationId = conversationKind === "private" ? event?.user_id : event?.group_id;
      const senderId = conversationKind === "private" ? event?.user_id : event?.sender?.user_id ?? event?.user_id;
      const decision = evaluateIncomingObservation({
        config: normalizedConfig, conversationKind, conversationId, senderId, selfId: event?.self_id,
        event, denyUsers, denyConversations,
      });
      if (!decision.allowed) return { captured: false, reason: decision.reason };
      const sourceMessageId = event?.message_id ?? event?.msg_id ?? event?.message_seq;
      if (sourceMessageId == null || String(sourceMessageId).trim() === "") {
        return { captured: false, reason: "missing_source_message_id" };
      }
      const extracted = extractIncomingText(event?.message, normalizedConfig.maxRecordChars);
      if (!extracted.accepted) return { captured: false, reason: extracted.reason };
      const receivedAt = now().toISOString();
      const observedAt = toIsoTime(event?.time, receivedAt);
      const identityInput = `${conversationKind}\0${conversationId}\0${sourceMessageId}`;
      const conversationRef = opaqueRef(hmacKey, `qq-conversation:${conversationKind}`, conversationId);
      const senderRef = opaqueRef(hmacKey, "qq-sender", senderId);
      const externalRef = opaqueRef(hmacKey, "qq-source-message", identityInput);
      const recordId = opaqueRef(hmacKey, "qq-record", identityInput);
      const cursor = state.latestCursor + 1;
      const record = {
        schema_version: 1,
        platform: "qq",
        record_id: recordId,
        cursor,
        external_ref: externalRef,
        observation_kind: "qq.message.incoming",
        account_ref: streamRef,
        conversation_kind: conversationKind,
        conversation_ref: conversationRef,
        sender_ref: senderRef,
        actor_role: "sender",
        content_origin: "source_provided",
        modality: "text",
        content: extracted.content,
        source_ref: `surfcore://qq/message/${externalRef}`,
        observed_at: observedAt,
        received_at: receivedAt,
        extraction_method: EXTRACTION_METHOD,
        historical: false,
        coverage: {
          modality: "text",
          extraction_method: EXTRACTION_METHOD,
          complete: extracted.complete,
          start_ms: null,
          end_ms: null,
          missing_ranges_ms: [],
          notes: extracted.notes,
        },
      };
      validateRecord(record, streamRef, cursor);
      const line = Buffer.from(`${JSON.stringify(record)}\n`, "utf8");
      if (state.bytes + line.length > maxBytes) {
        state.failures += 1;
        state.writable = false;
        const time = now().getTime();
        if (time - lastFailureLogAt >= 60000) {
          lastFailureLogAt = time;
          try { log("QQ observation journal capacity reached; capture paused without deleting prior records"); } catch { /* diagnostics must not affect QQ */ }
        }
        return { captured: false, reason: "journal_capacity_reached" };
      }
      try {
        await handle.writeFile(line);
        await handle.sync();
        state.bytes += line.length;
        state.latestCursor = cursor;
        state.appended += 1;
        return { captured: true, cursor, recordId };
      } catch (error) {
        reportFailure("journal_append_failed");
        return { captured: false, reason: "journal_append_failed" };
      }
    });
    queue = operation.catch(() => {});
    return operation;
  }

  function readPage({ afterCursor = 0, limit = 100 } = {}) {
    if (!Number.isSafeInteger(afterCursor) || afterCursor < 0) throw new TypeError("afterCursor must be a non-negative integer");
    if (!Number.isSafeInteger(limit) || limit < 1 || limit > 500) throw new RangeError("limit must be from 1 to 500");
    const operation = queue.then(async () => {
      if (!state.opened || !state.healthy) throw new Error("journal_unavailable");
      if (afterCursor > state.latestCursor) throw new RangeError("afterCursor exceeds latest cursor");
      const data = await fs.readFile(filePath, "utf8");
      const records = [];
      for (const line of data.split("\n")) {
        if (!line) continue;
        const record = JSON.parse(line);
        if (record.cursor > afterCursor && records.length < limit) records.push(record);
      }
      const nextCursor = records.length ? records[records.length - 1].cursor : afterCursor;
      return { schema_version: 1, stream_ref: streamRef, after_cursor: afterCursor, next_cursor: nextCursor, records };
    });
    queue = operation.catch(() => {});
    return operation;
  }

  async function close() {
    await queue;
    if (handle) {
      await handle.sync().catch(() => {});
      await handle.close();
      handle = null;
    }
    state.opened = false;
  }

  function health() {
    return Object.freeze({
      schemaVersion: 1,
      opened: state.opened,
      healthy: state.healthy,
      writable: state.writable,
      latestCursor: state.latestCursor,
      appended: state.appended,
      failures: state.failures,
    });
  }

  return Object.freeze({ open, capture, readPage, close, health, streamRef });
}
