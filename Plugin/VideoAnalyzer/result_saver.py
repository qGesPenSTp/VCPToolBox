"""
结果保存模块
保存分析结果到文件
"""

import sys
import json
from pathlib import Path
from datetime import datetime


class ResultSaver:
    """结果保存器"""
    
    def __init__(self, config):
        self.config = config
        self.output_dir = config['output_dir']
    
    def save(self, result, video_id, screenshots=None):
        """
        保存分析结果
        
        Args:
            result: 分析结果字典
            video_id: 视频ID
            screenshots: 截图文件路径列表
        
        Returns:
            dict: 保存的文件路径
        """
        try:
            # 创建输出目录
            video_output_dir = self.output_dir / video_id
            video_output_dir.mkdir(parents=True, exist_ok=True)
            
            saved_files = {}
            
            # 保存转录文本
            if 'transcript' in result:
                transcript_path = video_output_dir / 'transcript.txt'
                with open(transcript_path, 'w', encoding='utf-8') as f:
                    f.write(result['transcript'])
                saved_files['transcript'] = str(transcript_path)
                
                if self.config['debug']:
                    print(f"[ResultSaver] 转录文本已保存: {transcript_path}", file=sys.stderr)
            
            # 保存笔记（Markdown格式）
            if 'content' in result:
                notes_path = video_output_dir / 'notes.md'
                
                # 生成Markdown内容
                markdown_content = self._generate_markdown(result, screenshots)
                
                with open(notes_path, 'w', encoding='utf-8') as f:
                    f.write(markdown_content)
                saved_files['notes'] = str(notes_path)
                
                if self.config['debug']:
                    print(f"[ResultSaver] 笔记已保存: {notes_path}", file=sys.stderr)
            
            # 保存JSON结果
            json_path = video_output_dir / 'result.json'
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            saved_files['json'] = str(json_path)
            
            if self.config['debug']:
                print(f"[ResultSaver] JSON结果已保存: {json_path}", file=sys.stderr)
            
            return saved_files
            
        except Exception as e:
            if self.config['debug']:
                print(f"[ResultSaver] 保存失败: {str(e)}", file=sys.stderr)
            return {}
    
    def _generate_markdown(self, result, screenshots=None):
        """生成Markdown内容"""
        lines = []
        
        # 标题
        lines.append(f"# 视频分析笔记\n")
        
        # 元信息
        lines.append(f"## 基本信息\n")
        lines.append(f"- **视频URL**: {result.get('url', 'N/A')}")
        lines.append(f"- **分析模式**: {result.get('mode', 'N/A')}")
        lines.append(f"- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"\n---\n")
        
        # 截图（如果有）
        if screenshots and len(screenshots) > 0:
            lines.append(f"## 视频截图\n")
            for i, screenshot in enumerate(screenshots):
                # 使用相对路径
                rel_path = Path(screenshot).relative_to(self.output_dir.parent)
                lines.append(f"### 截图 {i+1}\n")
                lines.append(f"![截图{i+1}]({rel_path})\n")
            lines.append(f"\n---\n")
        
        # 主要内容
        lines.append(f"## 分析内容\n")
        lines.append(result.get('content', ''))
        
        # 转录文本（如果与content不同）
        if 'transcript' in result and result['transcript'] != result.get('content'):
            lines.append(f"\n---\n")
            lines.append(f"## 完整转录\n")
            lines.append(f"```\n{result['transcript']}\n```")
        
        return '\n'.join(lines)

