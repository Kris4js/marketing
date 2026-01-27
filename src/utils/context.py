import os
import hashlib
import json

from datetime import datetime, timezone
from typing import Optional, Any
from dataclasses import dataclass, asdict
from pydantic import BaseModel

from src.model import llm_call_with_structured_output, DEFAULT_MODEL
from src.agent.prompts import CONTEXT_SELECTION_SYSTEM_PROMPT


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


@dataclass
class ToolSummary:
    """Lightweight summary of a tool call result (keep in context during loop)"""

    id: str  # Filepath pointer to full data on disk
    tool_name: str
    args: dict[str, Any]
    summary: str


class SelectedContextSchema(BaseModel):
    context_ids: list[int]


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

    def _generate_filename(
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
        filename = self._generate_filename(tool_name, args)
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

        context_data: ContextData = ContextData(
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
            json.dump(
                asdict(context_data), f, ensure_ascii=False, indent=2
            )

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

    def save_and_get_summary(
        self,
        tool_name: str,
        args: dict[str, Any],
        result: Any,
        query_id: str,
    ) -> ToolSummary:
        """保存上下文并返回简要摘要字符串"""
        filepath = self.save_context(
            tool_name, args, result, None, query_id
        )
        summary = self.get_tool_description(tool_name, args)

        return ToolSummary(
            id=filepath,
            tool_name=tool_name,
            args=args,
            summary=summary,
        )

    def get_all_pointers(self) -> list[ContextPointer]:
        """获取所有存储的上下文指针"""
        return self.pointer.copy()

    def get_pointers_for_query(
        self, query_id: str
    ) -> list[ContextPointer]:
        """根据查询ID获取相关的上下文指针"""
        return [
            pointer
            for pointer in self.pointer
            if pointer.query_id == query_id
        ]

    def load_contexts(self, filepaths: list[str]) -> list[ContextData]:
        """基于文件路径加载工具上下文内容"""
        contexts: list[ContextData] = []
        for filepath in filepaths:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    context = ContextData(
                        tool_name=data["tool_name"],
                        args=data["args"],
                        tool_description=data["tool_description"],
                        timestamp=data["timestamp"],
                        task_id=data.get("task_id"),
                        query_id=data.get("query_id"),
                        source_urls=data.get("source_urls"),
                        result=data["result"],
                    )
                    contexts.append(context)
            except FileNotFoundError:
                # skip failed files silently
                pass
        return contexts

    async def select_relevant_contexts(
        self,
        query: str,
        available_pointers: list[ContextPointer],
    ) -> Any:
        """使用LLM选择与查询最相关的工具上下文"""
        if len(available_pointers) == 0:
            return []

        # Load all contexts from pointers
        pointer_info = [
            {
                "id": i,
                "tool_name": ptr.tool_name,
                "tool_description": ptr.tool_description,
                "args": ptr.args,
            }
            for i, ptr in enumerate(available_pointers)
        ]

        prompt = f"""
Original user query: "{query}"

Available tool outputs:
{json.dumps(pointer_info, ensure_ascii=False, indent=2)}

Select which tool outputs are relevant for answering the query.
Return a JSON object with a "context_ids" field containing a list of IDs (0-indexed) of the relevant outputs.
Only select outputs that contain data directly relevant to answering the query.
        """

        try:
            response = await llm_call_with_structured_output(
                prompt,
                system_prompt=CONTEXT_SELECTION_SYSTEM_PROMPT,
                model=self.model,
                output_schema=SelectedContextSchema,
            )
            print("Context selection response:", response)

            selected_ids = response.context_ids
            print("Selected context IDs:", selected_ids)

            return [
                available_pointers[i].filepath
                for i in selected_ids
                if 0 <= i < len(available_pointers)
            ]

        except Exception as e:
            print("Error during context selection:", str(e))
            return [ptr.filepath for ptr in available_pointers]
