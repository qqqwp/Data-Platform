# 出租车运营画像平台 V1 方案

## Summary

- 以现有 `/car` 为唯一入口，直接升级为“出租车运营画像平台”，保留现有通过 `device_id` 查询和从异常排行跳转的链路。
- 统计口径默认使用当前车辆全部可用行程；“聚类分组图”按车辆同行分组实现，突出行业分析而不是单车回放。
- v1 不新增地图模块，重点交付 5 个核心展示：画像卡片、活跃时段图、区域雷达图、日运行节奏图、同行聚类分组图，并保留底部行程列表。

## Key Changes

### 后端与数据

- 新增 `GET /api/cars/{device_id}/portrait`，返回 `summary`、`active_time_bins`、`region_radar`、`daily_rhythm`、`route_clusters`、`peer_groups` 六段数据；现有 `/api/cars/{device_id}` 和 `/api/cars/{device_id}/trips` 保持不变。
- 当前车画像数据统一来自 `trip_data` 的完整行程摘要，取数顺序与现有逻辑一致：优先 `car.trip_ids`，缺失时回退到 `trip_data.devid = device_id`。
- 新增服务层聚合函数，把单车所有行程转换为标准特征：总行程数、总里程、平均行程长度、平均行程时长、活跃天数、日均工作时长、夜间占比、高峰占比、热点集中度、主运营时段。
- 区域雷达图采用“围绕车辆活动中心的 8 向扇区”口径，标签固定为 `北/东北/东/东南/南/西南/西/西北`；每个 trip 取起终点，累计扇区活跃度并做 0-100 归一化。
- 日运行节奏按日期聚合，输出 `date`、`first_start_hour`、`last_end_hour`、`work_span_hours`、`trip_count`、`distance_km`；前端用“起始偏移 + 工作跨度”堆叠条表达工作窗口。
- 常跑路线簇不做重型轨迹算法，使用“起点网格 + 终点网格”的 OD 网格聚类，保留 Top 5，返回簇大小、平均距离、平均开始小时、起终点中心坐标。
- 同行聚类分组固定做轻量特征分类，不引入训练模型。分类规则统一用于当前车和同行样本，类别固定为 `night_shift`、`commuter_peak`、`long_haul`、`local_shuttle`、`steady_all_day`。
- 同行样本默认取 `car` 表中活跃度较高的 120 辆车，加上当前车，批量从 `trip_data` 拉取行程摘要后统一算特征；散点图横轴为 `avg_trip_distance_km`，纵轴为 `avg_daily_work_hours`，点大小为 `total_trips`，颜色为运营模式，当前车始终高亮。

### 接口与类型

- `summary` 固定包含：`device_id`、`total_trips`、`total_distance_km`、`avg_trip_distance_km`、`avg_trip_duration_minutes`、`active_days`、`avg_daily_work_hours`、`dominant_shift`、`operation_mode`、`night_trip_ratio`、`hotspot_concentration`。
- `active_time_bins` 固定为 12 个 2 小时桶，返回 `label`、`trip_count`、`distance_km`、`share_ratio`。
- `region_radar` 返回 8 个方向桶，返回 `region`、`score`、`trip_count`。
- `daily_rhythm` 返回按日期升序的数组，不做分页；若日期过多，前端只展示最近 14 个活跃日。
- `route_clusters` 返回 Top 5 OD 簇，字段固定为 `cluster_key`、`trip_count`、`avg_distance_km`、`avg_start_hour`、`start_center`、`end_center`。
- `peer_groups` 返回同行散点所需字段：`device_id`、`operation_mode`、`avg_trip_distance_km`、`avg_daily_work_hours`、`total_trips`、`is_current`。
- 模式和时段文案映射放前端维护，接口只传稳定 code；404 规则沿用现有风格，车辆不存在或无可用行程时返回 404。

### 前端与交互

- `CarView.vue` 升级为运营画像页，顶部搜索保持不变，请求改为并行拉取 `/api/cars/{id}/portrait` 和 `/api/cars/{id}/trips`。
- 首屏用画像卡片展示 `运营模式 / 总里程 / 平均单程 / 日均工作时长 / 夜间占比 / 活跃天数`，突出“行业画像”叙事。
- 中部左侧放“活跃时段分布”组合图，柱表示 trip 数，线表示里程；中部右侧放“常驻区域雷达图”。
- 下一区域放“日运行节奏图”和“常跑路线簇”卡片；路线簇以列表形式展示 `OD 簇、出现次数、平均里程、平均出车时段`。
- 底部放“同行聚类分组图”和现有行程列表；同行图支持 hover 看车辆 ID，点击点位跳转到该车 `/car?id=...`。
- 保留现有 trip 列表跳转 `/trip` 的行为；从 `/anomaly` 排行跳到 `/car` 的链路无需变更。
- 文案统一改为“出租车运营画像 / 运营模式 / 常跑区域 / 同行分组”等中文表述，并同步更新 README 与 `docs/anomaly-diagnosis-plan.md` 对 `/car` 能力的描述。

## Test Plan

- 后端单元测试覆盖 5 类分类规则各 1 个样本：夜间型、通勤高峰型、长距巡游型、短距接驳型、全天均衡型。
- 后端单元测试覆盖 3 个聚合场景：2 小时桶统计正确、区域雷达 8 向归类正确、OD 网格聚类能把相近路线聚成一个簇。
- 后端单元测试覆盖边界：少量 trip 时接口仍返回 summary 且数组字段为空；完全无行程时返回 404。
- 前端验收检查 `/car?id=<valid>` 是否能渲染 5 类核心展示，窗口缩放后图表仍自适应，点击同行散点与 trip 列表跳转正确。
- 回归检查 `/trip`、`/anomaly`、现有 `/api/cars/{id}`、`/api/cars/{id}/trips` 不受影响。

## Assumptions

- v1 只做车辆视角，不做司机视角，因为当前库里只有 `device_id/devid`，没有稳定 `driver_id`。
- 单车画像使用全量可用行程；同行分组为控制响应时间固定采样 120 辆活跃车，不在 v1 暴露筛选参数。
- 轨迹“聚类”在 v1 解释为 OD 网格聚类和同行特征分组，不引入离线任务、机器学习模型或新表。
- v1 不增加地图可视化，优先把运营画像叙事和指标闭环做完整。
