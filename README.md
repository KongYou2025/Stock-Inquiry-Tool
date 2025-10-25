# 股票查询工具

集中化的多源稳健股票行情查询项目目录。包含源代码、构建配置、分发产物、工具脚本与文档，后续开发维护均在此目录进行。

## 目录结构
- `src/` 源代码（CLI、GUI与多源采集模块）
  - `股票查询.py` CLI入口，支持多源与来源标注
  - `股票查询_gui.py` GUI入口，ttk样式、美观优化与来源标注
  - `multi_source_fetcher.py` 多源采集、动态速率限制、熔断与数据清洗
- `specs/` PyInstaller打包配置
  - `股票查询CLI.spec` CLI打包配置（指向`src/股票查询.py`）
  - `股票查询GUI.spec` GUI打包配置（指向`src/股票查询_gui.py`）
- `dist/` 分发产物
  - `股票查询CLI.exe`
  - `股票查询GUI.exe`
- `tools/` 辅助工具脚本
  - `bench_multi_source.py` 多源性能/稳定性基准采集脚本

## 构建与发布
- 进入虚拟环境后执行（建议将构建目录也集中到本目录）：
  - CLI：`pyinstaller --distpath d:\code\股票查询工具\dist --workpath d:\code\股票查询工具\build d:\code\股票查询工具\specs\股票查询CLI.spec`
  - GUI：`pyinstaller --distpath d:\code\股票查询工具\dist --workpath d:\code\股票查询工具\build d:\code\股票查询工具\specs\股票查询GUI.spec`

## 使用
- CLI：`d:\code\股票查询工具\dist\股票查询CLI.exe --code <股票代码>`
- GUI：`d:\code\股票查询工具\dist\股票查询GUI.exe`

## 维护建议
- 所有源代码修改在`src/`目录进行，打包配置在`specs/`维护，分发产物归档在`dist/`。
- 如需增加数据源或调整速率限制/熔断参数，请在`multi_source_fetcher.py`内修改并更新说明。
- 基准脚本位于`tools/`，可周期性跑数生成性能与稳定性报告。

## 许可证
- 协议：MIT License（全文见项目根目录 `LICENSE`）
- 版权声明：本程序由空游开发 · © 2025 空游
- 分发要求：任何再分发或修改必须保留上述版权与许可声明；二进制分发建议随附 `LICENSE` 文件
- SPDX 标识：`MIT`
- 二进制说明：CLI 与 GUI 在界面/输出中已显示版权与许可证提示，便于使用者知悉与合规

## 校验与完整性
- 发布包：`D:\code\股票查询工具_发布版.zip`
- 算法：`SHA-256`
- 校验值：`A6514F498C652A787303C52955CBA3CC359817D2349F540E278F91860AB9EEAA`
- 验证（Windows PowerShell）：`Get-FileHash -Algorithm SHA256 -Path D:\code\股票查询工具_发布版.zip`
- 验证（Linux）：`sha256sum 股票查询工具_发布版.zip`
- 验证（macOS）：`shasum -a 256 股票查询工具_发布版.zip`
