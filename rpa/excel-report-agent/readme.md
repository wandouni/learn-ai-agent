# Excel 报表 AI 分析自动化

定时扫描指定目录下的部门周报 Excel，提取关键数据，调用 **DeepSeek** 生成分析摘要，输出 Markdown 报告，并可选推送到钉钉群或邮件。

---

## 目录结构

```
excel-report-agent/
├── main.py               # 入口：定时任务 + CLI 参数
├── extractor.py          # Excel 读取、字段提取、校验
├── analyzer.py           # Prompt 构造、DeepSeek API 调用
├── reporter.py           # Markdown 报告生成
├── notifier.py           # 钉钉 / 邮件推送
├── create_sample_data.py # 生成测试用 Excel 样例
├── config.yaml           # 所有可变参数
├── requirements.txt
├── data/
│   └── excels/           # 放各部门 Excel 文件
├── reports/              # 自动生成的报告
└── logs/                 # 运行日志
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.yaml`，至少填写 DeepSeek API Key：

```yaml
deepseek:
  api_key: "sk-xxxx"      # 替换为真实 Key
  model: "deepseek-chat"
```

### 3. 生成测试数据

```bash
python3 create_sample_data.py
```

在 `data/excels/` 下生成 4 个样例文件：销售部、研发部、市场部（正常）和一个格式错误文件（用于异常验收）。

### 4. 运行

```bash
# 验证读取逻辑（不调用 DeepSeek）
python3 main.py --dry-run

# 立即执行完整流程
python3 main.py --run-now

# 处理指定周期的文件
python3 main.py --date 2025-W23

# 启动定时任务（按 config.yaml 配置，默认每周一 09:00）
python3 main.py
```

---

## Excel 文件格式

所有 Excel 文件须遵循统一模板，文件名格式：`部门名_周报_日期.xlsx`

| 行 | A 列 | B 列 | C 列 |
|----|------|------|------|
| 1 | `部门名称` | 销售部 | |
| 2 | `汇报周期` | 2025-W23 | |
| 3 | *(空行)* | | |
| 4 | `本周完成事项` | | |
| 5+ | `- 完成事项描述` | | |
| … | *(空行)* | | |
| … | `本周关键指标` | | |
| … | `指标名` | `数值` | `环比变化` |
| … | 月销售额(万元) | 1250 | +8.3% |
| … | *(空行)* | | |
| … | `下周计划` | | |
| … | `- 计划描述` | | |
| … | *(空行)* | | |
| … | `风险与问题` | | |
| … | `- 风险描述`（可为空）| | |

**环比变化格式**：`+8.3%`（上升）/ `-2.1%`（下降）/ `0%` 或 `持平`

---

## 配置说明

```yaml
deepseek:
  api_key: "your-key-here"
  model: "deepseek-chat"

paths:
  excel_dir: "./data/excels"   # Excel 文件目录
  report_dir: "./reports"      # 报告输出目录
  log_dir: "./logs"            # 日志目录

schedule:
  run_at: "09:00"              # 每次触发时间
  weekday: "monday"            # 触发星期（monday/tuesday/…）

notify:
  enabled: false               # 是否启用推送
  channel: "dingtalk"          # dingtalk / email

  # 钉钉配置
  dingtalk_webhook: ""

  # 邮件配置
  email_to: []
  smtp_host: ""
  smtp_port: 465
  smtp_user: ""
  smtp_password: ""
  email_from: ""
```

---

## 输出报告结构

报告文件存放在 `reports/` 目录，文件名包含周期和时间戳：

```
# 周报分析 · 2025-W23

## 执行摘要
（跨部门汇总分析，500 字以内）

## 各部门分析

### 销售部
（单部门分析，300 字以内）

**指标概览**

| 指标名 | 数值 | 环比变化 |
| --- | --- | --- |
| 月销售额(万元) | 1250.0 | ↑ +8.3% |
| 销售漏斗转化(%) | 12.3 | ↓ -15.2% |

### 研发部
...

## 数据异常记录
（格式不符合模板的文件及原因）

## 生成信息
生成时间：xxx  处理文件数：3  调用DeepSeek次数：4
```

---

## 推送配置

### 选项 A：钉钉群推送

1. 在钉钉群设置 → 智能群助手 → 添加"自定义机器人"
2. 复制 Webhook 地址，填入 `config.yaml`
3. 设置 `notify.enabled: true` 和 `channel: "dingtalk"`

报告生成后自动将执行摘要推送到群，摘要超过 450 字自动截断。

### 选项 B：邮件发送

填写 SMTP 相关配置后设置 `channel: "email"`，完整 Markdown 报告将以正文形式发送到 `email_to` 列表。

---

## 验收标准

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 基础验收 | `python3 main.py --run-now` | `reports/` 下生成含各部门分析和汇总的 Markdown 报告 |
| 异常验收 | 目录中含格式错误文件时运行 | 错误文件被跳过，记录在报告的「数据异常记录」章节 |
| Dry-run 验收 | `python3 main.py --dry-run` | 控制台打印结构化数据，不调用 DeepSeek，不生成报告 |
| 推送验收 | 配置钉钉 Webhook 后运行 | 群里收到执行摘要消息 |

---

## 系统流程

```
定时任务（每周一 09:00）
     ↓
扫描 data/excels/ 目录
     ↓
逐文件提取 + 校验（格式错误的跳过并记录）
     ↓
单部门 Prompt → DeepSeek → 分析摘要
     ↓
跨部门汇总 Prompt → DeepSeek → 整体摘要
     ↓
生成 Markdown 报告（reports/）
     ↓（可选）
推送钉钉 / 发送邮件
```

---

## 延伸方向

- **MCP 工具**：包装为 MCP Server，让 Claude Desktop 通过对话触发分析（"帮我分析上周的报表"）
- **数据库接入**：将 Excel 目录替换为 SQLite / MySQL 查询，实现实时取数，组合为完整数据分析 Agent 系统
