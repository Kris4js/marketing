import os
import hashlib
import json

from datetime import datetime, timezone
from typing import Optional, Any
from dataclasses import dataclass, asdict

from src.model import llm_call_with_structured_output, DEFAULT_MODEL


@dataclass
class ContextPointer:
    """存储在内存中，指向磁盘上完整的工具执行详情"""

    filepath: str
    filename: str
    tool_name: str
    tool_description: str
    args: Optional[dict[str, Any]]
    task_id: Optional[int]
    query_id: Optional[str]
    source_urls: Optional[list[str]]


@dataclass
class ContextData:
    """存储在磁盘上，记录完整的工具执行详情"""

    tool_name: str
    tool_description: str
    args: dict[str, Any]
    timestamp: str
    task_id: Optional[int]
    query_id: Optional[str]
    source_urls: Optional[list[str]]
    result: Any


class ToolContextManager:
    """"""

    def __init__(
        self,
        context_dir: str = ".market/context",
        model: str = DEFAULT_MODEL,
    ) -> None:
        self.context_dir: str = context_dir
        self.model: str = model
        self.pointer: list[ContextPointer] = []
        if not os.path.exists(self.context_dir):
            os.makedirs(self.context_dir)

    def _hash_args(self, args: dict[str, Any]) -> str:
        """将参数字典转换为哈希值"""

        # 按键排序并序列化为JSON字符串
        sorted_keys = sorted(args.keys())
        args_str = json.dumps(
            {k: args[k] for k in sorted_keys}, separators=(",", ":")
        )

        # 计算MD5哈希值并取前12位
        hash_obj = hashlib.md5(args_str.encode("utf-8"))
        return hash_obj.hexdigest()[:12]

    def hash_query(self, query: str) -> str:
        """将查询字符串转换为哈希值"""
        hash_obj = hashlib.md5(query.encode("utf-8"))
        return hash_obj.hexdigest()[:12]

    def _generate_file_name(
        self, tool_name: str, args: dict[str, Any]
    ) -> str:
        """根据工具名称和参数生成唯一的文件名"""
        args_hash = self._hash_args(args)
        file_name = f"{tool_name}_{args_hash}.json"
        return file_name

    def get_tool_description(
        self, tool_name: str, args: dict[str, Any]
    ) -> str:
        """生成工具的描述性字符串"""
        parts: list[str] = []
        used_keys: set[str] = set()

        # Add search query if present
        if args.get("query"):
            parts.append(f"{args.get('query')}")
            used_keys.add("query")

        # Add date range if present
        if args.get("start_date") and args.get("end_date"):
            parts.append(
                f"from {args.get('start_date')} to {args.get('end_date')}"
            )
            used_keys.update({"start_date", "end_date"})

        # Append any remaining args not explicitly handled
        remaining_args = [
            f"{key}={value}"
            for key, value in args.items()
            if key not in used_keys
        ]
        if len(remaining_args) > 0:
            parts.append(f"[{', '.join(remaining_args)}]")

        return " ".join(parts)

    def save_context(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        task_id: Optional[int] = None,
        query_id: Optional[str] = None,
    ) -> str:
        """将工具执行的上下文数据保存到磁盘"""
        filename = self._generate_file_name(tool_name, args)
        filepath = os.path.join(self.context_dir, filename)

        tool_description = self.get_tool_description(tool_name, args)

        # Extract source_urls from ToolResult format
        source_urls: Optional[list[str]] = None
        actual_result = result

        if isinstance(result, str):
            try:
                # JSON.parser
                parsed = json.loads(result)
                if parsed.get("source_urls") is not None:
                    source_urls = parsed.get("sourceUrls")
                    actual_result = parsed["data"]

            except (json.JSONDecodeError, ValueError):
                # Result is not JSON, use as-is
                pass

        context_data = ContextData(
            tool_name=tool_name,
            args=args,
            tool_description=tool_description,
            timestamp=datetime.now(timezone.utc).isoformat(),
            task_id=task_id,
            query_id=query_id,
            source_urls=source_urls,
            result=actual_result,
        )

        # Write context data to JSON file
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(context_data), f, ensure_ascii=False, indent=2)

        context_pointer: ContextPointer = ContextPointer(
            filepath=filepath,
            filename=filename,
            tool_name=tool_name,
            args=args,
            tool_description=context_data.tool_description,
            task_id=task_id,
            query_id=query_id,
            source_urls=source_urls,
        )

        # Append to in-memory pointer list
        self.pointer.append(context_pointer)

        return filepath


if __name__ == "__main__":

    flag = '3'

    manager = ToolContextManager()

    if flag == '1':

        # 参数/查询 哈希处理示例
        args = {"param1": "value1", "param2": 42}
        print("Args Hash:", manager._hash_args(args))
        query = "What is the capital of France?"
        print("Query Hash:", manager.hash_query(query))

    elif flag == '2':
        # 生成文件名称示例
        file_name = manager._generate_file_name("web_search", args)
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

    elif flag == '3':
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
