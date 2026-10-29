# 图书管理系统 — 项目长期记忆

## 技术栈与约束
- Python 标准库 + SQLite，**零第三方依赖**
- 四层架构：`web.py`(控制器) → `service/` → `repository/` → `core/`
- 数据库测试纪律：**备份 → 测试 → 还原**，保持字节级干净

## 数据库快照（重要）
- 当前规范快照 md5（含 `schema_migrations` + borrow_record 索引）：`87e9a77b64b95a0985bc9e14be7b8153`
- 迁移前历史快照（无 schema_migrations）：`1d0dd66a637ca0d7a8b15b9da473c3e2`
- 迁移命令：`python -m core.migrations status|apply|rollback <版本|''>`
- 说明：`status` 只读（不改库）；`apply` 幂等；基线 `0001` 对既有库仅登记不重建表

## 约定
- 用户「我自己提交」：**AI 不得自动 git commit**
- 端到端测试用系统 Python：`C:/Users/justice/AppData/Local/Programs/Python/Python313/python.exe`
- 托管 Python 沙箱拦截本地端口绑定，故需系统 Python

## 已完成加固
版本化迁移、密码 PBKDF2 加盐哈希(遗留明文登录即升级)、集中配置+启动校验、结构化 JSON 日志+req_id、/ready、优雅停机、请求体 413、审计 CSV 导出、安全响应头+缓存策略、前端 5xx 幂等重试/离线提示/并发刷新去重
