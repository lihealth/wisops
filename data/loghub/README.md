# LogHub Raw Data Placement

Place open-source LogHub raw logs under:

`data/loghub/raw/`

Recommended structure (example):

```text
data/loghub/raw/
  hdfs/
    hdfs_1.log
  spark/
    spark_1.log
  kubernetes/
    k8s_1.log
  linux/
    linux_1.log
```

Accepted file extensions: `.log`, `.txt`, `.out`

## Traceable Import

Run:

```powershell
python scripts/import_loghub_traceable.py --raw-dir data/loghub/raw --api-url http://localhost:8021
```

Outputs:

- `data/loghub_traceable_faults.jsonl` (includes `source_file`, `source_line`, `matched_pattern`)
- `DATA_IMPORT_REPORT_V2.md` (import summary and trace samples)

## Dry Run

```powershell
python scripts/import_loghub_traceable.py --raw-dir data/loghub/raw --dry-run
```

