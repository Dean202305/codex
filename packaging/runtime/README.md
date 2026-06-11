# Local Runtime Binaries

This directory is for bundled `llama-server` binaries used by the local Qwen model mode.

Required layout:

```text
packaging/runtime/
  macos-arm64/llama-server
  macos-x64/llama-server
  windows-x64/llama-server.exe
```

If a runtime build produces supporting `.dll` or `.dylib` files, keep them in the same platform folder. The packaging specs include every file under `packaging/runtime` as resource files so the directory layout is preserved inside the app.

The lightweight app bundle includes only the runtime binary. For a fully offline Windows package, build with `-BundleLocalModel` and provide the GGUF file at `packaging/models/qwen/Qwen3.5-9B-Q4_K_M.gguf` or set `LOCAL_QWEN_MODEL_PATH`.

When a bundled model is present, the app automatically registers it on first Windows launch and uses it directly from the installation directory. The user does not need to download the model inside the app.

The Windows installer also includes a WebView2 check. If Microsoft Edge WebView2 Runtime is missing and the user keeps the installer task selected, the installer downloads and installs it before launching the app.

Build scripts check the runtime binary for the target platform before packaging. For development-only UI builds without the runtime, set `ALLOW_MISSING_LOCAL_RUNTIME=1`.
