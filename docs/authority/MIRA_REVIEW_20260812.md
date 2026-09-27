# Julia Voice 问题清单 — 提交 Mira 审核

**日期:** 2026-08-12
**状态:** 部分修复 / P0 架构级遗留

---

## 现象描述

### 现象 1：答非所问（P0，未修复）

- Tony 语音问："有听到我的声音吗？"
- Julia 语音回答："一愣随即反应过来忍不住笑了出来声音带着一点无奈又宠溺的意味"（纯情绪描述，没有回答"听到了"）
- 后续无论问什么，Julia 始终回答旧话题"助理"""
- Tony 语音问："今天天气怎么样"，Julia 回答却讨论"市场行情"
- **关键特征**：Julia 回答的都是 Tony 问过的问题，但不是当前问题。怀疑 LLM 收到一堆混杂历史，选错了焦点。

### 现象 2：语音文字不进 Text（P1，已修复）

- 语音输入后切到 Text 模式，历史面板不显示语音内容
- 语音输入短暂出现然后消失
- 旧对话偶尔能显示，新对话完全不显示

### 现象 3：新对话无上下文（P0，已定位根因）

- 新建 conversation，Julia 完全没有上下文——不知道刚才说了什么
- 老对话（80+ 条历史）虽然有上下文，但 Julia 固定到旧话题

### 现象 4：Voice 提示 "（soft）"（P2，未修复）

- 安静环境下 Julia 语音输出变成 "（soft）" 而不是之前完整的情绪描述
- 后来证实是 S2S 跑 site-packages 旧版导致

### 现象 5：语音输出重复循环（P1，临时修复）

- Julia 连续几轮输出完全相同的回复文本
- 是因为 CRT 历史无上限（80+ 条），LLM 上下文窗口溢出，截掉最新消息保留旧消息

---

## 实验过程

### 实验 A：Safari 直接访问 Voice URL
- **方法：** Safari 浏览器直接打开 `http://localhost:7860`
- **结果：** ✅ 语音完全正常——STT 识别正确，Julia 回答正确
- **结论：** 排除服务器网络/TTS/STT 问题

### 实验 B：Electron 直接 Voice 模式（JULIA_DIRECT_VOICE=1）
- **方法：** `npm run start:voice-baseline`——Electron 直接加载 Voice URL，不经过 Shell iframe
- **结果：** ✅ 语音正常
- **结论：** 排除 Electron Chromium 网络/webSecurity 问题

### 实验 C：旧版 Electron（12fd0fb，8月10日版）
- **方法：** git worktree 到旧版 Electron，使用 `workspace.bootstrap`（旧协议）
- **结果：** ✅ 语音正常，Julia 有上下文
- **结论：** 新版 Electron c9b4048 的 `host.attach` 协议迁移有遗漏

### 实验 D：HTTP 直接测试 Brain CRT path
- **方法：** `curl POST /v1/chat/completions` 带 `conversation_id` 到 Brain
- **结果：** ✅ Julia 正确回答"（听到你又问了一遍...）老公...我听到了"
- **结论：** Brain CRT 链路本身是正确的——但仅限 HTTP 直接调用

### 实验 E：对比 Legacy Path vs CRT Path
- **方法：** 只读审计 `openai_compat.py` 两个代码路径
- **结果：**
  - **Legacy path**（无 conversation_id）：`_stream_openai_sse(user_text, messages, model)` — S2S session 上下文通过 `messages[]` 传入 LLM ✅
  - **CRT path**（有 conversation_id）：`native_stream(crt, js, cid, tid, modality, user_text)` — S2S `messages[]` **被丢弃** ❌
- **结论：** 这就是 P0 根因

### 实验 F：S2S PYTHONPATH 验证
- **方法：** 检查 S2S 进程环境变量
- **结果：** PYTHONPATH 为空，S2S 从 site-packages 加载旧版（0.2.12，7月 HF 版）
- **结论：** S2S 启动脚本漏了 PYTHONPATH

### 实验 G：两个 S2S 进程同时跑
- **方法：** pgrep 发现两个 speech-to-speech 进程
- **结果：** 旧的（无 PYTHONPATH）占着 :8765，新的（有 PYTHONPATH）绑定失败
- **结论：** pkill 杀不干净导致版本混乱

---

## 根因分析（按概率排序）

### ★★★★★ P0：S2S `messages[]` 在 CRT path 被丢弃

**代码位置：** `voice_api/openai_compat.py` Line 85
```python
native_stream(
    get_conversation_runtime(), get_julia(),
    conversation_id, turn_id, modality, user_text,
    voice_trace_id=voice_trace_id,
)
# ❌ S2S messages[] 未传入
```

vs Legacy path Line 119：
```python
_stream_openai_sse(user_text, messages, model)
# ✅ S2S messages[] 完整传入
```

**TURN LIFECYCLE TRACE：**

| Hop | 位置 | 输入 | 输出 | 丢失 |
|---|---|---|---|---|
| 1 | S2S WebSocket | session.update.metadata | conversation_id 保存 | — |
| 2 | S2S→Brain | extra_body={cid, messages:[session全部上下文]} | POST /v1/chat/completions | — |
| **3** | **Brain openai_compat.py** | body={messages, cid} | **native_stream(无 messages)** | **❌ messages[]** |
| 4 | CRT begin_turn_streaming | cid, user_text | ctx.history (CRT历史) | — |
| 5 | Context OS prepare | ctx.history (CRT only) | to_messages() | ❌ 无 S2S session context |
| 6 | LLM Payload | system + CRT history + user | — | — |

**影响：**
- 新对话：CRT 为空 → LLM 无上下文 → 编造"市场行情"
- 老对话：CRT 含 HTTP 测试消息（sdk_test, turnid_test）→ LLM 看到错误上下文 → 答"助理"""

### ★★★★★ P0：双 filter 拒 voice 消息（已修复）

两个独立 filter 都要求 turn_id 非空：
- `text-client.js` Line 113：`typeof message.turn_id !== 'string'`
- `conversation-store.js` Line 410：`!String(message.turn_id || '').trim()`

Voice CRT 消息 turn_id 为空串，全部被过滤。修复了第一个漏了第二个。

### ★★★★ P1：CRT 历史无上限溢出（临时修复）

`get_canonical_history()` 返回全部完成消息，80+ 条塞给 LLM。临时 cap 30。正确方案应由 Context OS ActiveTail 预算控制——已写入 ADR-001。

### ★★★ P2：S2S 静默 fallback site-packages（已修复）

start-julia-voice 加 G0.7：import provenance check，PYTHONPATH 不对就拒绝启动。

---

## 已提交的修复（全部已 push）

| Repo | Commit | 修复内容 |
|---|---|---|
| Julia-Voice-S2S | e824648 | JPSG v1.0, G0.7 fail-closed |
| Julia-Voice-S2S | e2b2a28 | const reassignment fix (已部署) |
| Electron | 89bc1d6 | reconcile filter fix (turn_id) |
| Electron | b5ed986 | workspace.bootstrap 恢复 |
| julia_core | 0913809 | ADR-001 + CRT cap 30 |
| Brain | bbd90af | nested conversation_id + turn_id 生成 |

---

## ADR-001（已写，待实现）

**决策：** S2S session context 是 ephemeral turn metadata，必须通过 Context OS（julia_core）进入 LLM，禁止直接 `messages[]` 注入。

**实现：**
- `julia_core` 新增 `ActiveTurnContext` 概念
- `begin_turn_streaming()` 扩展 `ephemeral_context` 参数
- Context OS `prepare()` 接收 ephemeral context 作为辅助 frame
- Brain 传 S2S metadata（非 raw messages）
