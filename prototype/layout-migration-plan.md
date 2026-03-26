# 前端布局重构计划：横版卡片 → 竖版双栏 + 术语库全屏

---

## 零、核心决策：改还是重写？

**结论：TranslationApp.tsx 重写，其余所有文件不动或微调。**

原因：TranslationApp.tsx 是布局编排器（19.5 KB），布局从根本上变了——横向堆叠的三个独立面板 → 并排双栏 + overlay。现有代码中 ~60% 的逻辑（动画状态机、panel-slot 系统、transform-origin 计算、竖标题栏）会被删除，剩余 JSX 全部要重组。在原地改容易留残渣、漏引用、产生难以排查的交互 bug。

但这不是"凭记忆重写"——是在完整理解现有业务逻辑后，将所有业务逻辑原样搬入新的布局骨架。具体来说：

| 类别 | 处理方式 | 涉及内容 |
|------|---------|---------|
| **重写** | 新文件，新结构 | TranslationApp.tsx 的 JSX 布局 + 面板状态管理 |
| **原样搬入** | 逐行复制，不改一字 | 13 个 useState、4 个 useEffect、4 个 useCallback、5 个 handler 函数、所有 API 调用 |
| **完全不动** | 不碰这些文件 | FileUploadSection、LanguageSelector、TaskWorkbenchSection、TermLibraryContent、GlossaryReviewStep、PhaseCard、SettingsDialog、所有 UI 基础组件、api.ts、类型定义 |
| **微调** | 改 1-2 行 className | TaskWorkbenchSection 的根容器 padding |
| **删除** | 整个文件删掉 | TaskWorkbench.tsx（废弃）、TranslationWorkflow.tsx（废弃）、theme.css 中 ~50 行动画代码 |

---

## 一、架构对比

**当前：**
```
aside (sidebar) │ main (纵向滚动)
                │   panel-slot: 新建翻译  ← 横版，黑色竖标题栏 + 4列grid
                │   panel-slot: 翻译查看  ← 横版，黑色竖标题栏 + 内容区
                │   panel-slot: 术语库    ← 横版，黑色竖标题栏 + 内容区
                │   SettingsDialog (modal)
```

**目标：**
```
aside (不变) │ workspace (flex-1, relative, 不滚动)
             │   ┌─ 新建翻译 (1/3) ─┐┌─ 翻译查看 (2/3) ─┐  ← 始终并排
             │   │  纵向可滚动       ││  纵向可滚动       │
             │   │  底部固定按钮     ││                   │
             │   └──────────────────┘└───────────────────┘
             │
             │   术语库 overlay (absolute inset-0, z-50)  ← 按需全屏覆盖
             │   SettingsDialog (modal，不变)
```

---

## 二、防屎山：架构改进

当前项目已有的代码异味，这次重构一并解决：

### 2.1 拆分 TranslationApp.tsx 的职责

当前 19.5 KB 一个文件混了四件事：布局、状态管理、业务逻辑、表单 UI。重写时拆为：

```
components/
  layout/
    WorkspaceLayout.tsx    ← 新文件：双栏 + overlay 布局骨架（纯布局，~60 行）
    Panel.tsx              ← 新文件：通用面板容器组件（header + scrollable body + footer）
    Sidebar.tsx            ← 新文件：侧边栏（图标 + 行为），从 TranslationApp 中提取
  TranslationApp.tsx       ← 瘦身后：只做状态管理 + 业务逻辑 + 组合子组件（~250 行）
```

**Panel.tsx（~30 行）——所有面板复用：**
```tsx
interface PanelProps {
  title?: string;
  headerRight?: ReactNode;   // 工具栏按钮等
  footer?: ReactNode;        // 固定底部（如"开始翻译"按钮）
  children: ReactNode;
  className?: string;
}

function Panel({ title, headerRight, footer, children, className }: PanelProps) {
  return (
    <div className={cn("flex flex-col bg-card border border-border rounded-[var(--panel-radius)] overflow-hidden", className)}>
      {title && (
        <div className="px-5 pt-4 pb-3 border-b border-border flex items-center justify-between flex-shrink-0">
          <h2 className="text-sm font-semibold">{title}</h2>
          {headerRight}
        </div>
      )}
      <div className="flex-1 overflow-y-auto">{children}</div>
      {footer && <div className="border-t border-border flex-shrink-0">{footer}</div>}
    </div>
  );
}
```

### 2.2 CSS 变量管理面板风格

在 theme.css 中新增布局变量，避免到处硬编码：

```css
:root {
  --panel-gap: 12px;
  --panel-inset: 12px;      /* workspace 内边距 */
  --panel-radius: 12px;
  --panel-header-px: 20px;
  --panel-header-py: 16px;
}
```

后续调整间距、圆角只改这一处。

### 2.3 删除废弃文件

| 文件 | 状态 | 证据 |
|------|------|------|
| `TaskWorkbench.tsx` | 废弃 | 全项目无 import |
| `TranslationWorkflow.tsx` | 废弃 | 全项目无 import |

重构完成后直接删除。

---

## 三、TranslationApp.tsx 业务逻辑清单

以下是必须原样保留的所有业务逻辑（重写时逐项核对）：

### 3.1 State（13 个 useState）

| State | 用途 | 保留 |
|-------|------|------|
| `files` | 上传文件列表 | YES |
| `selectedLanguages` | 目标语言 | YES |
| `isTranslating` | 提交中标记 | YES |
| `jobs` | 任务列表 | YES |
| `useGlossary` | PRO 模式开关（localStorage 持久化） | YES |
| `libraryDomains` | 可用术语域列表 | YES |
| `selectedDomainIds` | 已选术语域 | YES |
| `settingsOpen` / `settingsTab` | 设置弹窗 | YES |
| `domainDropdownOpen` / `proInfoHover` | 下拉/提示 UI 状态 | YES |
| `domainDropdownRef` | 点击外部关闭 | YES |
| `visiblePanels` / `closingPanels` / `enteredPanels` | 旧面板动画系统 | **DELETE** → 替换为 `showLibrary: boolean` |

### 3.2 Effects（4 个 useEffect）

| Effect | 用途 | 保留 |
|--------|------|------|
| panel enter 动画 origin 计算 | 旧动画系统 | **DELETE** |
| domain dropdown 点击外部关闭 | 业务 UI | YES |
| mount 时 fetchLibraryDomains | 初始化 | YES |
| 1500ms 轮询 fetchJobs | 任务状态更新 | YES |

### 3.3 Handlers（5 个业务函数）

| 函数 | 用途 | 改动 |
|------|------|------|
| `handleStartTranslation` | 提交翻译任务 | 删掉最后一行 `setVisiblePanels`（新布局下不需要），其余不变 |
| `handleCancelJob` | 取消任务 | 不变 |
| `handleGlossaryConfirmed` | 术语确认后刷新 | 不变 |
| `handleUseGlossaryChange` | PRO 模式切换 | 不变 |
| `openSettings` | 打开设置 | 不变 |

### 3.4 要删除的代码（旧动画系统）

- `computeTransformOrigin()` — transform-origin 像素计算
- `togglePanel()` — 面板开关 + 动画触发
- `handlePanelAnimationEnd()` — 动画结束回调
- `shouldRender()` / `isClosing()` / `panelAnimClass()` — 渲染判断
- `iconRefs` / `panelRefs` / `originCache` — 动画 ref 系统
- `PANELS` 常量数组
- `NavIcon` 子组件（内联到 Sidebar.tsx）

---

## 四、分阶段执行

### Phase 0：准备

- [ ] Git commit 当前状态（包含之前的 bug 修复）
- [ ] 浏览器打开 `prototype/create-panel-vertical.html` 最终确认视觉方向

### Phase 1：创建新的布局组件

**新建 3 个文件，不动任何现有文件：**

1. `components/layout/Panel.tsx` — 通用面板容器
2. `components/layout/Sidebar.tsx` — 提取侧边栏
3. `components/layout/WorkspaceLayout.tsx` — 双栏 + overlay 骨架

**验证方式：** 这三个文件此时还没被引用，`npm run build` 应该正常通过。

### Phase 2：重写 TranslationApp.tsx

**操作：** 将现有 TranslationApp.tsx 重命名为 TranslationApp.old.tsx（保留参考），新建 TranslationApp.tsx：

1. 复制所有 import
2. 复制所有 state、effect、handler（3.1-3.3 中标记 YES 的）
3. 写新的 JSX：使用 WorkspaceLayout + Panel + Sidebar 组合
4. 删除旧动画系统相关代码（3.4 中列出的）
5. 新增 `const [showLibrary, setShowLibrary] = useState(false)`

**核对清单（逐项检查）：**
- [ ] 13 个 useState 中保留的 10 个都已搬入
- [ ] 4 个 useEffect 中保留的 3 个都已搬入
- [ ] 5 个 handler 都已搬入，`handleStartTranslation` 删了 `setVisiblePanels` 那行
- [ ] 子组件 props 传递与旧版完全一致：
  - `<FileUploadSection files={files} onFilesChange={setFiles} />`
  - `<LanguageSelector selectedLanguages={selectedLanguages} onLanguagesChange={setSelectedLanguages} variant="inline" />`
  - `<TranslationModeSelector useGlossary={useGlossary} onUseGlossaryChange={handleUseGlossaryChange} />`
  - `<TaskWorkbenchSection jobs={jobs} onCancelJob={handleCancelJob} onGlossaryConfirmed={handleGlossaryConfirmed} />`
  - `<TermLibraryContent />`（无 props）
  - `<SettingsDialog open={settingsOpen} onOpenChange={setSettingsOpen} initialTab={settingsTab} />`
- [ ] `useTheme()` / `useLanguage()` context hooks 都已引入
- [ ] `loadUseGlossarySetting` / `saveUseGlossarySetting` / `POLL_INTERVAL` 常量都已搬入
- [ ] domain 选择的 JSX（包括 `domainName(d)` 函数、`domainDropdownRef`、click-outside effect）都已搬入

**验证：** `npm run build` + 浏览器打开，确认所有功能可用。

### Phase 3：修复浮动元素裁切问题（风险 #2）

Panel 组件外层必须 `overflow-hidden`（圆角需要），但内容区只用 `overflow-y-auto`。
此外，5 个自定义 `position: absolute` 浮动元素需要改造：

| 位置 | 元素 | 改造方式 |
|------|------|---------|
| TranslationApp.tsx:290 | PRO 信息提示框 | 改用 Radix `HoverCard` 或 `Tooltip`（自带 Portal） |
| GlossaryReviewStep.tsx:324 | 策略帮助下拉框 (w-80) | 改用 Radix `Popover`（自带 Portal） |
| GlossaryReviewStep.tsx:409 | 不确定性 tooltip | 改用 Radix `Tooltip`（自带 Portal） |
| TermLibraryPage.tsx:407 | 语言列选择器 (w-56) | 改用 Radix `Popover`（自带 Portal） |
| FileUploadSection.tsx:121 | 文件删除按钮 | 保持不变（16px 小按钮，不会溢出） |

**原则：** 项目已大量使用 Radix 组件，替换路径清晰。每个浮动元素单独替换 + 验证，不批量操作。

**验证：** 在 1/3 和 2/3 面板中分别触发每个下拉/提示，确认不被裁切。

### Phase 4：适配 TaskWorkbenchSection + GlossaryReviewStep

**TaskWorkbenchSection：**
- 根容器 `px-14 py-14` → `px-5 py-4`（适配 2/3 宽度）
- 保留 `overflow-x-hidden`（之前 bug 修复）

**GlossaryReviewStep 术语审校表格（风险 #1）：**
- 当前固定列宽总计 >1400px，在 800px 容器中横向滚动量过大
- 改造方案：
  - context 列从 `width: 42rem` (672px) → `min-w-[200px]`（缩短默认宽度，内容自适应）
  - 原文列从 `w-56` (224px) → `w-40` (160px)
  - 策略列从 `w-44` (176px) → `w-36` (144px)
  - 保持 `overflow-x-auto` 横向滚动
  - 保持 sticky 列和内联编辑不动
- **风险控制：** 只改 `<col>` 的 className/style，不动 `<TableCell>` 的内容和交互逻辑

**验证：**
- 展开任务详情、审校记录，宽度不溢出
- 术语审校表格在 800px 下可滚动，内联编辑正常，sticky 列对齐

### Phase 5：术语库 overlay 完善（风险 #4, #7, #9）

**焦点管理（风险 #4）：**
- overlay 打开时：调用 `setDomainDropdownOpen(false)` 关闭下层 dropdown
- 参考 SettingsDialog 使用的 Radix Dialog 焦点捕获模式
- 或简单方案：overlay 根元素加 `tabIndex={-1}` + `onKeyDown` 拦截 Tab

**事件穿透（风险 #4）：**
- overlay 根元素 `pointer-events: auto` + 完整背景色遮挡
- domain dropdown 的 `document.addEventListener("mousedown")` 会被 overlay 元素截获（事件目标不在 dropdown 外 → 不触发关闭）

**Dialog 层级（风险 #7）：**
- overlay 不加 `isolation: isolate` 或 `transform`（避免创建新 stacking context）
- TermLibraryContent 内部的 3 个 Radix Dialog 通过 Portal 渲染到 body，z-50 自然在 overlay 之上

**scroll position（风险 #9）：**
- overlay 用 `position: absolute`，脱离文档流，不影响下层双栏的 DOM
- 双栏始终挂载（不条件渲染），scroll position 自然保持

**验证：**
- 打开术语库 → Tab 键不会跳到下层
- 打开术语库 → 内部创建域/添加术语 Dialog 正常弹出
- 关闭术语库 → 双栏 scroll position 未变

### Phase 6：清理

1. **删除 TranslationApp.old.tsx**
2. **删除 TaskWorkbench.tsx**（废弃）
3. **删除 TranslationWorkflow.tsx**（废弃）
4. **清理 theme.css：**
   - 删除 `.panel-slot` 相关（~15 行）
   - 删除 `@keyframes panel-enter` / `panel-exit`（~30 行）
   - 删除 `.panel-entering` / `.panel-exiting`（~5 行）
   - 新增 `--panel-gap` / `--panel-inset` / `--panel-radius` 变量
   - 更新 reduced-motion 媒体查询中的类名引用
5. **全局搜索确认无残留：**
   ```
   grep: panel-slot → 0 results
   grep: panel-entering → 0 results
   grep: writing-mode → 0 results
   grep: visiblePanels → 0 results
   grep: closingPanels → 0 results
   grep: TranslationWorkflow → 0 results
   grep: TaskWorkbench[^S] → 0 results (排除 TaskWorkbenchSection)
   ```
6. **检查未使用 import：** `npm run build` 无 warning

**验证：** 全流程测试（见第六节 Checklist）。

---

## 五、防 Bug 策略

### 5.1 子组件零改动原则

以下组件的 props 接口和内部实现完全不动——它们自适应父容器，放进新布局就能工作：

- FileUploadSection、LanguageSelector、TranslationModeSelector
- TaskWorkbenchSection（仅改 padding）、TermLibraryContent
- GlossaryReviewStep、PhaseCard、StepBadge
- SettingsDialog、所有 UI 基础组件

### 5.2 业务逻辑逐项核对

Phase 2 中的核对清单不是建议，是强制要求。每搬一个 handler / effect / state，在旧文件中标记已搬，确保不遗漏。

### 5.3 风险清单与对应 Phase

所有 9 个已识别风险在计划中的覆盖位置：

| # | 风险 | 严重程度 | 对应 Phase | 预防措施 |
|---|------|---------|-----------|---------|
| 1 | 术语审校表格 800px 下爆掉 | 高 | Phase 4 | 缩短固定列宽，保持横向滚动 |
| 2 | 5 个浮动元素被 overflow-hidden 裁切 | 高 | Phase 3 | 改用 Radix Portal 组件 |
| 3 | FileUploadSection 3 列网格拥挤 | 中 | Phase 6 验证 | 实测后按需改为 2 列 |
| 4 | overlay 焦点穿透 + 事件穿透 | 中 | Phase 5 | focus trap + 关闭下层 dropdown |
| 5 | handleStartTranslation 残留引用 | 中 | Phase 2 核对 | TypeScript 编译器兜底 |
| 6 | 轮询 interval 泄漏 | 低 | Phase 2 | 原样复制 cleanup |
| 7 | Library 内部 Dialog 层级冲突 | 低 | Phase 5 | overlay 不加 isolation/transform |
| 8 | 暗色模式颜色不一致 | 低 | Phase 6 验证 | 只用语义色类，不用硬编码色 |
| 9 | scroll position 重置 | 低 | Phase 5 | overlay 用 absolute，双栏始终挂载 |

### 5.4 每阶段 commit

```
Phase 0 → commit: "chore: prepare for layout refactor"
Phase 1 → commit: "feat: add Panel, Sidebar, WorkspaceLayout components"
Phase 2 → commit: "refactor: rewrite TranslationApp with dual-column layout"
Phase 3 → commit: "fix: convert custom floating elements to Radix Portal components"
Phase 4 → commit: "fix: adapt TaskWorkbenchSection padding and GlossaryReviewStep table widths"
Phase 5 → commit: "feat: library overlay focus trap, event isolation, scroll preservation"
Phase 6 → commit: "chore: remove dead code and legacy panel animation system"
```

每次 commit 前 `npm run build` + 浏览器验证。如果某个 Phase 出问题，`git checkout` 回上一个 commit 重来。

---

## 六、最终验证 Checklist

### 功能验证
- [ ] 上传文件 → 选术语域 → 选语言 → 点击开始翻译 → 右栏出现任务
- [ ] 任务列表展示正常，进度条更新（轮询工作）
- [ ] 展开任务详情 → 下载翻译稿/审校稿
- [ ] 展开审校记录 → 宽度不溢出
- [ ] 取消任务 → 状态更新
- [ ] 打开术语库 → 全屏覆盖 → 内部 CRUD 正常 → 关闭恢复双栏
- [ ] 设置弹窗正常打开/关闭
- [ ] PRO 模式切换 → 术语域选择出现/消失
- [ ] 中英文切换 → 所有文本正确

### 风险专项验证
- [ ] **风险 #1**：术语审校表格在 800px 右栏中可横向滚动，内联编辑正常，sticky 列对齐
- [ ] **风险 #2**：PRO 信息提示框在 1/3 面板中不被裁切
- [ ] **风险 #2**：GlossaryReviewStep 策略帮助下拉框不被裁切
- [ ] **风险 #2**：TermLibraryPage 语言列选择器不被裁切
- [ ] **风险 #3**：FileUploadSection 文件网格在 1/3 面板中布局合理（3 列不拥挤）
- [ ] **风险 #4**：术语库 overlay 打开时，Tab 键不跳到下层
- [ ] **风险 #4**：术语库 overlay 打开时，点击 overlay 内不触发下层 dropdown 关闭
- [ ] **风险 #7**：术语库内部的"创建域""添加术语""导入"Dialog 正常弹出在 overlay 之上
- [ ] **风险 #8**：暗色模式下——双栏背景、面板边框、overlay 背景颜色正确
- [ ] **风险 #9**：打开/关闭术语库后，右栏任务列表 scroll position 不变

### 代码质量验证
- [ ] `npm run build` 无错误
- [ ] 搜索 `panel-slot` / `panel-entering` / `writing-mode` / `visiblePanels` → 0 结果
- [ ] 搜索 `TaskWorkbench` (排除 Section) / `TranslationWorkflow` → 0 结果
- [ ] 无未使用的 import
- [ ] TranslationApp.tsx < 300 行
- [ ] 新增文件各自职责清晰：Panel（容器）、Sidebar（导航）、WorkspaceLayout（布局）

---

## 七、文件变更总览

```
新增：
  components/layout/Panel.tsx              ~30 行
  components/layout/Sidebar.tsx            ~80 行
  components/layout/WorkspaceLayout.tsx    ~60 行

重写：
  components/TranslationApp.tsx            19.5 KB → ~250 行（瘦身 50%+）

小改（浮动元素 Portal 化）：
  components/TranslationApp.tsx            PRO 信息提示框 → Radix HoverCard/Tooltip
  components/GlossaryReviewStep.tsx        2 个自定义 tooltip/dropdown → Radix Popover/Tooltip
  components/TermLibraryPage.tsx           语言列选择器 → Radix Popover

微调（1-5 行 className）：
  components/TaskWorkbenchSection.tsx      改 padding
  components/GlossaryReviewStep.tsx        缩短 <col> 固定列宽

删除：
  components/TranslationApp.old.tsx        重写完对照后删
  components/TaskWorkbench.tsx             废弃旧组件
  components/TranslationWorkflow.tsx       废弃旧组件
  styles/theme.css                         删 ~50 行动画代码，新增 ~5 行变量

不动：
  FileUploadSection, LanguageSelector, TranslationModeSelector,
  PhaseCard, StepBadge, SettingsDialog, 所有 UI 基础组件,
  api.ts, 类型定义, 工具函数
```
