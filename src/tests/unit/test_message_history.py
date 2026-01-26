"""
单元测试用于测试 message_history.py 模块

测试覆盖：
- Message 数据类
- SelectedMessagesSchema Pydantic 模型
- MessageHistory 类的所有方法
"""

import hashlib
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import ValidationError

from src.utils.message_history import (
    Message,
    MessageHistory,
    SelectedMessagesSchema,
)


# ======================================================================
# Message 数据类测试
# ======================================================================


class TestMessage:
    """测试 Message 数据类"""

    def test_message_creation(self):
        """测试创建 Message 对象"""
        message = Message(
            id=0,
            query="What is the capital of France?",
            answer="The capital of France is Paris.",
            summary="Paris is the capital of France.",
        )

        assert message.id == 0
        assert message.query == "What is the capital of France?"
        assert message.answer == "The capital of France is Paris."
        assert message.summary == "Paris is the capital of France."

    def test_message_with_empty_strings(self):
        """测试带有空字符串的 Message"""
        message = Message(id=1, query="", answer="", summary="")
        assert message.id == 1
        assert message.query == ""
        assert message.answer == ""
        assert message.summary == ""

    def test_message_with_long_content(self):
        """测试带有长内容的 Message"""
        long_query = "Query " * 100
        long_answer = "Answer " * 200
        long_summary = "Summary " * 50

        message = Message(id=2, query=long_query, answer=long_answer, summary=long_summary)

        assert len(message.query) == len(long_query)
        assert len(message.answer) == len(long_answer)
        assert len(message.summary) == len(long_summary)


# ======================================================================
# SelectedMessagesSchema 测试
# ======================================================================


class TestSelectedMessagesSchema:
    """测试 SelectedMessagesSchema Pydantic 模型"""

    def test_valid_schema(self):
        """测试创建有效的 schema"""
        schema = SelectedMessagesSchema(message_ids=[0, 1, 2])
        assert schema.message_ids == [0, 1, 2]

    def test_empty_message_ids(self):
        """测试空的消息 ID 列表"""
        schema = SelectedMessagesSchema(message_ids=[])
        assert schema.message_ids == []

    def test_single_message_id(self):
        """测试单个消息 ID"""
        schema = SelectedMessagesSchema(message_ids=[5])
        assert schema.message_ids == [5]

    def test_missing_message_ids_field(self):
        """测试缺少必需字段"""
        with pytest.raises(ValidationError):
            SelectedMessagesSchema()

    def test_invalid_message_ids_type(self):
        """测试无效的消息 ID 类型"""
        # Pydantic v2 会自动转换字符串数字，所以需要使用非数字字符串
        with pytest.raises(ValidationError):
            SelectedMessagesSchema(message_ids=[0, "abc", 2])


# ======================================================================
# MessageHistory 类测试
# ======================================================================


class TestMessageHistoryInit:
    """测试 MessageHistory 初始化"""

    def test_initialization(self):
        """测试默认初始化"""
        history = MessageHistory(model="test-model")
        assert history.messages == []
        assert history.model == "test-model"
        assert history.relevantMessagesByQuery == {}

    def test_initialization_with_different_model(self):
        """测试使用不同模型初始化"""
        history = MessageHistory(model="gpt-4")
        assert history.model == "gpt-4"


class TestMessageHistoryHashQuery:
    """测试 _hash_query 方法"""

    def test_hash_query_basic(self):
        """测试基本的哈希功能"""
        history = MessageHistory(model="test-model")
        result = history._hash_query("hello world")
        assert len(result) == 12
        assert isinstance(result, str)

    def test_hash_query_consistency(self):
        """测试哈希一致性"""
        history = MessageHistory(model="test-model")
        query = "test query"
        hash1 = history._hash_query(query)
        hash2 = history._hash_query(query)
        assert hash1 == hash2

    def test_hash_query_different_inputs(self):
        """测试不同输入产生不同哈希"""
        history = MessageHistory(model="test-model")
        hash1 = history._hash_query("query 1")
        hash2 = history._hash_query("query 2")
        assert hash1 != hash2

    def test_hash_query_matches_md5(self):
        """测试哈希与 MD5 匹配"""
        history = MessageHistory(model="test-model")
        query = "hello world"
        expected = hashlib.md5(query.encode()).hexdigest()[:12]
        assert history._hash_query(query) == expected

    def test_hash_query_empty_string(self):
        """测试空字符串哈希"""
        history = MessageHistory(model="test-model")
        result = history._hash_query("")
        assert len(result) == 12

    def test_hash_query_unicode(self):
        """测试 Unicode 字符哈希"""
        history = MessageHistory(model="test-model")
        result = history._hash_query("你好世界")
        assert len(result) == 12


class TestMessageHistorySetModel:
    """测试 set_model 方法"""

    def test_set_model(self):
        """测试设置模型"""
        history = MessageHistory(model="test-model")
        history.set_model("new-model")
        assert history.model == "new-model"


class TestMessageHistoryGenerateSummary:
    """测试 generate_summary 方法"""

    @pytest.mark.asyncio
    async def test_generate_summary_success(self):
        """测试成功生成摘要"""
        history = MessageHistory(model="test-model")

        with patch(
            "src.utils.message_history.llm_call", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "Paris is the capital of France."

            summary = await history.generate_summary(
                query="What is the capital of France?",
                answer="The capital of France is Paris.",
            )

            assert summary == "Paris is the capital of France."
            mock_llm.assert_called_once()

            # 验证调用参数
            call_args = mock_llm.call_args
            assert "Query:" in call_args[1]["prompt"]
            assert "What is the capital" in call_args[1]["prompt"]
            assert "test-model" in call_args[1]["model"]

    @pytest.mark.asyncio
    async def test_generate_summary_truncates_long_answer(self):
        """测试长答案被截断"""
        history = MessageHistory(model="test-model")
        long_answer = "A" * 2000  # 超过 1500 字符限制

        with patch(
            "src.utils.message_history.llm_call", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "Summary"

            await history.generate_summary(query="Test", answer=long_answer)

            call_args = mock_llm.call_args
            # 验证答案被截断到 1500 字符
            assert len(call_args[1]["prompt"]) < len(long_answer) + 100

    @pytest.mark.asyncio
    async def test_generate_summary_on_exception(self):
        """测试异常时的回退行为"""
        history = MessageHistory(model="test-model")

        with patch(
            "src.utils.message_history.llm_call", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.side_effect = Exception("LLM error")

            summary = await history.generate_summary(
                query="What is the capital of France?",
                answer="The capital of France is Paris.",
            )

            # 验证回退到默认摘要格式
            assert "Answer to:" in summary
            assert "What is the capital" in summary


class TestMessageHistoryAddMessage:
    """测试 add_message 方法"""

    @pytest.mark.asyncio
    async def test_add_message_success(self):
        """测试成功添加消息"""
        history = MessageHistory(model="test-model")

        with patch(
            "src.utils.message_history.llm_call", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "Test summary"

            await history.add_message(
                query="Test query",
                answer="Test answer",
            )

            assert len(history.messages) == 1
            message = history.messages[0]
            assert message.id == 0
            assert message.query == "Test query"
            assert message.answer == "Test answer"
            assert message.summary == "Test summary"

    @pytest.mark.asyncio
    async def test_add_multiple_messages(self):
        """测试添加多条消息"""
        history = MessageHistory(model="test-model")

        with patch(
            "src.utils.message_history.llm_call", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "Summary"

            await history.add_message(query="Query 1", answer="Answer 1")
            await history.add_message(query="Query 2", answer="Answer 2")
            await history.add_message(query="Query 3", answer="Answer 3")

            assert len(history.messages) == 3
            assert history.messages[0].id == 0
            assert history.messages[1].id == 1
            assert history.messages[2].id == 2

    @pytest.mark.asyncio
    async def test_add_message_clears_cache(self):
        """测试添加消息时清除缓存"""
        history = MessageHistory(model="test-model")

        # 先在缓存中添加一些数据
        cache_key = history._hash_query("test query")
        history.relevantMessagesByQuery[cache_key] = []

        with patch(
            "src.utils.message_history.llm_call", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "Summary"
            await history.add_message(query="New query", answer="New answer")

            # 验证缓存被清除
            assert len(history.relevantMessagesByQuery) == 0


class TestMessageHistorySelectRelevantMessages:
    """测试 select_relevant_messages 方法"""

    @pytest.mark.asyncio
    async def test_select_with_empty_history(self):
        """测试空历史记录时返回空列表"""
        history = MessageHistory(model="test-model")
        selected = await history.select_relevant_messages("Current query")
        assert selected == []

    @pytest.mark.asyncio
    async def test_select_with_cache_hit(self):
        """测试缓存命中"""
        history = MessageHistory(model="test-model")

        # 需要先有消息才能使用缓存
        history.messages = [
            Message(id=0, query="Old query", answer="Old answer", summary="Old summary")
        ]

        # 添加缓存条目
        cache_key = history._hash_query("test query")
        cached_messages = [history.messages[0]]
        history.relevantMessagesByQuery[cache_key] = cached_messages

        # 验证从缓存返回
        selected = await history.select_relevant_messages("test query")
        assert selected == cached_messages

    @pytest.mark.asyncio
    async def test_select_messages_success(self):
        """测试成功选择相关消息"""
        history = MessageHistory(model="test-model")

        # 添加一些消息
        history.messages = [
            Message(id=0, query="Query 1", answer="Answer 1", summary="Summary 1"),
            Message(id=1, query="Query 2", answer="Answer 2", summary="Summary 2"),
            Message(id=2, query="Query 3", answer="Answer 3", summary="Summary 3"),
        ]

        with patch(
            "src.utils.message_history.llm_call_with_structured_output",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = {"message_ids": [0, 2]}

            selected = await history.select_relevant_messages("Current query")

            assert len(selected) == 2
            assert selected[0].id == 0
            assert selected[1].id == 2

    @pytest.mark.asyncio
    async def test_select_messages_caches_result(self):
        """测试结果被缓存"""
        history = MessageHistory(model="test-model")
        history.messages = [
            Message(id=0, query="Query 1", answer="Answer 1", summary="Summary 1")
        ]

        with patch(
            "src.utils.message_history.llm_call_with_structured_output",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.return_value = {"message_ids": [0]}

            # 第一次调用
            selected1 = await history.select_relevant_messages("test query")
            # 第二次调用（应该从缓存返回）
            selected2 = await history.select_relevant_messages("test query")

            assert selected1 == selected2
            # LLM 应该只被调用一次
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_select_messages_with_invalid_ids(self):
        """测试处理无效 ID"""
        history = MessageHistory(model="test-model")
        history.messages = [
            Message(id=0, query="Query 1", answer="Answer 1", summary="Summary 1"),
            Message(id=1, query="Query 2", answer="Answer 2", summary="Summary 2"),
        ]

        with patch(
            "src.utils.message_history.llm_call_with_structured_output",
            new_callable=AsyncMock,
        ) as mock_llm:
            # 返回无效 ID
            mock_llm.return_value = {"message_ids": [0, 5, -1, 1]}

            selected = await history.select_relevant_messages("test query")

            # 只有有效 ID 应该被返回
            assert len(selected) == 2
            assert selected[0].id == 0
            assert selected[1].id == 1

    @pytest.mark.asyncio
    async def test_select_messages_on_exception(self):
        """测试异常时返回空列表"""
        history = MessageHistory(model="test-model")
        history.messages = [
            Message(id=0, query="Query 1", answer="Answer 1", summary="Summary 1")
        ]

        with patch(
            "src.utils.message_history.llm_call_with_structured_output",
            new_callable=AsyncMock,
        ) as mock_llm:
            mock_llm.side_effect = Exception("LLM error")

            selected = await history.select_relevant_messages("test query")
            assert selected == []

    @pytest.mark.asyncio
    async def test_select_messages_with_malformed_response(self):
        """测试处理格式错误的响应"""
        history = MessageHistory(model="test-model")
        history.messages = [
            Message(id=0, query="Query 1", answer="Answer 1", summary="Summary 1")
        ]

        with patch(
            "src.utils.message_history.llm_call_with_structured_output",
            new_callable=AsyncMock,
        ) as mock_llm:
            # 返回格式错误的响应
            mock_llm.return_value = {"invalid_field": [0, 1]}

            selected = await history.select_relevant_messages("test query")
            assert selected == []


class TestMessageHistoryFormatForPlanning:
    """测试 format_for_planning 方法"""

    def test_format_empty_messages(self):
        """测试格式化空消息列表"""
        history = MessageHistory(model="test-model")
        result = history.format_for_planning([])
        assert result == ""

    def test_format_single_message(self):
        """测试格式化单条消息"""
        history = MessageHistory(model="test-model")
        messages = [
            Message(
                id=0, query="What is France?", answer="Paris", summary="Capital is Paris"
            )
        ]

        result = history.format_for_planning(messages)
        assert "User: What is France?" in result
        assert "Assistant: Capital is Paris" in result

    def test_format_multiple_messages(self):
        """测试格式化多条消息"""
        history = MessageHistory(model="test-model")
        messages = [
            Message(id=0, query="Query 1", answer="Answer 1", summary="Summary 1"),
            Message(id=1, query="Query 2", answer="Answer 2", summary="Summary 2"),
            Message(id=2, query="Query 3", answer="Answer 3", summary="Summary 3"),
        ]

        result = history.format_for_planning(messages)
        lines = result.split("\n\n")

        assert len(lines) == 3
        assert "User: Query 1" in lines[0]
        assert "Assistant: Summary 1" in lines[0]
        assert "User: Query 2" in lines[1]
        assert "Assistant: Summary 2" in lines[1]
        assert "User: Query 3" in lines[2]
        assert "Assistant: Summary 3" in lines[2]


class TestMessageHistoryGetMessages:
    """测试 get_messages 方法"""

    def test_get_messages_empty(self):
        """测试获取空消息列表"""
        history = MessageHistory(model="test-model")
        messages = history.get_messages()
        assert messages == []

    def test_get_messages_returns_copy(self):
        """测试返回消息的副本"""
        history = MessageHistory(model="test-model")
        history.messages = [
            Message(id=0, query="Query", answer="Answer", summary="Summary")
        ]

        messages = history.get_messages()
        messages.append(Message(id=1, query="New", answer="New", summary="New"))

        # 原始列表不应该被修改
        assert len(history.messages) == 1

    def test_get_messages_with_content(self):
        """测试获取有内容的消息列表"""
        history = MessageHistory(model="test-model")
        history.messages = [
            Message(id=0, query="Query 1", answer="Answer 1", summary="Summary 1"),
            Message(id=1, query="Query 2", answer="Answer 2", summary="Summary 2"),
        ]

        messages = history.get_messages()
        assert len(messages) == 2
        assert messages[0].id == 0
        assert messages[1].id == 1


class TestMessageHistoryGetUserMessages:
    """测试 get_user_messages 方法"""

    def test_get_user_messages_empty(self):
        """测试获取空用户消息列表"""
        history = MessageHistory(model="test-model")
        user_messages = history.get_user_messages()
        assert user_messages == []

    def test_get_user_messages_with_content(self):
        """测试获取用户消息"""
        history = MessageHistory(model="test-model")
        history.messages = [
            Message(id=0, query="Query 1", answer="Answer 1", summary="Summary 1"),
            Message(id=1, query="Query 2", answer="Answer 2", summary="Summary 2"),
            Message(id=2, query="Query 3", answer="Answer 3", summary="Summary 3"),
        ]

        user_messages = history.get_user_messages()
        assert len(user_messages) == 3
        assert user_messages == ["Query 1", "Query 2", "Query 3"]


class TestMessageHistoryHasMessages:
    """测试 has_messages 方法"""

    def test_has_messages_empty(self):
        """测试空历史记录"""
        history = MessageHistory(model="test-model")
        assert not history.has_messages()

    def test_has_messages_with_content(self):
        """测试有消息的历史记录"""
        history = MessageHistory(model="test-model")
        history.messages = [
            Message(id=0, query="Query", answer="Answer", summary="Summary")
        ]
        assert history.has_messages()


class TestMessageHistoryClear:
    """测试 clear 方法"""

    def test_clear_messages(self):
        """测试清除消息"""
        history = MessageHistory(model="test-model")
        history.messages = [
            Message(id=0, query="Query 1", answer="Answer 1", summary="Summary 1"),
            Message(id=1, query="Query 2", answer="Answer 2", summary="Summary 2"),
        ]
        history.relevantMessagesByQuery = {"key": []}

        history.clear()

        assert history.messages == []
        assert history.relevantMessagesByQuery == {}

    def test_clear_empty_history(self):
        """测试清除空历史记录"""
        history = MessageHistory(model="test-model")
        history.clear()

        assert history.messages == []
        assert history.relevantMessagesByQuery == {}


# ======================================================================
# 集成测试
# ======================================================================


class TestMessageHistoryIntegration:
    """集成测试 - 测试多个方法的组合使用"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """测试完整的工作流程"""
        history = MessageHistory(model="test-model")

        with patch(
            "src.utils.message_history.llm_call", new_callable=AsyncMock
        ) as mock_llm:
            mock_llm.return_value = "Summary"

            # 1. 添加消息
            await history.add_message(query="Query 1", answer="Answer 1")
            await history.add_message(query="Query 2", answer="Answer 2")

            assert history.has_messages()
            assert len(history.get_messages()) == 2

            # 2. 获取用户消息
            user_queries = history.get_user_messages()
            assert user_queries == ["Query 1", "Query 2"]

            # 3. 清除
            history.clear()
            assert not history.has_messages()

    @pytest.mark.asyncio
    async def test_message_selection_workflow(self):
        """测试消息选择工作流程"""
        history = MessageHistory(model="test-model")

        with patch(
            "src.utils.message_history.llm_call", new_callable=AsyncMock
        ) as mock_summarize:
            mock_summarize.return_value = "Summary"

            # 添加消息
            await history.add_message(query="France capital", answer="Paris")
            await history.add_message(query="UK capital", answer="London")

            with patch(
                "src.utils.message_history.llm_call_with_structured_output",
                new_callable=AsyncMock,
            ) as mock_select:
                mock_select.return_value = {"message_ids": [0]}

                # 选择相关消息
                selected = await history.select_relevant_messages("Tell me about France")
                assert len(selected) == 1
                assert selected[0].query == "France capital"

                # 再次调用应该使用缓存
                selected_cached = await history.select_relevant_messages(
                    "Tell me about France"
                )
                assert selected == selected_cached
                mock_select.assert_called_once()
