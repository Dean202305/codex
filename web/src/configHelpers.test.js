import assert from "node:assert/strict";
import { test } from "node:test";

import { buildProviderConfig } from "./configHelpers.js";

test("switching from local model to custom model clears the default local model name", () => {
  const config = {
    model: {
      provider: "local-qwen",
      base_url: "https://api.example.com/v1",
      api_key: "test-key",
      model: "qwen3.5-local",
      timeout_seconds: 120,
      allow_without_model: false,
      fallback_to_local_when_unavailable: true,
      local: {}
    }
  };

  const next = buildProviderConfig(config, "openai-compatible");

  assert.equal(next.model.provider, "openai-compatible");
  assert.equal(next.model.model, "");
  assert.equal(next.model.allow_without_model, false);
  assert.equal(next.model.fallback_to_local_when_unavailable, true);
});

test("switching to local model uses the local model defaults", () => {
  const config = {
    model: {
      provider: "openai-compatible",
      base_url: "https://api.example.com/v1",
      api_key: "test-key",
      model: "gpt-4.1-mini",
      timeout_seconds: 60,
      allow_without_model: true,
      fallback_to_local_when_unavailable: true,
      local: {}
    }
  };

  const next = buildProviderConfig(config, "local-qwen");

  assert.equal(next.model.provider, "local-qwen");
  assert.equal(next.model.model, "qwen3.5-local");
  assert.equal(next.model.timeout_seconds, 120);
  assert.equal(next.model.allow_without_model, false);
  assert.equal(next.model.fallback_to_local_when_unavailable, true);
});

test("custom model keeps disabled local fallback when explicitly turned off", () => {
  const config = {
    model: {
      provider: "openai-compatible",
      base_url: "https://api.example.com/v1",
      api_key: "test-key",
      model: "custom-model",
      timeout_seconds: 60,
      allow_without_model: false,
      fallback_to_local_when_unavailable: false,
      local: {}
    }
  };

  const next = buildProviderConfig(config, "openai-compatible");

  assert.equal(next.model.fallback_to_local_when_unavailable, false);
  assert.equal(next.model.allow_without_model, false);
});
