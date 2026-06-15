"""
agent.py — Agent 核心循环

整个 Agent 的"大脑循环"：
1. 接收用户输入
2. 把工具说明书 + 用户消息发给 LLM
3. LLM 自主决策：调工具 or 直接回答
4. 如果调工具 → 执行 → 结果回传 → 回到步骤 2
5. 如果直接回答 → 返回最终答案

关键点：决策权在 LLM，我们的代码只是"执行者"。
"""

import json
from openai import AsyncOpenAI
from logger import get_logger


class Agent:
    """AI Agent，负责管理 LLM 对话和工具调用循环"""

    def __init__(
        self,
        llm: AsyncOpenAI,
        model: str,
        tools: list[dict],
        tool_executors: dict[str, callable],
        verbose: bool = False,
        max_rounds: int = 10,
    ):
        self.llm = llm
        self.model = model
        self.tools = tools
        self.tool_executors = tool_executors
        self.logger = get_logger()
        self.round = 0
        self.verbose = verbose
        self.max_rounds = max_rounds
        self.max_retries = 1  # 工具失败时额外重试次数

    async def run(self, user_input: str) -> str:
        """
        运行 Agent，处理用户输入并返回最终答案。
        """
        self.logger.info("=" * 60)
        self.logger.info("Agent 启动")
        self.logger.info("=" * 60)

        # ── 工具列表（启动时打印一次）────────────────────
        self._log_tools_summary()

        # ── 用户输入 ─────────────────────────────────────
        self.logger.info("")
        self.logger.info("用户输入：%s", user_input)

        # 消息历史（system message 引导 LLM 使用 ReAct 思考模式）
        messages: list[dict] = [
            {
                "role": "system",
                "content": (
                    "你是一个使用 ReAct（Reasoning + Acting）模式工作的 AI 助手。\n"
                    "每次调用工具前，先用简短的一句话说明：你现在知道什么，以及为什么需要调用这个工具。\n"
                    "格式：先写思考，再调用工具。"
                ),
            },
            {"role": "user", "content": user_input},
        ]

        # ── 核心循环 ──────────────────────────────────────
        while self.round < self.max_rounds:
            self.round += 1
            self.logger.info("")
            self.logger.info("─" * 40)
            self.logger.info("第 %d 轮 / 上限 %d", self.round, self.max_rounds)
            self.logger.info("─" * 40)

            # 打印本轮发给 LLM 的消息
            self._log_messages(messages)

            self._think(f"\n[第 {self.round} 轮] 思考中...")

            # 调用 LLM
            response = await self.llm.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.tools,
                tool_choice="auto",
            )

            choice = response.choices[0]
            finish_reason = choice.finish_reason

            # 打印 LLM 原始响应
            self._log_llm_response(choice, finish_reason)

            # ── 情况 1：LLM 决定调工具 ───────────────────
            if finish_reason == "tool_calls":
                assistant_msg = choice.message
                messages.append(assistant_msg.model_dump())

                for tool_call in assistant_msg.tool_calls:
                    tool_name = tool_call.function.name
                    tool_args = json.loads(tool_call.function.arguments)

                    self._think(f"   决定调用工具：{tool_name}({json.dumps(tool_args, ensure_ascii=False)})")

                    self.logger.info("   执行工具：%s", tool_name)
                    self.logger.info("   参数：%s", json.dumps(tool_args, ensure_ascii=False))

                    executor = self.tool_executors.get(tool_name)
                    if executor is None:
                        result = f"错误：未找到工具 {tool_name}"
                    else:
                        result = await self._execute_with_retry(
                            executor, tool_name, tool_args
                        )

                    self._think(f"   观察结果：{str(result)[:200]}")

                    self.logger.info("   返回：%s", result[:500])

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

                continue

            # ── 情况 2：LLM 认为任务完成 ──────────────────
            if finish_reason == "stop":
                final_answer = choice.message.content or "（Agent 未返回内容）"
                self._think(f"   任务完成，准备回答")
                self.logger.info("")
                self.logger.info("=" * 60)
                self.logger.info("任务完成")
                self.logger.info("=" * 60)
                self.logger.info("最终答案：%s", final_answer)
                return final_answer

            # ── 其他情况 ──────────────────────────────────
            return f"对话异常结束（finish_reason={finish_reason}）"

        # ── 循环超限 ──────────────────────────────────────
        self._think(f"\n达到最大循环次数（{self.max_rounds} 轮），强制终止")
        self.logger.warning("达到最大循环次数 %d，强制终止", self.max_rounds)
        return f"任务未完成：已达到最大循环次数（{self.max_rounds} 轮），请尝试简化问题"

    # ── 终端思考输出 ──────────────────────────────────────

    def _think(self, msg: str) -> None:
        """verbose 模式下向终端输出思考过程"""
        if self.verbose:
            print(msg)

    # ── 工具重试 ──────────────────────────────────────────

    async def _execute_with_retry(
        self, executor, tool_name: str, tool_args: dict
    ) -> str:
        """执行工具，失败时自动重试一次"""
        last_error = None

        for attempt in range(self.max_retries + 1):  # 1 次正常 + N 次重试
            try:
                result = await executor(**tool_args)
                if attempt > 0:
                    self._think(f"   重试成功！（第 {attempt} 次重试）")
                    self.logger.info("   重试成功（第 %d 次重试）", attempt)
                return result
            except Exception as e:
                last_error = e
                if attempt < self.max_retries:
                    self._think(f"   工具执行失败：{e}，准备重试...")
                    self.logger.warning("   工具 %s 执行失败（第 %d 次）：%s，准备重试",
                                        tool_name, attempt + 1, e)
                else:
                    self.logger.error("   工具 %s 重试 %d 次后仍失败：%s",
                                      tool_name, self.max_retries, e)

        return f"工具执行出错（已重试 {self.max_retries} 次）：{last_error}"

    # ── 日志辅助方法 ──────────────────────────────────────

    def _log_tools_summary(self) -> None:
        """打印工具列表摘要"""
        self.logger.info("")
        self.logger.info("已注册工具（%d 个）：", len(self.tools))
        for t in self.tools:
            func = t["function"]
            params = func["parameters"]["properties"]
            param_names = ", ".join(params.keys())
            self.logger.info("   - %s(%s) — %s", func["name"], param_names, func["description"])

    def _log_messages(self, messages: list[dict]) -> None:
        """打印本轮发给 LLM 的消息摘要"""
        self.logger.info("")
        self.logger.info("   发送给 LLM 的消息（%d 条）：", len(messages))
        for i, msg in enumerate(messages):
            role = msg["role"]
            if role == "user":
                content = str(msg.get("content", ""))[:200]
                self.logger.info("      [%d] role=user        content=%s", i, content)
            elif role == "assistant":
                if msg.get("tool_calls"):
                    calls = msg["tool_calls"]
                    for tc in calls:
                        self.logger.info(
                            "      [%d] role=assistant   tool_calls: %s(%s)",
                            i, tc["function"]["name"], tc["function"]["arguments"],
                        )
                else:
                    content = str(msg.get("content", ""))[:200]
                    self.logger.info("      [%d] role=assistant   content=%s", i, content)
            elif role == "tool":
                content = str(msg.get("content", ""))[:200]
                call_id = str(msg.get("tool_call_id", ""))[:8]
                self.logger.info("      [%d] role=tool        tool_call_id=%s result=%s", i, call_id, content)
            else:
                self.logger.info("      [%d] role=%s", i, role)

    def _log_llm_response(self, choice, finish_reason: str) -> None:
        """打印 LLM 原始响应"""
        self.logger.info("")
        self.logger.info("   LLM 原始响应：")
        self.logger.info("      finish_reason: %s", finish_reason)

        if finish_reason == "tool_calls":
            for tc in choice.message.tool_calls:
                self.logger.info("      tool_call:")
                self.logger.info("         id:       %s", tc.id)
                self.logger.info("         name:     %s", tc.function.name)
                self.logger.info("         arguments:%s", tc.function.arguments)
        elif finish_reason == "stop":
            content = choice.message.content or ""
            self.logger.info("      content: %s", content[:500])
