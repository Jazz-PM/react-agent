from openai import OpenAI
import re
import os
import subprocess
import datetime
from tavily import TavilyClient
from dotenv import load_dotenv  # 引入dotenv

# ===================== 全局常量定义（核心：显式指定文件绝对路径）=====================
load_dotenv()  # 加载.env文件中的环境变量
os_name = os.name  # 返回nt(Windows)/posix(Linux/Mac)
current_dir = os.path.abspath(os.getcwd())  # 当前目录绝对路径

# 显式指定tasks.md和user_info.md的绝对路径，后续所有地方统一引用
USER_INFO_FILE = os.path.join(current_dir, "user_info.md")  # 用户信息文件
TASKS_FILE = os.path.join(current_dir, "tasks.md")          # 待办任务文件
file_list = [f for f in os.listdir(current_dir) if not f.startswith('.')]  # 过滤隐藏文件

# ===================== 规范读取用户信息（初次运行兼容，简洁过滤无效内容）=====================
user_info = {}
def load_user_info():
    """规范加载用户信息，兼容文件不存在/空文件/无效行，返回干净的用户信息字典"""
    info = {}
    if os.path.exists(USER_INFO_FILE):
        try:
            with open(USER_INFO_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f.readlines() if line.strip()]  # 过滤空行/空白行
            for line in lines:
                if "：" in line:  # 严格匹配【xx】：xx 或 xx：xx 格式
                    key, val = line.split("：", 1)  # 仅分割第一个冒号，避免内容含冒号
                    info[key.strip()] = val.strip()
        except Exception as e:
            print(f"用户信息文件读取警告：{str(e)}，将使用空信息")
    return info

user_info = load_user_info()  # 初始化加载用户信息

# ===================== 工具函数：日期/模型初始化 =====================
def get_current_date():
    """获取格式化当前日期"""
    return datetime.datetime.now().strftime("%Y-%m-%d")

current_date = get_current_date()

# 从.env读取DeepSeek API Key，增加异常提醒
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("未在.env文件中配置DEEPSEEK_API_KEY，请检查配置")

# 初始化大模型客户端
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

# ===================== 第一步：实现实际可执行的工具函数 =====================
def read_file(file_path):
    """读取文件内容工具，处理文件不存在/读取失败的异常"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return f"文件读取成功，内容为：{content}"
    except FileNotFoundError:
        return f"工具执行失败：文件{file_path}不存在"
    except Exception as e:
        return f"工具执行失败：{str(e)}"

def write_to_file(filename, content):
    """写入文件工具，自动处理路径，返回成功/失败信息"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return "写入成功"
    except Exception as e:
        return f"工具执行失败：{str(e)}"

def run_terminal_command(command):
    """执行终端命令工具，兼容Windows，返回输出/错误信息（修复乱码）"""
    try:
        # 执行命令，捕获stdout和stderr，超时30秒
        result = subprocess.run(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            universal_newlines=False,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        # 核心修复：先试Windows默认的gbk/gb2312，再试utf-8，最后兜底replace
        def decode_output(byte_data):
            if not byte_data:
                return ""
            # 优先gbk（Windows终端默认）
            try:
                return byte_data.decode("gbk").strip()
            except:
                pass
            # 再试utf-8（通用编码）
            try:
                return byte_data.decode("utf-8").strip()
            except:
                pass
            # 最终兜底：忽略无法解码的字符，避免乱码
            return byte_data.decode("utf-8", errors="replace").strip()
        stdout = decode_output(result.stdout)
        stderr = decode_output(result.stderr)
        if result.returncode == 0:
            return f"命令执行成功，输出：{stdout}"
        else:
            return f"命令执行失败，错误信息：{stderr}"
    except subprocess.TimeoutExpired:
        return "工具执行失败：命令执行超时（30秒）"
    except Exception as e:
        return f"工具执行失败：{str(e)}"

def web_search(query, max_results=3):
    """
    联网搜索工具，基于Tavily Search API v0实现（修复链接/摘要为空问题）
    :param query: 搜索关键词（必填）
    :param max_results: 返回结果数量（可选，默认3条）
    :return: 格式化的搜索结果/错误信息
    """
    # 从.env读取Tavily API Key，增加异常提醒
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    if not TAVILY_API_KEY:
        return "工具执行失败：未在.env文件中配置TAVILY_API_KEY，请检查配置"
    
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY)
    try:
        # 关键优化：设置search_depth="deep" 深度搜索，获取完整信息
        # 补充language="zh" 限定中文结果，提升匹配度
        search_results = tavily_client.search(
            query=query,
            max_results=max_results,
            search_depth="advanced",
            language="zh"
        )
        if not search_results or "results" not in search_results:
            return "工具执行失败：未获取到搜索结果"
        # 格式化搜索结果：修正字段名 url=链接 / content=摘要
        formatted_results = []
        for idx, item in enumerate(search_results["results"]):
            title = item.get("title", "无标题")
            url = item.get("url", "无链接")  # 正确字段：url
            content = item.get("content", "无摘要")  # 正确字段：content
            formatted_results.append(f"{idx+1}. {title}\n链接: {url}\n摘要: {content}")
        return "\n\n".join(formatted_results)
    except Exception as e:
        return f"工具执行失败：{str(e)}"

def save_user_info(info_dict):
    """
    保存用户信息到user_info.md，格式为【信息类型】：信息内容
    :param info_dict: 存储用户信息的字典，如{"姓名": "张三", "职业": "程序员"}
    """
    try:
        with open(USER_INFO_FILE, "w", encoding="utf-8") as f:
            for key, val in info_dict.items():
                f.write(f"{key}：{val}\n")
        return f"用户信息已保存到{USER_INFO_FILE}"
    except Exception as e:
        return f"用户信息保存失败：{str(e)}"

# 建立【工具名-工具函数】的映射字典，方便快速调用
TOOL_MAP = {
    "read_file": read_file,
    "write_to_file": write_to_file,
    "run_terminal_command": run_terminal_command,
    "web_search": web_search,
    "save_user_info": save_user_info
}

# ===================== 第二步：解析大模型输出的XML标签 =====================
def parse_assistant_response(response):
    """
    解析大模型的回复，提取<thought>、<action>、<final_answer>
    返回格式：(thought, action, final_answer)，不存在的字段为None
    """
    # 正则匹配XML标签，忽略换行/空格
    thought_pattern = re.compile(r"<thought>([\s\S]*?)</thought>", re.I)
    action_pattern = re.compile(r"<action>([\s\S]*?)</action>", re.I)
    final_answer_pattern = re.compile(r"<final_answer>([\s\S]*?)</final_answer>", re.I)
    thought = thought_pattern.search(response).group(1).strip() if thought_pattern.search(response) else None
    action = action_pattern.search(response).group(1).strip() if action_pattern.search(response) else None
    final_answer = final_answer_pattern.search(response).group(1).strip() if final_answer_pattern.search(response) else None
    return thought, action, final_answer

def parse_action(action_str):
    """
    解析<action>里的内容，提取工具名和参数
    兼容：位置参数(web_search("关键词"))、关键字参数(web_search(query="关键词",max_results=3))
    自动适配工具默认参数，仅校验必填参数数量
    """
    import inspect
    # 正则匹配 工具名(参数1,参数2,...)
    tool_pattern = re.compile(r"^(\w+)\(([\s\S]*)\)$")
    match = tool_pattern.match(action_str)
    if not match:
        return None, "Action格式错误，示例：read_file(\"test.txt\") 或 web_search(query=\"关键词\",max_results=3)"
    tool_name = match.group(1)
    param_str = match.group(2).strip()
    # 空参数处理
    if not param_str:
        params_dict = {}
    else:
        params_dict = {}
        # 匹配关键字参数：key="value" （优先解析，兼容大模型输出）
        kw_param_pattern = re.compile(r'(\w+)\s*=\s*"([\s\S]*?)"(?:,\s*)?')
        kw_matches = kw_param_pattern.findall(param_str)
        if kw_matches:
            for key, val in kw_matches:
                params_dict[key] = val.replace(r"\n", "\n")  # 还原换行
        else:
            # 匹配位置参数："value1","value2" （兼容原始位置参数格式）
            pos_param_pattern = re.compile(r'"([\s\S]*?)"(?:,\s*)?')
            pos_matches = pos_param_pattern.findall(param_str)
            for val in pos_matches:
                params_dict[len(params_dict)] = val.replace(r"\n", "\n")  # 用索引做key，后续转位置参数
    # 校验工具是否存在
    if tool_name not in TOOL_MAP:
        return None, f"不存在的工具：{tool_name}"
    func = TOOL_MAP[tool_name]
    sig = inspect.signature(func)
    param_names = list(sig.parameters.keys())
    param_info = sig.parameters
    # 提取【必填参数】（无默认值的参数），仅校验必填参数数量
    required_params = [p for p in param_names if param_info[p].default is inspect.Parameter.empty]
    # 位置参数转关键字参数
    final_param_dict = {}
    if len(params_dict) > 0 and isinstance(list(params_dict.keys())[0], int):
        # 处理位置参数
        if len(params_dict) < len(required_params):
            return None, f"必填参数数量不匹配，需要{len(required_params)}个（必填形参：{','.join(required_params)}），实际{len(params_dict)}个"
        # 位置参数按顺序赋值给形参
        for idx, p_name in enumerate(param_names):
            if idx in params_dict:
                final_param_dict[p_name] = params_dict[idx]
    else:
        # 处理关键字参数
        # 校验必填参数是否齐全
        missing_params = [p for p in required_params if p not in params_dict]
        if missing_params:
            return None, f"缺少必填参数：{','.join(missing_params)}，必填形参：{','.join(required_params)}"
        final_param_dict = params_dict
    # 补充工具默认参数（未传的参数用函数默认值）
    for p_name in param_names:
        if p_name not in final_param_dict and param_info[p_name].default is not inspect.Parameter.empty:
            final_param_dict[p_name] = param_info[p_name].default
    return tool_name, final_param_dict

# ===================== 第三步：工具执行核心函数 =====================
def execute_tool(action_str):
    """执行工具，输入action字符串，返回执行结果（observation）"""
    tool_name, param_info = parse_action(action_str)
    if tool_name is None:
        return f"<observation>{param_info}</observation>"  # 解析失败的错误信息
    # 新增：执行终端命令前强制用户确认
    if tool_name == "run_terminal_command":
        command = param_info.get("command", "")
        print(f"\n⚠️  即将执行终端命令：{command}")
        confirm = input("请确认是否执行？")
        if confirm.lower() not in ["y", "yes", "确认", "是", "执行", "ok", "好的", "同意", "允许", "确认执行"]:
            return f"<observation>用户取消了命令执行，任务终止</observation>"

    # 调用工具函数
    try:
        result = TOOL_MAP[tool_name](**param_info)
        # 新增：转义XML特殊字符，避免破坏标签格式
        result = result.replace("<", "&lt;").replace(">", "&gt;")
        return f"<observation>{result}</observation>"
    except Exception as e:
        err_msg = str(e).replace("<", "&lt;").replace(">", "&gt;")
        return f"<observation>工具调用异常：{err_msg}</observation>"

# ===================== 第四步：初始化对话历史（PROMPT直接引用文件路径常量）=====================
conversation_history = [
    {"role": "system", "content": fr"""
你是一个AI助手，致力于帮助人类用户解决问题。为此，你需要将问题分解为多个步骤。对于每个步骤，首先使用 <thought> 思考要做什么，然后使用可用工具之一决定一个 <action>。接着，你将根据你的行动从环境/工具中收到一个 <observation>。持续这个思考和行动的过程，直到你有足够的信息来提供 <final_answer>。
所有步骤请严格使用以下 XML 标签格式输出：
- <question> 用户问题
- <thought> 思考
- <action> 采取的工具操作
- <observation> 工具或环境返回的结果
- <final_answer> 最终答案
⸻
例子 1:
<question>埃菲尔铁塔有多高？</question>
<thought>我需要找到埃菲尔铁塔的高度。可以使用搜索工具。</thought>
<action>web_search("埃菲尔铁塔 高度")</action>
<observation>埃菲尔铁塔的高度约为330米（包含天线）。</observation>
<thought>搜索结果显示了高度。我已经得到答案了。</thought>
<final_answer>埃菲尔铁塔的高度约为330米。</final_answer>
⸻
例子 2:
<question>帮我找一个简单的番茄炒蛋食谱，并看看家里的冰箱里有没有西红柿。</question>
<thought>这个任务分两步。第一步，找到番茄炒蛋的食谱。第二步，检查冰箱里是否有西红柿。我先用 web_search 工具找食谱。</thought>
<action>web_search("简单番茄炒蛋食谱 家常")</action>
<observation>简单的番茄炒蛋食谱：将2个鸡蛋打散，2个番茄切块。热油，先炒鸡蛋，盛出。再热油，炒番茄至软烂，加入鸡蛋，放盐调味即可。</observation>
<thought>好的，我已经有食谱了。食谱需要西红柿。现在我需要用 check_fridge 工具看看冰箱里有没有西红柿。</thought>
<action>check_fridge(item="西红柿")</action>
<observation>冰箱检查结果：有3个西红柿。</observation>
<thought>我找到了食谱，并且确认了冰箱里有西红柿。可以回答问题了。</thought>
<final_answer>简单的番茄炒蛋食谱是：鸡蛋打散，番茄切块。先炒鸡蛋，再炒番茄，混合后加盐调味。冰箱里有3个西红柿。</final_answer>
     
⸻
     
请严格遵守：
1. 检测到用户姓名、性别、年龄、职业、国籍、生日、爱好、个人偏好等个人信息的增量或更新时，按【信息类型】：信息内容格式记录至 {USER_INFO_FILE}，用于个性化服务
2. 你每次回答都必须包括两个标签，第一个是 <thought>，第二个是 <action> 或 <final_answer>
3. 输出 <action> 后立即停止生成，等待真实的 <observation>，擅自生成 <observation> 将导致错误
4. 如果 <action> 中的某个工具参数有多行的话，请使用 \n 来表示，如：<action>write_to_file("/tmp/test.txt", "a\nb\nc")</action>
5. 工具参数中的文件路径请使用绝对路径，不要只给出一个文件名。比如要写 write_to_file("/tmp/test.txt", "内容")，而不是 write_to_file("test.txt", "内容")
6. 每次请求执行终端命令：run_terminal_command(command)前，务必向用户确认命令内容和潜在风险，用户回复确认后才执行，未确认前请勿执行任何命令。
7. 当需要获取全网最新/未知信息（如时事、百科、数据、食谱等）时，优先调用 web_search 工具联网搜索。但是调用联网服务须保持克制，仅当确实需要时才调用，避免过度依赖工具。搜索时请尽量使用具体且包含年份的关键词，以获取最新数据。
8. 【日期规则】当用户询问「今天是什么日期/几号」时，直接使用环境信息中的当前日期{current_date}，按「xxxx年xx月xx日」的中文格式返回答案，无需调用任何工具
9. 【时效规则】搜索时效性数据（如人口、经济、时事）时，必须将环境信息中的当前日期{current_date}的年份加入搜索关键词，优先搜索当前年份/上一年度数据，禁止使用固定旧年份
10. 【待办任务专属规则】当用户提及“待办”“任务”“待做事项”等相关关键词时，默认从待办任务文件 {TASKS_FILE} 中读取内容，无需额外询问文件路径，直接调用read_file工具即可。
⸻
     
可用工具：
read_file(file_path)：用于读取文件内容
write_to_file(filename,content)：将指定内容写入指定文件。成功时返回“写入成功"。
run_terminal_command(command)：用于执行终端命令，执行前需用户确认
web_search(query, max_results=3)：基于Tavily实现联网搜索，query为搜索关键词（必填），max_results为返回结果数（可选，默认3，可省略）
⸻
     
环境信息
操作系统:{os_name}
当前目录:{current_dir}
目录下文件列表:{file_list}
当前日期:{current_date}
用户信息及偏好:{user_info}
待办任务文件路径:{TASKS_FILE}
用户信息文件路径:{USER_INFO_FILE}
"""
     }
]

# ===================== 第五步：主对话循环（增加工具调用闭环） =====================
if __name__ == "__main__":
    print("多轮对话Agent已启动，输入exit/quit/退出结束对话\n")
    while True:
        # 获取用户输入
        user_input = input("User: ")
        # 退出指令
        if user_input.lower() in ["exit", "quit", "退出"]:
            print("对话结束")
            break
        # 封装用户任务为<question>标签，添加到对话历史（匹配大模型的指令格式）
        user_question = f"<question>{user_input}</question>"
        conversation_history.append({"role": "user", "content": user_question})
        # 工具调用循环：直到大模型输出final_answer
        while True:
            # 发送请求给大模型
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=conversation_history,
                stream=True,
                timeout=60
            )
            # 流式接收并拼接大模型回复
            print("\n小助理: ", end="", flush=True)
            assistant_response = ""
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content is not None:
                    assistant_response += content
                    print(content, end="", flush=True)
            print("\n")
            # 将大模型原始回复添加到对话历史
            conversation_history.append({"role": "assistant", "content": assistant_response})
            # 解析大模型回复：提取thought/action/final_answer
            thought, action, final_answer = parse_assistant_response(assistant_response)
            # 情况1：大模型输出final_answer，本轮任务结束，跳出工具调用循环
            if final_answer:
                break
            # 情况2：大模型输出action，执行工具并回传observation
            if action:
                # 执行工具，获取observation
                observation = execute_tool(action)
                print(f"工具执行结果: {observation}\n")
                # 将observation添加到对话历史，让大模型继续推理
                conversation_history.append({"role": "user", "content": observation})
            else:
                # 格式错误，无action/final_answer，本轮任务结束
                print("小助理回复格式错误，未检测到<action>或<final_answer>")
                break