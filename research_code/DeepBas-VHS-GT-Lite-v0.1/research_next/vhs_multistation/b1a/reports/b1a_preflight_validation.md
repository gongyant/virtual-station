# VHS-NEXT-B1A｜预检查验证

日期：2026-10-12（Asia/Singapore）。验证范围限PRE-DOWNLOAD，不是完整B1A验收。

- 官方API record=5153305/version=1.0、唯一日尺度文件名、公布MD5通过一致性检查；HEAD字节数与API一致。
- E盘剩余37.39GiB，≥16.00GiB要求；缓存及临时目录落E盘。
- 596个历史/B0/输入保护项SHA-256前后一致；未重跑历史科研审计。
- 9个合成归档路径案例通过；实际archive成员未扫描，生产安全提取、label-blind coverage程序未执行，不把NOT_TESTABLE改成PASS。
- 新增脚本AST语法通过；没有安装新依赖、修改系统代理或启用GPU。
- 官方元数据小JSON请求完成，archive GET=0、archive HEAD正文=0、归档下载=0、真实Q解码=0、拟合/评分=0。
- 许可正文与API标识差异已记录；包内Info尚未读取，完整许可审查未通过。
- 本轮停止等待下载确认；没有生成站点对/覆盖/分组的虚假完整CSV或完整B1A状态。

完整性证据见evidence/integrity_before.json和preflight_delivery_manifest.json。运行记录由脚本与请求类型保留，不宣称OS全局安全监测；同账户目录不构成密码学或OS封存。
