// WisOps Graph Schema V2.0
// 幂等初始化脚本 — 全部使用 ifNotExist()，V1.x 数据安全保留
// 执行方式：通过 graph-api startup 自动调用，或手动 POST 到 HugeGraph Gremlin 端点

// ─── 属性键 ───────────────────────────────────────────────────────────────────
schema.propertyKey('name').asText().ifNotExist().create()
schema.propertyKey('description').asText().ifNotExist().create()
schema.propertyKey('title').asText().ifNotExist().create()
schema.propertyKey('steps').asText().ifNotExist().create()
schema.propertyKey('version').asText().ifNotExist().create()
schema.propertyKey('author').asText().ifNotExist().create()
schema.propertyKey('asset_id').asText().ifNotExist().create()
schema.propertyKey('asset_type').asText().ifNotExist().create()
schema.propertyKey('ip').asText().ifNotExist().create()
schema.propertyKey('env').asText().ifNotExist().create()
schema.propertyKey('alert_id').asText().ifNotExist().create()
schema.propertyKey('content').asText().ifNotExist().create()
schema.propertyKey('level').asText().ifNotExist().create()
schema.propertyKey('source').asText().ifNotExist().create()
schema.propertyKey('occurred_at').asLong().ifNotExist().create()
schema.propertyKey('incident_id').asText().ifNotExist().create()
schema.propertyKey('status').asText().ifNotExist().create()
schema.propertyKey('created_at').asLong().ifNotExist().create()
schema.propertyKey('closed_at').asLong().ifNotExist().create()
schema.propertyKey('mttr_minutes').asInt().ifNotExist().create()
schema.propertyKey('username').asText().ifNotExist().create()
schema.propertyKey('team').asText().ifNotExist().create()
schema.propertyKey('expertise').asText().ifNotExist().create()
schema.propertyKey('code').asText().ifNotExist().create()
schema.propertyKey('domain').asText().ifNotExist().create()
schema.propertyKey('data_source').asText().ifNotExist().create()
schema.propertyKey('confidence').asDouble().ifNotExist().create()
schema.propertyKey('import_batch_id').asText().ifNotExist().create()
schema.propertyKey('score').asDouble().ifNotExist().create()
schema.propertyKey('method').asText().ifNotExist().create()
schema.propertyKey('chunk_ref').asText().ifNotExist().create()
schema.propertyKey('role').asText().ifNotExist().create()
schema.propertyKey('adopted_at').asLong().ifNotExist().create()
schema.propertyKey('category').asText().ifNotExist().create()
schema.propertyKey('severity').asText().ifNotExist().create()

// ─── 顶点标签 ─────────────────────────────────────────────────────────────────
// V1.x 保留（扩展属性）
schema.vertexLabel('Fault')
    .properties('name','description','category','severity','data_source','confidence','import_batch_id','created_at')
    .primaryKeys('name').ifNotExist().create()

schema.vertexLabel('Solution')
    .properties('name','description','data_source','confidence','import_batch_id','created_at')
    .primaryKeys('name').ifNotExist().create()

// V2.0 新增
schema.vertexLabel('SOP')
    .properties('title','steps','version','author','data_source','created_at')
    .primaryKeys('title').ifNotExist().create()

schema.vertexLabel('Asset')
    .properties('asset_id','name','asset_type','ip','env','data_source','created_at')
    .primaryKeys('asset_id').ifNotExist().create()

schema.vertexLabel('Alert')
    .properties('alert_id','content','level','source','occurred_at','data_source')
    .primaryKeys('alert_id').ifNotExist().create()

schema.vertexLabel('Incident')
    .properties('incident_id','title','status','created_at','closed_at','mttr_minutes','data_source')
    .primaryKeys('incident_id').ifNotExist().create()

schema.vertexLabel('Person')
    .properties('username','name','team','expertise')
    .primaryKeys('username').ifNotExist().create()

schema.vertexLabel('Category')
    .properties('code','name','level','domain')
    .primaryKeys('code').ifNotExist().create()

// ─── 边标签 ───────────────────────────────────────────────────────────────────
// V1.x 保留
schema.edgeLabel('HAS_SOLUTION')
    .sourceLabel('Fault').targetLabel('Solution')
    .ifNotExist().create()

// V2.0 新增
schema.edgeLabel('HAS_SOP')
    .sourceLabel('Fault').targetLabel('SOP')
    .ifNotExist().create()

schema.edgeLabel('CLASSIFIED_AS')
    .sourceLabel('Fault').targetLabel('Category')
    .ifNotExist().create()

schema.edgeLabel('SIMILAR_TO')
    .sourceLabel('Fault').targetLabel('Fault')
    .properties('score','method')
    .ifNotExist().create()

schema.edgeLabel('HAS_ALERT')
    .sourceLabel('Asset').targetLabel('Alert')
    .properties('created_at')
    .ifNotExist().create()

schema.edgeLabel('TRIGGERS')
    .sourceLabel('Alert').targetLabel('Fault')
    .properties('confidence')
    .ifNotExist().create()

schema.edgeLabel('INVOLVES')
    .sourceLabel('Incident').targetLabel('Asset')
    .properties('role')
    .ifNotExist().create()

schema.edgeLabel('CAUSED_BY')
    .sourceLabel('Incident').targetLabel('Fault')
    .ifNotExist().create()

schema.edgeLabel('RESOLVED_BY')
    .sourceLabel('Incident').targetLabel('Solution')
    .properties('adopted_at')
    .ifNotExist().create()

schema.edgeLabel('CONTRIBUTED')
    .sourceLabel('Person').targetLabel('Solution')
    .properties('created_at')
    .ifNotExist().create()

schema.edgeLabel('HANDLED_BY')
    .sourceLabel('Incident').targetLabel('Person')
    .properties('role')
    .ifNotExist().create()
