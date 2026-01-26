import asyncio

from loguru import logger
from src.utils import message_history


async def main():
    # Example usage of MessageHistory
    logger.info("1. Starting MessageHistory example")
    history = message_history.MessageHistory("google/gemini-2.5-flash-lite-preview-09-2025")

    # Add a message
    logger.info("2. Adding a message to history")
    await history.add_message("What is the capital of France?", "The capital of France is Paris.")

    # Get all messages
    messages = history.get_messages()
    for msg in messages:
        logger.info(f"User: {msg.query}, Assistant: {msg.summary}")

    # Clear message history
    history.clear()


if __name__ == "__main__":
    asyncio.run(main())
