# SQLite 查询 MCP Server

用 Python 实现的 MCP Server，将本地 SQLite 数据库的查询能力暴露给 Claude Desktop，让 Claude 能用自然语言查数据。

## 系统结构

```
Claude Desktop
     ↓  MCP 协议（stdio）
server.py（本项目）
     ↓  SQL
demo.db（本地 SQLite 文件）
```

## 暴露的工具

| 工具               | 入参                | 说明                                                               |
| ------------------ | ------------------- | ------------------------------------------------------------------ |
| `list_tables`    | 无                  | 列出数据库中所有表名                                               |
| `describe_table` | `table_name: str` | 查看指定表的字段结构（名称、类型、是否主键）                       |
| `run_query`      | `sql: str`        | 执行 SELECT 查询，禁止写操作（INSERT/UPDATE/DELETE/DROP 会被拦截） |

## 快速开始

### 1. 安装依赖

```bash
pip install mcp
```

### 2. 验证工具可用（可选）

```bash
python3 -c "import server; print(server.list_tables())"
```

### 3. 接入 Claude Desktop

编辑 Claude Desktop 配置文件：

```
  方式一：Finder 直接跳转
  Finder → 菜单栏「前往」→「前往文件夹」→ 粘贴路径回车：
  ~/Library/Application Support/Claude/
  
  方式二：终端直接编辑
  open ~/Library/Application\ Support/Claude/claude_desktop_config.json
  用默认文本编辑器打开，或者换成 code / cursor 等编辑器命令。

  方式三：终端创建并编辑（如果文件不存在）
  mkdir -p ~/Library/Application\ Support/Claude
  open ~/Library/Application\ Support/Claude/
  然后在打开的 Finder 窗口里新建 claude_desktop_config.json。
```

- macOS：`~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows：`%APPDATA%\Claude\claude_desktop_config.json`

添加以下配置（替换路径为实际路径）：

```json
{
  "mcpServers": {
    "sqlite": {
      "command": "python3",
      "args": ["/绝对路径/mcpServer/server.py"]
    }
  }
}
```

重启 Claude Desktop 即可生效。

## 演示数据

首次启动时若 `demo.db` 不存在，会自动创建两张表：

**employees**（员工信息）

| 字段       | 类型    | 说明     |
| ---------- | ------- | -------- |
| id         | INTEGER | 主键     |
| name       | TEXT    | 姓名     |
| department | TEXT    | 部门名   |
| salary     | REAL    | 薪资     |
| hire_date  | TEXT    | 入职日期 |

**departments**（部门信息）

| 字段    | 类型    | 说明   |
| ------- | ------- | ------ |
| id      | INTEGER | 主键   |
| name    | TEXT    | 部门名 |
| manager | TEXT    | 负责人 |

预置 20 名员工、5 个部门的假数据。

## 对话示例

> **用户**：这个数据库里有哪些表？
>
> **Claude**：调用 `list_tables`，返回 `departments`、`employees`

---

> **用户**：帮我查薪资最高的 5 名员工及其部门
>
> **Claude**：先调用 `describe_table` 了解结构，再调用 `run_query` 执行 JOIN 查询，以自然语言呈现结果

---

> **用户**：帮我删掉所有员工数据
>
> **Claude**：`run_query` 拦截请求，告知只支持查询操作

## 文件说明

```
mcpServer/
├── server.py   # MCP Server 主程序
├── demo.db     # SQLite 数据库（自动创建）
├── task.md     # 项目需求文档
└── README.md   # 本文件
```
