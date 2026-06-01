# 天气播报 Agent

用 DeepSeek Function Calling 自动查天气 + AQI，综合回答"适合跑步吗"这类问题。

## 快速开始

**第一步：安装依赖**

```bash
pip3 install -r requirements.txt
```

**第二步：配置 API Key**

```bash
cp .env.example .env
# 编辑 .env，填入你的 DeepSeek Key
```

**第三步：运行**

```bash
python3 weather_agent.py
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `weather_agent.py` | Agent 主程序 |
| `explainer.html` | 执行流程可视化说明 |
| `requirements.txt` | 依赖列表 |
| `.env.example` | API Key 配置模板 |

## 注意

`.env` 文件含真实 Key，已加入 `.gitignore`，不会被提交到 git。

如需永久保存 Key，也可以写入 shell 配置：

```bash
echo 'export DEEPSEEK_API_KEY="sk-你的key"' >> ~/.zshrc
source ~/.zshrc
```
