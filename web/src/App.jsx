import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, CircleAlert, FileSpreadsheet, KeyRound, Loader2, Play, Save } from "lucide-react";

const steps = ["文件路径", "模型配置", "运行前预检", "开始筛选"];

const emptyConfig = {
  resume_dir: "",
  job_book: "",
  result_book: "",
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
    allow_without_model: true
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
  return { ...emptyConfig, ...config, model: { ...emptyConfig.model, ...config.model } };
}

export function App() {
  const [step, setStep] = useState(0);
  const [config, setConfig] = useState(emptyConfig);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [precheck, setPrecheck] = useState(null);
  const [run, setRun] = useState(null);
  const [runId, setRunId] = useState("");

  useEffect(() => {
    requestJson("/api/config")
      .then((body) => setConfig(mergeConfig(body.config)))
      .catch((exc) => setError(exc.message));
  }, []);

  useEffect(() => {
    if (!runId || run?.state === "completed" || run?.state === "failed") return;
    const timer = window.setInterval(() => {
      requestJson(`/api/runs/${runId}`)
        .then((body) => setRun(body.run))
        .catch((exc) => setError(exc.message));
    }, 1200);
    return () => window.clearInterval(timer);
  }, [runId, run?.state]);

  const progress = useMemo(() => {
    if (!run || !run.total) return 0;
    return Math.round((run.current / run.total) * 100);
  }, [run]);

  function updateField(name, value) {
    setConfig((current) => ({ ...current, [name]: value }));
  }

  function updateModel(name, value) {
    setConfig((current) => ({ ...current, model: { ...current.model, [name]: value } }));
  }

  async function saveConfig() {
    setError("");
    setNotice("");
    try {
      const body = await requestJson("/api/config", { method: "POST", body: JSON.stringify(config) });
      setConfig(mergeConfig(body.config));
      setNotice("配置已保存到本地 config.yaml");
    } catch (exc) {
      setError(exc.message);
    }
  }

  async function runPrecheck() {
    setError("");
    try {
      const body = await requestJson("/api/precheck");
      setPrecheck(body);
      setStep(2);
    } catch (exc) {
      setError(exc.message);
    }
  }

  async function startRun() {
    setError("");
    try {
      const body = await requestJson("/api/runs", { method: "POST", body: "{}" });
      setRun(body.run);
      setRunId(body.run.run_id);
      setStep(3);
    } catch (exc) {
      setError(exc.message);
    }
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div>
          <p className="eyebrow">本地运行</p>
          <h1>简历初筛工具</h1>
        </div>
        <div className="stepper">
          {steps.map((label, index) => (
            <button key={label} className={index === step ? "active" : ""} onClick={() => setStep(index)}>
              {index + 1}. {label}
            </button>
          ))}
        </div>
      </section>

      {notice && <div className="notice success"><CheckCircle2 size={18} />{notice}</div>}
      {error && <div className="notice danger"><CircleAlert size={18} />{error}</div>}

      {step === 0 && (
        <section className="panel">
          <h2><FileSpreadsheet size={22} />文件路径</h2>
          <label>简历文件夹<input value={config.resume_dir} onChange={(event) => updateField("resume_dir", event.target.value)} /></label>
          <label>岗位说明书<input value={config.job_book} onChange={(event) => updateField("job_book", event.target.value)} /></label>
          <label>招聘结果表<input value={config.result_book} onChange={(event) => updateField("result_book", event.target.value)} /></label>
          <div className="actions">
            <button onClick={saveConfig}><Save size={18} />保存配置</button>
            <button className="primary" onClick={() => setStep(1)}>下一步</button>
          </div>
        </section>
      )}

      {step === 1 && (
        <section className="panel">
          <h2><KeyRound size={22} />模型配置</h2>
          <label>API 地址<input value={config.model.base_url} onChange={(event) => updateModel("base_url", event.target.value)} /></label>
          <label>API Key<input type="password" value={config.model.api_key} onChange={(event) => updateModel("api_key", event.target.value)} /></label>
          <label>模型名<input value={config.model.model} onChange={(event) => updateModel("model", event.target.value)} /></label>
          <label>超时时间（秒）<input type="number" value={config.model.timeout_seconds} onChange={(event) => updateModel("timeout_seconds", Number(event.target.value))} /></label>
          <label className="checkbox"><input type="checkbox" checked={config.model.allow_without_model} onChange={(event) => updateModel("allow_without_model", event.target.checked)} />允许无模型运行并进入待人工二筛</label>
          <div className="actions">
            <button onClick={saveConfig}><Save size={18} />保存配置</button>
            <button className="primary" onClick={runPrecheck}>运行预检</button>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="panel">
          <h2>运行前预检</h2>
          {!precheck && <button className="primary" onClick={runPrecheck}>开始预检</button>}
          {precheck && (
            <div className="checks">
              <div className={`summary ${precheck.status}`}>支持格式简历：{precheck.resume_file_count} 个</div>
              {precheck.items.map((item) => <div className={`check ${item.status}`} key={item.name}><strong>{item.name}</strong><span>{item.message}</span></div>)}
              <button className="primary" onClick={startRun}><Play size={18} />开始筛选</button>
            </div>
          )}
        </section>
      )}

      {step === 3 && (
        <section className="panel">
          <h2>{run?.state === "running" ? <Loader2 className="spin" size={22} /> : <Play size={22} />}开始筛选</h2>
          {!run && <button className="primary" onClick={startRun}>开始筛选</button>}
          {run && (
            <>
              <div className="progress"><span style={{ width: `${progress}%` }} /></div>
              <p className="muted">{run.current_file || "等待任务更新"} {run.total ? `${run.current}/${run.total}` : ""}</p>
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
