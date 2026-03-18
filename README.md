# ReAct Agent

基于 ReAct (Reasoning + Acting) 模式的 AI 助手，集成网络搜索能力。

## 功能特性

- **ReAct 推理模式**：结合推理与行动，实现更智能的决策
- **网络搜索**：集成 Tavily 搜索引擎，获取实时信息
- **任务管理**：支持待办事项管理
- **用户偏好**：支持持久化记录用户信息和偏好并提供个性化的服务
- **意图分析**：智能理解用户意图

## 环境要求

- Python 3.8+

## 安装

1. 克隆项目：
```bash
git clone <你的仓库URL>
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 配置环境变量：
   复制 `.env.example` 为 `.env` 并填入你的 API 密钥：
```bash
cp .env.example .env
```

## 使用方法

1. 设置环境变量（API密钥）：
   - `OPENAI_API_KEY` - OpenAI API 密钥
   - `TAVILY_API_KEY` - Tavily 搜索 API 密钥

2. 运行程序：
```bash
python ReAct_Agent.py
```

## 项目结构

```
自创agent/
├── ReAct_Agent.py    # 主程序
├── requirements.txt  # 依赖列表
├── .env              # 环境变量（不提交）
├── .gitignore        # Git忽略配置
├── README.md         # 项目说明
├── tasks.md          # 用户待办清单文件
└── user_info.md      # 用户基础信息和个人偏好存储文件
```

## License

MIT License
