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
    ):
        self.llm = llm
        self.model = model
        self.tools = tools
        self.tool_executors = tool_executors
        self.logger = get_logger()
        self.round = 0

    async def run(self, user_input: str) -> str:
        """
        运行 Agent，处理用户输入并返回最终答案。
        """
        self.logger.info("=" * 60)
        self.logger.info("🚀 Agent 启动")
        self.logger.info("=" * 60)

        # ── 工具列表（启动时打印一次）────────────────────
        self._log_tools_summary()

        # ── 用户输入 ─────────────────────────────────────
        self.logger.info("")
        self.logger.info("👤 用户输入：%s", user_input)

        # 消息历史
        messages: list[dict] = [
            {"role": "user", "content": user_input}
        ]

        # ── 核心循环 ──────────────────────────────────────
        while True:
            self.round += 1
            self.logger.info("")
            self.logger.info("─" * 40)
            self.logger.info("📋 第 %d 轮", self.round)
            self.logger.info("─" * 40)

            # 打印本轮发给 LLM 的消息
            self._log_messages(messages)

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

                    self.logger.info("   🔧 执行工具：%s", tool_name)
                    self.logger.info("   📥 参数：%s", json.dumps(tool_args, ensure_ascii=False))

                    executor = self.tool_executors.get(tool_name)
                    if executor is None:
                        result = f"错误：未找到工具 {tool_name}"
                    else:
                        try:
                            result = await executor(**tool_args)
                        except Exception as e:
                            result = f"工具执行出错：{e}"

                    self.logger.info("   📤 返回：%s", result[:500])

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

                continue

            # ── 情况 2：LLM 认为任务完成 ──────────────────
            if finish_reason == "stop":
                final_answer = choice.message.content or "（Agent 未返回内容）"
                self.logger.info("")
                self.logger.info("=" * 60)
                self.logger.info("✅ 任务完成")
                self.logger.info("=" * 60)
                self.logger.info("💬 最终答案：%s", final_answer)
                return final_answer

            # ── 其他情况 ──────────────────────────────────
            return f"对话异常结束（finish_reason={finish_reason}）"

    # ── 日志辅助方法 ──────────────────────────────────────

    def _log_tools_summary(self) -> None:
        """打印工具列表摘要"""
        self.logger.info("")
        self.logger.info("🛠️  已注册工具（%d 个）：", len(self.tools))
        for t in self.tools:
            func = t["function"]
            params = func["parameters"]["properties"]
            param_names = ", ".join(params.keys())
            self.logger.info("   • %s(%s) — %s", func["name"], param_names, func["description"])

    def _log_messages(self, messages: list[dict]) -> None:
        """打印本轮发给 LLM 的消息摘要"""
        self.logger.info("")
        self.logger.info("   📨 发送给 LLM 的消息（%d 条）：", len(messages))
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
        self.logger.info("   ⬅️  LLM 原始响应：")
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
