import sqlite3
import os
from mcp.server.fastmcp import FastMCP

DB_PATH = os.path.join(os.path.dirname(__file__), "demo.db")

mcp = FastMCP("SQLite 查询助手")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if os.path.exists(DB_PATH):
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE departments (
            id        INTEGER PRIMARY KEY,
            name      TEXT NOT NULL,
            manager   TEXT NOT NULL
        );

        CREATE TABLE employees (
            id            INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            department    TEXT NOT NULL,
            salary        REAL NOT NULL,
            hire_date     TEXT NOT NULL
        );

        INSERT INTO departments VALUES
            (1, '工程部', '张伟'),
            (2, '产品部', '李娜'),
            (3, '市场部', '王芳'),
            (4, '人事部', '刘洋'),
            (5, '财务部', '陈静');

        INSERT INTO employees VALUES
            (1,  '赵雷',   '工程部', 28000, '2020-03-15'),
            (2,  '钱梦',   '工程部', 25000, '2021-07-01'),
            (3,  '孙亮',   '工程部', 32000, '2019-11-20'),
            (4,  '李敏',   '产品部', 22000, '2022-01-10'),
            (5,  '周涛',   '产品部', 26000, '2020-08-05'),
            (6,  '吴静',   '市场部', 18000, '2023-03-01'),
            (7,  '郑强',   '市场部', 19500, '2022-09-15'),
            (8,  '王霞',   '市场部', 21000, '2021-04-20'),
            (9,  '冯刚',   '人事部', 17000, '2023-06-01'),
            (10, '陈磊',   '人事部', 16500, '2022-11-10'),
            (11, '褚丽',   '财务部', 20000, '2020-12-01'),
            (12, '卫东',   '财务部', 21500, '2019-05-18'),
            (13, '蒋浩',   '工程部', 29500, '2018-09-01'),
            (14, '沈燕',   '产品部', 24000, '2021-02-14'),
            (15, '韩宇',   '市场部', 17500, '2023-01-08'),
            (16, '杨帆',   '工程部', 31000, '2019-03-22'),
            (17, '朱玲',   '人事部', 15500, '2023-07-15'),
            (18, '秦博',   '财务部', 23000, '2020-06-30'),
            (19, '许晨',   '产品部', 27000, '2020-10-11'),
            (20, '何洁',   '工程部', 26500, '2021-12-05');
    """)

    conn.commit()
    conn.close()


@mcp.tool()
def list_tables() -> str:
    """列出数据库中所有的表名。"""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = [r["name"] for r in rows]
        if not names:
            return "数据库中没有任何表。"
        return "数据库中的表：\n" + "\n".join(f"- {n}" for n in names)
    finally:
        conn.close()


@mcp.tool()
def describe_table(table_name: str) -> str:
    """查看指定表的字段结构（字段名、类型、是否主键）。

    Args:
        table_name: 要查看的表名
    """
    conn = get_db()
    try:
        # Verify table exists
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        if not exists:
            return f"表 '{table_name}' 不存在。"

        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        lines = ["字段名       | 类型          | 主键", "-" * 38]
        for col in cols:
            pk = "是" if col["pk"] else "否"
            lines.append(f"{col['name']:<12} | {col['type']:<13} | {pk}")
        return "\n".join(lines)
    finally:
        conn.close()


@mcp.tool()
def run_query(sql: str) -> str:
    """执行 SELECT 查询并返回结果。只允许 SELECT 语句，禁止写操作。

    Args:
        sql: 要执行的 SELECT SQL 语句
    """
    stripped = sql.strip().lstrip(";").strip()
    if not stripped.upper().startswith("SELECT"):
        return "拒绝执行：只允许 SELECT 查询，不支持 INSERT / UPDATE / DELETE / DROP 等写操作。"

    conn = get_db()
    try:
        rows = conn.execute(stripped).fetchall()
        if not rows:
            return "查询成功，结果为空（0 行）。"

        col_names = rows[0].keys()
        header = " | ".join(col_names)
        separator = "-" * len(header)
        data_lines = [" | ".join(str(row[c]) for c in col_names) for row in rows]
        result = "\n".join([header, separator] + data_lines)
        return f"{result}\n\n共 {len(rows)} 行。"
    except sqlite3.Error as e:
        return f"SQL 执行出错：{e}"
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    mcp.run(transport="stdio")
