"""Mecha WebUI server — provides a chat interface via HTTP."""

import json
import os
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from mecha.config import Config
from mecha.credentials import get_key
from mecha.llm.deepseek import DeepSeekLLM
from mecha.models import Action
from mecha.loop import _parse_action, _execute_action
from mecha.guardrails import guardrail, log_audit
from mecha.feedback import get_feedback

sessions = {}


class MechaHandler(BaseHTTPRequestHandler):

    def __init__(self, *args, config=None, llm=None, **kwargs):
        self.config = config
        self.llm = llm
        super().__init__(*args, **kwargs)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_html()
        elif self.path == "/api/sessions":
            self._handle_new_session()
        elif self.path == "/api/usage":
            self._handle_usage()
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/chat":
            self._handle_chat()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _handle_new_session(self):
        sid = str(uuid.uuid4())
        sessions[sid] = [{
            "role": "system",
            "content": "You are Mecha, a helpful coding agent. Reply in Chinese. You can chat or execute actions using JSON format."
        }]
        self._send_json({"session_id": sid})

    def _handle_usage(self):
        u = {"prompt": 0, "completion": 0, "total": 0}
        if hasattr(self.llm, "total_tokens"):
            u = {
                "prompt": self.llm.total_prompt_tokens,
                "completion": self.llm.total_completion_tokens,
                "total": self.llm.total_tokens,
            }
        self._send_json(u)

    def _handle_chat(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body)
        user_message = data.get("message", "")
        session_id = data.get("session_id", "")

        if not session_id or session_id not in sessions:
            session_id = str(uuid.uuid4())
            sessions[session_id] = [{
                "role": "system",
                "content": "You are Mecha, a helpful coding agent. Reply in Chinese."
            }]

        messages = sessions[session_id]
        messages.append({"role": "user", "content": user_message})

        response_text = ""
        iteration = 0
        max_iter = self.config.max_iterations if self.config else 20

        while iteration < max_iter:
            iteration += 1
            try:
                raw = self.llm.chat(messages)
            except Exception as e:
                response_text = f"Error: {e}"
                break

            action = _parse_action(raw)
            if action is None:
                response_text = raw
                messages.append({"role": "assistant", "content": raw})
                break

            if action.type == "complete":
                response_text = action.params.get("summary", "Done.")
                messages.append({"role": "assistant", "content": raw})
                break

            if self.config:
                decision = guardrail(
                    action,
                    custom_block=self.config.custom_danger_rules,
                    custom_confirm=self.config.custom_confirm_rules,
                )
                if decision.level == "block":
                    log_audit(action, decision, executed=False)
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({"role": "user", "content": f"Action blocked: {decision.reason}"})
                    continue

            project_root = os.getcwd()
            result = _execute_action(action, project_root, self.config or Config())

            if action.type == "run_command":
                feedback = get_feedback(result, action.params.get("command", ""))
            else:
                feedback = result.output if result.success else f"Error: {result.error}"

            messages.append({"role": "assistant", "content": raw})
            messages.append({"role": "user", "content": f"Action result: {feedback}"})

        sessions[session_id] = messages

        usage = {"prompt": 0, "completion": 0, "total": 0}
        if hasattr(self.llm, "total_tokens"):
            usage = {
                "prompt": self.llm.total_prompt_tokens,
                "completion": self.llm.total_completion_tokens,
                "total": self.llm.total_tokens,
            }
        self._send_json({"response": response_text, "session_id": session_id, "usage": usage})

    def _serve_html(self):
        html = self._get_html()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        pass

    def _get_html(self):
        return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mecha WebUI</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #1a1a2e; color: #e0e0e0; height: 100vh; display: flex; flex-direction: column; }
header { background: #16213e; padding: 12px 20px; font-size: 18px; font-weight: 600; border-bottom: 1px solid #0f3460; display: flex; align-items: center; justify-content: space-between; }
header .left { display: flex; align-items: center; gap: 8px; }
header .dot { width: 8px; height: 8px; border-radius: 50%; background: #4ecca3; }
header .usage { font-size: 12px; color: #888; font-weight: 400; }
#chat { flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }
.msg { max-width: 80%; padding: 10px 14px; border-radius: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }
.msg.user { align-self: flex-end; background: #0f3460; }
.msg.assistant { align-self: flex-start; background: #16213e; }
footer { padding: 12px 20px; border-top: 1px solid #0f3460; display: flex; gap: 8px; }
footer input { flex: 1; padding: 10px 14px; border-radius: 8px; border: 1px solid #0f3460; background: #16213e; color: #e0e0e0; font-size: 14px; outline: none; }
footer input:focus { border-color: #4ecca3; }
footer button { padding: 10px 18px; border-radius: 8px; border: none; background: #4ecca3; color: #1a1a2e; font-weight: 600; cursor: pointer; font-size: 14px; }
footer button:hover { background: #3db88f; }
footer button:disabled { opacity: 0.5; cursor: not-allowed; }
.loading { display: flex; gap: 4px; padding: 10px 14px; }
.loading span { width: 6px; height: 6px; border-radius: 50%; background: #4ecca3; animation: bounce 1.4s infinite; }
.loading span:nth-child(2) { animation-delay: 0.2s; }
.loading span:nth-child(3) { animation-delay: 0.4s; }
@keyframes bounce { 0%,80%,100% { transform: scale(0); } 40% { transform: scale(1); } }
</style>
</head>
<body>
<header>
<div class="left"><span class="dot"></span>Mecha WebUI</div>
<div class="usage" id="usage">Tokens: 0</div>
</header>
<div id="chat"></div>
<footer>
<input id="input" type="text" placeholder="输入任务或问题..." onkeydown="if(event.key==='Enter')send()">
<button id="sendBtn" onclick="send()">发送</button>
</footer>
<script>
let sessionId = "";
async function init() {
  const r = await fetch("/api/sessions");
  const d = await r.json();
  sessionId = d.session_id;
}
async function send() {
  const input = document.getElementById("input");
  const btn = document.getElementById("sendBtn");
  const msg = input.value.trim();
  if (!msg) return;
  addMessage("user", msg);
  input.value = "";
  btn.disabled = true;
  addLoading();
  try {
    const r = await fetch("/api/chat", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({message: msg, session_id: sessionId})
    });
    const d = await r.json();
    removeLoading();
    addMessage("assistant", d.response);
    sessionId = d.session_id;
    if (d.usage) {
      document.getElementById("usage").textContent =
        "Tokens: " + d.usage.total + " (P:" + d.usage.prompt + " C:" + d.usage.completion + ")";
    }
  } catch(e) {
    removeLoading();
    addMessage("assistant", "Error: " + e.message);
  }
  btn.disabled = false;
  input.focus();
}
function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = "msg " + role;
  div.textContent = text;
  document.getElementById("chat").appendChild(div);
  document.getElementById("chat").scrollTop = document.getElementById("chat").scrollHeight;
}
function addLoading() {
  const div = document.createElement("div");
  div.className = "loading";
  div.id = "loading";
  div.innerHTML = "<span></span><span></span><span></span>";
  document.getElementById("chat").appendChild(div);
  document.getElementById("chat").scrollTop = document.getElementById("chat").scrollHeight;
}
function removeLoading() {
  const el = document.getElementById("loading");
  if (el) el.remove();
}
init();
</script>
</body>
</html>"""


def create_app(config, llm):
    class Handler(MechaHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, config=config, llm=llm, **kwargs)
    return Handler


def run_server(host="127.0.0.1", port=8080):
    config = Config.from_file(".mecha.yaml")
    api_key = get_key()
    if api_key is None:
        print("No API key configured. Run 'mecha --set-key' first.")
        return
    llm = DeepSeekLLM(config, api_key)
    handler = create_app(config, llm)
    server = HTTPServer((host, port), handler)
    url = f"http://{host}:{port}"
    print(f"Mecha WebUI running at {url}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    run_server(host, port)
