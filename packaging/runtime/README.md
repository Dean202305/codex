# Local Runtime Binaries

This directory is for bundled `llama-server` binaries used by the local Qwen model mode.

Required layout:

```text
packaging/runtime/
  macos-arm64/llama-server
  macos-x64/llama-server
  windows-x64/llama-server.exe
```

The app does not bundle Qwen model weights. It bundles the runtime binary and downloads the selected GGUF model after the user confirms in the app.

Build scripts check the runtime binary for the target platform before packaging. For development-only UI builds without the runtime, set `ALLOW_MISSING_LOCAL_RUNTIME=1`.
