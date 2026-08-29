# 需求文档

## 简介

本功能将现有 intelliprocess 项目的 AI 助手能力从基于关键词分类的静态路由方案（`intent.py` + 固定工具调用）升级为基于 **Strands Agents** 框架的单 Agent 架构。Agent 使用 Amazon Bedrock Claude 3 Sonnet 作为推理引擎，自主决策调用哪些工具（DynamoDB 结构化查询、Bedrock Knowledge Base RAG 检索、S3 Vectors 语义向量检索），并通过 **Server-Sent Events（SSE）** 流式推送响应。前端 ChatDrawer / ChatWindow 同步改造为消费 SSE 流。对话历史持久化逻辑从旧路由迁移至新架构，继续写入 DynamoDB `CONVERSATION_TABLE`。

---

## 词汇表

- **Agent**：基于 Strands Agents 框架实例化的单一 AI 代理，使用 Claude 3 Sonnet 作为底层模型，通过工具调用完成多数据源查询与回答。
- **Strands Agents**：AWS 提供的 Python Agent 编排框架，支持将普通函数注册为工具并由 LLM 自主调用。
- **SSE（Server-Sent Events）**：基于 HTTP 的单向流式协议，服务端持续推送 `text/event-stream` 格式的事件块，客户端通过 `EventSource` 或 `fetch` + `ReadableStream` 消费。
- **Bedrock Knowledge Base（KB）**：AWS 托管的 RAG 服务，用于检索组织文档（政策、合同、程序等）。
- **S3 Vectors**：AWS S3 语义向量检索能力，用于对非结构化内容进行相似性搜索，作为 KB 的补充检索路径。
- **DynamoDB 工具**：`app/services/tools.py` 中已有的五个函数（`query_invoices`、`count_invoices_by_status`、`get_invoice_detail`、`query_purchase_orders`、`query_goods_receipts`），将直接注册为 Strands 工具。
- **CONVERSATION_TABLE**：DynamoDB 表，存储每轮对话的 user/assistant 消息，由 `settings.CONVERSATION_TABLE` 配置。
- **ChatDrawer**：前端右侧弹出式抽屉组件（`ChatDrawer.tsx`），包裹 ChatWindow。
- **ChatWindow**：前端核心对话窗口组件（`ChatWindow.tsx`），负责消息列表渲染与用户输入。
- **SSE 流式 Token**：Agent 推理过程中逐步产出的文本片段，通过 SSE 事件实时推送至客户端。
- **BedrockService**：`app/services/bedrock.py` 中待实现的 Bedrock 调用封装类。

---

## 需求

### 需求 1：Strands Agent 替换现有路由逻辑

**用户故事：** 作为后端工程师，我希望用 Strands Agents 框架完全替换 `app/routers/chat.py` 中基于关键词分类的路由方案，以便让 Agent 自主决策工具调用，无需维护关键词词典和 intent 分类器。

#### 验收标准

1. THE Agent 服务 SHALL 使用 Strands Agents 框架初始化单一 Agent 实例，并注册所有可用工具。
2. WHEN 后端启动时，THE Agent 服务 SHALL 从 `settings.BEDROCK_MODEL_ID` 读取模型 ID 并配置 Claude 3 Sonnet 作为推理引擎。
3. THE Agent 服务 SHALL 将 `app/services/tools.py` 中的 `query_invoices`、`count_invoices_by_status`、`get_invoice_detail`、`query_purchase_orders`、`query_goods_receipts` 五个函数直接注册为 Strands 工具，保持其现有函数签名和文档字符串不变。
4. WHEN 用户提交问题时，THE Agent 服务 SHALL 自主决定调用零个或多个工具，并综合工具返回结果生成最终回答，不再依赖 `classify()` 函数或 `intent.py` 中的关键词规则。
5. THE `app/services/intent.py` 模块 SHALL 在新 Agent 架构上线后保留文件但不再被 `chat.py` 路由引用。
6. IF Agent 初始化失败（例如 `BEDROCK_MODEL_ID` 为空或 Bedrock 服务不可达），THEN THE Agent 服务 SHALL 抛出带有明确错误描述的 `RuntimeError`，并在应用启动日志中记录该错误。

---

### 需求 2：多数据源工具注册

**用户故事：** 作为产品经理，我希望 Agent 能够访问 Bedrock Knowledge Base、S3 Vectors 和 DynamoDB 三类数据源，以便它能回答结构化业务问题、文档政策问题和语义相似性问题。

#### 验收标准

1. THE Agent 服务 SHALL 注册一个 `search_knowledge_base` 工具，该工具接受 `query: str` 和可选 `category_filter: str` 参数，调用 Bedrock Knowledge Base 的 `retrieve_and_generate` 接口并返回答案文本及引用列表。
2. THE Agent 服务 SHALL 注册一个 `search_s3_vectors` 工具，该工具接受 `query: str` 参数，对 S3 Vectors 索引执行语义相似性检索并返回相关文档片段列表。
3. WHEN `settings.KNOWLEDGE_BASE_ID` 为空或为占位符值时，THE `search_knowledge_base` 工具 SHALL 返回表示该能力不可用的固定消息字符串，而不是抛出异常。
4. WHEN `settings.S3_VECTORS_INDEX` 为空或未配置时，THE `search_s3_vectors` 工具 SHALL 返回表示该能力不可用的固定消息字符串，而不是抛出异常。
5. THE Agent 服务 SHALL 在工具注册时为每个工具提供清晰的自然语言描述（docstring），使 Claude 能够正确判断何时调用哪个工具。
6. WHERE `settings.STAGE` 等于 `"dev"` 时，THE `search_knowledge_base` 工具 SHALL 返回标明"本地开发环境不可用"的固定消息，与现有 `_handle_document` 行为保持一致。

---

### 需求 3：SSE 流式响应端点

**用户故事：** 作为前端工程师，我希望聊天 API 以 SSE 流的形式逐 Token 推送 Agent 回答，以便用户在等待完整响应时能看到文字逐步显示，改善交互体验。

#### 验收标准

1. THE Chat 路由器 SHALL 提供 `POST /chat/stream` 端点，返回 `Content-Type: text/event-stream` 响应，支持 CORS 并设置 `Cache-Control: no-cache`。
2. WHEN Agent 产出文本 Token 时，THE Chat 路由器 SHALL 以 `data: {"type": "token", "content": "<text>"}` 格式通过 SSE 逐块推送该 Token。
3. WHEN Agent 完成全部推理并产出最终回答后，THE Chat 路由器 SHALL 推送一条 `data: {"type": "done", "sessionId": "<id>", "sourceType": "<type>", "citations": [...], "dataSnapshot": {...}}` 格式的终止事件。
4. IF Agent 推理过程中发生异常，THEN THE Chat 路由器 SHALL 推送一条 `data: {"type": "error", "message": "<描述>"}` 格式的错误事件，并关闭流连接，HTTP 状态码维持 200（遵循 SSE 规范）。
5. THE `POST /chat` 端点 SHALL 保留并继续正常工作，以维持与现有客户端的向后兼容性，直至前端改造完成。
6. WHILE SSE 流处于活跃状态时，THE Chat 路由器 SHALL 每 15 秒推送一条 `data: {"type": "ping"}` 保活事件，防止代理或负载均衡器关闭空闲连接。
7. THE `POST /chat/stream` 端点 SHALL 接受与 `POST /chat` 相同的请求体结构（`question`、`sessionId`、`categoryFilter`），并执行相同的 Cognito 身份验证中间件。

---

### 需求 4：对话历史持久化迁移

**用户故事：** 作为系统架构师，我希望新 Agent 架构继续将每轮对话写入 DynamoDB `CONVERSATION_TABLE`，以便对话历史、会话列表和会话详情接口无需改动。

#### 验收标准

1. WHEN Agent 完成一次回答后，THE Chat 路由器 SHALL 将用户消息和 Assistant 消息各写入一条记录到 `CONVERSATION_TABLE`，记录结构与现有 `_persist_turn` 函数写入的字段格式完全一致（`sessionId`、`timestamp`、`userId`、`role`、`content`、`intent`、`citations`、`source_type`）。
2. THE Chat 路由器 SHALL 在 SSE 流的 `done` 事件推送完成后（流关闭前）执行持久化操作。
3. IF 持久化写入 DynamoDB 失败，THEN THE Chat 路由器 SHALL 仅记录错误日志，不中断已完成的流式响应，与现有 `_persist_turn` 的容错行为一致。
4. THE `GET /chat/sessions` 和 `GET /chat/sessions/{session_id}` 端点 SHALL 在新架构上线后无需修改，直接复用现有实现。
5. WHEN 新会话首次请求时 `sessionId` 为空，THE Chat 路由器 SHALL 生成一个新的 UUID 作为 `sessionId`，并在 SSE `done` 事件中返回该值。

---

### 需求 5：前端 ChatWindow SSE 流式消费

**用户故事：** 作为前端工程师，我希望 ChatWindow 组件改用 `fetch` + `ReadableStream` 消费 SSE 流，以便用户能看到 Assistant 回答逐字显示的打字机效果。

#### 验收标准

1. THE ChatWindow 组件 SHALL 在用户发送消息后向 `POST /chat/stream` 发起 `fetch` 请求，并通过 `response.body.getReader()` 读取 SSE 事件流。
2. WHEN 收到 `type: "token"` 事件时，THE ChatWindow 组件 SHALL 将 `content` 字段追加到当前 Assistant 消息气泡中，实现逐字显示效果。
3. WHEN 收到 `type: "done"` 事件时，THE ChatWindow 组件 SHALL 用事件中的 `citations`、`dataSnapshot`、`sessionId` 字段更新当前消息记录，并将加载状态重置为 `false`。
4. WHEN 收到 `type: "error"` 事件或 `fetch` 请求本身抛出异常时，THE ChatWindow 组件 SHALL 在错误提示横幅中展示错误信息，并将加载状态重置为 `false`。
5. THE `sendChatMessage` 函数（`api.ts`）SHALL 被一个新的 `streamChatMessage` 函数取代或补充，该函数返回一个 `AsyncIterable` 或接受回调参数，以供 ChatWindow 消费 SSE 事件。
6. WHILE SSE 流读取进行中，THE ChatWindow 组件 SHALL 禁用发送按钮，与现有 `loading` 状态逻辑一致。
7. IF 用户在流结束前关闭 ChatDrawer，THEN THE ChatWindow 组件 SHALL 中止正在进行的 `fetch` 请求（通过 `AbortController`），并清理相关状态。

---

### 需求 6：新增配置项

**用户故事：** 作为 DevOps 工程师，我希望所有新数据源和框架所需的配置项都通过现有的 `Settings` 类和 `.env` 文件管理，以便部署配置与现有基础设施保持一致。

#### 验收标准

1. THE `Settings` 类 SHALL 新增 `S3_VECTORS_INDEX: str = ""` 字段，用于存储 S3 Vectors 索引名称或 ARN。
2. THE `Settings` 类 SHALL 新增 `STRANDS_MAX_TOKENS: int = 4096` 字段，用于控制 Agent 单次推理的最大输出 Token 数。
3. THE `Settings` 类 SHALL 新增 `STRANDS_TEMPERATURE: float = 0.0` 字段，用于控制 Agent 推理的采样温度，默认值 `0.0` 保证输出确定性。
4. THE `.env.example` 文件 SHALL 包含上述三个新字段的示例值和注释说明。
5. WHERE 新配置项未在 `.env` 中设置时，THE `Settings` 类 SHALL 使用上述默认值，不抛出校验错误，确保本地开发零配置可启动。

---

### 需求 7：`BedrockService` 实现

**用户故事：** 作为后端工程师，我希望 `app/services/bedrock.py` 提供完整的 `BedrockService` 类实现，以便 `search_knowledge_base` 工具和 Strands Agent 能够通过统一接口调用 Bedrock。

#### 验收标准

1. THE `BedrockService` 类 SHALL 实现 `invoke_model(prompt: str, max_tokens: int, temperature: float) -> str` 方法，通过 `bedrock-runtime` 客户端调用 `settings.BEDROCK_MODEL_ID` 指定的模型，并返回模型输出的文本内容。
2. THE `BedrockService` 类 SHALL 实现 `retrieve_and_generate(question: str, knowledge_base_id: str, category_filter: str | None) -> dict` 方法，调用 Bedrock Knowledge Base 的 `RetrieveAndGenerate` API，并返回包含 `answer` 和 `citations` 字段的字典。
3. IF `bedrock-runtime` 或 `bedrock-agent-runtime` 客户端调用返回 `ClientError`，THEN THE `BedrockService` 方法 SHALL 将原始异常包装为带有上下文描述的新异常并重新抛出，同时记录 `ERROR` 级别日志。
4. THE `BedrockService` 类 SHALL 使用 `settings.AWS_REGION` 初始化 boto3 客户端，不硬编码区域值。
