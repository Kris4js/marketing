"""
ToolContextManager 示例用法
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.utils.context import ToolContextManager


def example_usage_tool_context_manager():
    """ToolContextManager 示例用法"""
    manager = ToolContextManager()

    # 参数/查询 哈希处理示例
    args = {"param1": "value1", "param2": 42}
    print("Args Hash:", manager._hash_args(args))
    query = "What is the capital of France?"
    print("Query Hash:", manager.hash_query(query))

    # 生成文件名称示例
    file_name = manager._generate_filename("web_search", args)
    print("Generated File Name:", file_name)
    tool_description = manager.get_tool_description(
        "web_search",
        {
            "query": query,
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "param1": "value1",
        },
    )
    print("Tool Description:", tool_description)

    # 保存上下文示例
    filepath = manager.save_context(
        tool_name="web_search",
        args={
            "query": "What is the capital of France?",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        },
        result={
            "data": "The capital of France is Paris.",
            "source_urls": [
                "https://en.wikipedia.org/wiki/Paris",
                "https://www.britannica.com/place/Paris",
            ],
        },
        task_id=1,
        query_id="query_123",
    )
    print("Context saved at:", filepath)


async def example_usage_tool_select_relevant_contexts():
    """ToolContextManager 选择相关上下文示例用法"""
    manager = ToolContextManager()

    manager.save_context(
        tool_name="sales_data_tool",
        args={"region": "北京", "week": "2024-W22"},
        result="Sales data for Beijing region for week 22 of 2024.",
        query_id="query_456",
    )

    manager.save_context(
        tool_name="product_policy_tool",
        args={"product_model": "JSQ-12A2", "policy_type": "sales"},
        result="Sales policy for product model JSQ-12A2.",
        query_id="query_456",
    )

    # 假设已经保存了一些上下文
    pointers = manager.get_all_pointers()

    # 用户查询
    user_query = "帮我分析一下上周北京地区的产品销售数据"

    # 选择相关上下文
    relevant_filepaths = await manager.select_relevant_contexts(
        user_query, pointers
    )

    print("Relevant Context Filepaths:", relevant_filepaths)


if __name__ == "__main__":
    # example_usage_tool_context_manager()
    asyncio.run(example_usage_tool_select_relevant_contexts())
