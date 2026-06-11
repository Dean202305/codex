# iOS 26 High Contrast UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the React web interface with an iOS 26-inspired high-contrast workbench style without changing screening behavior.

**Architecture:** Keep the current single React entry point and backend API contracts. Add semantic wrapper classes in `web/src/App.jsx`, replace the stylesheet in `web/src/styles.css`, then run the Vite build so the packaged local app uses the new static assets.

**Tech Stack:** React 18, Vite, lucide-react, CSS.

---

### Task 1: Add Visual Structure Classes

**Files:**
- Modify: `web/src/App.jsx`

- [ ] **Step 1: Add derived run status text**

Inside `App`, after the `progress` memo, add:

```jsx
  const runStateLabel = {
    queued: "排队中",
    running: "筛选中",
    stopping: "停止中",
    completed: "已完成",
    cancelled: "已取消",
    failed: "失败"
  }[run?.state] || "待开始";
```

- [ ] **Step 2: Replace the top-level shell and stepper markup**

Keep the existing event handlers and field bindings. Replace only wrapper class names and add status copy:

```jsx
    <main className="app-shell">
      <section className="topbar glass-surface">
        <div className="brand-block">
          <p className="eyebrow">本地运行</p>
          <h1>简历初筛工具</h1>
          <p className="subhead">配置模型、检查文件、批量筛选并写入本地结果表。</p>
        </div>
        <div className="top-status">
          <span>当前步骤</span>
          <strong>{steps[step]}</strong>
        </div>
      </section>
```

- [ ] **Step 3: Move the stepper below the top bar**

Render the existing `steps.map` inside:

```jsx
      <nav className="stepper glass-surface" aria-label="筛选步骤">
```

Each button should keep the existing click handler and active class logic.

- [ ] **Step 4: Add panel helper classes**

Use `panel work-panel` for each step section. Use `panel-title` around icon and heading text where practical. Keep form controls unchanged.

### Task 2: Replace CSS With High-Contrast Workbench Styles

**Files:**
- Modify: `web/src/styles.css`

- [ ] **Step 1: Define design tokens**

Create variables for background, surfaces, text, borders, accent, danger, success, warning, and focus ring.

- [ ] **Step 2: Style glass functional layers**

Add `.glass-surface`, `.topbar`, `.stepper`, `.stepper button`, and active states with translucent backgrounds, blur, borders, and crisp contrast.

- [ ] **Step 3: Style content panels**

Make panels bright and readable with 8px radius, strong borders, compact headings, high-contrast labels, inputs, textareas, focus states, notices, checks, progress, stats, and logs.

- [ ] **Step 4: Add responsive rules**

At `max-width: 760px`, stack the top bar, stepper, actions, and check rows without overlapping text.

### Task 3: Build And Verify

**Files:**
- Update generated build output under `src/resume_screening/web/static`

- [ ] **Step 1: Build frontend**

Run:

```bash
npm run build
```

inside `web`.

Expected: Vite exits with code 0 and emits assets.

- [ ] **Step 2: Start local app**

Run the local web server using the existing project command and open the browser to verify the screen.

- [ ] **Step 3: Browser check**

Inspect desktop and mobile widths for visible controls, no overlapping text, readable contrast, and working step navigation.

- [ ] **Step 4: Commit**

Stage only the UI source files, generated static assets, and design/plan docs. Leave unrelated `.DS_Store` untracked.
