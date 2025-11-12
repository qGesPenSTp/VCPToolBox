"""
笔记生成模块
使用AI生成视频笔记
"""

import sys
import requests
import json


class NoteGenerator:
    """笔记生成器"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config['ai_api_key']
        self.api_url = config['ai_api_url']
        self.model = config['ai_model']
        self.max_tokens = config['ai_max_tokens']
        
        if not self.api_key:
            raise ValueError("未配置AI API Key")
        
        if not self.api_url:
            raise ValueError("未配置AI API URL")
    
    def generate_notes(self, transcript, style='brief', custom_prompt=None):
        """
        生成视频笔记

        Args:
            transcript: 转录文本
            style: 笔记风格（academic/casual/detailed/brief/custom）
            custom_prompt: 自定义提示词（当style='custom'时使用）

        Returns:
            str: Markdown格式的笔记
        """
        # 如果使用自定义提示词
        if style == 'custom' and custom_prompt:
            prompt = custom_prompt.format(transcript=transcript)
            return self._call_ai(prompt)

        # 根据风格选择提示词
        prompts = {
            'academic': """请基于以下视频转录文本，生成学术风格的笔记。要求：
1. 使用正式的学术语言
2. 提取关键概念和理论
3. 组织成清晰的层次结构
4. 包含重要的论据和证据
5. 使用Markdown格式

转录文本：
{transcript}""",
            
            'casual': """请基于以下视频转录文本，生成口语化的笔记。要求：
1. 使用轻松易懂的语言
2. 提取核心要点
3. 保持简洁明了
4. 使用Markdown格式

转录文本：
{transcript}""",
            
            'detailed': """请基于以下视频转录文本，生成详细的笔记。要求：
1. 完整记录所有重要信息
2. 保留细节和例子
3. 组织成清晰的结构
4. 使用Markdown格式，包含标题、列表等

转录文本：
{transcript}""",
            
            'brief': """请基于以下视频转录文本，生成简要笔记。要求：
1. 提取核心要点
2. 简洁明了
3. 使用Markdown格式

转录文本：
{transcript}"""
        }
        
        prompt = prompts.get(style, prompts['brief']).format(transcript=transcript)
        
        return self._call_ai(prompt)
    
    def generate_summary(self, transcript):
        """
        生成视频摘要
        
        Args:
            transcript: 转录文本
        
        Returns:
            str: 视频摘要
        """
        prompt = f"""请基于以下视频转录文本，生成简短的摘要（200字以内）。

转录文本：
{transcript}"""
        
        return self._call_ai(prompt)
    
    def _call_ai(self, prompt):
        """
        调用AI API
        
        Args:
            prompt: 提示词
        
        Returns:
            str: AI响应
        """
        try:
            if self.config['debug']:
                print(f"[NoteGenerator] 调用AI API...", file=sys.stderr)
            
            # 构建API URL
            api_url = self.api_url.rstrip('/')
            if not api_url.endswith('/chat/completions'):
                api_url = f"{api_url}/chat/completions"
            
            # 准备请求
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json'
            }
            
            data = {
                'model': self.model,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': self.max_tokens,
                'temperature': 0.7
            }
            
            # 发送请求
            response = requests.post(
                api_url,
                headers=headers,
                json=data,
                timeout=120
            )
            
            # 检查响应
            if response.status_code != 200:
                raise RuntimeError(f"API请求失败 ({response.status_code}): {response.text}")
            
            # 解析响应
            result = response.json()
            
            if 'choices' not in result or len(result['choices']) == 0:
                raise RuntimeError(f"API响应格式错误: {result}")
            
            content = result['choices'][0]['message']['content']
            
            if self.config['debug']:
                print(f"[NoteGenerator] AI响应完成，长度: {len(content)}", file=sys.stderr)
            
            return content
            
        except requests.exceptions.Timeout:
            raise RuntimeError("AI API请求超时（120秒）")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"AI API请求失败: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"笔记生成失败: {str(e)}")

