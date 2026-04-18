<template>
  <div class="page">
    <div class="header">
      <div>
        <div class="title">出租车运营画像</div>
        <div class="subtitle">
          从车辆视角查看活跃时段、常驻区域、日运行节奏、常跑路线簇和同行分组。
        </div>
      </div>

      <div class="controls">
        <SearchSelect
          v-model="deviceId"
          :fetch-options="fetchDeviceSuggestions"
          :min-chars="1"
          :max-items="200"
          placeholder="选择或输入 device_id，例如 100032066"
        />
        <button class="btn" :disabled="!deviceId || loading" @click="submitCar">查询画像</button>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>

    <div class="overview-grid">
      <div class="hero-card" :class="`hero-card--${summary?.operation_mode || 'steady_all_day'}`">
        <div class="hero-eyebrow">运营模式</div>
        <div class="hero-title">
          {{ summary ? operationModeLabel(summary?.operation_mode) : '暂无画像数据' }}
        </div>
        <div class="hero-meta">
          {{ summary ? `主运营时段：${shiftLabel(summary?.dominant_shift)}` : '请输入 device_id 并查询运营画像' }}
        </div>
        <p class="hero-desc">
          {{
            summary
              ? '基于当前车辆全部可用行程自动聚合，突出营运习惯、出车节奏和常驻经营区域。'
              : '画像卡片会在查询成功后展示当前车辆的运营模式、工作节奏和区域活跃特征。'
          }}
        </p>
      </div>

      <div
        v-for="item in summaryCards"
        :key="item.label"
        class="stat-card"
      >
        <div class="stat-label">{{ item.label }}</div>
        <div class="stat-value">{{ item.value }}</div>
        <div class="stat-note">{{ item.note }}</div>
      </div>
    </div>

    <div class="chart-grid">
      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">活跃时段分布</div>
            <div class="card-subtitle">柱状展示行程数量，折线展示里程贡献</div>
          </div>
        </div>
        <div ref="chartActiveEl" class="chart chart--medium"></div>
      </div>

      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">常驻区域雷达图</div>
            <div class="card-subtitle">围绕车辆活动中心统计起终点方向活跃度</div>
          </div>
        </div>
        <div ref="chartRadarEl" class="chart chart--medium"></div>
      </div>
    </div>

    <div class="chart-grid">
      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">日运行节奏</div>
            <div class="card-subtitle">最近 {{ displayedRhythm.length || 0 }} 个活跃日的出车窗口</div>
          </div>
        </div>
        <div ref="chartRhythmEl" class="chart chart--medium"></div>
      </div>

      <div class="card">
        <div class="card-head">
          <div>
            <div class="card-title">常跑路线簇</div>
            <div class="card-subtitle">基于起终点网格聚合的 Top {{ routeClusters.length || 0 }} OD 簇</div>
          </div>
        </div>

        <div v-if="routeClusters.length" class="cluster-list">
          <div
            v-for="(cluster, index) in routeClusters"
            :key="cluster.cluster_key"
            class="cluster-item"
          >
            <div class="cluster-rank">OD-{{ String(index + 1).padStart(2, '0') }}</div>
            <div class="cluster-main">
              <div class="cluster-title-row">
                <strong>出现 {{ cluster.trip_count }} 次</strong>
                <span class="cluster-chip">{{ formatHour(cluster.avg_start_hour) }} 出车</span>
              </div>
              <div class="cluster-meta">
                <span>平均里程 {{ fmt(cluster.avg_distance_km) }} km</span>
                <span>起点 {{ formatCenter(cluster.start_center) }}</span>
                <span>终点 {{ formatCenter(cluster.end_center) }}</span>
              </div>
              <div class="cluster-key">{{ cluster.cluster_key }}</div>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">
          当前样本不足以形成稳定路线簇，通常需要至少两条带起终点的行程。
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">同行聚类分组图</div>
          <div class="card-subtitle">横轴平均单程，纵轴日均工作时长，气泡大小代表总行程数</div>
        </div>
        <div class="legend-list">
          <span
            v-for="item in operationLegend"
            :key="item.code"
            class="legend-item"
          >
            <span class="legend-dot" :style="{ backgroundColor: item.color }"></span>
            <span>{{ item.label }}</span>
          </span>
        </div>
      </div>
      <div ref="chartPeerEl" class="chart chart--large"></div>
    </div>

    <div class="card">
      <div class="card-head">
        <div>
          <div class="card-title">车辆关联行程</div>
          <div class="card-subtitle">保留最近 {{ trips.length }} 条行程，可跳转到轨迹页继续查看</div>
        </div>
      </div>

      <div class="table">
        <div class="tr head">
          <div>行程 ID</div>
          <div>行程日期</div>
          <div>行程公里数</div>
          <div>行程时长</div>
          <div>开始时间</div>
          <div>结束时间</div>
        </div>
        <div v-for="t in trips" :key="`${t.trip_id}-${t.log_date}`" class="tr">
          <div><code class="click" @click="goTrip(t.trip_id)">{{ t.trip_id }}</code></div>
          <div>{{ t.log_date }}</div>
          <div>{{ fmt(t.distance_km) }}</div>
          <div>{{ fmtDurationSeconds(t.duration_seconds) }}</div>
          <div>{{ formatDateTime(t.start_time) }}</div>
          <div>{{ formatDateTime(t.end_time) }}</div>
        </div>
        <div v-if="!trips.length" class="empty-state">
          当前车辆没有可展示的关联行程。
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'

import { api } from '@/lib/api'
import SearchSelect from '@/components/SearchSelect.vue'

const router = useRouter()
const route = useRoute()

const OPERATION_MODE_LABEL = {
  night_shift: '夜间营运型',
  commuter_peak: '通勤高峰型',
  long_haul: '长距巡游型',
  local_shuttle: '短距接驳型',
  steady_all_day: '全天均衡型',
}

const OPERATION_MODE_COLOR = {
  night_shift: '#334155',
  commuter_peak: '#2563eb',
  long_haul: '#ea580c',
  local_shuttle: '#0f766e',
  steady_all_day: '#7c3aed',
}

const SHIFT_LABEL = {
  night: '夜间主导',
  morning_peak: '早高峰主导',
  daytime: '日间主导',
  evening_peak: '晚高峰主导',
  mixed: '多时段均衡',
}

const REGION_LABEL = {
  north: '北',
  northeast: '东北',
  east: '东',
  southeast: '东南',
  south: '南',
  southwest: '西南',
  west: '西',
  northwest: '西北',
}

const deviceId = ref('100032066')
const loading = ref(false)
const error = ref('')

const portrait = ref(null)
const trips = ref([])

const chartActiveEl = ref(null)
const chartRadarEl = ref(null)
const chartRhythmEl = ref(null)
const chartPeerEl = ref(null)

let chartActive = null
let chartRadar = null
let chartRhythm = null
let chartPeer = null

const summary = computed(() => portrait.value?.summary ?? null)
const activeTimeBins = computed(() => portrait.value?.active_time_bins ?? [])
const regionRadar = computed(() => portrait.value?.region_radar ?? [])
const dailyRhythm = computed(() => portrait.value?.daily_rhythm ?? [])
const displayedRhythm = computed(() => dailyRhythm.value.slice(-14))
const routeClusters = computed(() => portrait.value?.route_clusters ?? [])
const peerGroups = computed(() => portrait.value?.peer_groups ?? [])

const operationLegend = computed(() => [
  { code: 'night_shift', label: OPERATION_MODE_LABEL.night_shift, color: OPERATION_MODE_COLOR.night_shift },
  { code: 'commuter_peak', label: OPERATION_MODE_LABEL.commuter_peak, color: OPERATION_MODE_COLOR.commuter_peak },
  { code: 'long_haul', label: OPERATION_MODE_LABEL.long_haul, color: OPERATION_MODE_COLOR.long_haul },
  { code: 'local_shuttle', label: OPERATION_MODE_LABEL.local_shuttle, color: OPERATION_MODE_COLOR.local_shuttle },
  { code: 'steady_all_day', label: OPERATION_MODE_LABEL.steady_all_day, color: OPERATION_MODE_COLOR.steady_all_day },
])

const summaryCards = computed(() => {
  const item = summary.value
  if (!item) return []
  return [
    {
      label: '总里程',
      value: `${fmt(item.total_distance_km)} km`,
      note: `共 ${item.total_trips} 条行程`,
    },
    {
      label: '平均单程',
      value: `${fmt(item.avg_trip_distance_km)} km`,
      note: `平均时长 ${fmt(item.avg_trip_duration_minutes)} 分钟`,
    },
    {
      label: '日均工作时长',
      value: `${fmt(item.avg_daily_work_hours)} h`,
      note: `${item.active_days} 个活跃日`,
    },
    {
      label: '夜间占比',
      value: fmtPercent(item.night_trip_ratio),
      note: `热点集中度 ${fmtPercent(item.hotspot_concentration)}`,
    },
    {
      label: '活跃天数',
      value: String(item.active_days),
      note: `主时段 ${shiftLabel(item.dominant_shift)}`,
    },
  ]
})

function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return Number(value).toFixed(2)
}

function fmtPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return `${(Number(value) * 100).toFixed(1)}%`
}

function fmtDurationSeconds(sec) {
  if (!sec && sec !== 0) return '-'
  const total = Math.max(0, Math.floor(Number(sec)))
  const hh = String(Math.floor(total / 3600)).padStart(2, '0')
  const mm = String(Math.floor((total % 3600) / 60)).padStart(2, '0')
  const ss = String(total % 60).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

function formatHour(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  const totalMinutes = Math.max(0, Math.round(Number(value) * 60))
  const hh = String(Math.floor(totalMinutes / 60)).padStart(2, '0')
  const mm = String(totalMinutes % 60).padStart(2, '0')
  return `${hh}:${mm}`
}

function formatDateTime(value) {
  if (!value) return '-'
  return String(value).replace('T', ' ')
}

function formatCenter(center) {
  if (!Array.isArray(center) || center.length < 2) return '-'
  return `${Number(center[0]).toFixed(3)}, ${Number(center[1]).toFixed(3)}`
}

function operationModeLabel(mode) {
  return OPERATION_MODE_LABEL[mode] || '全天均衡型'
}

function shiftLabel(code) {
  return SHIFT_LABEL[code] || '多时段均衡'
}

function regionLabel(code) {
  return REGION_LABEL[code] || code || '-'
}

function goTrip(tripId) {
  router.push({ path: '/trip', query: { id: String(tripId) } })
}

function openPeerCar(targetDeviceId) {
  router.push({ path: '/car', query: { id: String(targetDeviceId) } })
}

function handleResize() {
  chartActive?.resize()
  chartRadar?.resize()
  chartRhythm?.resize()
  chartPeer?.resize()
}

function renderCharts() {
  const activeItems = activeTimeBins.value
  const radarItems = regionRadar.value
  const rhythmItems = displayedRhythm.value
  const peerItems = peerGroups.value

  chartActive?.dispose()
  chartRadar?.dispose()
  chartRhythm?.dispose()
  chartPeer?.dispose()

  chartActive = chartActiveEl.value ? echarts.init(chartActiveEl.value) : null
  chartRadar = chartRadarEl.value ? echarts.init(chartRadarEl.value) : null
  chartRhythm = chartRhythmEl.value ? echarts.init(chartRhythmEl.value) : null
  chartPeer = chartPeerEl.value ? echarts.init(chartPeerEl.value) : null

  chartActive?.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: {
      top: 6,
      textStyle: { color: 'rgba(16,32,51,0.72)' },
    },
    grid: { left: 42, right: 22, top: 46, bottom: 30 },
    xAxis: {
      type: 'category',
      data: activeItems.map((item) => item.label),
      axisLabel: { color: 'rgba(16,32,51,0.72)' },
    },
    yAxis: [
      {
        type: 'value',
        name: '行程数',
        axisLabel: { color: 'rgba(16,32,51,0.72)' },
        splitLine: { lineStyle: { color: 'rgba(148,163,184,0.14)' } },
      },
      {
        type: 'value',
        name: '里程 km',
        axisLabel: { color: 'rgba(16,32,51,0.56)' },
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '行程数',
        type: 'bar',
        data: activeItems.map((item) => item.trip_count),
        barMaxWidth: 28,
        itemStyle: {
          borderRadius: [10, 10, 0, 0],
          color: 'rgba(37,99,235,0.78)',
        },
      },
      {
        name: '里程',
        type: 'line',
        yAxisIndex: 1,
        data: activeItems.map((item) => item.distance_km),
        smooth: true,
        symbolSize: 7,
        lineStyle: { width: 3, color: 'rgba(15,118,110,0.82)' },
        itemStyle: { color: 'rgba(15,118,110,0.82)' },
      },
    ],
  })

  chartRadar?.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const source = radarItems[params.dataIndex]
        return `${regionLabel(source?.region)}<br/>活跃得分 ${fmt(source?.score)}<br/>起终点 ${source?.trip_count ?? 0} 次`
      },
    },
    radar: {
      radius: '62%',
      indicator: radarItems.map((item) => ({ name: regionLabel(item.region), max: 100 })),
      splitArea: {
        areaStyle: {
          color: ['rgba(255,255,255,0.88)', 'rgba(248,250,252,0.52)'],
        },
      },
      axisName: { color: '#102033' },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.22)' } },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.22)' } },
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: radarItems.map((item) => item.score),
            name: '区域活跃度',
            itemStyle: { color: 'rgba(124,58,237,0.9)' },
            lineStyle: { width: 3, color: 'rgba(124,58,237,0.78)' },
            areaStyle: { color: 'rgba(124,58,237,0.18)' },
          },
        ],
      },
    ],
  })

  chartRhythm?.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const index = params?.[0]?.dataIndex ?? 0
        const row = rhythmItems[index]
        if (!row) return ''
        return [
          `${row.date}`,
          `出车窗口 ${formatHour(row.first_start_hour)} - ${formatHour(row.last_end_hour)}`,
          `工作跨度 ${fmt(row.work_span_hours)} h`,
          `行程数 ${row.trip_count}`,
          `里程 ${fmt(row.distance_km)} km`,
        ].join('<br/>')
      },
    },
    grid: { left: 42, right: 18, top: 24, bottom: 34 },
    xAxis: {
      type: 'category',
      data: rhythmItems.map((item) => item.date),
      axisLabel: { color: 'rgba(16,32,51,0.72)', rotate: rhythmItems.length > 8 ? 25 : 0 },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: Math.max(24, ...rhythmItems.map((item) => Number(item.last_end_hour || 0))),
      axisLabel: {
        color: 'rgba(16,32,51,0.72)',
        formatter: (value) => `${Math.round(value)}h`,
      },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.14)' } },
    },
    series: [
      {
        name: '起始偏移',
        type: 'bar',
        stack: 'window',
        data: rhythmItems.map((item) => Number(item.first_start_hour || 0)),
        itemStyle: { color: 'rgba(226,232,240,0.14)' },
        emphasis: { disabled: true },
      },
      {
        name: '工作跨度',
        type: 'bar',
        stack: 'window',
        data: rhythmItems.map((item) => Number(item.work_span_hours || 0)),
        barMaxWidth: 26,
        itemStyle: {
          borderRadius: [10, 10, 10, 10],
          color: 'rgba(234,88,12,0.76)',
        },
      },
    ],
  })

  const peerData = peerItems.map((item) => ({
    value: [item.avg_trip_distance_km, item.avg_daily_work_hours, item.total_trips],
    deviceId: item.device_id,
    label: operationModeLabel(item.operation_mode),
    isCurrent: item.is_current,
    totalTrips: item.total_trips,
    itemStyle: {
      color: OPERATION_MODE_COLOR[item.operation_mode] || '#7c3aed',
      borderColor: item.is_current ? '#102033' : 'rgba(255,255,255,0.9)',
      borderWidth: item.is_current ? 3 : 1.5,
      shadowBlur: item.is_current ? 18 : 0,
      shadowColor: item.is_current ? 'rgba(16,32,51,0.18)' : 'transparent',
    },
  }))

  chartPeer?.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        const data = params.data || {}
        return [
          `车辆 ${data.deviceId || '-'}`,
          `${data.label || '-'}`,
          `平均单程 ${fmt(params.value?.[0])} km`,
          `日均工作 ${fmt(params.value?.[1])} h`,
          `总行程 ${data.totalTrips ?? 0}`,
          data.isCurrent ? '当前车辆' : '同行样本',
        ].join('<br/>')
      },
    },
    xAxis: {
      type: 'value',
      name: '平均单程 (km)',
      nameTextStyle: { color: 'rgba(16,32,51,0.72)' },
      axisLabel: { color: 'rgba(16,32,51,0.72)' },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.14)' } },
    },
    yAxis: {
      type: 'value',
      name: '日均工作时长 (h)',
      nameTextStyle: { color: 'rgba(16,32,51,0.72)' },
      axisLabel: { color: 'rgba(16,32,51,0.72)' },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.14)' } },
    },
    series: [
      {
        type: 'scatter',
        data: peerData,
        symbolSize: (value) => {
          const tripsTotal = Number(value?.[2] || 0)
          return Math.max(12, Math.min(34, 8 + Math.sqrt(tripsTotal)))
        },
      },
    ],
  })

  chartPeer?.off('click')
  chartPeer?.on('click', (params) => {
    const targetDeviceId = params?.data?.deviceId
    if (targetDeviceId) {
      openPeerCar(targetDeviceId)
    }
  })

  window.removeEventListener('resize', handleResize)
  window.addEventListener('resize', handleResize)
}

async function loadCar() {
  error.value = ''
  loading.value = true
  try {
    const nextId = encodeURIComponent(deviceId.value)
    const [portraitResp, tripsResp] = await Promise.all([
      api.get(`/api/cars/${nextId}/portrait`),
      api.get(`/api/cars/${nextId}/trips`, { params: { limit: 200 } }),
    ])
    portrait.value = portraitResp.data
    trips.value = tripsResp.data || []
    await nextTick()
    renderCharts()
  } catch (e) {
    portrait.value = null
    trips.value = []
    error.value = e?.response?.data?.detail || e?.message || String(e)
    await nextTick()
    renderCharts()
  } finally {
    loading.value = false
  }
}

function submitCar() {
  const nextId = String(deviceId.value || '').trim()
  if (!nextId) {
    error.value = 'device_id 不能为空'
    return
  }
  if (String(route.query?.id || '') === nextId) {
    loadCar()
    return
  }
  router.replace({ path: '/car', query: { id: nextId } })
}

async function fetchDeviceSuggestions(keyword = '') {
  const trimmed = String(keyword || '').trim()
  if (!trimmed) return []
  const resp = await api.get('/api/meta/device-ids', {
    params: { q: trimmed, limit: 200 },
  })
  return resp.data || []
}

onMounted(() => {
  const qid = route.query?.id
  if (qid) {
    deviceId.value = String(qid)
  }
  if (deviceId.value) {
    loadCar()
  }
})

watch(
  () => route.query?.id,
  (qid) => {
    if (!qid) return
    deviceId.value = String(qid)
    loadCar()
  }
)

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chartActive?.dispose()
  chartRadar?.dispose()
  chartRhythm?.dispose()
  chartPeer?.dispose()
})
</script>

<style scoped>
.page {
  display: grid;
  gap: 16px;
}

.header {
  display: flex;
  gap: 16px;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
}

.title {
  font-size: 20px;
  font-weight: 700;
}

.subtitle {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 13px;
}

.controls {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: nowrap;
  width: 100%;
  min-width: 0;
}

.btn {
  height: 36px;
  padding: 0 14px;
  border-radius: 10px;
  border: 1px solid rgba(37, 99, 235, 0.22);
  background: rgba(37, 99, 235, 0.1);
  color: var(--text);
  cursor: pointer;
  flex: 0 0 auto;
  white-space: nowrap;
  box-shadow: var(--shadow-sm);
}

.btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.btn:hover:not(:disabled) {
  border-color: rgba(37, 99, 235, 0.3);
  background: rgba(37, 99, 235, 0.14);
}

.overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.hero-card,
.stat-card,
.card {
  border-radius: var(--radius-lg);
  border: 1px solid var(--border);
  background: linear-gradient(180deg, var(--surface-2), var(--surface-0));
  box-shadow: var(--shadow-sm);
}

.hero-card {
  padding: 20px;
  color: #fff;
  position: relative;
  overflow: hidden;
}

.hero-card::after {
  content: '';
  position: absolute;
  inset: auto -10% -36% auto;
  width: 180px;
  height: 180px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
}

.hero-card--night_shift {
  background: linear-gradient(135deg, #1e293b, #475569);
}

.hero-card--commuter_peak {
  background: linear-gradient(135deg, #1d4ed8, #3b82f6);
}

.hero-card--long_haul {
  background: linear-gradient(135deg, #c2410c, #f97316);
}

.hero-card--local_shuttle {
  background: linear-gradient(135deg, #0f766e, #14b8a6);
}

.hero-card--steady_all_day {
  background: linear-gradient(135deg, #6d28d9, #8b5cf6);
}

.hero-eyebrow {
  font-size: 12px;
  opacity: 0.84;
}

.hero-title {
  position: relative;
  z-index: 1;
  margin-top: 8px;
  font-size: 28px;
  font-weight: 700;
}

.hero-meta {
  position: relative;
  z-index: 1;
  margin-top: 10px;
  font-size: 14px;
  opacity: 0.92;
}

.hero-desc {
  position: relative;
  z-index: 1;
  margin-top: 12px;
  line-height: 1.7;
  max-width: 42ch;
  opacity: 0.9;
}

.stat-card {
  padding: 16px;
}

.stat-label {
  color: var(--text-muted);
  font-size: 12px;
}

.stat-value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 700;
  color: var(--text);
}

.stat-note {
  margin-top: 6px;
  color: var(--text-soft);
  font-size: 12px;
}

.chart-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.card {
  padding: 16px;
}

.card-head {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.card-title {
  font-weight: 700;
  color: var(--text);
}

.card-subtitle {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 12px;
}

.chart {
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  background: rgba(255, 255, 255, 0.9);
}

.chart--medium {
  height: 320px;
}

.chart--large {
  height: 360px;
}

.legend-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 10px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.08);
  color: var(--text-muted);
  font-size: 12px;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
}

.cluster-list {
  display: grid;
  gap: 10px;
}

.cluster-item {
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(255, 255, 255, 0.86);
}

.cluster-rank {
  display: grid;
  place-items: center;
  width: 74px;
  min-height: 74px;
  border-radius: 16px;
  background: rgba(37, 99, 235, 0.08);
  color: #1d4ed8;
  font-weight: 700;
}

.cluster-main {
  min-width: 0;
}

.cluster-title-row {
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
}

.cluster-chip {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(15, 118, 110, 0.1);
  color: #0f766e;
  font-size: 12px;
  font-weight: 700;
}

.cluster-meta {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  color: var(--text-muted);
  font-size: 12px;
}

.cluster-key {
  margin-top: 8px;
  color: var(--text-soft);
  font-size: 12px;
  font-family: 'Courier New', monospace;
}

.table {
  width: 100%;
  overflow: auto;
}

.tr {
  display: grid;
  grid-template-columns: 110px 110px 110px 110px 1fr 1fr;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  min-width: 860px;
}

.tr.head {
  color: var(--text-muted);
  font-size: 12px;
}

.click {
  cursor: pointer;
  color: var(--primary);
}

.empty-state {
  color: var(--text-muted);
  padding: 8px 0;
}

.error {
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(217, 91, 115, 0.2);
  background: rgba(217, 91, 115, 0.08);
  color: #9f1f3d;
}

@media (max-width: 1400px) {
  .overview-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .hero-card {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1120px) {
  .chart-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 980px) {
  .controls,
  .card-head {
    flex-wrap: wrap;
    align-items: center;
  }

  .overview-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 680px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .cluster-item {
    grid-template-columns: 1fr;
  }

  .cluster-rank {
    width: 100%;
    min-height: 54px;
  }
}
</style>
