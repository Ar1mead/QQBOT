import assert from "node:assert/strict";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  evaluateIncomingObservation,
  extractIncomingText,
  normalizeObservationIngressConfig,
} from "./observation-policy.mjs";
import { createObservationJournal } from "./observation-journal.mjs";

function config(overrides = {}) {
  return normalizeObservationIngressConfig({
    enabled: true,
    private: { enabled: true, conversationAllowlist: ["friend-1"] },
    groups: { enabled: true, conversationAllowlist: ["group-1"] },
    ...overrides,
  });
}

function privateEvent(overrides = {}) {
  return {
    post_type: "message",
    message_type: "private",
    self_id: "bot-1",
    user_id: "friend-1",
    message_id: 101,
    time: 1794988800,
    message: [{ type: "text", data: { text: "hello from QQ" } }],
    ...overrides,
  };
}

function groupEvent(overrides = {}) {
  return {
    post_type: "message",
    message_type: "group",
    self_id: "bot-1",
    user_id: "group-1",
    group_id: "group-1",
    message_id: 202,
    time: 1794988800,
    sender: { user_id: "member-2" },
    message: [{ type: "text", data: { text: "group message" } }],
    ...overrides,
  };
}

async function fixture(t, options = {}) {
  const directory = await fs.mkdtemp(path.join(os.tmpdir(), "surfcore-qq-journal-"));
  const journal = createObservationJournal({
    directory,
    accountId: "bot-account-1",
    hmacKey: Buffer.alloc(32, 7),
    config: options.config ?? config(),
    secureDirectory: options.secureDirectory ?? (async () => {}),
    maxBytes: options.maxBytes ?? 64 * 1024,
    now: options.now ?? (() => new Date("2026-11-18T08:00:00.000Z")),
    log: options.log ?? (() => {}),
  });
  await journal.open();
  t.after(async () => {
    await journal.close().catch(() => {});
    await fs.rm(directory, { recursive: true, force: true });
  });
  return { directory, journal };
}

test("defaults disable ingress and empty allowlists never mean allow all", () => {
  const defaults = normalizeObservationIngressConfig();
  assert.equal(defaults.enabled, false);
  assert.deepEqual(defaults.private.conversationAllowlist, []);
  assert.deepEqual(defaults.groups.conversationAllowlist, []);

  const enabledButEmpty = normalizeObservationIngressConfig({
    enabled: true,
    private: { enabled: true, conversationAllowlist: [] },
  });
  const decision = evaluateIncomingObservation({
    config: enabledButEmpty,
    conversationKind: "private",
    conversationId: "friend-1",
    senderId: "friend-1",
    event: privateEvent(),
  });
  assert.equal(decision.allowed, false);
  assert.equal(decision.reason, "kind_not_explicitly_allowed");
});

test("private/group policy is independent and deny lists override allowlists", () => {
  const policy = config({ groups: { enabled: false, conversationAllowlist: ["group-1"] } });
  const privateAllowed = evaluateIncomingObservation({
    config: policy, conversationKind: "private", conversationId: "friend-1",
    senderId: "friend-1", selfId: "bot-1", event: privateEvent(),
  });
  const groupDenied = evaluateIncomingObservation({
    config: policy, conversationKind: "group", conversationId: "group-1",
    senderId: "member-2", selfId: "bot-1", event: groupEvent(),
  });
  const senderDenied = evaluateIncomingObservation({
    config: config(), conversationKind: "private", conversationId: "friend-1",
    senderId: "friend-1", selfId: "bot-1", event: privateEvent(), denyUsers: ["friend-1"],
  });
  assert.equal(privateAllowed.allowed, true);
  assert.equal(groupDenied.allowed, false);
  assert.equal(senderDenied.reason, "sender_denied");
});

test("self-authored, non-message, and mismatched event types are rejected", () => {
  const base = { config: config(), conversationKind: "private", conversationId: "friend-1",
    senderId: "friend-1", selfId: "bot-1" };
  assert.equal(evaluateIncomingObservation({ ...base, senderId: "bot-1", event: privateEvent() }).reason, "self_authored");
  assert.equal(evaluateIncomingObservation({ ...base, event: { ...privateEvent(), post_type: "notice" } }).reason, "not_message_event");
  assert.equal(evaluateIncomingObservation({ ...base, event: { ...privateEvent(), message_type: "group" } }).reason, "conversation_kind_mismatch");
});

test("text extraction records omitted segment coverage and truncation", () => {
  const partial = extractIncomingText([
    { type: "text", data: { text: "hello" } },
    { type: "image", data: { file: "private-path-or-token" } },
  ], 10);
  assert.equal(partial.accepted, true);
  assert.equal(partial.content, "hello");
  assert.equal(partial.complete, false);
  assert.deepEqual(partial.notes, ["unsupported_segments_omitted:image"]);

  const truncated = extractIncomingText("abcdefghijk", 5);
  assert.equal(truncated.content, "abcde");
  assert.equal(truncated.complete, false);
  assert.ok(truncated.notes.includes("text_truncated_at_configured_limit"));
  assert.equal(extractIncomingText([{ type: "image", data: { url: "x" } }]).accepted, false);
});

test("journal captures a DTO accepted by the Python mapper and hides raw QQ identifiers", async (t) => {
  const { directory, journal } = await fixture(t);
  const result = await journal.capture(privateEvent(), { conversationKind: "private" });
  assert.equal(result.captured, true);
  assert.equal(result.cursor, 1);

  const page = await journal.readPage({ afterCursor: 0, limit: 10 });
  assert.equal(page.schema_version, 1);
  assert.equal(page.stream_ref, journal.streamRef);
  assert.equal(page.next_cursor, 1);
  assert.equal(page.records.length, 1);
  const record = page.records[0];
  assert.equal(record.account_ref, page.stream_ref);
  assert.equal(record.observation_kind, "qq.message.incoming");
  assert.equal(record.actor_role, "sender");
  assert.equal(record.historical, false);
  assert.equal(record.coverage.complete, true);
  assert.match(record.record_id, /^hmac:v1:[a-f0-9]{64}$/);

  const bytes = await fs.readFile(path.join(directory, "qq-observations-v1.jsonl"), "utf8");
  assert.equal(bytes.includes("bot-account-1"), false);
  assert.equal(bytes.includes("friend-1"), false);
  assert.equal(bytes.includes('"message_id"'), false);
  assert.equal(bytes.includes("\\"101\\""), false);
});

test("private and group callbacks share one serialized cursor and duplicate source IDs stay stable", async (t) => {
  const { journal } = await fixture(t);
  const results = await Promise.all([
    journal.capture(privateEvent(), { conversationKind: "private" }),
    journal.capture(groupEvent(), { conversationKind: "group" }),
    journal.capture(privateEvent(), { conversationKind: "private" }),
  ]);
  assert.deepEqual(results.map((item) => item.cursor), [1, 2, 3]);
  const page = await journal.readPage({ afterCursor: 0, limit: 10 });
  assert.equal(page.records[0].record_id, page.records[2].record_id);
  assert.equal(page.records[0].cursor, 1);
  assert.equal(page.records[2].cursor, 3);
});

test("unsupported media is marked partial rather than silently treated as complete", async (t) => {
  const { journal } = await fixture(t);
  const event = privateEvent({
    message: [
      { type: "text", data: { text: "caption" } },
      { type: "image", data: { url: "must-not-be-copied" } },
    ],
  });
  const result = await journal.capture(event, { conversationKind: "private" });
  assert.equal(result.captured, true);
  const page = await journal.readPage({ afterCursor: 0 });
  assert.equal(page.records[0].content, "caption");
  assert.equal(page.records[0].coverage.complete, false);
  assert.deepEqual(page.records[0].coverage.notes, ["unsupported_segments_omitted:image"]);
});

test("restart rebuilds cursor and repairs only an incomplete final tail", async (t) => {
  const { directory, journal } = await fixture(t);
  await journal.capture(privateEvent(), { conversationKind: "private" });
  await journal.close();
  await fs.appendFile(path.join(directory, "qq-observations-v1.jsonl"), '{"partial":');

  const reopened = createObservationJournal({
    directory, accountId: "bot-account-1", hmacKey: Buffer.alloc(32, 7),
    config: config(), secureDirectory: async () => {},
  });
  await reopened.open();
  assert.equal(reopened.health().latestCursor, 1);
  assert.equal((await reopened.readPage({ afterCursor: 0 })).records.length, 1);
  await reopened.close();
});

test("a corrupt complete line fails closed instead of being skipped", async (t) => {
  const { directory, journal } = await fixture(t);
  await journal.close();
  await fs.appendFile(path.join(directory, "qq-observations-v1.jsonl"), '{"bad":true}\n');
  const reopened = createObservationJournal({
    directory, accountId: "bot-account-1", hmacKey: Buffer.alloc(32, 7),
    config: config(), secureDirectory: async () => {},
  });
  await assert.rejects(() => reopened.open(), /journal_complete_line_corrupt|record_schema_mismatch/);
});

test("duplicate-key JSON lines are rejected during recovery", async (t) => {
  const { directory, journal } = await fixture(t);
  await journal.capture(privateEvent(), { conversationKind: "private" });
  await journal.close();
  const file = path.join(directory, "qq-observations-v1.jsonl");
  const validLine = (await fs.readFile(file, "utf8")).trimEnd();
  await fs.writeFile(file, validLine.replace("{", '{"schema_version":1,') + "\n");
  const reopened = createObservationJournal({
    directory, accountId: "bot-account-1", hmacKey: Buffer.alloc(32, 7),
    config: config(), secureDirectory: async () => {},
  });
  await assert.rejects(() => reopened.open(), /journal_complete_line_corrupt/);
});

test("capacity stops new capture without truncating prior records and leaves reads available", async (t) => {
  const { directory, journal } = await fixture(t, { maxBytes: 1600 });
  const first = await journal.capture(privateEvent(), { conversationKind: "private" });
  assert.equal(first.captured, true);
  const second = await journal.capture(privateEvent({
    message_id: 303,
    message: [{ type: "text", data: { text: "x".repeat(1500) } }],
  }), { conversationKind: "private" });
  assert.equal(second.reason, "journal_capacity_reached");
  assert.equal(journal.health().healthy, true);
  assert.equal(journal.health().writable, false);
  assert.equal((await journal.readPage({ afterCursor: 0 })).records.length, 1);
  const size = (await fs.stat(path.join(directory, "qq-observations-v1.jsonl"))).size;
  assert.ok(size < 1600);
});

test("ACL hardening callback and a dedicated HMAC key are mandatory", () => {
  assert.throws(() => createObservationJournal({
    directory: "x", accountId: "a", hmacKey: Buffer.alloc(32), config: config(),
  }), /ACL callback is required/);
  assert.throws(() => createObservationJournal({
    directory: "x", accountId: "a", hmacKey: Buffer.alloc(8), config: config(), secureDirectory: async () => {},
  }), /32-byte random Buffer/);
});
