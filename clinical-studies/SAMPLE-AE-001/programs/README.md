# Program chain boundary

本目录保存 EDC → SDTM 程序链路。

当前 POC 约定：

- 测试阶段：R 为 primary，Python 为 independent QC/reference chain。
- 生产演化目标：SAS 为 primary，R 为 independent QC/reference chain。
- 每条链路后续必须记录：
  - source input hashes；
  - program hash；
  - execution log；
  - validation report；
  - output artifact hash；
  - provenance 与 traceability。

当前脚手架阶段不放可执行程序。
