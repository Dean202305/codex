import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, CloudDownload, Cpu, FileSpreadsheet, KeyRound, Loader2, Play, Plus, RefreshCcw, Save, StopCircle, X } from "lucide-react";
import { buildProviderConfig } from "./configHelpers.js";

const steps = ["模型配置", "文件路径", "运行前预检", "开始筛选"];

const emptyConfig = {
  resume_dir: "",
  job_book: "",
  result_book: "",
  job_aliases: {},
  job_profile_overrides: {},
  default_source_channel: "",
  default_interviewer: "",
  index_path: "data/processed_index.json",
  ocr_command: "tesseract",
  model: {
    provider: "openai-compatible",
    base_url: "",
    api_key: "",
    model: "",
    timeout_seconds: 60,
    temperature: 0.1,
    allow_without_model: false,
    fallback_to_local_when_unavailable: true,
    local: {
      runtime: "llama.cpp",
      model_family: "qwen3.5",
      model_display_name: "Qwen3.5 本地模型",
      model_path: "",
      manifest_path: "models/qwen/manifest.json",
      host: "127.0.0.1",
      port: 18080,
      context_size: 8192,
      threads: 0,
      gpu_layers: "auto",
      auto_start: true,
      auto_download: false
    }
  }
};

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  const body = await response.json();
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail : body.detail?.message || "请求失败");
  }
  return body;
}

function mergeConfig(config) {
  return {
    ...emptyConfig,
    ...config,
    model: {
      ...emptyConfig.model,
      ...config.model,
      local: { ...emptyConfig.model.local, ...config.model?.local }
    }
  };
}

function formatBytes(value = 0) {
  if (!value) return "未知大小";
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`;
  return `${value} B`;
}

function localStatusLabel(state) {
  return {
    ready: "本地模型可用",
    model_missing: "需要下载模型",
    runtime_missing: "运行器缺失"
  }[state] || "等待检测";
}

function environmentStateLabel(state) {
  return {
    ready: "已就绪",
    missing: "需处理",
    error: "异常"
  }[state] || "待检测";
}

function formatJobAliases(aliases = {}) {
  return Object.entries(aliases).map(([source, target]) => `${source}=${target}`).join("\n");
}

function parseJobAliases(text) {
  const aliases = {};
  text.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) return;
    const separator = trimmed.includes("=") ? "=" : ":";
    const index = trimmed.indexOf(separator);
    if (index <= 0) return;
    const source = trimmed.slice(0, index).trim();
    const target = trimmed.slice(index + 1).trim();
    if (source && target) aliases[source] = target;
  });
  return aliases;
}

function withProfileIds(profiles = []) {
  return profiles.map((profile, index) => ({
    ...profile,
    client_id: profile.client_id || `${profile.job_name || "job"}-${profile.sheet_name || "sheet"}-${index}`
  }));
}

function emptyProfileTemplate() {
  return [
    "学历: 未写明",
    "年龄: 未写明",
    "性别: 未写明",
    "工作内容: ",
    "匹配程度: 核心工作内容匹配优先"
  ].join("\n");
}

export function App() {
  const [step, setStep] = useState(0);
  const [config, setConfig] = useState(emptyConfig);
  const [jobAliasText, setJobAliasText] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [precheck, setPrecheck] = useState(null);
  const [run, setRun] = useState(null);
  const [runId, setRunId] = useState("");
  const [localStatus, setLocalStatus] = useState(null);
  const [localEnvironment, setLocalEnvironment] = useState(null);
  const [downloadPlan, setDownloadPlan] = useState(null);
  const [downloadTask, setDownloadTask] = useState(null);
  const [showDownloadConfirm, setShowDownloadConfirm] = useState(false);
  const [checkingLocalModel, setCheckingLocalModel] = useState(false);
  const [savedProvider, setSavedProvider] = useState("");
  const [jobProfiles, setJobProfiles] = useState([]);
  const [profileDrafts, setProfileDrafts] = useState({});
  const [profilesConfirmed, setProfilesConfirmed] = useState(false);

  useEffect(() => {
    requestJson("/api/config")
      .then((body) => {
        const merged = mergeConfig(body.config);
        setConfig(merged);
        setJobAliasText(formatJobAliases(merged.job_aliases));
        setSavedProvider(merged.model.provider);
      })
      .catch((exc) => setError(exc.message));
  }, []);

  useEffect(() => {
    if (!runId || run?.state === "completed" || run?.state === "cancelled" || run?.state === "failed") return;
    const timer = window.setInterval(() => {
      requestJson(`/api/runs/${runId}`)
        .then((body) => setRun(body.run))
        .catch((exc) => setError(exc.message));
    }, 1200);
    return () => window.clearInterval(timer);
  }, [runId, run?.state]);

  useEffect(() => {
    if (step !== 0 || config.model.provider !== "local-qwen" || savedProvider !== "local-qwen") return;
    refreshLocalModelInfo();
  }, [step, config.model.provider, savedProvider]);

  useEffect(() => {
    if (!downloadTask?.task_id || !["queued", "running"].includes(downloadTask.state)) return;
    const timer = window.setInterval(() => {
      requestJson(`/api/local-model/download/${downloadTask.task_id}`)
        .then((body) => {
          setDownloadTask(body.task);
          if (body.task.state === "completed") {
            setNotice("本地模型已安装完成，请点击“检测可用”启动并验证本地服务");
            refreshLocalModelInfo();
          }
          if (body.task.state === "failed") {
            setError(body.task.error || "模型下载失败");
          }
        })
        .catch((exc) => setError(exc.message));
    }, 900);
    return () => window.clearInterval(timer);
  }, [downloadTask?.task_id, downloadTask?.state]);

  const progress = useMemo(() => {
    if (!run || !run.total) return 0;
    return Math.round((run.current / run.total) * 100);
  }, [run]);

  const runStateLabel = {
    queued: "排队中",
    running: "筛选中",
    stopping: "停止中",
    completed: "已完成",
    cancelled: "已取消",
    failed: "失败"
  }[run?.state] || "待开始";

  const runStateTone = run?.state === "failed"
    ? "danger"
    : run?.state === "completed"
      ? "success"
      : run?.state === "cancelled"
        ? "warning"
        : "info";

  function resetPrecheckState() {
    setPrecheck(null);
    setJobProfiles([]);
    setProfileDrafts({});
    setProfilesConfirmed(false);
  }

  function updateField(name, value) {
    resetPrecheckState();
    setConfig((current) => ({ ...current, [name]: value }));
  }

  function updateModel(name, value) {
    resetPrecheckState();
    setConfig((current) => ({ ...current, model: { ...current.model, [name]: value } }));
  }

  function updateLocalModel(name, value) {
    resetPrecheckState();
    setConfig((current) => ({
      ...current,
      model: {
        ...current.model,
        local: { ...current.model.local, [name]: value }
      }
    }));
  }

  async function updateProvider(provider) {
    const nextConfig = buildProviderConfig(config, provider);
    setConfig(nextConfig);
    resetPrecheckState();
    setLocalStatus(null);
    setLocalEnvironment(null);
    setDownloadPlan(null);
    await persistConfig(nextConfig, provider === "local-qwen" ? "已切换到本地模型" : "已切换到自定义模型，请填写 API 地址、API Key 和模型名");
    if (provider === "local-qwen") {
      await refreshLocalModelInfo();
    }
  }

  async function persistConfig(configToSave, successMessage) {
    setError("");
    setNotice("");
    try {
      const body = await requestJson("/api/config", { method: "POST", body: JSON.stringify({ ...configToSave, job_aliases: parseJobAliases(jobAliasText) }) });
      const merged = mergeConfig(body.config);
      setConfig(merged);
      setJobAliasText(formatJobAliases(merged.job_aliases));
      setSavedProvider(merged.model.provider);
      setNotice(successMessage);
      return merged;
    } catch (exc) {
      setError(exc.message);
      return null;
    }
  }

  async function saveConfig() {
    const merged = await persistConfig(config, "配置已保存到本地 config.yaml");
    if (merged?.model.provider === "local-qwen") {
      await refreshLocalModelInfo();
    }
  }

  async function goToFileStep() {
    const merged = await persistConfig(config, "模型配置已保存");
    if (merged) setStep(1);
  }

  function applyReturnedConfig(returnedConfig) {
    if (!returnedConfig) return null;
    const merged = mergeConfig(returnedConfig);
    setConfig(merged);
    setJobAliasText(formatJobAliases(merged.job_aliases));
    setSavedProvider(merged.model.provider);
    return merged;
  }

  async function loadJobProfiles() {
    const body = await requestJson("/api/job-profiles");
    const profiles = withProfileIds(body.profiles || []);
    setJobProfiles(profiles);
    setProfileDrafts(Object.fromEntries(profiles.map((profile) => [profile.client_id, profile.profile || ""])));
    setProfilesConfirmed(profiles.length === 0);
    return profiles;
  }

  async function saveJobProfileDrafts() {
    setError("");
    try {
      const payloadProfiles = jobProfiles
        .map((profile) => ({
          job_name: profile.job_name.trim(),
          profile: profileDrafts[profile.client_id] || ""
        }))
        .filter((profile) => profile.job_name && profile.profile.trim());
      if (payloadProfiles.length === 0) {
        setError("请至少保留一个岗位画像");
        return;
      }
      const body = await requestJson("/api/job-profiles", {
        method: "POST",
        body: JSON.stringify({
          profiles: payloadProfiles
        })
      });
      applyReturnedConfig(body.config);
      const profiles = withProfileIds(body.profiles || []);
      setJobProfiles(profiles);
      setProfileDrafts(Object.fromEntries(profiles.map((profile) => [profile.client_id, profile.profile || ""])));
      setProfilesConfirmed(true);
      setNotice("岗位画像已保存并确认");
    } catch (exc) {
      setError(exc.message);
    }
  }

  function updateProfileDraft(clientId, value) {
    setProfileDrafts((current) => ({ ...current, [clientId]: value }));
    setProfilesConfirmed(false);
  }

  function updateProfileName(clientId, value) {
    setJobProfiles((current) => current.map((profile) => (
      profile.client_id === clientId ? { ...profile, job_name: value } : profile
    )));
    setProfilesConfirmed(false);
  }

  function addJobProfileCard() {
    const clientId = `custom-${Date.now()}-${jobProfiles.length + 1}`;
    const nextProfile = {
      client_id: clientId,
      job_name: `自定义岗位${jobProfiles.length + 1}`,
      sheet_name: "手动新增",
      profile: emptyProfileTemplate(),
      source: "custom",
      is_custom_only: true,
      is_complete: true,
      missing_fields: []
    };
    setJobProfiles((current) => [...current, nextProfile]);
    setProfileDrafts((current) => ({ ...current, [clientId]: emptyProfileTemplate() }));
    setProfilesConfirmed(false);
  }

  async function runPrecheck() {
    setError("");
    try {
      const saved = await persistConfig(config, "配置已保存，正在运行预检");
      if (!saved) return;
      const modelCheck = await requestJson("/api/model/check", { method: "POST", body: "{}" });
      applyReturnedConfig(modelCheck.config);
      if (modelCheck.message) {
        if (modelCheck.available || modelCheck.switched) {
          setNotice(modelCheck.message);
        } else {
          setError(modelCheck.message);
        }
      }
      const body = await requestJson("/api/precheck");
      setPrecheck(body);
      await loadJobProfiles();
      setStep(2);
    } catch (exc) {
      setError(exc.message);
    }
  }

  async function loadLocalModelStatus() {
    try {
      const body = await requestJson("/api/local-model/status");
      setLocalStatus(body.status);
    } catch (exc) {
      setLocalStatus(null);
      setError(exc.message);
    }
  }

  async function loadLocalEnvironment() {
    try {
      const body = await requestJson("/api/local-model/environment");
      setLocalEnvironment(body.environment);
    } catch (exc) {
      setLocalEnvironment(null);
      setError(exc.message);
    }
  }

  async function loadDownloadPlan() {
    try {
      const body = await requestJson("/api/local-model/download-plan");
      setDownloadPlan(body.plan);
    } catch (exc) {
      setDownloadPlan(null);
      setError(exc.message);
    }
  }

  async function refreshLocalModelInfo() {
    await loadLocalModelStatus();
    await loadDownloadPlan();
    await loadLocalEnvironment();
  }

  async function startLocalModelDownload() {
    setError("");
    setNotice("");
    setShowDownloadConfirm(false);
    try {
      const body = await requestJson("/api/local-model/download", { method: "POST", body: "{}" });
      setDownloadTask(body.task);
      setNotice("已开始下载本地模型");
    } catch (exc) {
      setError(exc.message);
    }
  }

  async function cancelLocalModelDownload() {
    if (!downloadTask?.task_id) return;
    try {
      const body = await requestJson(`/api/local-model/download/${downloadTask.task_id}/cancel`, { method: "POST", body: "{}" });
      setDownloadTask(body.task);
    } catch (exc) {
      setError(exc.message);
    }
  }

  async function checkLocalModel() {
    setCheckingLocalModel(true);
    setError("");
    try {
      const body = await requestJson("/api/local-model/check", { method: "POST", body: "{}" });
      setLocalStatus(body.status);
      await loadLocalEnvironment();
      if (body.available) {
        setNotice("本地模型服务可用");
      } else {
        setError(body.message || "本地模型服务暂不可用");
      }
    } catch (exc) {
      setError(exc.message);
    } finally {
      setCheckingLocalModel(false);
    }
  }

  async function startRun() {
    setError("");
    if (jobProfiles.length > 0 && !profilesConfirmed) {
      setError("请先确认岗位画像，或修改后点击保存并确认岗位画像");
      setStep(2);
      return;
    }
    try {
      const saved = await persistConfig(config, "配置已保存，正在开始筛选");
      if (!saved) return;
      const body = await requestJson("/api/runs", { method: "POST", body: "{}" });
      setRun(body.run);
      setRunId(body.run.run_id);
      setStep(3);
    } catch (exc) {
      setError(exc.message);
    }
  }

  async function cancelRun() {
    if (!runId) return;
    setError("");
    try {
      const body = await requestJson(`/api/runs/${runId}/cancel`, { method: "POST", body: "{}" });
      setRun(body.run);
    } catch (exc) {
      setError(exc.message);
    }
  }

  return (
    <main className="app-shell">
      <section className="topbar glass-surface">
        <div className="brand-block">
          <p className="eyebrow">本地运行</p>
          <h1>简历初筛工具</h1>
        </div>
        <div className={`top-status ${runStateTone}`}>
          <span>{run ? "任务状态" : "当前步骤"}</span>
          <strong>{run ? runStateLabel : steps[step]}</strong>
        </div>
      </section>

      <nav className="stepper glass-surface" aria-label="筛选步骤">
        {steps.map((label, index) => (
          <button key={label} className={index === step ? "active" : ""} onClick={() => setStep(index)}>
            <span className="step-index">{String(index + 1).padStart(2, "0")}</span>
            <span>{label}</span>
          </button>
        ))}
      </nav>

      {notice && <div className="notice success"><CheckCircle2 size={18} />{notice}</div>}
      {error && <div className="notice danger"><CircleAlert size={18} />{error}</div>}
      {showDownloadConfirm && (
        <div className="modal-backdrop">
          <section className="modal panel">
            <button className="icon-button close-button" onClick={() => setShowDownloadConfirm(false)} aria-label="关闭"><X size={18} /></button>
            <div className="panel-title">
              <span className="title-icon"><CloudDownload size={22} /></span>
              <div>
                <p className="eyebrow">LOCAL MODEL</p>
                <h2>下载本地模型</h2>
              </div>
            </div>
            <div className="download-detail">
              <div><span>模型</span><strong>{downloadPlan?.display_name || "Qwen3.5 本地模型"}</strong></div>
              <div><span>大小</span><strong>{formatBytes(downloadPlan?.size_bytes)}</strong></div>
              <div><span>保存位置</span><strong>{downloadPlan?.target_path || config.model.local.model_path || "应用模型目录"}</strong></div>
            </div>
            <p className="muted">确认后会联网下载模型文件。下载完成后软件会自动安装；请点击“检测可用”启动并验证本地服务。</p>
            <div className="actions">
              <button onClick={() => setShowDownloadConfirm(false)}>取消</button>
              <button className="primary" onClick={startLocalModelDownload}><CloudDownload size={18} />确认下载</button>
            </div>
          </section>
        </div>
      )}

      {step === 1 && (
        <section className="panel work-panel">
          <div className="panel-title">
            <span className="title-icon"><FileSpreadsheet size={22} /></span>
            <div>
              <p className="eyebrow">STEP 02</p>
              <h2>文件路径</h2>
            </div>
          </div>
          <div className="form-grid">
            <label>简历文件夹<input value={config.resume_dir} onChange={(event) => updateField("resume_dir", event.target.value)} /></label>
            <label>岗位说明书<input value={config.job_book} onChange={(event) => updateField("job_book", event.target.value)} /></label>
            <label>招聘结果表<input value={config.result_book} onChange={(event) => updateField("result_book", event.target.value)} /></label>
            <label className="full-row">岗位别名映射<textarea value={jobAliasText} onChange={(event) => setJobAliasText(event.target.value)} placeholder={"后端开发工程师=全栈\n后端开发实习岗=全栈"} /></label>
          </div>
          <div className="actions">
            <button onClick={saveConfig}><Save size={18} />保存配置</button>
            <button className="primary" onClick={runPrecheck}>运行预检</button>
          </div>
        </section>
      )}

      {step === 0 && (
        <section className="panel work-panel">
          <div className="panel-title">
            <span className="title-icon"><KeyRound size={22} /></span>
            <div>
              <p className="eyebrow">STEP 01</p>
              <h2>模型配置</h2>
            </div>
          </div>
          <div className="provider-toggle" role="tablist" aria-label="模型模式">
            <button className={config.model.provider === "local-qwen" ? "active" : ""} onClick={() => updateProvider("local-qwen")}><Cpu size={18} />本地模型</button>
            <button className={config.model.provider === "openai-compatible" ? "active" : ""} onClick={() => updateProvider("openai-compatible")}><KeyRound size={18} />自定义模型</button>
          </div>
          {config.model.provider === "local-qwen" ? (
            <div className="local-model-grid">
              {localEnvironment && (
                <div className={`environment-card ${localEnvironment.ready ? "ready" : "pending"}`}>
                  <div className="environment-head">
                    <div>
                      <span>安装环境检测</span>
                      <strong>{localEnvironment.ready ? "全部就绪" : "需要处理"}</strong>
                    </div>
                    <button onClick={refreshLocalModelInfo}><RefreshCcw size={18} />刷新</button>
                  </div>
                  <div className="environment-items">
                    {localEnvironment.items.map((item) => (
                      <div className={`environment-item ${item.state}`} key={item.id}>
                        <div className="environment-copy">
                          <strong>{item.label}</strong>
                          <span>{item.message}</span>
                          <small>{item.path}</small>
                        </div>
                        <div className="environment-action">
                          <span>{environmentStateLabel(item.state)}</span>
                          {item.action === "download_model" && (
                            <button className="primary small-button" onClick={() => setShowDownloadConfirm(true)}>
                              <CloudDownload size={16} />下载
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div className={`local-model-card ${localStatus?.state || "unknown"}`}>
                <div>
                  <span>本地模型状态</span>
                  <strong>{localStatusLabel(localStatus?.state)}</strong>
                </div>
                <p>{localStatus?.message || "选择本地模型后可检测安装状态"}</p>
                <div className="actions compact-actions">
                  <button onClick={refreshLocalModelInfo}><RefreshCcw size={18} />刷新</button>
                  {localStatus?.state === "model_missing" && <button className="primary" onClick={() => setShowDownloadConfirm(true)}><CloudDownload size={18} />下载并安装</button>}
                  <button onClick={checkLocalModel} disabled={checkingLocalModel || localStatus?.state !== "ready"}>{checkingLocalModel ? <Loader2 className="spin" size={18} /> : <CheckCircle2 size={18} />}检测可用</button>
                </div>
              </div>
              <div className="form-grid local-settings">
                <label>模型名<input value={config.model.model} onChange={(event) => updateModel("model", event.target.value)} /></label>
                <label>服务端口<input type="number" value={config.model.local.port} onChange={(event) => updateLocalModel("port", Number(event.target.value))} /></label>
                <label>模型文件路径<input value={config.model.local.model_path || ""} onChange={(event) => updateLocalModel("model_path", event.target.value)} placeholder={downloadPlan?.target_path || "自动保存到应用模型目录"} /></label>
                <label>超时时间（秒）<input type="number" value={config.model.timeout_seconds} onChange={(event) => updateModel("timeout_seconds", Number(event.target.value))} /></label>
                <label>上下文长度<input type="number" value={config.model.local.context_size} onChange={(event) => updateLocalModel("context_size", Number(event.target.value))} /></label>
                <label>GPU 层数<input value={config.model.local.gpu_layers} onChange={(event) => updateLocalModel("gpu_layers", event.target.value)} /></label>
              </div>
              {downloadTask && (
                <div className={`download-task ${downloadTask.state}`}>
                  <div className="download-task-head">
                    <strong>{downloadTask.display_name}</strong>
                    <span>{downloadTask.state}</span>
                  </div>
                  <div className="progress"><span style={{ width: `${downloadTask.total_bytes ? Math.round((downloadTask.bytes_downloaded / downloadTask.total_bytes) * 100) : 0}%` }} /></div>
                  <p className="muted">{formatBytes(downloadTask.bytes_downloaded)} / {formatBytes(downloadTask.total_bytes)} · {downloadTask.message}</p>
                  {["queued", "running"].includes(downloadTask.state) && <button className="danger-button" onClick={cancelLocalModelDownload}><StopCircle size={18} />取消下载</button>}
                  {downloadTask.error && <p className="danger-text">{downloadTask.error}</p>}
                </div>
              )}
            </div>
          ) : (
            <div className="form-grid">
              <label>API 地址<input value={config.model.base_url} onChange={(event) => updateModel("base_url", event.target.value)} /></label>
              <label>API Key<input type="password" value={config.model.api_key} onChange={(event) => updateModel("api_key", event.target.value)} /></label>
              <label>模型名<input value={config.model.model} onChange={(event) => updateModel("model", event.target.value)} /></label>
              <label>超时时间（秒）<input type="number" value={config.model.timeout_seconds} onChange={(event) => updateModel("timeout_seconds", Number(event.target.value))} /></label>
              <label className="checkbox full-row">
                <input type="checkbox" checked={Boolean(config.model.fallback_to_local_when_unavailable)} onChange={(event) => updateModel("fallback_to_local_when_unavailable", event.target.checked)} />
                自定义模型不可用时自动使用本地模型
              </label>
            </div>
          )}
          <div className="actions">
            <button onClick={saveConfig}><Save size={18} />保存配置</button>
            <button className="primary" onClick={goToFileStep}>下一步</button>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="panel work-panel">
          <div className="panel-title">
            <span className="title-icon"><CheckCircle2 size={22} /></span>
            <div>
              <p className="eyebrow">STEP 03</p>
              <h2>运行前预检</h2>
            </div>
          </div>
          {!precheck && <button className="primary" onClick={runPrecheck}>开始预检</button>}
          {precheck && (
            <div className="checks">
              <div className={`summary ${precheck.status}`}>
                <span>待处理文件</span>
                <strong>{precheck.resume_file_count}</strong>
                <small>个</small>
              </div>
              {precheck.items.map((item) => <div className={`check ${item.status}`} key={item.name}><strong>{item.name}</strong><span>{item.message}</span></div>)}
              <div className="profile-review">
                <div className="profile-review-head">
                  <div>
                    <p className="eyebrow">JOB PROFILE</p>
                    <h3>岗位画像确认</h3>
                  </div>
                  <div className="profile-review-actions">
                    <button onClick={addJobProfileCard}><Plus size={18} />新增岗位</button>
                    <span className={`confirm-pill ${profilesConfirmed ? "confirmed" : ""}`}>{profilesConfirmed ? "已确认" : "待确认"}</span>
                  </div>
                </div>
                {jobProfiles.length === 0 && <p className="muted">未读取到岗位画像，可以点击新增岗位手动填写。</p>}
                {jobProfiles.map((profile) => (
                  <div className="job-profile-card" key={profile.client_id}>
                    <div className="job-profile-title">
                      {profile.is_custom_only ? (
                        <label className="profile-name-field">
                          岗位名称
                          <input value={profile.job_name} onChange={(event) => updateProfileName(profile.client_id, event.target.value)} />
                        </label>
                      ) : (
                        <strong>{profile.job_name}</strong>
                      )}
                      <span>{profile.source === "custom" ? "自定义画像" : profile.source === "model" ? "模型生成画像" : "规则生成画像"}</span>
                    </div>
                    <textarea
                      value={profileDrafts[profile.client_id] || ""}
                      onChange={(event) => updateProfileDraft(profile.client_id, event.target.value)}
                    />
                    {profile.profile_error && <p className="muted">{profile.profile_error}</p>}
                    {profile.missing_fields?.length > 0 && <p className="muted">缺失项：{profile.missing_fields.join("、")}</p>}
                  </div>
                ))}
              </div>
              <div className="actions">
                {jobProfiles.length > 0 && <button onClick={saveJobProfileDrafts}><Save size={18} />保存并确认岗位画像</button>}
                <button className="primary" onClick={startRun} disabled={jobProfiles.length > 0 && !profilesConfirmed}><Play size={18} />开始筛选</button>
              </div>
            </div>
          )}
        </section>
      )}

      {step === 3 && (
        <section className="panel work-panel">
          <div className="panel-title">
            <span className="title-icon">{run?.state === "running" || run?.state === "stopping" ? <Loader2 className="spin" size={22} /> : <Play size={22} />}</span>
            <div>
              <p className="eyebrow">STEP 04</p>
              <h2>开始筛选</h2>
            </div>
            <span className={`state-pill ${run?.state || "idle"}`}>{runStateLabel}</span>
          </div>
          {!run && <button className="primary" onClick={startRun}>开始筛选</button>}
          {run && (
            <>
              <div className="progress"><span style={{ width: `${progress}%` }} /></div>
              <p className="muted">{run.current_file || "等待任务更新"} {run.total ? `${run.current}/${run.total}` : ""}</p>
              {(run.state === "queued" || run.state === "running" || run.state === "stopping") && (
                <div className="actions run-actions">
                  <button className="danger-button" onClick={cancelRun} disabled={run.state === "stopping"}>
                    <StopCircle size={18} />{run.state === "stopping" ? "停止中" : "停止筛选"}
                  </button>
                </div>
              )}
              <div className="stats">
                {Object.entries(run.stats || {}).map(([key, value]) => <div key={key}><strong>{value}</strong><span>{key}</span></div>)}
              </div>
              <div className="logs">
                {(run.logs || []).map((log, index) => <p key={`${log.timestamp}-${index}`} className={log.level}>{log.message}</p>)}
              </div>
              {run.error && <div className="notice danger">{run.error}</div>}
            </>
          )}
        </section>
      )}
    </main>
  );
}
