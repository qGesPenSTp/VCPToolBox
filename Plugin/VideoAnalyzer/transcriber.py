"""
音频转文字模块
使用OpenAI Whisper API
"""

import sys
import requests
from pathlib import Path


class Transcriber:
    """音频转文字器"""
    
    def __init__(self, config):
        self.config = config
        self.api_key = config['whisper_api_key']
        self.api_url = config['whisper_api_url']
        self.model = config['whisper_model']
        
        if not self.api_key:
            raise ValueError("未配置Whisper API Key")
        
        if not self.api_url:
            raise ValueError("未配置Whisper API URL")
    
    def transcribe(self, audio_path, language=None):
        """
        音频转文字
        
        Args:
            audio_path: 音频文件路径
            language: 音频语言（可选）
        
        Returns:
            str: 转录文本
        """
        try:
            if self.config['debug']:
                print(f"[Transcriber] 转录音频: {audio_path}", file=sys.stderr)
            
            # 准备请求
            audio_file = Path(audio_path)
            
            if not audio_file.exists():
                raise FileNotFoundError(f"音频文件不存在: {audio_path}")
            
            # 构建API URL
            api_url = self.api_url.rstrip('/')
            if not api_url.endswith('/audio/transcriptions'):
                api_url = f"{api_url}/audio/transcriptions"
            
            # 准备文件和数据
            with open(audio_path, 'rb') as f:
                files = {
                    'file': (audio_file.name, f, 'audio/wav')
                }
                
                data = {
                    'model': self.model
                }
                
                # 添加语言参数
                if language and language != 'auto':
                    data['language'] = language
                
                # 准备headers
                headers = {
                    'Authorization': f'Bearer {self.api_key}'
                }
                
                # 发送请求
                response = requests.post(
                    api_url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=300
                )
            
            # 检查响应
            if response.status_code != 200:
                raise RuntimeError(f"API请求失败 ({response.status_code}): {response.text}")

            if self.config['debug']:
                print(f"[Transcriber] API响应状态: {response.status_code}", file=sys.stderr)
                print(f"[Transcriber] API响应内容: {response.text[:500]}", file=sys.stderr)

            # 解析响应
            result = response.json()
            
            if 'text' not in result:
                raise RuntimeError(f"API响应格式错误: {result}")
            
            transcript = result['text']
            
            if self.config['debug']:
                print(f"[Transcriber] 转录完成，文本长度: {len(transcript)}", file=sys.stderr)
            
            return transcript
            
        except requests.exceptions.Timeout:
            raise RuntimeError("API请求超时（300秒）")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API请求失败: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"转录失败: {str(e)}")

