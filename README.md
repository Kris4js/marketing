# Marketing

## Coding Phase

- [x] [message_history](src/utils/message_history.py): 将消息历史完全记录在内存中，重启时清除；

- [x] [context](src/utils/context.py): 工具调用的上下文内容，存储在磁盘中，重启时不会清除；

- [ ] [phase](src/agent/phases/): 理解、规划、执行、反思和答案合成。
  - [ ] [understand](src/agent/phases/understand.py): 从用户的查询中提取结构化信息，为后续阶段提供信息。

  - [ ] [plan](src/agent/phases/plan.py): 生成一个带有依赖关系的待办事项列表，以回答用户的查询;
    - 创建一个结构化计划 TodoLists，包括 0-5 个任务，每个任务都有一个类型（`use_tools` 或 `reason`）和依赖信息.
    - 
  
  - [ ] []

- [ ] [tool](src/tools/): 使用 DynamicStructuredTool 来实现 StructuredToolInterface

- [ ] [orchestrator](agent): 多阶段执行管道的中心协调器（Orchestrator），实例化并协调五个不同阶段的实现；
