<template>
  <div class="app-container">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <div class="search-section">
        <input
          v-model="stockCode"
          @keyup.enter="loadStockData"
          class="stock-input"
          placeholder="输入股票代码，如：000001.SZ 或 000001"
          type="text"
        />
        <button @click="loadStockData" class="search-btn">查询</button>
      </div>
      
      <div class="period-section">
        <button
          v-for="period in periods"
          :key="period.value"
          @click="selectPeriod(period.value)"
          :class="['period-btn', { active: currentPeriod === period.value }]"
        >
          {{ period.label }}
        </button>
      </div>
      
    <div class="info-section" v-if="stockInfo">
      <div class="info-block">
        <span class="info-label">代码</span>
        <span class="info-value code">{{ stockInfo.stock_code }}</span>
      </div>
      <div class="info-block">
        <span class="info-label">名称</span>
        <span class="info-value">{{ stockBasics?.name || '-' }}</span>
      </div>
      <div class="info-block">
        <span class="info-label">年份</span>
        <span class="info-value">{{ stockInfo.year }}</span>
      </div>
      <div class="info-block">
        <span class="info-label">总市值</span>
        <span class="info-value">{{ formatBillion(stockBasics?.market_cap) }}</span>
      </div>
      <div class="info-block">
        <span class="info-label">PE(TTM)</span>
        <span class="info-value">{{ formatNumber(stockBasics?.pe_ttm) }}</span>
      </div>
      <div class="info-block">
        <span class="info-label">PS(TTM)</span>
        <span class="info-value">{{ formatNumber(stockBasics?.ps_ttm) }}</span>
      </div>
      <div class="info-block">
        <span class="info-label">数据量</span>
        <span class="info-value">{{ stockInfo.count }}</span>
      </div>
    </div>
    </div>

    <!-- 图表容器 -->
    <div class="chart-container">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <div v-show="!loading && !error" ref="chartRef" class="chart"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const stockCode = ref('000001.SZ')
const currentPeriod = ref('minute')
const loading = ref(false)
const error = ref('')
const chartRef = ref(null)
let chartInstance = null

const stockInfo = ref(null)
const stockBasics = ref(null)

const periods = [
  { label: '分钟', value: 'minute' },
  { label: '日线', value: 'day' },
  { label: '周线', value: 'week' },
  { label: '月线', value: 'month' }
]

// 初始化图表
const initChart = async () => {
  await nextTick()
  if (!chartRef.value) {
    console.error('图表容器未找到，等待DOM渲染...')
    // 再等待一下
    await new Promise(resolve => setTimeout(resolve, 100))
    if (!chartRef.value) {
      console.error('图表容器仍未找到')
      return false
    }
  }
  
  if (chartInstance) {
    chartInstance.dispose()
  }
  
  try {
    chartInstance = echarts.init(chartRef.value, 'dark')
    console.log('图表初始化成功')
    
    // 设置响应式
    window.addEventListener('resize', () => {
      chartInstance?.resize()
    })
    return true
  } catch (err) {
    console.error('图表初始化失败:', err)
    return false
  }
}

// 选择周期
const selectPeriod = (period) => {
  currentPeriod.value = period
  if (stockCode.value) {
    loadStockData()
  }
}

// 加载股票数据
const loadStockData = async () => {
  if (!stockCode.value.trim()) {
    error.value = '请输入股票代码'
    loading.value = false
    return
  }

  loading.value = true
  error.value = ''
  
  try {
    // 确保图表已初始化
    if (!chartInstance) {
      const initSuccess = await initChart()
      if (!initSuccess) {
        error.value = '图表初始化失败，请刷新页面重试'
        loading.value = false
        return
      }
    }
    
    console.log(`正在加载股票数据: ${stockCode.value}, 周期: ${currentPeriod.value}`)
    const response = await axios.get(`/api/stock/${stockCode.value}`, {
      params: {
        period: currentPeriod.value
      },
      timeout: 30000 // 30秒超时
    })
    
    console.log('API响应:', response.data)
    
    if (response.data.success) {
      stockInfo.value = {
        stock_code: response.data.stock_code,
        year: response.data.year,
        count: response.data.count
      }
      await nextTick() // 等待DOM更新
      renderChart(response.data.data)
      fetchStockInfo(stockCode.value) // 异步获取公司基本面
    } else {
      error.value = response.data.error || '加载失败'
      loading.value = false
    }
  } catch (err) {
    console.error('加载股票数据失败:', err)
    if (err.code === 'ECONNABORTED') {
      error.value = '请求超时，请检查后端服务是否正常运行'
    } else if (err.response) {
      error.value = err.response.data?.error || `服务器错误: ${err.response.status}`
    } else if (err.request) {
      error.value = '无法连接到服务器，请确保后端服务在 http://localhost:8080 运行'
    } else {
      error.value = err.message || '网络错误'
    }
    loading.value = false
  }
}

// 获取公司基本面数据
const fetchStockInfo = async (code) => {
  try {
    const resp = await axios.get(`/api/stock_info/${code}`, { timeout: 8000 })
    if (resp.data?.success) {
      stockBasics.value = {
        name: resp.data.name,
        market_cap: resp.data.market_cap,
        pe_ttm: resp.data.pe_ttm,
        ps_ttm: resp.data.ps_ttm
      }
    } else {
      stockBasics.value = null
      console.warn(resp.data?.error || '未获取到公司信息')
    }
  } catch (e) {
    stockBasics.value = null
    console.warn('获取公司信息失败', e)
  }
}

// 渲染K线图
const renderChart = (data) => {
  if (!chartInstance) {
    console.error('图表实例未初始化')
    error.value = '图表初始化失败'
    loading.value = false
    return
  }
  
  if (!data || data.length === 0) {
    error.value = '没有数据可显示'
    loading.value = false
    return
  }

  // 准备K线数据
  const dates = data.map(item => item.trade_time)
  const klineData = data.map(item => [
    parseFloat(item.open),
    parseFloat(item.close),
    parseFloat(item.low),
    parseFloat(item.high)
  ])
  
  // 成交量数据
  const volumes = data.map(item => parseFloat(item.vol))
  
  // 计算MA5和MA20
  const ma5 = calculateMA(5, data)
  const ma20 = calculateMA(20, data)

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      data: ['K线', 'MA5', 'MA20', '成交量'],
      textStyle: {
        color: '#e0e0e0'
      },
      top: 10
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'cross'
      },
      backgroundColor: 'rgba(50, 50, 50, 0.9)',
      borderColor: '#777',
      textStyle: {
        color: '#fff'
      },
      formatter: function (params) {
        let result = params[0].axisValue + '<br/>'
        params.forEach(param => {
          if (param.seriesName === 'K线') {
            result += `${param.seriesName}: 开${param.value[0]} 收${param.value[1]} 低${param.value[2]} 高${param.value[3]}<br/>`
          } else if (param.seriesName === '成交量') {
            result += `${param.seriesName}: ${(param.value / 10000).toFixed(2)}万手<br/>`
          } else {
            result += `${param.seriesName}: ${param.value}<br/>`
          }
        })
        return result
      }
    },
    grid: [
      {
        left: '10%',
        right: '8%',
        top: '15%',
        height: '60%'
      },
      {
        left: '10%',
        right: '8%',
        top: '80%',
        height: '15%'
      }
    ],
    xAxis: [
      {
        type: 'category',
        data: dates,
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        splitLine: { show: false },
        min: 'dataMin',
        max: 'dataMax',
        axisLabel: {
          color: '#999',
          formatter: function (value) {
            // 根据周期显示不同格式
            if (currentPeriod.value === 'minute') {
              return value.split(' ')[1] || value
            } else {
              return value.split(' ')[0] || value
            }
          }
        }
      },
      {
        type: 'category',
        gridIndex: 1,
        data: dates,
        scale: true,
        boundaryGap: false,
        axisLine: { onZero: false },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        min: 'dataMin',
        max: 'dataMax'
      }
    ],
    yAxis: [
      {
        scale: true,
        splitArea: {
          show: true,
          areaStyle: {
            color: ['rgba(250,250,250,0.05)', 'rgba(200,200,200,0.02)']
          }
        },
        axisLabel: {
          color: '#999'
        },
        splitLine: {
          show: true,
          lineStyle: {
            color: '#333'
          }
        }
      },
      {
        scale: true,
        gridIndex: 1,
        splitNumber: 2,
        axisLabel: { show: false },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1],
        start: 0,
        end: 100
      },
      {
        show: true,
        xAxisIndex: [0, 1],
        type: 'slider',
        top: '95%',
        start: 0,
        end: 100,
        handleStyle: {
          color: '#666'
        },
        dataBackground: {
          areaStyle: {
            color: '#333'
          },
          lineStyle: {
            color: '#666'
          }
        },
        selectedDataBackground: {
          areaStyle: {
            color: '#444'
          },
          lineStyle: {
            color: '#888'
          }
        },
        textStyle: {
          color: '#999'
        }
      }
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: klineData,
        itemStyle: {
          color: '#ef5350',
          color0: '#26a69a',
          borderColor: '#ef5350',
          borderColor0: '#26a69a'
        }
      },
      {
        name: 'MA5',
        type: 'line',
        data: ma5,
        smooth: true,
        lineStyle: {
          width: 1,
          color: '#ff9800'
        },
        symbol: 'none'
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20,
        smooth: true,
        lineStyle: {
          width: 1,
          color: '#2196f3'
        },
        symbol: 'none'
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes,
        itemStyle: {
          color: function (params) {
            const dataIndex = params.dataIndex
            if (dataIndex === 0) return '#26a69a'
            const currentClose = klineData[dataIndex][1]
            const prevClose = klineData[dataIndex - 1][1]
            return currentClose >= prevClose ? '#26a69a' : '#ef5350'
          }
        }
      }
    ]
  }

  chartInstance.setOption(option)
  loading.value = false
}

// 计算移动平均线
const calculateMA = (period, data) => {
  const result = []
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push('-')
    } else {
      let sum = 0
      for (let j = 0; j < period; j++) {
        sum += parseFloat(data[i - j].close)
      }
      result.push((sum / period).toFixed(2))
    }
  }
  return result
}

// 数值格式化
const formatBillion = (val) => {
  if (val === null || val === undefined) return '-'
  return `${(Number(val) / 1e8).toFixed(2)}亿`
}

const formatNumber = (val, digits = 2) => {
  if (val === null || val === undefined) return '-'
  const num = Number(val)
  if (Number.isNaN(num)) return '-'
  return num.toFixed(digits)
}

onMounted(async () => {
  await initChart()
  // 默认加载000001.SZ的数据
  await loadStockData()
})
</script>

<style scoped>
.app-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #1a1a1a;
}

.toolbar {
  padding: 15px 20px;
  background: #252525;
  border-bottom: 1px solid #333;
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.search-section {
  display: flex;
  gap: 10px;
  align-items: center;
}

.stock-input {
  padding: 8px 15px;
  background: #1a1a1a;
  border: 1px solid #444;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 14px;
  width: 250px;
  outline: none;
  transition: border-color 0.3s;
}

.stock-input:focus {
  border-color: #2196f3;
}

.search-btn {
  padding: 8px 20px;
  background: #2196f3;
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.search-btn:hover {
  background: #1976d2;
}

.period-section {
  display: flex;
  gap: 5px;
}

.period-btn {
  padding: 6px 15px;
  background: #333;
  border: 1px solid #444;
  border-radius: 4px;
  color: #999;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.3s;
}

.period-btn:hover {
  background: #3a3a3a;
  color: #e0e0e0;
}

.period-btn.active {
  background: #2196f3;
  border-color: #2196f3;
  color: white;
}

.info-section {
  display: flex;
  gap: 16px;
  margin-left: auto;
  font-size: 13px;
  flex-wrap: wrap;
  align-items: center;
}

.info-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 90px;
}

.info-label {
  color: #777;
  font-size: 12px;
}

.info-value {
  color: #e0e0e0;
  font-weight: 600;
  line-height: 1.2;
}

.info-value.code {
  color: #2196f3;
}

.chart-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

.chart {
  width: 100%;
  height: 100%;
}

.loading,
.error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 16px;
  color: #999;
}

.error {
  color: #ef5350;
}
</style>

