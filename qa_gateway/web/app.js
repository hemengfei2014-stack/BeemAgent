const loginView = document.getElementById("loginView");
const chatView = document.getElementById("chatView");

const orgNameInput = document.getElementById("orgNameInput");
const userIdInput = document.getElementById("userIdInput");
const loginBtn = document.getElementById("loginBtn");
const loginError = document.getElementById("loginError");

const newChatBtn = document.getElementById("newChatBtn");
const conversationList = document.getElementById("conversationList");
const conversationTitle = document.getElementById("conversationTitle");
const messageList = document.getElementById("messageList");
const promptInput = document.getElementById("promptInput");
const sendBtn = document.getElementById("sendBtn");
const stopBtn = document.getElementById("stopBtn");
const sendError = document.getElementById("sendError");
const meLabel = document.getElementById("meLabel");
const logoutBtn = document.getElementById("logoutBtn");

let state = {
  me: null,
  conversations: [],
  activeConversationId: null,
  activeMessages: [],
  streaming: false,
  abortController: null,
};

function clearChatUI() {
  conversationList.innerHTML = "";
  conversationTitle.textContent = "新会话";
  messageList.innerHTML = "";
  sendError.textContent = "";
  promptInput.value = "";
}

function fmtTime(ms) {
  const d = new Date(ms);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function setView(view) {
  if (view === "login") {
    if (state.abortController) state.abortController.abort();
    state.abortController = null;
    setStreaming(false);
    loginView.classList.remove("hidden");
    chatView.classList.add("hidden");
    clearChatUI();
  } else {
    setStreaming(false);
    loginView.classList.add("hidden");
    chatView.classList.remove("hidden");
  }
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let body = null;
  const ct = resp.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    body = await resp.json().catch(() => null);
  } else {
    body = await resp.text().catch(() => "");
  }
  if (!resp.ok) {
    const err = new Error("API error");
    err.status = resp.status;
    err.body = body;
    throw err;
  }
  return body;
}

function renderConversations() {
  conversationList.innerHTML = "";
  for (const c of state.conversations) {
    const el = document.createElement("div");
    el.className = "convItem" + (c.id === state.activeConversationId ? " active" : "");
    el.addEventListener("click", () => selectConversation(c.id));
    const title = document.createElement("div");
    title.className = "convTitle";
    title.textContent = c.title || "新会话";
    const meta = document.createElement("div");
    meta.className = "convMeta";
    meta.textContent = fmtTime(c.updated_at_ms || c.created_at_ms);
    el.appendChild(title);
    el.appendChild(meta);
    conversationList.appendChild(el);
  }
}

function renderMessages() {
  messageList.innerHTML = "";
  for (const m of state.activeMessages) {
    const row = document.createElement("div");
    row.className = "msg";
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    avatar.textContent = m.role === "user" ? "你" : "AI";
    const bubble = document.createElement("div");
    bubble.className = "bubble" + (m.role === "user" ? " user" : "");

    const mainText = document.createElement("div");
    mainText.textContent = m.content || "";
    bubble.appendChild(mainText);

    if (m.role === "assistant" && m.reasoning_content) {
      const thinking = document.createElement("div");
      thinking.className = "thinking";
      thinking.textContent = m.reasoning_content;
      bubble.appendChild(thinking);
    }

    row.appendChild(avatar);
    row.appendChild(bubble);
    messageList.appendChild(row);
  }
  messageList.scrollTop = messageList.scrollHeight;
}

async function refreshMe() {
  try {
    const res = await api("/api/auth/me", { method: "GET" });
    state.me = res.user;
    meLabel.textContent = `${state.me.org_name} / ${state.me.user_id} ${state.me.user_name}`;
    return true;
  } catch {
    return false;
  }
}

async function loadConversations() {
  const res = await api("/api/conversations", { method: "GET" });
  state.conversations = res.conversations || [];
  if (state.activeConversationId && !state.conversations.some((c) => c.id === state.activeConversationId)) {
    state.activeConversationId = null;
    state.activeMessages = [];
    conversationTitle.textContent = "新会话";
    renderMessages();
  }
  if (!state.activeConversationId && state.activeMessages.length) {
    state.activeMessages = [];
    conversationTitle.textContent = "新会话";
    renderMessages();
  }
  renderConversations();
}

async function selectConversation(id) {
  state.activeConversationId = id;
  await loadConversations();
  const res = await api(`/api/conversations/${encodeURIComponent(id)}`, { method: "GET" });
  conversationTitle.textContent = res.conversation.title || "新会话";
  state.activeMessages = res.messages || [];
  renderMessages();
}

function setStreaming(on) {
  state.streaming = on;
  sendBtn.disabled = on;
  promptInput.disabled = on;
  stopBtn.disabled = !on;
  newChatBtn.disabled = on;
  logoutBtn.disabled = on;
}

async function ensureConversation() {
  if (state.activeConversationId) return state.activeConversationId;
  const res = await api("/api/conversations", { method: "POST", body: JSON.stringify({}) });
  state.activeConversationId = res.conversation.id;
  await loadConversations();
  await selectConversation(state.activeConversationId);
  return state.activeConversationId;
}

function appendOrUpdateAssistantMessage(messageId, contentAppend, reasoningAppend) {
  let msg = state.activeMessages.find((m) => m.id === messageId);
  if (!msg) {
    msg = { id: messageId, role: "assistant", content: "", reasoning_content: "" };
    state.activeMessages.push(msg);
  }
  if (contentAppend) msg.content += contentAppend;
  if (reasoningAppend) msg.reasoning_content += reasoningAppend;
  renderMessages();
}

async function sendMessage() {
  sendError.textContent = "";
  const text = (promptInput.value || "").trim();
  if (!text) return;

  // 立即进入 loading 状态，防止重复点击
  setStreaming(true);
  
  try {
    const convId = await ensureConversation();

    state.activeMessages.push({ id: crypto.randomUUID(), role: "user", content: text });
    renderMessages();
    promptInput.value = "";

    const controller = new AbortController();
    state.abortController = controller;

    const assistantMsgId = crypto.randomUUID();
    appendOrUpdateAssistantMessage(assistantMsgId, "", "");

    const body = {
      model: "gpt-oss-120b",
      stream: true,
      reasoning_effort: "high",
      messages: [{ role: "user", content: text }],
      metadata: { conversation_id: convId },
      max_tokens: 1024,
      temperature: 0.2,
    };

    const resp = await fetch("/v1/chat/completions", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    if (!resp.ok) {
      const t = await resp.text().catch(() => "");
      throw Object.assign(new Error("chat failed"), { status: resp.status, body: t });
    }

    const reader = resp.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buf = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      while (true) {
        const idx = buf.indexOf("\n\n");
        if (idx === -1) break;
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const lines = block.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const data = line.slice(5).trim();
          if (data === "[DONE]") continue;
          let obj = null;
          try { obj = JSON.parse(data); } catch { obj = null; }
          if (!obj) continue;
          const choice0 = (obj.choices || [])[0] || {};
          const delta = choice0.delta || {};
          const contentAppend = typeof delta.content === "string" ? delta.content : "";
          const reasoningAppend = typeof delta.reasoning_content === "string" ? delta.reasoning_content : "";
          if (contentAppend || reasoningAppend) {
            appendOrUpdateAssistantMessage(assistantMsgId, contentAppend, reasoningAppend);
          }
        }
      }
    }

    await loadConversations();
    if (convId) {
      const res = await api(`/api/conversations/${encodeURIComponent(convId)}`, { method: "GET" });
      conversationTitle.textContent = res.conversation.title || "新会话";
      state.activeMessages = res.messages || [];
      renderMessages();
    }
  } catch (e) {
    if (e.name === "AbortError") {
      sendError.textContent = "已中断生成";
    } else {
      sendError.textContent = `发送失败：${e.status || ""} ${typeof e.body === "string" ? e.body : (e.message || "")}`.trim();
      // 如果 ensureConversation 失败，可能需要把用户刚才输入的内容放回去？
      // 暂时不做，避免复杂。
    }
  } finally {
    setStreaming(false);
    state.abortController = null;
    // 聚焦回输入框
    setTimeout(() => promptInput.focus(), 0);
  }
}

loginBtn.addEventListener("click", async () => {
  loginError.textContent = "";
  try {
    const res = await api("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ org_name: orgNameInput.value, user_id: userIdInput.value }),
    });
    state.me = res.user;
    state.streaming = false;
    state.abortController = null;
    setStreaming(false);
    
    // 安全修复：登录新账号前，强制彻底清空旧的 UI 和状态
    clearChatUI();
    state.conversations = [];
    state.activeConversationId = null;
    state.activeMessages = [];
    renderConversations();
    renderMessages();

    await refreshMe();
    setView("chat");
    await loadConversations();
  } catch (e) {
    loginError.textContent = "组织名称或用户ID不正确";
  }
});

logoutBtn.addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST", body: JSON.stringify({}) }).catch(() => null);
  state = { me: null, conversations: [], activeConversationId: null, activeMessages: [], streaming: false, abortController: null };
  clearChatUI();
  setView("login");
});

newChatBtn.addEventListener("click", async () => {
  if (state.streaming) return;
  const res = await api("/api/conversations", { method: "POST", body: JSON.stringify({}) });
  state.activeConversationId = res.conversation.id;
  await loadConversations();
  await selectConversation(state.activeConversationId);
});

sendBtn.addEventListener("click", () => sendMessage());
stopBtn.addEventListener("click", () => {
  if (state.abortController) state.abortController.abort();
});

promptInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!state.streaming) sendMessage();
  }
});

async function bootstrap() {
  const ok = await refreshMe();
  if (!ok) {
    setView("login");
    return;
  }
  setView("chat");
  await loadConversations();
}

bootstrap();
