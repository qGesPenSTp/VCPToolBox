"""
截图提取模块
使用FFmpeg从视频中提取关键帧
"""

import sys
import subprocess
from pathlib import Path
import uuid


class ScreenshotExtractor:
    """截图提取器"""
    
    def __init__(self, config):
        self.config = config
        self.output_dir = config['output_dir']
        self.ffmpeg_path = config['ffmpeg_path']
        self.enable_screenshots = config['enable_screenshots']
        self.screenshot_interval = config['screenshot_interval']
        self.max_screenshots = config['max_screenshots']
    
    def extract(self, video_path, video_id):
        """
        从视频中提取截图
        
        Args:
            video_path: 视频文件路径
            video_id: 视频ID（用于命名截图文件）
        
        Returns:
            list: 截图文件路径列表
        """
        if not self.enable_screenshots:
            return []
        
        try:
            # 创建截图目录
            screenshot_dir = self.output_dir / video_id / 'screenshots'
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            
            if self.config['debug']:
                print(f"[ScreenshotExtractor] 提取截图: {video_path}", file=sys.stderr)
            
            # 获取视频时长
            duration = self._get_video_duration(video_path)
            
            if duration <= 0:
                if self.config['debug']:
                    print(f"[ScreenshotExtractor] 无法获取视频时长", file=sys.stderr)
                return []
            
            # 计算截图时间点
            timestamps = self._calculate_timestamps(duration)
            
            # 提取截图
            screenshots = []
            for i, timestamp in enumerate(timestamps):
                screenshot_path = screenshot_dir / f"screenshot_{i+1:03d}.jpg"
                
                if self._extract_frame(video_path, timestamp, screenshot_path):
                    screenshots.append(str(screenshot_path))
            
            if self.config['debug']:
                print(f"[ScreenshotExtractor] 提取完成，共{len(screenshots)}张截图", file=sys.stderr)
            
            return screenshots
            
        except Exception as e:
            if self.config['debug']:
                print(f"[ScreenshotExtractor] 截图提取失败: {str(e)}", file=sys.stderr)
            return []
    
    def _get_video_duration(self, video_path):
        """获取视频时长（秒）"""
        try:
            cmd = [
                self.ffmpeg_path,
                '-i', str(Path(video_path).absolute()),
                '-f', 'null',
                '-'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # 从stderr中解析时长
            for line in result.stderr.split('\n'):
                if 'Duration:' in line:
                    # Duration: 00:04:12.44, start: 0.000000, bitrate: 657 kb/s
                    duration_str = line.split('Duration:')[1].split(',')[0].strip()
                    h, m, s = duration_str.split(':')
                    duration = int(h) * 3600 + int(m) * 60 + float(s)
                    return duration
            
            return 0
            
        except Exception as e:
            if self.config['debug']:
                print(f"[ScreenshotExtractor] 获取时长失败: {str(e)}", file=sys.stderr)
            return 0
    
    def _calculate_timestamps(self, duration):
        """计算截图时间点"""
        # 根据间隔和最大数量计算时间点
        interval = self.screenshot_interval
        max_count = self.max_screenshots
        
        # 计算可能的截图数量
        possible_count = int(duration / interval)
        
        # 限制数量
        count = min(possible_count, max_count)
        
        if count <= 0:
            return []
        
        # 均匀分布时间点
        timestamps = []
        step = duration / (count + 1)
        
        for i in range(1, count + 1):
            timestamps.append(step * i)
        
        return timestamps
    
    def _extract_frame(self, video_path, timestamp, output_path):
        """提取单帧"""
        try:
            cmd = [
                self.ffmpeg_path,
                '-ss', str(timestamp),
                '-i', str(Path(video_path).absolute()),
                '-vframes', '1',
                '-q:v', '2',
                '-y',
                str(Path(output_path).absolute())
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                if self.config['debug']:
                    print(f"[ScreenshotExtractor] 提取帧失败: {result.stderr}", file=sys.stderr)
                return False
            
            return Path(output_path).exists()
            
        except Exception as e:
            if self.config['debug']:
                print(f"[ScreenshotExtractor] 提取帧异常: {str(e)}", file=sys.stderr)
            return False

