# AI / Agent 多厂商配置与排障

配置入口是仓库根目录 `.env`，由 `services/ai_gateway/config.py` 使用绝对路径加载，与启动工作目录无关。修改后重启 `ai_gateway`。真实密钥只放在服务端环境变量或忽略提交的 `.env` 中。

## 当前配置排查结论

后续经用户授权，使用真实密钥完成了最小在线检查：`.env` 能被加载，实际模型为 `openai/gpt-6-sol`，地址为官方 `https://api.openai.com/v1`。鉴权、模型可见性和普通对话均通过。Agent 失败有两个独立原因：

- 安装的 LiteLLM 1.82.2 尚未识别 GPT-6 的 `reasoning_effort`，在发出请求前抛出 `UnsupportedParamsError`。现在仅为 OpenAI GPT-6 显式放行这一官方参数，保留其他参数校验。
- `AI_REASONING_EFFORT=high` 与该模型在 Chat Completions 下的工具调用不兼容。官方接口返回 400，要求使用 Responses 或设置 `reasoning_effort=none`。当前 Agent 应配置 `AI_REASONING_ENABLED=true`、`AI_REASONING_STYLE=openai`、`AI_REASONING_EFFORT=none`；关闭 ENABLED 会省略参数，并不等于向模型发送 none。

上述修正已通过真实的两轮无副作用工具调用验证。此结果只验证当次使用的密钥、模型与调用链，不代表其他厂商已在线验证，也不代表密钥撤销后仍能工作。`gpt-6.1-sol` 的工具调用要求 Responses API，不能仅通过更改 Base URL 在当前 Agent 中启用。

原实现还存在以下独立问题，现已修正：

- `AI_TIMEOUT`、`AI_MAX_TOKENS` 未传给模型请求。
- 裸模型名和 `AI_PROVIDER` 只影响读取密钥，没有一致转换成 LiteLLM 的模型路由。
- Gemini 的 `GOOGLE_API_KEY` 别名未识别；千问、方舟、千帆需要与其接口协议匹配的路由。
- 非 OpenAI 厂商会回退读取 OpenAI 密钥及地址。
- Agent 固定传入 `temperature=0.2`，不适用于部分推理模型；工具调用历史会丢失部分厂商所需的推理状态、签名字段。

## 选择与优先级

工具请求可单独设置 `AI_TOOL_REASONING_EFFORT=none`。本次真实联调中的配置网关明确拒绝 Chat Completions 同时携带工具与非 `none` 推理级别，因此启用了此项；普通请求继续使用 `AI_REASONING_EFFORT`。该覆盖仅用于 OpenAI 路由的工具请求，默认不启用，不自动尝试付费重试，也不保证所有兼容网关接受同一参数。

1. 系统/启动进程环境变量优先于 `.env`（`override=False`）。若修改文件后仍使用旧值，检查启动脚本、终端和服务管理器中的同名变量。
2. 模型选择：调用方显式模型 > `AI_MODEL` > `AI_NAME` > `AI_MODEL_NAME`。明确的 `provider/model` 前缀优先于 `AI_PROVIDER`。
3. 未指定模型时，读取 `AI_PROVIDER` 对应的 `*_MODEL`；未指定厂商则读取 `OPENAI_MODEL`，最后默认 `openai/gpt-4o`。样例密钥不用于推断激活厂商。
4. 裸模型支持 Claude、Gemini、DeepSeek、Qwen、Doubao、ERNIE 常见名称识别；私有模型或组织名路径应明确写 `openai/<完整模型ID>`，或设置 `AI_PROVIDER=openai`。
5. 密钥：`AI_API_KEY` > 当前厂商专用变量；地址：`AI_BASE_URL` > `AI_API_BASE` > 当前厂商专用地址 > 内置/SDK 默认地址。全局覆盖项会影响图像模型，混用厂商时优先使用专用变量。

完整可复制片段在根目录 `.env.example`。每次只激活一个厂商的片段，保留模型 ID 原样；示例模型不是对账户权限或模型在线状态的保证。

| 服务 | AI_MODEL 写法 | 密钥变量 | 协议/地址说明 |
|---|---|---|---|
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| OpenAI 兼容代理 | `openai/<模型ID>` | `OPENAI_API_KEY` | `OPENAI_BASE_URL` 填代理的 API 根地址 |
| Anthropic | `anthropic/claude-sonnet-4-6` | `ANTHROPIC_API_KEY` | 原生 Messages，由 LiteLLM 转换 |
| Gemini / AI Studio | `gemini/gemini-2.5-flash` | `GEMINI_API_KEY` 或 `GOOGLE_API_KEY` | 原生 Gemini，由 LiteLLM 转换 |
| DeepSeek | `deepseek/deepseek-chat` | `DEEPSEEK_API_KEY` | 原生 LiteLLM DeepSeek 路由 |
| 百炼 / 千问 | `dashscope/qwen-plus` | `DASHSCOPE_API_KEY` | 转换到 OpenAI 兼容模式 |
| 火山方舟 / 豆包 | `ark/<模型或接入点ID>` | `ARK_API_KEY` | OpenAI 兼容 `/api/v3` |
| 百度千帆 | `qianfan/<模型ID>` | `QIANFAN_API_KEY` | OpenAI 兼容 v2，旧版 Secret Key 流程不适用 |
| Moonshot / Kimi | `moonshot/<模型ID>` | `MOONSHOT_API_KEY` | OpenAI 兼容接口 |
| 智谱 GLM | `zhipu/<模型ID>` | `ZHIPU_API_KEY` | OpenAI 兼容接口 |
| 硅基流动 | `siliconflow/Qwen/<模型ID>` | `SILICONFLOW_API_KEY` | 保留组织名和完整模型 ID |
| OpenRouter | `openrouter/anthropic/<模型ID>` | `OPENROUTER_API_KEY` | 保留二级厂商前缀 |
| Azure OpenAI | `azure/<部署名>` | `AZURE_API_KEY` | 另配 `AZURE_BASE_URL`、`AZURE_API_VERSION` |
| Ollama | `ollama_chat/qwen3:8b` | 本地通常无需 | `OLLAMA_BASE_URL=http://localhost:11434` |

千问别名 `qwen`、Google 别名 `google`、方舟别名 `doubao`/`volcengine` 也受支持。不同区域与 Coding Plan 套餐可能使用不同 URL 和密钥，需按服务商控制台替换。

## 离线诊断

在项目 Python 环境执行：

```sh
python -m services.ai_gateway.diagnose
```

输出加载路径、环境覆盖变量名、实际模型路由、脱敏后的地址、密钥是否存在及来源变量名、超时、输出预算、实际推理参数、LiteLLM 版本。命令不输出密钥，不向模型发送请求，也不验证账户权限。

检查顺序：

1. `provider` / `request_model` 是否匹配预期服务；只填写 `OPENAI_API_KEY` 不会覆盖现有的 `AI_MODEL=deepseek/...`。
2. 使用代理时必须填写其 Base URL。不要把完整 `/chat/completions`、`/responses` 或 `/messages` URL 当作 Base URL。
3. 若收到 401，检查选中厂商的密钥与套餐；404 / model-not-found 检查模型 ID、部署名、Base URL 和账户模型权限；429 检查额度和速率；连接/超时问题检查网络并调整 `AI_TIMEOUT`（毫秒）。
4. Agent 模型必须支持 tools / function calling。应用不会靠解析普通文本来执行工具，也不会因厂商不支持工具而绕过现有权限控制。只支持 Responses、只支持普通文本或自定义协议的接口不能仅靠换 Base URL 接入当前 Chat Completions 调用链。
5. 推理模型默认省略固定温度，OpenAI o 系列和 GPT-5/6 系列使用 `max_completion_tokens`。Anthropic thinking 预算须小于 `AI_MAX_TOKENS`。自定义网关的模型能力仍需根据其协议确认。

多厂商回归测试使用模拟响应验证请求路由和两轮工具调用，不代表已完成所有厂商的真实网络联调。

## 协议参考

- [OpenAI Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
- [GPT-6 Sol 工具调用限制](https://developers.openai.com/api/docs/models/gpt-6-sol)
- [GPT-6.1 Sol 工具调用限制](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
- [LiteLLM 支持的厂商](https://docs.litellm.ai/docs/providers)
- [LiteLLM OpenAI 兼容端点](https://docs.litellm.ai/docs/providers/openai_compatible)
- [LiteLLM Gemini](https://docs.litellm.ai/docs/providers/gemini)
- [方舟 Base URL 与鉴权](https://docs.volcengine.com/docs/ark/base-url-and-authentication?lang=en)
- [千帆 OpenAI 兼容接口](https://ai.baidu.com/ai-doc/WENXINWORKSHOP/2m3fihw8s)
