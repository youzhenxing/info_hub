# 播客模块改进建议清单

**创建时间**: 2026-02-11 17:30
**基于复盘**: 播客模块 12:00 未发送邮件问题复盘

---

## 短期改进（1 周内）

### ✅ 已完成
- [x] 修复配置传递问题
- [x] 添加环境变量支持
- [x] 验证功能恢复正常

### 🔄 待实施

#### 1. 添加配置完整性验证

**文件**: `deploy/pre-commit-verify.sh`

**检查项**:
```python
def verify_config_parameters():
    """验证配置参数传递完整性"""
    # 检查所有 ASRTranscriber 初始化是否传递 backend 参数
    files = find_files_with("ASRTranscriber(")
    for file in files:
        content = read_file(file)
        if "ASRTranscriber(" in content:
            # 检查是否传递 backend 参数
            if "backend=" not in content and "backend=asr_config.get" not in content:
                raise ConfigError(f"{file}: ASRTranscriber 未传递 backend 参数")
```

**优先级**: 高

---

#### 2. 优化错误日志输出

**文件**: `trendradar/podcast/transcriber.py`

**改进**:
```python
def __init__(self, backend="siliconflow", ...):
    self.backend = backend

    # ✅ 添加配置日志
    if backend == "assemblyai":
        if assemblyai_api_key:
            logger.info(f"[ASR] 使用 AssemblyAI，说话人分离: {'启用' if speaker_labels else '禁用'}")
        else:
            logger.warning("[ASR] 警告: AssemblyAI 模式未设置 API Key")
    elif backend == "siliconflow":
        logger.info("[ASR] 使用 SiliconFlow（无说话人分离）")
    else:
        logger.info(f"[ASR] 使用本地 WhisperX: {backend}")
```

**优先级**: 中

---

#### 3. 添加配置初始化日志

**文件**: `trendradar/podcast/processor.py`

**改进**:
```python
def _init_components(self):
    """初始化各个处理组件"""

    # ... 其他组件初始化 ...

    # ASR 转写器
    asr_config = self.podcast_config.get("ASR", self.podcast_config.get("asr", {}))
    backend = asr_config.get("BACKEND", asr_config.get("backend", "assemblyai"))

    # ✅ 输出配置信息
    print(f"[Podcast] ASR backend: {backend}")
    print(f"[Podcast] ASR model: {asr_config.get('MODEL', 'N/A')}")

    self.transcriber = ASRTranscriber(
        backend=backend,
        # ... 其他参数
    )
```

**优先级**: 中

---

## 中期改进（1 月内）

### 1. API 降级策略

**文件**: `trendradar/podcast/transcriber.py`

**实现**:
```python
class ASRTranscriber:
    def __init__(self, primary_backend="assemblyai", fallback_backend="siliconflow", ...):
        self.primary_backend = primary_backend
        self.fallback_backend = fallback_backend

    def transcribe_with_fallback(self, audio_path):
        """多级降级转写"""

        # 1. 主要方案：AssemblyAI
        result = self._transcribe_assemblyai(audio_path)
        if result.success:
            return result

        logger.warning(f"[ASR] AssemblyAI 失败: {result.error}，尝试降级")

        # 2. 备用方案：SiliconFlow（仅限小文件）
        size_mb = Path(audio_path).stat().st_size / (1024 * 1024)
        if size_mb < 200 and self.fallback_backend == "siliconflow":
            logger.info("[ASR] 降级到 SiliconFlow")
            result = self._transcribe_siliconflow(audio_path)
            if result.success:
                return result

        # 3. 最后手段：跳过转写
        logger.error("[ASR] 所有 API 失败，跳过转写")
        return TranscribeResult(
            success=False,
            skip=True,
            error="所有转写 API 均失败，建议稍后重试"
        )

    def _transcribe_assemblyai(self, audio_path):
        """AssemblyAI 转写"""
        try:
            return self._transcribe_assemblyai_internal(audio_path)
        except Exception as e:
            logger.error(f"[ASR-AssemblyAI] 转写异常: {e}")
            return TranscribeResult(success=False, error=str(e))

    def _transcribe_siliconflow(self, audio_path):
        """SiliconFlow 转写"""
        try:
            return self._transcribe_siliconflow_internal(audio_path)
        except Exception as e:
            logger.error(f"[ASR-SiliconFlow] 转写异常: {e}")
            return TranscribeResult(success=False, error=str(e))
```

**优先级**: 高

---

### 2. 文件大小预检查

**文件**: `trendradar/podcast/downloader.py`

**实现**:
```python
class AudioDownloader:
    MAX_FILE_SIZE_MB = 500  # AssemblyAI 限制

    def download(self, url: str) -> DownloadResult:
        """下载音频文件"""

        # 下载前检查文件大小
        if self.max_file_size_mb:
            # 尝试获取文件大小（HEAD 请求）
            size_mb = self._get_remote_size(url)
            if size_mb and size_mb > self.max_file_size_mb:
                logger.warning(f"[Download] 文件过大 ({size_mb:.1f}MB > {self.max_file_size_mb}MB)")
                # 提示用户或自动跳过
                return DownloadResult(
                    success=False,
                    error=f"文件过大 ({size_mb:.1f}MB)，建议使用分段处理"
                )

        # 继续下载
        ...
```

**优先级**: 中

---

### 3. 音频分段处理（用户建议）

**问题**: 超长音频（> 2小时）可能导致 API 超时

**方案**:
1. 使用 `ffprobe` 检测音频时长
2. 超过阈值时自动分段
3. 分段转写后智能合并
4. 添加段间重叠（5秒）保证连续性

**文件**:
- `trendradar/podcast/downloader.py`: 添加分段方法
- `trendradar/podcast/transcriber.py`: 添加批量转写和合并逻辑

**优先级**: 中

---

## 长期改进（持续）

### 1. 监控和告警

#### API 失败率监控
```python
# 在播客处理完成后记录统计
def record_api_stats(backend, success, duration, file_size):
    """记录 API 统计"""
    stats = {
        "backend": backend,
        "success": success,
        "duration": duration,
        "file_size": file_size,
        "timestamp": datetime.now().isoformat()
    }
    append_to_stats_file(stats)
```

#### 告警规则
- SiliconFlow 失败率 > 20%
- AssemblyAI 失败率 > 5%
- 单次转写超时 > 300 秒

**优先级**: 低

---

### 2. 配置管理改进

#### 配置验证工具
```bash
# agents/verify-config.sh
#!/bin/bash
# 验证配置参数传递完整性

echo "验证配置参数传递..."

# 检查所有创建类的地方
grep -r "ASRTranscriber(" trendradar/ | while read line; do
    file=$(echo "$line" | cut -d: -f1)
    if ! echo "$line" | grep -q "backend="; then
        echo "❌ $file: ASRTranscriber 未传递 backend 参数"
    fi
done
```

**优先级**: 中

---

### 3. 文档更新

#### 更新配置文档

**文件**: `docs/configuration.md`

**添加**:
- ASR 配置完整示例
- 环境变量配置说明
- 参数传递最佳实践

**优先级**: 低

---

## 实施优先级

| 优先级 | 改进项 | 预计工作量 | 风险 |
|--------|--------|------------|------|
| **P0** | API 降级策略 | 2h | 低 |
| **P1** | 文件大小检查 | 1h | 低 |
| **P1** | 配置完整性验证 | 1h | 中 |
| **P2** | 优化日志输出 | 0.5h | 低 |
| **P2** | 音频分段处理 | 4h | 中 |
| **P3** | 监控告警 | 2h | 低 |
| **P3** | 配置管理工具 | 1h | 低 |

**总工作量**: 约 11.5 小时

---

## 验证方法

### 短期改进验证
```bash
# 1. 配置完整性验证
bash agents/verify-config.sh

# 2. 日志输出验证
docker logs trendradar-prod 2>&1 | grep "\[ASR\]"

# 3. 功能测试
docker exec trendradar-prod python -m trendradar --podcast-only
```

### 中期改进验证
```bash
# 1. API 降级测试
# 模拟 AssemblyAI 失败场景

# 2. 文件大小检查测试
# 测试大文件处理

# 3. 音频分段测试
# 测试超长音频分段
```

---

**创建时间**: 2026-02-11 17:30
**下次审查**: 2026-03-11（1个月后）
