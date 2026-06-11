export const LOCAL_PROVIDER = "local-qwen";
export const CUSTOM_PROVIDER = "openai-compatible";
export const DEFAULT_LOCAL_MODEL = "qwen3.5-local";

export function buildProviderConfig(config, provider) {
  const currentModel = config.model || {};
  const switchingFromLocal = currentModel.provider === LOCAL_PROVIDER;
  const defaultLocalName = currentModel.model === DEFAULT_LOCAL_MODEL;
  return {
    ...config,
    model: {
      ...currentModel,
      provider,
      model: provider === LOCAL_PROVIDER
        ? (switchingFromLocal && currentModel.model ? currentModel.model : DEFAULT_LOCAL_MODEL)
        : (switchingFromLocal && defaultLocalName ? "" : currentModel.model),
      timeout_seconds: provider === LOCAL_PROVIDER
        ? Math.max(Number(currentModel.timeout_seconds) || 0, 120)
        : currentModel.timeout_seconds,
      allow_without_model: provider === LOCAL_PROVIDER
        ? false
        : false,
      fallback_to_local_when_unavailable: provider === CUSTOM_PROVIDER
        ? (switchingFromLocal && defaultLocalName ? true : currentModel.fallback_to_local_when_unavailable ?? true)
        : currentModel.fallback_to_local_when_unavailable ?? true
    }
  };
}
