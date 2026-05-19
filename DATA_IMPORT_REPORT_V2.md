# DATA_IMPORT_REPORT_V2 (LogHub Traceable)

- batch_id: `loghub-trace-1778203892`
- raw_dir: `data/loghub/raw`
- output_jsonl: `data/loghub_traceable_faults.jsonl`

## Summary
- scanned_files: 16
- scanned_lines: 32000
- matched_lines: 2791
- extracted_records: 2791
- unique_trace_points: 2791
- import_success: 2745
- import_failed: 46

## Top Faults
- SSH 暴力破解攻击（Brute Force Authentication Failure）: 994
- SSH 无效用户登录（Unknown User Login Attempt）: 617
- Apache mod_jk Worker 进入错误状态（mod_jk Error State）: 539
- ZooKeeper Peer 连接中断（Connection Broken）: 291
- ZooKeeper SendWorker 线程退出（SendWorker Leaving Thread）: 262
- HDFS DataNode 数据块传输异常（DataXceiver Exception）: 80
- Hadoop MapReduce Task 重试超限（Task Attempt Failed）: 8

## Sample Trace (first 10)

- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:2` | pattern=`mod_jk child workerEnv in error state`
- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:9` | pattern=`mod_jk child workerEnv in error state`
- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:10` | pattern=`mod_jk child workerEnv in error state`
- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:11` | pattern=`mod_jk child workerEnv in error state`
- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:17` | pattern=`mod_jk child workerEnv in error state`
- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:25` | pattern=`mod_jk child workerEnv in error state`
- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:26` | pattern=`mod_jk child workerEnv in error state`
- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:27` | pattern=`mod_jk child workerEnv in error state`
- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:33` | pattern=`mod_jk child workerEnv in error state`
- `Apache mod_jk Worker 进入错误状态（mod_jk Error State）` <= `Apache/Apache_2k.log:34` | pattern=`mod_jk child workerEnv in error state`
