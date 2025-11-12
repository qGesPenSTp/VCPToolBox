# VideoAnalyzer - AI视频分析插件

AI视频分析工具，支持视频下载、截图提取、音频转文字、AI笔记生成。

## 功能特性

### 核心功能
- ✅ **多平台支持**: Bilibili、YouTube、本地视频
- ✅ **视频下载**: 使用yt-dlp自动下载在线视频
- ✅ **截图提取**: 自动提取关键帧并插入笔记
- ✅ **音频转文字**: 使用OpenAI Whisper API（gpt-4o-transcribe）
- ✅ **AI笔记生成**: 使用AI API生成结构化Markdown笔记
- ✅ **完整保存**: 自动保存笔记、转录、截图和JSON结果

### 分析模式
- **download**: 只下载视频（不进行任何分析）
- **transcribe**: 只转文字（不生成笔记）
- **analyze**: 转文字+AI分析（默认）
- **summary**: 生成视频摘要

### 笔记风格
- **academic**: 学术风格
- **casual**: 口语风格
- **detailed**: 详细记录
- **brief**: 简要总结（默认）
- **custom**: 自定义风格（需提供custom_prompt）

## 安装依赖

### 必需依赖
```bash
# Python依赖
pip install -r requirements.txt

# FFmpeg（用于音频提取和截图）
# Windows (使用Chocolatey):
choco install ffmpeg

# macOS (使用Homebrew):
brew install ffmpeg

# Linux (Ubuntu/Debian):
sudo apt-get install ffmpeg
```

### 可选依赖
```bash
# yt-dlp（用于下载在线视频）
pip install yt-dlp
```

## 配置

编辑 `config.env` 文件：

```env
# Whisper API配置
WHISPER_API_KEY=your_api_key
WHISPER_API_URL=https://api.openai.com/v1
WHISPER_MODEL=gpt-4o-transcribe

# AI分析API配置
AI_API_KEY=your_api_key
AI_API_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# FFmpeg路径
FFMPEG_PATH=ffmpeg

# 截图配置
ENABLE_SCREENSHOTS=true
SCREENSHOT_INTERVAL=30
MAX_SCREENSHOTS=10
```

## 使用方法

### 基础用法

#### 只下载视频
```text
<<<[TOOL_REQUEST]>>>
tool_name:「始」VideoAnalyzer「末」,
url:「始」https://www.bilibili.com/video/BV1234567890「末」,
mode:「始」download「末」
<<<[END_TOOL_REQUEST]>>>
```

#### 只转录音频
```text
<<<[TOOL_REQUEST]>>>
tool_name:「始」VideoAnalyzer「末」,
url:「始」D:/Videos/example.mp4「末」,
mode:「始」transcribe「末」
<<<[END_TOOL_REQUEST]>>>
```

#### 分析Bilibili视频
```text
<<<[TOOL_REQUEST]>>>
tool_name:「始」VideoAnalyzer「末」,
url:「始」https://www.bilibili.com/video/BV1234567890「末」
<<<[END_TOOL_REQUEST]>>>
```

#### 分析本地视频
```text
<<<[TOOL_REQUEST]>>>
tool_name:「始」VideoAnalyzer「末」,
url:「始」D:/Videos/example.mp4「末」,
mode:「始」analyze「末」,
style:「始」academic「末」
<<<[END_TOOL_REQUEST]>>>
```

#### 生成视频摘要
```text
<<<[TOOL_REQUEST]>>>
tool_name:「始」VideoAnalyzer「末」,
url:「始」https://www.youtube.com/watch?v=xxxxx「末」,
mode:「始」summary「末」
<<<[END_TOOL_REQUEST]>>>
```

#### 自定义分析
```text
<<<[TOOL_REQUEST]>>>
tool_name:「始」VideoAnalyzer「末」,
url:「始」https://www.bilibili.com/video/BV1234567890「末」,
mode:「始」analyze「末」,
style:「始」custom「末」,
custom_prompt:「始」请将以下视频转录文本整理成一份简洁的要点列表，每个要点不超过20字：\n\n{transcript}「末」
<<<[END_TOOL_REQUEST]>>>
```

### 命令行测试

```bash
# 下载模式
echo '{"url":"https://www.bilibili.com/video/BV1234567890","mode":"download"}' | python VideoAnalyzer.py

# 转录模式
echo '{"url":"video.mp4","mode":"transcribe"}' | python VideoAnalyzer.py

# 分析模式
echo '{"url":"https://www.bilibili.com/video/BV1234567890","mode":"analyze","style":"detailed"}' | python VideoAnalyzer.py

# 摘要模式
echo '{"url":"video.mp4","mode":"summary"}' | python VideoAnalyzer.py

# 自定义分析
echo '{"url":"video.mp4","mode":"analyze","style":"custom","custom_prompt":"请将以下视频转录文本整理成一份简洁的要点列表：\n\n{transcript}"}' | python VideoAnalyzer.py
```

## 输出文件

插件会在 `output/{video_id}/` 目录下生成：

```
output/
└── {video_id}/
    ├── notes.md              # Markdown笔记（含截图、分析和转录）
    ├── transcript.txt        # 完整转录文本
    ├── result.json           # JSON格式结果
    └── screenshots/          # 视频截图目录
        ├── screenshot_001.jpg
        ├── screenshot_002.jpg
        └── ...
```

### notes.md 结构

```markdown
# 视频分析笔记

## 基本信息
- 视频URL
- 分析模式
- 分析时间

## 视频截图
![截图1](...)
![截图2](...)

## 分析内容
[AI生成的结构化笔记]

## 完整转录
[完整的转录文本]
```

## 使用场景

### 批量下载视频
```text
mode='download'
```
只下载视频文件，不进行任何分析。适合批量下载视频。

### 音频转文字
```text
mode='transcribe'
```
只转录音频，不进行AI分析。适合需要字幕或文字记录的场景。

### 学习笔记
```text
mode='analyze', style='academic'
```
适合学习视频，生成学术风格的结构化笔记。

### 视频摘要
```text
mode='summary', style='brief'
```
快速生成视频摘要，了解核心内容。

### 详细分析
```text
mode='analyze', style='detailed'
```
生成详细的分析笔记，包含所有细节。

### 自定义分析
```text
mode='analyze', style='custom', custom_prompt='...'
```
使用自定义提示词，完全控制AI分析的输出格式和内容。

## 技术架构

### 模块组成
- **VideoAnalyzer.py**: 主程序，协调各模块
- **video_downloader.py**: 视频下载模块（yt-dlp）
- **audio_extractor.py**: 音频提取模块（FFmpeg）
- **screenshot_extractor.py**: 截图提取模块（FFmpeg）
- **transcriber.py**: 音频转文字模块（Whisper API）
- **note_generator.py**: AI笔记生成模块
- **result_saver.py**: 结果保存模块

### 工作流程
1. 下载或获取视频文件
2. 提取视频截图（可选）
3. 提取音频
4. 音频转文字
5. AI分析生成笔记
6. 保存所有结果

## 常见问题

### Q: FFmpeg未找到
A: 确保FFmpeg已安装并在系统PATH中，或在config.env中指定完整路径。

### Q: yt-dlp下载失败
A: 确保yt-dlp已安装：`pip install yt-dlp`

### Q: Whisper API错误
A: 检查API Key和URL配置是否正确。

### Q: 截图提取失败
A: 确保下载的是完整视频（不是纯音频），检查YTDLP_FORMAT配置。

### Q: 下载的视频没有声音
A: 视频本身有音频流，可能是播放器不支持AV1编码。建议使用VLC等支持AV1的播放器。

### Q: 如何使用自定义提示词
A: 设置`style='custom'`并提供`custom_prompt`参数，使用`{transcript}`作为转录文本的占位符。

## 版本历史

### v1.0.0 (2025-10-05)
- ✅ 初始版本
- ✅ 支持视频下载
- ✅ 支持截图提取
- ✅ 支持音频转文字
- ✅ 支持AI笔记生成
- ✅ 支持多种分析模式和笔记风格
- ✅ 自动保存结果文件

## 许可证

MIT License

## 作者

VCP Team

