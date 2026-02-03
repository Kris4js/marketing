from src.agent.agent import Agent
from src.agent.types import AgentConfig, DoneEvent


async def main():
    config = AgentConfig(
        model="google/gemini-2.5-flash-lite-preview-09-2025",
        model_provider="openrouter",
        max_iterations=5,
    )
    agent = Agent.create(
        config=config,
    )

    session_key = "example-basic"

    print("Mini Agent 基础示例\n")

    # Example 1: Simple conversation with tools.
    print("示例 1: List files in current directory using tool\n")

    # agent.run() returns an async generator that yields events
    async for event in agent.run(
        query="列出当前目录下的所有文件",
        session_key=session_key,
    ):
        # DoneEvent contains the final answer
        if isinstance(event, DoneEvent):
            print(f"Response: {event.answer}")

    # Example 2: Code operations with tools.
    print("\n示例 2: Read file 'README.md' and summary the content\n")

    async for event in agent.run(
        query="读取文件 'README.md' 并总结内容",
        session_key=session_key,
    ):
        if isinstance(event, DoneEvent):
            print(f"Response: {event.answer}")

    # Close the agent to clean up resources
    await agent.reset(
        session_id_or_key=session_key,
    )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
