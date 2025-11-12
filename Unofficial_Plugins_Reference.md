# 非官方插件参考指南

本文档为 Agent 提供了两个社区非官方插件 `YtDLPDownload` 和 `VideoAnalyzer` 的快速参考信息。

---

### 1. 插件名称：`YtDLPDownload` (yt-dlp 下载器 (异步))

*   **占位符 (用于获取异步结果)**: `{{VCP_ASYNC_RESULT::YtDLPDownload::{req_id}}}`
    *   **说明**: `req_id` 是插件在提交任务后立即返回的唯一请求ID。Agent 需要将此占位符原样包含在回复中，以便服务器在任务完成后动态替换为实际结果。
*   **最简调用指令 (下载视频)**:
    ```
    <<<[TOOL_REQUEST]>>>
    tool_name:「始」YtDLPDownload「末」,
    command:「始」submit「末」,
    url:「始」[视频URL]「末」
    <<<[END_TOOL_REQUEST]>>>
    ```
    *   **说明**: `url` 参数是必填项，替换为要下载的视频链接。

---

### 2. 插件名称：`VideoAnalyzer` (AI视频分析插件)

*   **占位符**: 无特定异步结果占位符，结果通过文件保存和回调机制处理。
*   **最简调用指令 (分析视频并生成笔记)**:
    ```
    <<<[TOOL_REQUEST]>>>
    tool_name:「始」VideoAnalyzer「末」,
    command:「始」analyze「末」,
    url:「始」[视频URL或本地文件路径]「末」
    <<<[END_TOOL_REQUEST]>>>
    ```
    *   **说明**: `url` 参数是必填项，替换为要分析的视频链接或本地文件路径。`command` 字段已修正为 `analyze`，表示执行默认的分析模式。

---

## 给 Agent 的额外提示

*   `YtDLPDownload` 是一个**异步插件**，调用后会立即返回一个占位符。Agent 需要在回复中包含该占位符，以便在任务完成后获取最终结果。
*   `VideoAnalyzer` 也是一个异步插件，其结果会保存到 `Plugin/VideoAnalyzer/output/{video_id}/` 目录下，并可能通过回调机制通知。
*   在调用这两个插件时，请务必替换 `[视频URL]` 或 `[视频URL或本地文件路径]` 为实际的有效值。
*   如果需要更详细的参数（如 `YtDLPDownload` 的 `format`、`outputTemplate` 或 `VideoAnalyzer` 的 `mode`、`style` 等），请参考各自插件 `plugin-manifest.json` 中 `description` 字段的详细说明。
