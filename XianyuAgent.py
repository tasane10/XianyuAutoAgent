import re
from typing import List, Dict
import os
from openai import OpenAI
from loguru import logger


class XianyuReplyBot:
    def __init__(self):
        # 初始化OpenAI客户端
        self.client = OpenAI(
            api_key=os.getenv("API_KEY"),
            base_url=os.getenv("MODEL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        )
        self._init_system_prompts()
        self._init_agents()
        self.router = IntentRouter(self.agents['classify'])
        self.last_intent = None  # 记录最后一次意图


    def _init_agents(self):
        """初始化各领域Agent"""
        self.agents = {
            'classify':ClassifyAgent(self.client, self.classify_prompt, self._safe_filter),
            'price': PriceAgent(self.client, self.price_prompt, self._safe_filter),
            'tech': TechAgent(self.client, self.tech_prompt, self._safe_filter),
            'default': DefaultAgent(self.client, self.default_prompt, self._safe_filter),
        }

    def _init_system_prompts(self):
        """初始化各Agent专用提示词，优先加载用户自定义文件，否则使用Example默认文件"""
        prompt_dir = "prompts"
        
        def load_prompt_content(name: str) -> str:
            """尝试加载提示词文件"""
            # 优先尝试加载 target.txt
            target_path = os.path.join(prompt_dir, f"{name}.txt")
            if os.path.exists(target_path):
                file_path = target_path
            else:
                # 尝试默认提示词 target_example.txt
                file_path = os.path.join(prompt_dir, f"{name}_example.txt")

            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                logger.debug(f"已加载 {name} 提示词，路径: {file_path}, 长度: {len(content)} 字符")
                return content

        try:
            # 加载分类提示词
            self.classify_prompt = load_prompt_content("classify_prompt")
            # 加载价格提示词
            self.price_prompt = load_prompt_content("price_prompt")
            # 加载技术提示词
            self.tech_prompt = load_prompt_content("tech_prompt")
            # 加载默认提示词
            self.default_prompt = load_prompt_content("default_prompt")
                
            logger.info("成功加载所有提示词")
        except Exception as e:
            logger.error(f"加载提示词时出错: {e}")
            raise

    def _safe_filter(self, text: str) -> str:
        """安全过滤模块"""
        # Added '转账' and '私聊' to blocked phrases to catch more off-platform payment attempts
        blocked_phrases = ["微信", "QQ", "支付宝", "银行卡", "线下", "转账", "私聊"]
        return "[安全提醒]请通过平台沟通" if any(p in text for p in blocked_phrases) else text

    def format_history(self, context: List[Dict]) -> str:
        """格式化对话历史，返回完整的对话记录"""
        # 过滤掉系统消息，只保留用户和助手的对话
        user_assistant_msgs = [msg for msg in context if msg['role'] in ['user', 'assistant']]
        return "\n".join([f"{msg['role']}: {msg['content']}" for msg in user_assistant_msgs])

    def generate_reply(self, user_msg: str, item_desc: str, context: List[Dict]) -> str:
        """生成回复主流程"""
        # 记录用户消息
        # logger.debug(f'用户所发消息: {user_msg}')
        
        formatted_context = self.format_history(contex