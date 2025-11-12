"""
视频下载模块
支持URL下载和本地文件
"""

import sys
import os
from pathlib import Path
from urllib.parse import urlparse
import subprocess
import uuid


class VideoDownloader:
    """视频下载器"""
    
    def __init__(self, config):
        self.config = config
        self.temp_dir = config['temp_dir']
    
    def download(self, url):
        """
        下载视频或获取本地文件路径
        
        Args:
            url: 视频URL或本地文件路径
        
        Returns:
            str: 视频文件路径
        """
        # 检查是否为本地文件
        if self._is_local_file(url):
            return self._handle_local_file(url)
        
        # 下载远程视频
        return self._download_remote_video(url)
    
    def _is_local_file(self, url):
        """检查是否为本地文件"""
        # 检查是否为文件路径
        if os.path.exists(url):
            return True
        
        # 检查是否为file://协议
        parsed = urlparse(url)
        if parsed.scheme == 'file':
            return True
        
        # 检查是否为Windows路径
        if ':' in url and not url.startswith('http'):
            return True
        
        return False
    
    def _handle_local_file(self, url):
        """处理本地文件"""
        # 移除file://前缀
        if url.startswith('file://'):
            url = url[7:]
        
        # 转换为Path对象
        path = Path(url)
        
        if not path.exists():
            raise FileNotFoundError(f"本地文件不存在: {url}")
        
        if not path.is_file():
            raise ValueError(f"不是有效的文件: {url}")
        
        # 检查文件格式
        valid_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.m4v']
        if path.suffix.lower() not in valid_extensions:
            raise ValueError(f"不支持的视频格式: {path.suffix}")
        
        if self.config['debug']:
            print(f"[VideoDownloader] 使用本地文件: {path}", file=sys.stderr)
        
        return str(path.absolute())
    
    def _download_remote_video(self, url):
        """下载远程视频"""
        try:
            # 生成临时文件名
            video_id = str(uuid.uuid4())
            output_template = str(self.temp_dir / f"{video_id}.%(ext)s")
            
            if self.config['debug']:
                print(f"[VideoDownloader] 下载视频: {url}", file=sys.stderr)
            
            # 使用yt-dlp下载（使用Python模块方式）
            cmd = [
                sys.executable,  # Python解释器
                '-m', 'yt_dlp',
                '-f', self.config['ytdlp_format'],
                '-o', output_template,
                '--no-playlist',
                '--quiet',
                '--no-warnings',
                url
            ]
            
            # 执行下载
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config['download_timeout']
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"视频下载失败: {result.stderr}")
            
            # 查找下载的文件
            downloaded_files = list(self.temp_dir.glob(f"{video_id}.*"))
            
            if not downloaded_files:
                raise RuntimeError("下载完成但未找到文件")
            
            video_path = str(downloaded_files[0])
            
            if self.config['debug']:
                print(f"[VideoDownloader] 下载完成: {video_path}", file=sys.stderr)
            
            return video_path
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"下载超时（{self.config['download_timeout']}秒）")
        except FileNotFoundError:
            raise RuntimeError("未找到yt-dlp，请先安装: pip install yt-dlp")
        except Exception as e:
            raise RuntimeError(f"下载失败: {str(e)}")

