#!/usr/bin/env python3
"""
VideoAnalyzer Plugin - AI视频分析工具
支持视频下载、音频转文字、AI笔记生成
"""

import sys
import json
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载配置
plugin_dir = Path(__file__).parent
load_dotenv(plugin_dir / 'config.env')

# 加载主配置
main_config_path = plugin_dir.parent.parent / 'config.env'
if main_config_path.exists():
    load_dotenv(main_config_path)

# 导入模块
from video_downloader import VideoDownloader
from audio_extractor import AudioExtractor
from transcriber import Transcriber
from note_generator import NoteGenerator
from screenshot_extractor import ScreenshotExtractor
from result_saver import ResultSaver


class VideoAnalyzer:
    """视频分析器"""
    
    def __init__(self):
        self.config = {
            'whisper_api_key': os.getenv('WHISPER_API_KEY') or os.getenv('API_Key'),
            'whisper_api_url': os.getenv('WHISPER_API_URL') or os.getenv('API_URL'),
            'whisper_model': os.getenv('WHISPER_MODEL', 'whisper-1'),
            'whisper_language': os.getenv('WHISPER_LANGUAGE', 'auto'),
            'ai_api_key': os.getenv('AI_API_KEY') or os.getenv('API_Key'),
            'ai_api_url': os.getenv('AI_API_URL') or os.getenv('API_URL'),
            'ai_model': os.getenv('AI_MODEL', 'gpt-4o-mini'),
            'ai_max_tokens': int(os.getenv('AI_MAX_TOKENS', '4000')),
            'ffmpeg_path': os.getenv('FFMPEG_PATH', 'ffmpeg'),
            'temp_dir': plugin_dir / os.getenv('TEMP_DIR', './temp'),
            'output_dir': plugin_dir / os.getenv('OUTPUT_DIR', './output'),
            'max_video_duration': int(os.getenv('MAX_VIDEO_DURATION', '3600')),
            'audio_sample_rate': int(os.getenv('AUDIO_SAMPLE_RATE', '16000')),
            'ytdlp_format': os.getenv('YTDLP_FORMAT', 'bestaudio/best'),
            'download_timeout': int(os.getenv('DOWNLOAD_TIMEOUT', '300')),
            'enable_screenshots': os.getenv('ENABLE_SCREENSHOTS', 'true').lower() == 'true',
            'screenshot_interval': int(os.getenv('SCREENSHOT_INTERVAL', '30')),
            'max_screenshots': int(os.getenv('MAX_SCREENSHOTS', '10')),
            'debug': os.getenv('DEBUG', 'false').lower() == 'true',
            'keep_temp_files': os.getenv('KEEP_TEMP_FILES', 'false').lower() == 'true'
        }
        
        # 创建目录
        self.config['temp_dir'].mkdir(parents=True, exist_ok=True)
        self.config['output_dir'].mkdir(parents=True, exist_ok=True)

        # 初始化组件
        self.downloader = VideoDownloader(self.config)
        self.extractor = AudioExtractor(self.config)
        self.transcriber = Transcriber(self.config)
        self.generator = NoteGenerator(self.config)
        self.screenshot_extractor = ScreenshotExtractor(self.config)
        self.result_saver = ResultSaver(self.config)
    
    def analyze(self, url, mode='analyze', language=None, style='brief', custom_prompt=None):
        """
        分析视频

        Args:
            url: 视频URL或本地文件路径
            mode: 分析模式（download/transcribe/analyze/summary）
            language: 音频语言
            style: 笔记风格（academic/casual/detailed/brief/custom）
            custom_prompt: 自定义提示词（当style='custom'时使用）

        Returns:
            dict: 分析结果
        """
        video_id = None
        video_path = None
        audio_path = None

        try:
            # 生成视频ID
            import uuid
            video_id = str(uuid.uuid4())

            # 1. 下载或获取视频文件
            if self.config['debug']:
                print(f"[VideoAnalyzer] 处理视频: {url}", file=sys.stderr)

            video_path = self.downloader.download(url)

            # 如果只是下载模式，直接返回
            if mode == 'download':
                result = {
                    'url': url,
                    'mode': mode,
                    'video_id': video_id,
                    'video_path': video_path,
                    'content': f'视频已下载到: {video_path}'
                }

                if self.config['debug']:
                    print(f"[VideoAnalyzer] 下载完成: {video_path}", file=sys.stderr)

                return result

            # 2. 提取截图
            screenshots = []
            if self.config['enable_screenshots'] and mode != 'transcribe':
                if self.config['debug']:
                    print(f"[VideoAnalyzer] 提取截图...", file=sys.stderr)

                screenshots = self.screenshot_extractor.extract(video_path, video_id)

            # 3. 提取音频
            if self.config['debug']:
                print(f"[VideoAnalyzer] 提取音频...", file=sys.stderr)

            audio_path = self.extractor.extract(video_path)

            # 4. 音频转文字
            if self.config['debug']:
                print(f"[VideoAnalyzer] 音频转文字...", file=sys.stderr)

            transcript = self.transcriber.transcribe(audio_path, language)

            # 5. 根据模式处理
            result = {
                'url': url,
                'mode': mode,
                'transcript': transcript,
                'video_id': video_id
            }

            if mode == 'transcribe':
                # 只返回转录文本
                result['content'] = transcript

            elif mode == 'summary':
                # 生成摘要
                if self.config['debug']:
                    print(f"[VideoAnalyzer] 生成摘要...", file=sys.stderr)

                summary = self.generator.generate_summary(transcript)
                result['content'] = summary

            else:  # mode == 'analyze'
                # 生成完整笔记
                if self.config['debug']:
                    print(f"[VideoAnalyzer] 生成笔记...", file=sys.stderr)

                notes = self.generator.generate_notes(transcript, style, custom_prompt)
                result['content'] = notes

            # 6. 保存结果
            if self.config['debug']:
                print(f"[VideoAnalyzer] 保存结果...", file=sys.stderr)

            saved_files = self.result_saver.save(result, video_id, screenshots)
            result['saved_files'] = saved_files
            result['screenshots'] = screenshots

            # 7. 清理临时文件
            if not self.config['keep_temp_files']:
                self._cleanup(video_path, audio_path)

            return result

        except Exception as e:
            if self.config['debug']:
                import traceback
                print(f"[VideoAnalyzer] 错误: {str(e)}", file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
            raise
    
    def _cleanup(self, *paths):
        """清理临时文件"""
        for path in paths:
            if path and Path(path).exists():
                try:
                    Path(path).unlink()
                except Exception as e:
                    if self.config['debug']:
                        print(f"[VideoAnalyzer] 清理文件失败: {path} - {str(e)}", file=sys.stderr)


def main():
    """主函数"""
    try:
        # 读取stdin输入
        input_data = sys.stdin.read()
        
        if not input_data.strip():
            raise ValueError("未从stdin接收到输入数据")
        
        # 解析JSON
        data = json.loads(input_data)
        
        # 获取参数
        url = data.get('url')
        if not url:
            raise ValueError("缺少必需的参数: url")

        mode = data.get('mode', 'analyze')
        language = data.get('language')
        style = data.get('style', 'brief')
        custom_prompt = data.get('custom_prompt')

        # 创建分析器
        analyzer = VideoAnalyzer()

        # 执行分析
        result = analyzer.analyze(url, mode, language, style, custom_prompt)
        
        # 输出结果
        output = {
            'status': 'success',
            'result': result
        }
        
        print(json.dumps(output, ensure_ascii=False, indent=2))
        
    except Exception as e:
        output = {
            'status': 'error',
            'error': f'VideoAnalyzer错误: {str(e)}'
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == '__main__':
    main()

