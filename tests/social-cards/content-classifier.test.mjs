import { describe, it, mock } from "node:test";
import assert from "node:assert/strict";

// We test classifyTopic by injecting a mock OpenAI client
import { classifyTopic, CLASSIFIER_SYSTEM_PROMPT } from "../../scripts/social-cards/content-classifier.mjs";

function makeMockClient(responseJson) {
  return {
    chat: {
      completions: {
        create: mock.fn(async () => ({
          choices: [{ message: { content: JSON.stringify(responseJson) } }],
        })),
      },
    },
  };
}

describe("classifyTopic", () => {
  it("returns parsed classification from GPT-4o response", async () => {
    const expected = {
      domain: "macro", subtype: "geopolitics", hasScene: true,
      mood: "tense", visualDirection: "documentary-photo",
      colorHints: ["desaturated warm", "muted"],
      moodHints: ["tense", "watchful"],
      subjectHints: "oil tankers in strait",
      safeZoneStrategy: "atmospheric-fade",
    };
    const client = makeMockClient(expected);
    const result = await classifyTopic({
      topic: "美伊局势进入危险72小时",
      openai: client,
    });
    assert.equal(result.domain, "macro");
    assert.equal(result.visualDirection, "documentary-photo");
    assert.equal(client.chat.completions.create.mock.callCount(), 1);
  });

  it("validates required fields and rejects bad response", async () => {
    const client = makeMockClient({ domain: "macro" }); // missing fields
    await assert.rejects(
      () => classifyTopic({ topic: "test", openai: client }),
      /missing required field/i
    );
  });
});

describe("CLASSIFIER_SYSTEM_PROMPT", () => {
  it("mentions all three domains", () => {
    assert.match(CLASSIFIER_SYSTEM_PROMPT, /macro/);
    assert.match(CLASSIFIER_SYSTEM_PROMPT, /tech/);
    assert.match(CLASSIFIER_SYSTEM_PROMPT, /growth/);
  });
});
