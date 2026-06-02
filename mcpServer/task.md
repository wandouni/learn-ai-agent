
## 项目定义

**名称：** SQLite 查询 MCP Server

**一句话目标：** 用 Python 实现一个 MCP Server，把本地 SQLite 数据库的查询能力暴露给 Claude Desktop，让 Claude 能用自然语言查数据。

---

## 背景：MCP 是什么

MCP（Model Context Protocol）是 Anthropic 定义的一套标准协议，解决的问题是：**AI 怎么安全、统一地调用外部工具和数据源。**

类比理解：MCP Server 就像一个"插座面板"——你把数据库、OA 系统、文件系统都做成插座，Claude 这个"用电设备"随时插上就能用，不需要每次重新写集成代码。

---

## 系统边界

```
Claude Desktop
     ↓  MCP 协议（stdio）
MCP Server（你写的 Python 程序）
     ↓  SQL
SQLite 数据库文件（本地 .db 文件）
```

Claude Desktop 是客户端，你的 Python 程序是服务端，两者通过标准输入输出通信，不需要起 HTTP 服务。

---

## 需要暴露的工具（Tools）

MCP Server 对外暴露 3 个工具，Claude 可以按需调用：

**工具一：list_tables**

* 入参：无
* 出参：数据库中所有表名的列表
* 用途：让 Claude 先摸清楚"这个库里有什么"

**工具二：describe_table**

* 入参：`table_name`（字符串）
* 出参：该表的字段名、字段类型、是否主键
* 用途：让 Claude 了解表结构，才能写出正确 SQL

**工具三：run_query**

* 入参：`sql`（字符串，SELECT 语句）
* 出参：查询结果（行列格式）+ 实际返回行数
* 约束：只允许 SELECT，禁止 INSERT / UPDATE / DELETE / DROP，在 Server 端做拦截

---

## 演示数据

Server 启动时如果检测到数据库不存在，自动创建一个示例库，包含两张表：

* `employees`：员工信息（id、姓名、部门、薪资、入职日期）
* `departments`：部门信息（id、部门名、负责人）

预置约 20 条假数据，够用来演示各种查询场景。

---

## 验收标准

在 Claude Desktop 里能完成以下对话：

> 用户："这个数据库里有哪些表？"
> Claude：调用 list_tables，返回表名列表

> 用户："帮我查一下薪资最高的 5 个员工，以及他们所在的部门"
> Claude：先 describe_table 看结构，再 run_query 执行 JOIN 查询，结果以自然语言呈现

> 用户："帮我删掉所有员工数据"
> Claude：run_query 被拦截，告知只支持查询操作

---

## 不做的事

* 不做 Web UI，不起 HTTP 服务
* 不接真实业务数据库（练习用 SQLite 本地文件）
* 不做用户鉴权
* 不支持多数据库切换

---

这个项目的核心练习点是 **理解 MCP 协议本身** ——工具怎么定义、参数 schema 怎么写、结果怎么返回。搞懂之后，把 SQLite 换成你们公司的 OA 接口或者 MySQL，逻辑完全一样。
