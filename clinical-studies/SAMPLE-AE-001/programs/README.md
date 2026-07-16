# Program chain boundary

本目录保存 EDC → SDTM 程序链路。

当前 POC 约定：

- 测试阶段：Python 用于实际运行 reference/test chain，并输出可在终端查看的 CSV。
- R/SAS：仍作为代码产物轨道带出并纳入 provenance；SAS 在未配置执行环境前只生成、不执行。
- 生产演化目标：SAS 为 primary，R 为 independent QC/reference chain。
- 每条链路后续必须记录：
  - source input hashes；
  - program hash；
  - execution log；
  - validation report；
  - output artifact hash；
  - provenance 与 traceability。

当前脚手架阶段不放可执行程序。
