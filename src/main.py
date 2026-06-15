"""
main.py — CLI 入口

把 tools.py 和 agent.py 串起来，提供一个命令行交互界面。
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

# 加载 .env 文件（API Key 等配置）
load_dotenv(Path(__file__).parent.parent / ".env")

from tools import get_definitions, TOOLS as tool_registry
from agent import Agent


def build_llm_client() -> AsyncOpenAI:
    """根据环境变量创建 LLM 客户端"""
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o")

    if not api_key:
        print("请设置环境变量 LLM_API_KEY")
        print("   方式 1: 在 .env 文件中添加 LLM_API_KEY=your-key")
        print("   方式 2: export LLM_API_KEY=your-key")
        sys.exit(1)

    return AsyncOpenAI(api_key=api_key, base_url=base_url), model


async def main():
    # 读取用户输入
    if len(sys.argv) > 1:
        user_input = " ".join(sys.argv[1:])
    else:
        user_input = input("您：")

    if not user_input.strip():
        print("请输入内容")
        return

    # 构建 LLM 客户端
    llm, model = build_llm_client()

    # 创建 Agent
    agent = Agent(
        llm=llm,
        model=model,
        tools=get_definitions(),
        tool_executors={name: info["execute"] for name, info in tool_registry.items()},
        verbose=True,
    )

    # 运行
    print("Agent 思考中...")
    print("-" * 40)
    result = await agent.run(user_input)
    print(result)
    print("-" * 40)


if __name__ == "__main__":
    asyncio.run(main())
