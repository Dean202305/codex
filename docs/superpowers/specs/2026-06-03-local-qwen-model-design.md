# 本地 Qwen 模型集成设计

## 背景

当前简历筛选工具支持 OpenAI 兼容 API，模型配置依赖用户填写 API 地址、API Key 和模型名。新需求要求软件内增加本地模型模式：优先使用通义千问 Qwen3.5 本地化模型；当本机没有模型文件时，先提示用户确认需要下载的内容，用户确认后自动联网下载安装，安装完成后检测模型是否可用。同时保留自定义模型接口，并产出 macOS 和 Windows 两个本地版本。

Qwen 官方本地运行文档推荐用 GGUF 模型文件配合 llama.cpp 运行，`llama-server` 可提供 OpenAI 兼容接口。因此本次设计不重写模型调用协议，而是在 App 内管理本地推理运行器和模型文件，后端继续通过 OpenAI 兼容 `/chat/completions` 调用模型。

## 目标

1. API 配置页支持在“本地模型”和“自定义模型”之间切换。
2. 本地模型模式默认使用 Qwen3.5 GGUF 模型文件和内置 `llama-server` 推理运行器。
3. 如果本机缺少本地模型，先弹出确认提示，展示模型名称、下载大小、保存路径、网络需求和磁盘占用。
4. 用户确认后自动下载、校验、安装模型文件和必要运行组件。
5. 下载和安装过程显示进度，可失败重试，可取消。
6. 安装完成后自动启动本地模型服务，并做健康检查和简短 JSON 输出测试。
7. 本地模型可用时才能进入筛选；不可用时显示明确原因，并允许切回自定义模型。
8. 产出 macOS 和 Windows 两套打包配置。安装包内置推理运行器，模型按需下载。

## 非目标

1. 不把完整大模型权重直接塞进默认安装包。模型文件通常很大，默认安装包只内置运行器和下载管理能力。
2. 不承诺所有电脑都能流畅运行同一个模型。本地模型是否可用取决于系统、CPU 架构、内存、磁盘和可用加速能力。
3. 不在 macOS 本机直接验证 Windows 安装包运行结果。Windows 构建脚本和配置会补齐，最终 Windows 产物需要在 Windows 电脑或 CI 环境构建测试。
4. 不替换现有自定义 API 模式。用户仍可接入阿里云百炼、OpenAI 兼容服务、Ollama、LM Studio 或其他私有模型接口。

## 用户流程

1. 打开 App，进入 API 配置页。
2. 选择“本地模型”。
3. App 检查本地运行器和模型文件：
   - 运行器存在、模型存在：显示“本地模型已安装”，允许检测或直接使用。
   - 运行器存在、模型缺失：弹出下载确认。
   - 运行器缺失：提示当前安装包不完整，显示修复建议。
4. 下载确认弹窗展示：
   - 模型：Qwen3.5 本地 GGUF 模型。
   - 用途：用于简历岗位匹配、评分、分类理由生成。
   - 保存位置：应用数据目录下的 `models/qwen`。
   - 下载方式：联网下载，支持失败重试。
   - 注意事项：需要足够磁盘空间和内存，低配电脑可能运行较慢。
5. 用户点击确认后，App 开始下载模型文件，展示下载进度、速度、剩余大小和当前步骤。
6. 下载完成后，App 校验文件大小和校验值；校验通过后写入模型清单。
7. App 启动本地 `llama-server`，等待健康检查通过。
8. App 发送一次测试请求，要求模型返回简单 JSON。通过后显示“本地模型可用”。
9. 用户进入后续岗位配置、文件上传和筛选流程。

## 配置结构

`model.provider` 从单一值扩展为两类：

```yaml
model:
  provider: "local-qwen"
  base_url: ""
  api_key: ""
  model: "qwen3.5-local"
  timeout_seconds: 120
  temperature: 0.1
  allow_without_model: false
  local:
    runtime: "llama.cpp"
    model_family: "qwen3.5"
    model_display_name: "Qwen3.5 本地模型"
    model_path: ""
    manifest_path: "models/qwen/manifest.json"
    host: "127.0.0.1"
    port: 18080
    context_size: 8192
    threads: 0
    gpu_layers: "auto"
    auto_start: true
    auto_download: false
```

自定义模型模式继续使用：

```yaml
model:
  provider: "openai-compatible"
  base_url: "https://example.com/v1"
  api_key: ""
  model: ""
  timeout_seconds: 60
  temperature: 0.1
  allow_without_model: false
```

配置兼容策略：

- 老配置没有 `provider` 时按 `openai-compatible` 读取。
- 本地模式下 `api_key` 不再必填。
- 本地模式下运行时生成 `base_url=http://127.0.0.1:<port>/v1`，模型名使用本地服务可识别名称。
- `allow_without_model` 仅作为用户显式兜底；默认不建议开启，避免筛选结果全部进入人工二筛。

## 后端组件

新增 `local_model.py`：

- 解析当前系统和 CPU 架构，选择对应的 `llama-server` 可执行文件。
- 管理应用数据目录，例如 macOS 使用 `~/Library/Application Support/ResumeScreening`，Windows 使用 `%APPDATA%/ResumeScreening`。
- 读取本地模型清单，判断模型是否已安装。
- 生成下载计划，包含 URL、目标路径、文件大小、校验值和展示名称。
- 执行下载、临时文件写入、断点或失败重试、校验、原子替换。
- 启动和停止本地 `llama-server` 子进程。
- 做健康检查和模型测试。

调整 `model_client.py`：

- 对 `local-qwen` provider 先请求本地模型管理器确保服务可用。
- 服务启动后复用现有 OpenAI 兼容请求代码。
- 本地模型请求超时时，给出“本地模型启动或推理超时”的明确错误。

调整 `precheck.py`：

- 自定义模型模式检查 API 地址、模型名和 API Key。
- 本地模型模式检查运行器、模型文件、端口占用和可启动性。
- 模型缺失时返回可恢复状态，不直接失败；前端据此显示下载确认。

新增 Web API：

- `GET /api/local-model/status`：返回运行器、模型、服务和测试状态。
- `GET /api/local-model/download-plan`：返回需要下载的内容。
- `POST /api/local-model/download`：开始下载。
- `GET /api/local-model/download/{task_id}`：查询下载进度。
- `POST /api/local-model/download/{task_id}/cancel`：取消下载。
- `POST /api/local-model/check`：启动本地服务并执行可用性测试。
- `POST /api/local-model/stop`：停止本地模型服务。

## 前端结构

API 配置页改为双模式布局：

- 顶部使用分段选择：`本地模型`、`自定义模型`。
- 本地模型卡片显示安装状态、模型名称、占用空间、服务状态、检测按钮。
- 缺少模型时显示“下载并安装本地模型”按钮，点击后打开确认弹窗。
- 下载弹窗包含模型说明、保存位置、空间提醒、确认按钮和取消按钮。
- 下载中显示进度条、速度、已下载大小、日志。
- 安装成功后弹出可用性检测结果。
- 自定义模型卡片保留 API 地址、API Key、模型名、超时时间和检测能力。

结果页和筛选流程不因 provider 变化而改变。模型输出仍走统一 JSON 解析和现有结果表格展示。

## 下载和校验策略

模型文件不能直接写入最终路径。下载流程使用：

1. 创建下载任务。
2. 写入 `.part` 临时文件。
3. 下载完成后校验文件大小和 SHA256。
4. 校验成功后移动到最终模型目录。
5. 写入 `manifest.json`，记录模型名称、版本、文件路径、校验值、安装时间和来源。
6. 校验失败时删除临时文件并提示重试。

下载源先采用可配置清单，不把 URL 写死在 UI。后端提供默认清单，后续可以更新模型版本或换镜像源。

## 打包方案

macOS：

- 保留现有 PyInstaller `.app` 和 DMG 构建流程。
- 在 macOS 包内放入对应架构的 `llama-server`。
- Apple Silicon 和 Intel Mac 需要区分二进制，首版优先当前机器架构，后续可扩展 universal 或双包。

Windows：

- 新增 PyInstaller Windows spec。
- 新增 PowerShell 构建脚本。
- 包内放入 Windows x64 版本 `llama-server.exe`。
- 产物形态优先 `.zip` 或单目录 `.exe` 包，后续可补 NSIS/MSIX 安装器。

跨平台运行器目录约定：

```text
packaging/runtime/
  macos-arm64/llama-server
  macos-x64/llama-server
  windows-x64/llama-server.exe
```

构建脚本会检查当前平台需要的运行器是否存在。缺失时构建失败并提示下载或放置路径。

## 错误处理

- 模型缺失：提示用户下载，不开始筛选。
- 用户取消下载：保持当前页面状态，不修改模型配置。
- 下载失败：显示网络错误、HTTP 状态或磁盘写入错误，允许重试。
- 校验失败：删除临时文件，提示文件可能损坏。
- 磁盘空间不足：下载前阻止并提示需要释放空间。
- 端口占用：尝试换备用端口；仍失败则提示用户关闭占用程序或切换自定义模型。
- 启动超时：停止子进程，提示本机性能可能不足或模型不兼容。
- 推理超时：提示调大超时时间或换用自定义模型。
- 本地服务崩溃：记录日志，筛选任务失败项写入明确模型失败原因。

## 测试计划

后端：

- 配置兼容测试：旧配置、自定义模型、本地模型。
- 本地模型状态测试：模型缺失、模型存在、运行器缺失。
- 下载计划测试：返回模型名称、目标路径、大小和校验字段。
- 下载任务测试：成功、取消、失败、校验失败。
- 本地服务命令构造测试：macOS、Windows 路径和端口。
- 预检测试：本地模型缺失可恢复、本地模型可用、自定义模型缺失失败。
- 模型客户端测试：本地 provider 能复用 OpenAI 兼容调用。

前端：

- 本地/自定义模式切换。
- 模型缺失时下载确认弹窗。
- 下载进度展示和取消。
- 安装完成后的可用性提示。
- 自定义模型配置不受影响。
- 前端构建通过。

打包：

- macOS 构建脚本能检查并复制运行器。
- Windows 构建脚本和 spec 存在并能在 Windows 环境执行。
- macOS DMG 生成后可启动 App。
- Windows 产物需要在 Windows 电脑或 CI 上做最终启动验证。

## 参考资料

- Qwen 官方本地运行文档：`https://qwen.readthedocs.io/en/stable/run_locally/llama.cpp.html`
- Alibaba Qwen3.5 发布说明：`https://www.alibabagroup.com/en-US/document-1960233590314762240`
