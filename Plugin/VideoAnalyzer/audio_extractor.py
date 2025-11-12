"""
音频提取模块
使用FFmpeg从视频中提取音频
"""

import sys
import subprocess
from pathlib import Path
import uuid


class AudioExtractor:
    """音频提取器"""
    
    def __init__(self, config):
        self.config = config
        self.temp_dir = config['temp_dir']
        self.ffmpeg_path = config['ffmpeg_path']
    
    def extract(self, video_path):
        """
        从视频中提取音频
        
        Args:
            video_path: 视频文件路径
        
        Returns:
            str: 音频文件路径
        """
        try:
            # 生成音频文件名
            audio_id = str(uuid.uuid4())
            audio_path = self.temp_dir / f"{audio_id}.wav"
            
            if self.config['debug']:
                print(f"[AudioExtractor] 提取音频: {video_path}", file=sys.stderr)
            
            # 构建FFmpeg命令
            # 在Windows上需要使用绝对路径
            video_path_abs = Path(video_path).absolute()
            audio_path_abs = Path(audio_path).absolute()

            cmd = [
                self.ffmpeg_path,
                '-i', str(video_path_abs),
                '-vn',  # 不处理视频
                '-acodec', 'pcm_s16le',  # 音频编码
                '-ar', str(self.config['audio_sample_rate']),  # 采样率
                '-ac', '1',  # 单声道
                '-y',  # 覆盖输出文件
                '-loglevel', 'error',  # 只显示错误
                str(audio_path_abs)
            ]

            if self.config['debug']:
                print(f"[AudioExtractor] FFmpeg命令: {' '.join(cmd)}", file=sys.stderr)

            # 执行FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"音频提取失败: {result.stderr}")
            
            if not audio_path.exists():
                raise RuntimeError("音频提取完成但未找到文件")
            
            if self.config['debug']:
                print(f"[AudioExtractor] 提取完成: {audio_path}", file=sys.stderr)
            
            return str(audio_path)
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("音频提取超时（300秒）")
        except FileNotFoundError:
            raise RuntimeError(f"未找到FFmpeg: {self.ffmpeg_path}")
        except Exception as e:
            raise RuntimeError(f"音频提取失败: {str(e)}")

