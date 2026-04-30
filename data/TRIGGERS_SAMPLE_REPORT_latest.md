# TRIGGERS 抽样验收报告

- 生成时间: 2026-04-29 17:15:12
- 数据文件: `data/triggers_audit_latest.csv`
- 总候选边数: 1446
- 抽样条数: 100
- 随机种子: 20260429

## 统计概览
- rule 命中: 1446 (100.0%)
- fuzzy 命中: 0 (0.0%)
- 已存在边: 0 (0.0%)
- 平均置信度: 0.945

## 抽样复核清单（人工勾选）

| # | alert_id | fault_name | confidence | method | rule_name | 复核结论 | 备注 |
|---|---|---|---:|---|---|---|---|
| 1 | `5:gaia-2021-08-03-2021-08-03_09`:26`:34-cpu_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.94 | rule | gaia-cpu-mob | ☐通过 / ☐不通过 | |
| 2 | `5:gaia-dbservice2-2021-07-12_01`:33`:01-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 3 | `5:gaia-webservice1-2021-07-21_17`:31`:06-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 4 | `5:gaia-dbservice1-2021-07-11_19`:37`:18-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 5 | `5:gaia-2021-08-18-2021-08-18_15`:51`:41-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 6 | `5:gaia-dbservice1-2021-07-26_08`:36`:33-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 7 | `5:gaia-logservice1-2021-07-29_08`:04`:54-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 8 | `5:gaia-2021-08-08-2021-08-08_08`:55`:23-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 9 | `5:gaia-2021-08-04-2021-08-04_17`:19`:10-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 10 | `5:gaia-2021-08-08-2021-08-08_22`:04`:37-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 11 | `5:gaia-dbservice1-2021-07-09_16`:43`:48-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 12 | `5:gaia-2021-08-25-2021-08-25_13`:49`:32-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 13 | `5:gaia-2021-08-12-2021-08-12_21`:08`:45-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 14 | `5:gaia-2021-08-01-2021-08-01_10`:19`:50-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 15 | `5:gaia-2021-08-06-2021-08-06_05`:16`:46-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 16 | `5:gaia-2021-08-04-2021-08-04_05`:05`:58-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 17 | `5:gaia-2021-08-12-2021-08-12_06`:53`:50-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 18 | `5:gaia-webservice2-2021-07-14_18`:41`:45-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 19 | `5:gaia-2021-08-17-2021-08-17_19`:56`:02-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 20 | `5:gaia-2021-08-10-2021-08-10_23`:31`:24-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 21 | `5:gaia-logservice1-2021-07-18_01`:27`:42-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 22 | `5:gaia-dbservice1-2021-07-17_20`:08`:58-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 23 | `5:gaia-2021-08-12-2021-08-12_13`:41`:44-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 24 | `5:gaia-redisservice2-2021-07-31_16`:24`:57-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 25 | `5:gaia-logservice1-2021-07-05_14`:00`:02-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 26 | `5:gaia-dbservice2-2021-07-30_11`:03`:50-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 27 | `5:gaia-2021-08-22-2021-08-22_03`:43`:58-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 28 | `5:gaia-dbservice1-2021-07-15_08`:40`:04-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 29 | `5:gaia-dbservice2-2021-07-23_01`:10`:02-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 30 | `5:gaia-2021-08-22-2021-08-22_22`:44`:43-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 31 | `5:gaia-2021-08-19-2021-08-19_19`:30`:40-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 32 | `5:gaia-2021-08-11-2021-08-11_16`:17`:37-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 33 | `5:gaia-dbservice1-2021-07-01_22`:33`:05-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 34 | `5:gaia-webservice1-2021-07-26_23`:31`:22-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 35 | `5:gaia-mobservice2-2021-07-02_05`:51`:32-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 36 | `5:gaia-dbservice1-2021-07-18_08`:55`:08-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 37 | `5:gaia-2021-08-05-2021-08-05_20`:04`:25-cpu_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.94 | rule | gaia-cpu-mob | ☐通过 / ☐不通过 | |
| 38 | `5:gaia-2021-08-26-2021-08-26_20`:28`:09-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 39 | `5:gaia-mobservice1-2021-07-11_17`:06`:33-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 40 | `5:gaia-2021-08-10-2021-08-10_04`:22`:48-cpu_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.94 | rule | gaia-cpu-mob | ☐通过 / ☐不通过 | |
| 41 | `5:gaia-2021-08-12-2021-08-12_11`:22`:02-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 42 | `5:gaia-dbservice2-2021-07-20_16`:42`:19-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 43 | `5:gaia-2021-08-23-2021-08-23_07`:40`:37-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 44 | `5:gaia-redisservice2-2021-07-20_07`:25`:49-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 45 | `5:gaia-2021-08-01-2021-08-01_21`:19`:52-cpu_anomalies` | K8s Pod Pending 无法调度（Insufficient CPU/Memory） | 0.93 | rule | gaia-cpu-db | ☐通过 / ☐不通过 | |
| 46 | `5:gaia-2021-08-19-2021-08-19_20`:08`:41-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 47 | `5:gaia-dbservice1-2021-07-31_03`:57`:07-cpu_anomalies` | K8s Pod Pending 无法调度（Insufficient CPU/Memory） | 0.93 | rule | gaia-cpu-db | ☐通过 / ☐不通过 | |
| 48 | `5:gaia-2021-08-14-2021-08-14_17`:26`:37-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 49 | `5:gaia-webservice2-2021-07-16_06`:30`:18-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 50 | `5:gaia-2021-08-21-2021-08-21_12`:31`:45-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 51 | `5:gaia-dbservice2-2021-07-29_00`:50`:36-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 52 | `5:gaia-2021-08-19-2021-08-19_03`:04`:40-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 53 | `5:gaia-2021-08-31-2021-08-31_11`:35`:45-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 54 | `5:gaia-2021-08-10-2021-08-10_00`:30`:26-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 55 | `5:gaia-dbservice1-2021-07-02_01`:21`:29-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 56 | `5:gaia-2021-08-01-2021-08-01_03`:53`:11-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 57 | `5:gaia-mobservice1-2021-07-17_15`:10`:07-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 58 | `5:gaia-redisservice2-2021-07-12_00`:02`:44-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 59 | `5:gaia-2021-08-19-2021-08-19_01`:45`:45-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 60 | `5:gaia-logservice2-2021-07-06_10`:38`:46-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 61 | `5:gaia-2021-08-12-2021-08-12_13`:50`:49-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 62 | `5:gaia-logservice1-2021-07-22_03`:58`:03-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 63 | `5:gaia-logservice1-2021-07-31_20`:07`:23-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 64 | `5:gaia-2021-08-06-2021-08-06_19`:22`:07-cpu_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.94 | rule | gaia-cpu-mob | ☐通过 / ☐不通过 | |
| 65 | `5:gaia-webservice2-2021-07-12_01`:22`:58-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 66 | `5:gaia-2021-08-03-2021-08-03_21`:30`:15-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 67 | `5:gaia-redisservice1-2021-07-30_18`:36`:43-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 68 | `5:gaia-2021-08-22-2021-08-22_08`:53`:01-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 69 | `5:gaia-2021-08-30-2021-08-30_12`:00`:34-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 70 | `5:gaia-2021-08-27-2021-08-27_21`:50`:36-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 71 | `5:gaia-2021-08-29-2021-08-29_03`:15`:35-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 72 | `5:gaia-2021-08-10-2021-08-10_17`:44`:45-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 73 | `5:gaia-redisservice2-2021-07-10_21`:59`:39-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 74 | `5:gaia-webservice1-2021-07-09_20`:01`:58-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 75 | `5:gaia-dbservice1-2021-07-31_03`:37`:06-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 76 | `5:gaia-dbservice2-2021-07-07_11`:21`:32-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 77 | `5:gaia-2021-08-14-2021-08-14_13`:38`:40-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 78 | `5:gaia-mobservice2-2021-07-06_15`:19`:48-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 79 | `5:gaia-logservice2-2021-07-07_07`:48`:24-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 80 | `5:gaia-logservice2-2021-07-01_20`:45`:20-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 81 | `5:gaia-2021-08-29-2021-08-29_09`:54`:39-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 82 | `5:gaia-redisservice2-2021-07-30_07`:21`:54-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 83 | `5:gaia-logservice1-2021-07-12_08`:44`:58-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 84 | `5:gaia-2021-08-10-2021-08-10_03`:06`:53-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 85 | `5:gaia-2021-08-04-2021-08-04_23`:28`:10-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 86 | `5:gaia-2021-08-23-2021-08-23_13`:47`:57-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 87 | `5:gaia-2021-08-31-2021-08-31_20`:33`:32-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 88 | `5:gaia-redisservice2-2021-07-15_00`:01`:36-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 89 | `5:gaia-2021-08-29-2021-08-29_04`:02`:05-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 90 | `5:gaia-2021-08-05-2021-08-05_15`:32`:59-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 91 | `5:gaia-redisservice2-2021-07-07_21`:16`:30-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 92 | `5:gaia-webservice1-2021-07-11_08`:23`:28-memory_anomalies` | Apache SSL 握手失败 | 0.94 | rule | gaia-memory-web | ☐通过 / ☐不通过 | |
| 93 | `5:gaia-2021-08-14-2021-08-14_18`:35`:41-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 94 | `5:gaia-2021-08-06-2021-08-06_14`:20`:57-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 95 | `5:gaia-logservice2-2021-07-15_04`:58`:53-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 96 | `5:gaia-2021-08-18-2021-08-18_05`:10`:54-memory_anomalies` | API Key 泄露到公共代码仓库（K8s 场景） | 0.95 | rule | gaia-memory-mob | ☐通过 / ☐不通过 | |
| 97 | `5:gaia-2021-08-23-2021-08-23_03`:14`:16-memory_anomalies` | MongoDB 副本集选举失败 | 0.95 | rule | gaia-memory-db | ☐通过 / ☐不通过 | |
| 98 | `5:gaia-redisservice2-2021-07-09_00`:20`:00-memory_anomalies` | Redis Cluster 节点下线导致 slot 不可用 | 0.95 | rule | gaia-memory-redis | ☐通过 / ☐不通过 | |
| 99 | `5:gaia-logservice1-2021-07-08_03`:32`:06-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |
| 100 | `5:gaia-2021-08-18-2021-08-18_19`:36`:40-memory_anomalies` | Elasticsearch 写入拒绝（429） | 0.94 | rule | gaia-memory-log | ☐通过 / ☐不通过 | |

## 验收建议
- 建议抽样通过率 >= 85% 作为当前规则上线阈值。
- 若不通过样本集中在某类 rule_name，优先调整该规则。
- 对空 rule_name 且 method=fuzzy 的样本，建议后续沉淀为显式规则。

