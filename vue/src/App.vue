<template>
  <div class="app-container">
    <!-- 左侧自选窗口 -->
    <div class="favorites-sidebar">
      <div class="favorites-header">
        <h3>自选</h3>
        <span class="favorites-count">({{ favoriteStocks.length }})</span>
      </div>
      <div class="favorites-list">
        <div v-for="(stocks, category) in groupedFavorites" :key="category" class="favorite-group">
          <div 
            v-if="stocks.length > 0" 
            class="favorite-group-header" 
            @click="toggleCategory(category)"
          >
            <span class="group-arrow" :class="{ 'collapsed': collapsedCategories[category] }">▼</span>
            <span class="group-title">{{ category }}</span>
            <span class="group-count">({{ stocks.length }})</span>
          </div>
          
          <div v-show="!collapsedCategories[category]" class="favorite-group-content">
            <div
              v-for="stock in stocks"
              :key="stock.code"
              class="favorite-item"
              @click="selectFavoriteStock(stock.code)"
            >
              <span class="favorite-name">{{ stock.name || '-' }}</span>
            </div>
          </div>
        </div>

        <div v-if="favoriteStocks.length === 0" class="favorites-empty">
          暂无自选股票
        </div>
      </div>
    </div>
    
    <!-- 主内容区 -->
    <div class="main-content">
    <!-- 顶部工具栏 -->
    <div class="toolbar">
      <div class="toolbar-scroll">
        <div class="search-section">
          <div class="search-input-wrapper">
            <input
              v-model="searchQuery"
              @input="handleSearchInput"
              @keydown="handleKeyDown"
              @keyup.enter="handleSearchEnter"
              @focus="showSuggestions = true"
              @blur="handleInputBlur"
              class="stock-input"
              placeholder="输入股票代码、公司名称或拼音，如：000001.SZ、平安银行、pinganyinhang、PAYH"
              type="text"
              autocomplete="off"
            />
            <!-- 搜索建议下拉列表 -->
            <div v-if="showSuggestions && searchSuggestions.length > 0" class="suggestions-dropdown">
              <div
                v-for="(item, index) in searchSuggestions"
                :key="index"
                @mousedown="selectStock(item)"
                class="suggestion-item"
                :class="{ 'highlighted': highlightedIndex === index }"
              >
                <span class="suggestion-code">{{ item.code }}</span>
                <span class="suggestion-name">{{ item.name }}</span>
              </div>
            </div>
          </div>
          <button @click="loadStockData" class="search-btn">查询</button>
          
          <!-- 数据补齐勾选框 -->
          <div class="fetch-latest-wrapper">
            <label class="checkbox-label disabled-label" title="该功能暂不可用">
              <input type="checkbox" v-model="fillMissingData" disabled />
              补齐缺失数据
            </label>
            <label class="checkbox-label" style="margin-left: 15px;">
              <input type="checkbox" v-model="remoteData" />
              远程数据(2018至今)
            </label>
          </div>
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

        <div class="zoom-section">
          <button
            v-for="range in zoomRanges"
            :key="range.label"
            @click="zoomToRange(range)"
            class="zoom-btn"
          >
            {{ range.label }}
          </button>
        </div>
        
        <div class="info-section" v-if="stockInfo">
          <!-- 桃心图标 -->
          <div class="favorite-heart" @click="toggleFavorite" :title="isFavorite ? '取消自选' : '加入自选'">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
                :fill="isFavorite ? '#ff4757' : '#666'"
                :stroke="isFavorite ? '#ff4757' : '#666'"
                stroke-width="1.5"
                stroke-linejoin="round"
              />
            </svg>
          </div>
          
          <div class="info-block">
            <span class="info-label">名称</span>
            <span
              class="info-value code clickable"
              @click="openStockDetail(stockInfo.stock_code)"
              :title="'点击查看 ' + stockInfo.stock_code + ' 的详情'"
            >
              {{ stockBasics?.name || '-' }}
            </span>
          </div>
          <div class="info-block">
            <span class="info-label">最新价</span>
            <span class="info-value">{{ formatNumber(stockBasics?.price) }}</span>
          </div>
          <div class="info-block">
            <span class="info-label">总市值</span>
            <span class="info-value">{{ formatBillion(stockBasics?.market_cap) }}</span>
          </div>
          <div class="info-block">
            <span class="info-label">市盈率-静</span>
            <span class="info-value">{{ formatNumber(stockBasics?.pe_static) }}</span>
          </div>
          <div class="info-block">
            <span class="info-label">市盈率-TTM</span>
            <span class="info-value">{{ formatNumber(stockBasics?.pe_ttm) }}</span>
          </div>
          <div class="info-block">
            <span class="info-label">市净率</span>
            <span class="info-value">{{ formatNumber(stockBasics?.pb) }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 图表容器 -->
    <div class="chart-container">
      <div v-if="loading" class="loading">加载中...</div>
      <div v-else-if="error" class="error">{{ error }}</div>
      <div v-show="!loading && !error" ref="chartRef" class="chart"></div>
    </div>

    <!-- 底部日志窗口 -->
    <div class="strategy-log-window" v-if="strategyLogs.length > 0">
      <div class="log-header">
        <span>策略运行日志</span>
        <button @click="strategyLogs = []" class="clear-log-btn">清空</button>
      </div>
      <div class="log-content" ref="logContentRef">
        <div v-for="(log, index) in strategyLogs" :key="index" class="log-item">
          <span class="log-time">[{{ log.time }}]</span>
          <span class="log-message" :class="log.type">{{ log.message }}</span>
        </div>
      </div>
    </div>
    </div>

    <!-- 右侧交易策略窗口 -->
    <div class="strategy-sidebar">
      <div class="strategy-header">
        <h3>交易策略</h3>
      </div>
      
      <div class="strategy-content">
        <!-- 第一部分：时间窗口配置 -->
        <div class="strategy-section">
          <div class="section-title">时间窗口配置</div>
          <div class="config-item">
            <label>买入窗口</label>
            <div class="date-range">
              <input v-model="strategyConfig.buyStart" placeholder="YYYYMMDD" class="date-input" />
              <span>至</span>
              <input v-model="strategyConfig.buyEnd" placeholder="YYYYMMDD" class="date-input" />
            </div>
          </div>
          <div class="config-item">
            <label>卖出窗口</label>
            <div class="date-range">
              <input v-model="strategyConfig.sellStart" placeholder="YYYYMMDD" class="date-input" />
              <span>至</span>
              <input v-model="strategyConfig.sellEnd" placeholder="YYYYMMDD" class="date-input" />
            </div>
          </div>
        </div>

        <!-- 第二部分：策略选择 -->
        <div class="strategy-section">
          <div class="section-title">选择策略</div>
          <div v-for="strategy in availableStrategies" :key="strategy.id" class="strategy-option">
            <label class="radio-label">
              <input 
                type="radio" 
                v-model="selectedStrategyId" 
                :value="strategy.id"
                @change="handleStrategyChange"
              />
              {{ strategy.name }}
            </label>
            <div v-if="selectedStrategyId === strategy.id" class="strategy-desc">
              {{ strategy.description }}
            </div>
          </div>
        </div>

        <!-- 第三部分：评估结果 -->
        <div class="strategy-section" v-if="evaluationResult">
          <div class="section-title">策略效果评估</div>
          <div class="evaluation-grid">
            <div class="eval-item" v-if="evaluationResult.strategyProfit !== undefined">
              <span class="eval-label">策略实际收益率</span>
              <span class="eval-value" :class="getProfitClass(evaluationResult.strategyProfit)">{{ formatValue(evaluationResult.strategyProfit) }}</span>
            </div>
            <div class="eval-item">
              <span class="eval-label">最大收益率</span>
              <span class="eval-value" :class="getProfitClass(evaluationResult.maxProfit)">{{ formatValue(evaluationResult.maxProfit) }}</span>
            </div>
            <div class="eval-item">
              <span class="eval-label">最低收益率</span>
              <span class="eval-value" :class="getProfitClass(evaluationResult.minProfit)">{{ formatValue(evaluationResult.minProfit) }}</span>
            </div>
            <div class="eval-item">
              <span class="eval-label">中位数收益率</span>
              <span class="eval-value" :class="getProfitClass(evaluationResult.medianProfit)">{{ formatValue(evaluationResult.medianProfit) }}</span>
            </div>
            <div class="eval-item">
              <span class="eval-label">买入后30天最大收益率</span>
              <span class="eval-value" :class="getProfitClass(evaluationResult.maxProfit30d)">{{ formatValue(evaluationResult.maxProfit30d) }}</span>
            </div>
            <div class="eval-item">
              <span class="eval-label">买入后30天中位数收益率</span>
              <span class="eval-value" :class="getProfitClass(evaluationResult.medianProfit30d)">{{ formatValue(evaluationResult.medianProfit30d) }}</span>
            </div>
          </div>
        </div>
        
        <div class="strategy-actions">
          <button @click="runStrategy" class="run-strategy-btn" :disabled="!selectedStrategyId || loading">
            执行回测
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const stockCode = ref('')
const searchQuery = ref('')
const currentPeriod = ref(localStorage.getItem('current_period') || 'day')
const fillMissingData = ref(localStorage.getItem('fill_missing_data') === 'true')
const remoteData = ref(localStorage.getItem('remote_data') === 'true')

// 监听周期变化并保存到本地
watch(currentPeriod, (newVal) => {
  localStorage.setItem('current_period', newVal)
})

// 监听补齐缺失数据变化并保存到本地
watch(fillMissingData, (newVal) => {
  localStorage.setItem('fill_missing_data', newVal)
  if (stockCode.value) {
    loadStockData()
  }
})

// 监听远程数据变化并保存到本地
watch(remoteData, (newVal) => {
  localStorage.setItem('remote_data', newVal)
  if (stockCode.value) {
    loadStockData()
  }
})

const loading = ref(false)
const error = ref('')
const chartRef = ref(null)
let chartInstance = null

const stockInfo = ref(null)
const stockBasics = ref(null)
const peHistory = ref([]) // 存储历史 PE 数据
const isFavorite = ref(false)
const favoriteStocks = ref([])

// 自选股分类和折叠
const collapsedCategories = ref({
  'A股': false,
  '港股': true,
  '美股': true
})

const toggleCategory = (category) => {
  collapsedCategories.value[category] = !collapsedCategories.value[category]
}

const groupedFavorites = computed(() => {
  const groups = {
    'A股': [],
    '港股': [],
    '美股': []
  }
  
  favoriteStocks.value.forEach(stock => {
    const code = (stock.code || '').toUpperCase()
    if (code.endsWith('.HK')) {
      groups['港股'].push(stock)
    } else if (code.endsWith('.US')) {
      groups['美股'].push(stock)
    } else {
      groups['A股'].push(stock)
    }
  })
  
  return groups
})

// 交易策略相关
const savedConfig = localStorage.getItem('strategy_config')
const strategyConfig = ref(savedConfig ? JSON.parse(savedConfig) : {
  buyStart: '20210101',
  buyEnd: '20221231',
  sellStart: '20230101',
  sellEnd: '20231231'
})

const availableStrategies = [
  {
    id: 'trend',
    name: '趋势交易策略',
    description: '买入：20日均线 > 60日均线，股价站上60日均线 ≥ 5个交易日。'
  },
  {
    id: 'smart_oversold',
    name: '智能抄底回升策略',
    description: '通过2021-2023年历史数据回测优化。逻辑：在2021-2022年寻找极度超跌机会（20日跌幅>20%且偏离60日线>10%），在2023年价值回归至60日线时获利了结。'
  },
  {
    id: 'turtle',
    name: '海龟交易法则',
    description: '经典趋势跟随策略。买入：股价创20日新高；卖出：股价跌破10日新低。'
  },
  {
    id: 'mean_reversion',
    name: '均值回归策略',
    description: '反向交易策略。买入：股价偏离20日均线下方2倍标准差(布林线下轨)；卖出：股价回升至20日均线。'
  }
]

const selectedStrategyId = ref(localStorage.getItem('selected_strategy_id') || null)

// 监听策略配置变化并保存到本地
watch(strategyConfig, (newVal) => {
  localStorage.setItem('strategy_config', JSON.stringify(newVal))
}, { deep: true })

// 监听选中的策略变化并保存到本地
watch(selectedStrategyId, (newVal) => {
  if (newVal) {
    localStorage.setItem('selected_strategy_id', newVal)
  } else {
    localStorage.removeItem('selected_strategy_id')
  }
})

const evaluationResult = ref(null)
const tradingSignals = ref([]) // 存储 B/S 信号
const strategyLogs = ref([]) // 策略运行日志
const logContentRef = ref(null)

// 监听日志长度变化，当日志窗口出现/消失时调整图表大小
watch(() => strategyLogs.value.length, (newLen, oldLen) => {
  if ((newLen > 0 && oldLen === 0) || (newLen === 0 && oldLen > 0)) {
    nextTick(() => {
      chartInstance?.resize()
    })
  }
})

const addLog = (message, type = 'info') => {
  const now = new Date()
  const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
  strategyLogs.value.push({ time, message, type })
  
  // 自动滚动到底部
  nextTick(() => {
    if (logContentRef.value) {
      logContentRef.value.scrollTop = logContentRef.value.scrollHeight
    }
  })
}

// 搜索建议相关
const searchSuggestions = ref([])
const showSuggestions = ref(false)
const highlightedIndex = ref(-1)
let searchTimeout = null
const localStockList = ref([])
const localStockListLoaded = ref(false)

const periods = [
  { label: '日线', value: 'day' },
  { label: '周线', value: 'week' },
  { label: '月线', value: 'month' }
]

const zoomRanges = [
  { label: '近1周', value: 7, unit: 'day' },
  { label: '近1月', value: 1, unit: 'month' },
  { label: '近1年', value: 1, unit: 'year' },
  { label: '近3年', value: 3, unit: 'year' },
  { label: '近5年', value: 5, unit: 'year' }
]

// 缩放至指定范围
const zoomToRange = (range) => {
  if (!chartInstance) return
  
  const option = chartInstance.getOption()
  if (!option.xAxis || !option.xAxis[0] || !option.xAxis[0].data) return
  
  const dates = option.xAxis[0].data
  if (dates.length === 0) return

  // 获取最后一个日期
  const lastDateStr = dates[dates.length - 1]
  // 兼容处理日期字符串，确保能正确解析
  const lastDate = new Date(lastDateStr.replace(/-/g, '/')) 
  
  const targetDate = new Date(lastDate)
  
  if (range.unit === 'day') {
    targetDate.setDate(targetDate.getDate() - range.value)
  } else if (range.unit === 'month') {
    targetDate.setMonth(targetDate.getMonth() - range.value)
  } else if (range.unit === 'year') {
    targetDate.setFullYear(targetDate.getFullYear() - range.value)
  }
  
  // 查找最接近目标日期的索引
  let targetIndex = 0
  for (let i = 0; i < dates.length; i++) {
    const currentDate = new Date(dates[i].replace(/-/g, '/'))
    if (currentDate >= targetDate) {
      targetIndex = i
      break
    }
  }
  
  const startPercent = (targetIndex / dates.length) * 100
  
  chartInstance.dispatchAction({
    type: 'dataZoom',
    start: startPercent,
    end: 100
  })
}

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

const getLocalSuggestions = (query, limit = 10) => {
  const q = query.trim()
  if (!q) return []
  const queryLower = q.toLowerCase().replace(/\s+/g, '')
  const queryUpper = q.toUpperCase().replace(/\s+/g, '')
  const queryNoSpace = q.replace(/\s+/g, '')
  const results = []
  const seen = new Set()

  const pushResult = (stock) => {
    if (results.length >= limit || seen.has(stock.code)) return
    results.push({ code: stock.code, name: stock.name })
    seen.add(stock.code)
  }

  for (let i = 0; i < localStockList.value.length && results.length < limit; i++) {
    const stock = localStockList.value[i]
    const codeMatch = stock.code?.toUpperCase().includes(queryUpper)
    const nameMatch = stock.name?.replace(/\s+/g, '').includes(queryNoSpace)
    if (codeMatch || nameMatch) {
      pushResult(stock)
    }
  }

  if (results.length < limit) {
    for (let i = 0; i < localStockList.value.length && results.length < limit; i++) {
      const stock = localStockList.value[i]
      const pinyinMatch = stock.pinyin?.includes(queryLower)
      const initialsMatch = stock.pinyin_initials?.includes(queryUpper)
      if (pinyinMatch || initialsMatch) {
        pushResult(stock)
      }
    }
  }

  return results
}

const loadLocalStockList = async () => {
  try {
    const response = await axios.get('/api/stock_list', { timeout: 10000 })
    if (response.data?.success) {
      localStockList.value = response.data.results || []
      localStockListLoaded.value = true
    }
  } catch (err) {
    console.warn('加载股票列表失败，使用后端搜索', err)
  }
}

// 搜索股票
const searchStocks = async (query) => {
  if (!query || query.trim().length < 1) {
    searchSuggestions.value = []
    return
  }
  
  if (localStockListLoaded.value) {
    searchSuggestions.value = getLocalSuggestions(query, 10)
    return
  }

  try {
    const response = await axios.get('/api/search_stocks', {
      params: {
        q: query.trim(),
        limit: 10
      }
    })
    
    if (response.data.success) {
      searchSuggestions.value = response.data.results || []
    } else {
      searchSuggestions.value = []
    }
  } catch (err) {
    console.error('搜索股票失败:', err)
    searchSuggestions.value = []
  }
}

// 处理搜索输入
const handleSearchInput = () => {
  // 重置高亮索引
  highlightedIndex.value = -1
  showSuggestions.value = true
  
  // 清除之前的定时器
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  
  // 防抖：300ms后执行搜索
  searchTimeout = setTimeout(() => {
    searchStocks(searchQuery.value)
  }, 300)
}

// 处理键盘按键
const handleKeyDown = (e) => {
  if (!showSuggestions.value || (searchSuggestions.value.length === 0 && !searchQuery.value)) {
    return
  }

  // 如果提示框没显示但按了方向键，尝试显示
  if (!showSuggestions.value && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    showSuggestions.value = true
    if (searchSuggestions.value.length === 0) {
      searchStocks(searchQuery.value)
    }
    return
  }

  switch (e.key) {
    case 'ArrowDown':
      e.preventDefault()
      if (searchSuggestions.value.length > 0) {
        highlightedIndex.value = (highlightedIndex.value + 1) % searchSuggestions.value.length
      }
      break
    case 'ArrowUp':
      e.preventDefault()
      if (searchSuggestions.value.length > 0) {
        highlightedIndex.value = (highlightedIndex.value - 1 + searchSuggestions.value.length) % searchSuggestions.value.length
      }
      break
    case 'Escape':
      showSuggestions.value = false
      highlightedIndex.value = -1
      break
    case 'Enter':
      if (highlightedIndex.value >= 0 && searchSuggestions.value[highlightedIndex.value]) {
        e.preventDefault()
        selectStock(searchSuggestions.value[highlightedIndex.value])
      }
      break
  }
}

// 处理输入框失焦
const handleInputBlur = () => {
  // 延迟隐藏，以便点击选项时能触发
  setTimeout(() => {
    showSuggestions.value = false
  }, 200)
}

// 选择股票
const selectStock = (item) => {
  stockCode.value = item.code
  searchQuery.value = ''
  searchSuggestions.value = []
  showSuggestions.value = false
  loadStockData()
}

// 处理回车键
const handleSearchEnter = () => {
  if (highlightedIndex.value >= 0 && searchSuggestions.value[highlightedIndex.value]) {
    // 如果有高亮的选项，选择它
    selectStock(searchSuggestions.value[highlightedIndex.value])
  } else if (searchQuery.value.trim()) {
    // 否则直接使用输入的内容作为股票代码
    stockCode.value = searchQuery.value.trim()
    searchQuery.value = ''
    showSuggestions.value = false
    loadStockData()
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
  peHistory.value = [] // 切换股票时重置历史 PE 数据
  
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
    
    console.log(`正在加载股票数据: ${stockCode.value}, 周期: ${currentPeriod.value}, 补齐缺失: ${fillMissingData.value}, 远程数据: ${remoteData.value}`)
    const response = await axios.get(`/api/stock/${stockCode.value}`, {
      params: {
        period: currentPeriod.value,
        fill_missing_data: fillMissingData.value ? 'true' : 'false',
        remote_data: remoteData.value ? 'true' : 'false'
      },
      timeout: 30000 // 30秒超时
    })
    
    console.log('API响应:', response.data)
    
    if (response.data.success) {
      stockInfo.value = {
        stock_code: response.data.stock_code,
        year: response.data.year,
        count: response.data.count,
        data: response.data.data
      }
      await nextTick() // 等待DOM更新
      renderChart(response.data.data)
      fetchStockInfo(stockCode.value) // 异步获取公司基本面
      fetchPEHistory(stockCode.value) // 异步获取历史 PE 趋势
      checkFavoriteStatus(stockCode.value) // 检查自选状态

      // 如果当前已选择策略，则自动执行回测
      if (selectedStrategyId.value) {
        runStrategy()
      }
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
    // 检查代码是否匹配
    if (code !== stockCode.value) return
    
    if (resp.data?.success) {
      stockBasics.value = {
        name: resp.data.name,
        price: resp.data.price,
        market_cap: resp.data.market_cap,
        pe_static: resp.data.pe_static,
        pe_ttm: resp.data.pe_ttm,
        pb: resp.data.pb
      }
    } else {
      stockBasics.value = null
      console.warn(resp.data?.error || '未获取到公司信息')
    }
  } catch (e) {
    // 检查代码是否匹配
    if (code !== stockCode.value) return
    stockBasics.value = null
    console.warn('获取公司信息失败', e)
  }
}

// 获取历史 PE 数据
const fetchPEHistory = async (code) => {
  try {
    const resp = await axios.get(`/api/stock_pe/${code}`, { timeout: 15000 })
    // 检查代码是否匹配，防止竞态条件
    if (code !== stockCode.value) return
    
    if (resp.data?.success) {
      peHistory.value = resp.data.data
      // 重新渲染图表以包含 PE 趋势
      if (stockInfo.value && stockInfo.value.data) {
        renderChart(stockInfo.value.data)
      }
    } else {
      peHistory.value = []
      console.warn(resp.data?.error || '未获取到历史 PE 数据')
    }
  } catch (e) {
    // 检查代码是否匹配
    if (code !== stockCode.value) return
    peHistory.value = []
    console.warn('获取历史 PE 数据失败', e)
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
  
  // 准备 PE 数据，需要对齐 K 线日期
  // peHistory 格式: [{date: '2023-01-01', value: 15.5}, ...]
  const peMap = {}
  peHistory.value.forEach(item => {
    peMap[item.date] = item.value
  })
  
  // 填充 PE 数据，如果某天没有 PE 数据，则寻找最近的前一天数据
  const peTrend = []
  let lastPe = null
  dates.forEach(dateTime => {
    const dateOnly = dateTime.split(' ')[0]
    if (peMap[dateOnly] !== undefined) {
      lastPe = peMap[dateOnly]
    }
    peTrend.push(lastPe)
  })
  
  // 计算MA5、MA20和MA60
  const ma5 = calculateMA(5, data)
  const ma20 = calculateMA(20, data)
  const ma60 = calculateMA(60, data)

  const option = {
    backgroundColor: 'transparent',
    animation: false,
    legend: {
      data: ['K线', 'MA5', 'MA20', 'MA60', '成交量', 'PE-TTM'],
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
          } else if (param.seriesName === 'PE-TTM') {
            result += `${param.seriesName}: ${param.value && param.value !== '-' ? parseFloat(param.value).toFixed(2) : '-'}<br/>`
          } else {
            result += `${param.seriesName}: ${param.value}<br/>`
          }
        })
        return result
      }
    },
    grid: [
      {
        left: '50px',
        right: '20px',
        top: '40px',
        height: '52%'
      },
      {
        left: '50px',
        right: '20px',
        top: '65%',
        height: '12%'
      },
      {
        left: '50px',
        right: '20px',
        top: '80%',
        height: '12%'
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
            return value.split(' ')[0] || value
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
      },
      {
        type: 'category',
        gridIndex: 2,
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
      },
      {
        scale: true,
        gridIndex: 2,
        splitNumber: 2,
        axisLabel: { color: '#999', fontSize: 10 },
        axisLine: { show: false },
        axisTick: { show: false },
        splitLine: { show: false }
      }
    ],
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: [0, 1, 2],
        start: 0,
        end: 100
      },
      {
        show: true,
        xAxisIndex: [0, 1, 2],
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
        itemStyle: { color: '#ff9800' },
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
        itemStyle: { color: '#2196f3' },
        lineStyle: {
          width: 1,
          color: '#2196f3'
        },
        symbol: 'none'
      },
      {
        name: 'MA60',
        type: 'line',
        data: ma60,
        smooth: true,
        itemStyle: { color: '#9c27b0' },
        lineStyle: {
          width: 1,
          color: '#9c27b0'
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
      },
      {
        name: 'PE-TTM',
        type: 'line',
        xAxisIndex: 2,
        yAxisIndex: 2,
        data: peTrend,
        smooth: true,
        itemStyle: { color: '#00bcd4' },
        lineStyle: {
          width: 1.5,
          color: '#00bcd4'
        },
        symbol: 'none',
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(0, 188, 212, 0.3)' },
            { offset: 1, color: 'rgba(0, 188, 212, 0)' }
          ])
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

// 加载自选股票列表
const loadFavoriteStocks = async () => {
  try {
    const response = await axios.get('/api/favorites', { timeout: 5000 })
    if (response.data?.success) {
      favoriteStocks.value = response.data.stocks || []
    }
  } catch (e) {
    console.warn('加载自选股票失败', e)
    favoriteStocks.value = []
  }
}

// 检查股票是否为自选
const checkFavoriteStatus = async (code) => {
  if (!code) {
    isFavorite.value = false
    return
  }
  try {
    const response = await axios.get('/api/favorites/check', {
      params: { stock_code: code },
      timeout: 5000
    })
    if (response.data?.success) {
      isFavorite.value = response.data.is_favorite || false
    }
  } catch (e) {
    console.warn('检查自选状态失败', e)
    isFavorite.value = false
  }
}

// 切换自选状态
const toggleFavorite = async () => {
  if (!stockInfo.value?.stock_code) return
  
  const code = stockInfo.value.stock_code
  const name = stockBasics.value?.name || ''
  
  try {
    if (isFavorite.value) {
      // 取消自选
      await axios.delete('/api/favorites', {
        params: { stock_code: code },
        timeout: 5000
      })
      isFavorite.value = false
    } else {
      // 添加自选
      await axios.post('/api/favorites', {
        stock_code: code,
        stock_name: name
      }, { timeout: 5000 })
      isFavorite.value = true
    }
    // 重新加载自选列表
    await loadFavoriteStocks()
  } catch (e) {
    console.error('切换自选状态失败', e)
    alert('操作失败，请稍后重试')
  }
}

// 选择自选股票
const selectFavoriteStock = (code) => {
  stockCode.value = code
  searchQuery.value = ''
  loadStockData()
}

// 策略相关方法
const handleStrategyChange = () => {
  evaluationResult.value = null
  tradingSignals.value = []
}

const getProfitClass = (profit) => {
  if (!profit) return ''
  return profit > 0 ? 'profit-positive' : (profit < 0 ? 'profit-negative' : '')
}

const formatValue = (val) => {
  if (val === null || val === undefined) return '-'
  return `${val.toFixed(2)}%`
}

const runStrategy = () => {
  if (!selectedStrategyId.value || !chartInstance) return
  
  strategyLogs.value = [] // 清空旧日志
  addLog(`开始执行策略: ${availableStrategies.find(s => s.id === selectedStrategyId.value)?.name}`, 'info')
  
  const option = chartInstance.getOption()
  const dates = option.xAxis[0].data
  const klineSeries = option.series.find(s => s.name === 'K线')
  const seriesData = klineSeries.data
  const ma20 = option.series.find(s => s.name === 'MA20').data
  const ma60 = option.series.find(s => s.name === 'MA60').data
  
  const signals = []
  const buyWindowPrices = []
  const sellWindowPrices = []
  let buySignalIndex = -1
  let buySignalPrice = 0
  
  // 转换日期格式 YYYYMMDD -> YYYY-MM-DD
  const formatDate = (str) => {
    if (!str || str.length !== 8) return ''
    return `${str.slice(0, 4)}-${str.slice(4, 6)}-${str.slice(6, 8)}`
  }
  const buyStart = formatDate(strategyConfig.value.buyStart)
  const buyEnd = formatDate(strategyConfig.value.buyEnd)
  const sellStart = formatDate(strategyConfig.value.sellStart)
  const sellEnd = formatDate(strategyConfig.value.sellEnd)

  const getMedianRate = (rates) => {
    if (rates.length === 0) return 0
    const sortedRates = [...rates].sort((a, b) => a - b)
    const midIndex = Math.floor(sortedRates.length / 2)
    return sortedRates.length % 2 === 0
      ? (sortedRates[midIndex - 1] + sortedRates[midIndex]) / 2
      : sortedRates[midIndex]
  }

  addLog(`配置参数: 买入窗口(${buyStart} 至 ${buyEnd}), 卖出窗口(${sellStart} 至 ${sellEnd})`, 'info')

  for (let i = 0; i < dates.length; i++) {
    const date = dates[i]
    const close = seriesData[i][1]
    if (date >= buyStart && date <= buyEnd) {
      buyWindowPrices.push(close)
    }
    if (date >= sellStart && date <= sellEnd) {
      sellWindowPrices.push(close)
    }
  }

  const buyAvgPrice = buyWindowPrices.length > 0
    ? buyWindowPrices.reduce((sum, price) => sum + price, 0) / buyWindowPrices.length
    : 0

  if (selectedStrategyId.value === 'trend') {
    let holdPrice = 0
    let above60Days = 0
    
    // 1. 查找第一个符合买入条件的日期
    for (let i = 60; i < dates.length; i++) {
      const date = dates[i]
      const close = seriesData[i][1]
      
      if (date >= buyStart && date <= buyEnd && holdPrice === 0) {
        const currentMA20 = parseFloat(ma20[i])
        const currentMA60 = parseFloat(ma60[i])
        
        if (!isNaN(currentMA20) && !isNaN(currentMA60) && currentMA20 > currentMA60 && close > currentMA60) {
          above60Days++
        } else {
          above60Days = 0
        }
        
        if (above60Days >= 5) {
          holdPrice = close
          buySignalIndex = i
          buySignalPrice = close
          const buyPrice = parseFloat(seriesData[i][3])
          signals.push({ index: i, type: 'B', price: buyPrice, date: date })
          addLog(`${date}: [买入] 触发买入信号，买入价格 ${holdPrice.toFixed(2)}`, 'buy')
          break // 找到第一个买入点后停止查找
        }
      }
    }

    if (holdPrice === 0) {
      addLog(`买入窗口内未触发买入信号，仅用于标注展示`, 'info')
    }

    let maxProfit30d = 0
    let medianProfit30d = 0
    if (buySignalIndex >= 0 && buySignalPrice > 0) {
      const rates30d = []
      let counted = 0
      for (let i = buySignalIndex; i < dates.length && counted < 30; i++) {
        const close = seriesData[i][1]
        rates30d.push(((close - buySignalPrice) / buySignalPrice) * 100)
        counted += 1
      }
      if (rates30d.length > 0) {
        maxProfit30d = Math.max(...rates30d)
        medianProfit30d = getMedianRate(rates30d)
      }
    }

    if (buyAvgPrice > 0 && sellWindowPrices.length > 0) {
      const yieldRates = sellWindowPrices.map(price => ((price - buyAvgPrice) / buyAvgPrice) * 100)
      const medianRate = getMedianRate(yieldRates)
      const maxSellPrice = Math.max(...sellWindowPrices)
      const minSellPrice = Math.min(...sellWindowPrices)

      evaluationResult.value = {
        maxProfit: ((maxSellPrice - buyAvgPrice) / buyAvgPrice) * 100,
        minProfit: ((minSellPrice - buyAvgPrice) / buyAvgPrice) * 100,
        medianProfit: medianRate,
        maxProfit30d,
        medianProfit30d
      }
      addLog(`策略执行完毕，买入窗口均价 ${buyAvgPrice.toFixed(2)}，卖出窗口交易日 ${sellWindowPrices.length} 个`, 'info')
      addLog(`最大收益率: ${evaluationResult.value.maxProfit.toFixed(2)}%`, 'info')
    } else {
      evaluationResult.value = {
        maxProfit: 0,
        minProfit: 0,
        medianProfit: 0,
        maxProfit30d: 0,
        medianProfit30d: 0
      }
      addLog(`策略执行完毕，买入或卖出窗口无有效交易日`, 'info')
    }
  } else if (selectedStrategyId.value === 'smart_oversold') {
    let holdPrice = 0
    
    // 1. 查找第一个符合买入条件的日期
    for (let i = 60; i < dates.length; i++) {
      const date = dates[i]
      const close = seriesData[i][1]
      
      if (date >= buyStart && date <= buyEnd && holdPrice === 0) {
        const prev20Close = seriesData[i - 20][1]
        const currentMA60 = parseFloat(ma60[i])
        
        // 买入：20日内跌幅 > 20% 且低于60日线10%
        if (close < prev20Close * 0.8 && close < currentMA60 * 0.9) {
          holdPrice = close
          buySignalIndex = i
          buySignalPrice = close
          const buyPrice = parseFloat(seriesData[i][3])
          signals.push({ index: i, type: 'B', price: buyPrice, date: date })
          addLog(`${date}: [买入] 触发超跌信号，买入价格 ${holdPrice.toFixed(2)}`, 'buy')
          break
        }
      }
    }

    // 2. 查找卖出信号 (2023年回归60日线)
    let sellSignalPrice = 0
    if (holdPrice > 0) {
      for (let i = buySignalIndex + 1; i < dates.length; i++) {
        const date = dates[i]
        const close = seriesData[i][1]
        const currentMA60 = parseFloat(ma60[i])
        
        if (date >= sellStart && date <= sellEnd) {
          if (close >= currentMA60) {
            sellSignalPrice = close
            const sellPrice = parseFloat(seriesData[i][3])
            signals.push({ index: i, type: 'S', price: sellPrice, date: date })
            addLog(`${date}: [卖出] 股价回归60日线，卖出价格 ${close.toFixed(2)}`, 'sell')
            break
          }
        }
      }
    }

    if (holdPrice === 0) {
      addLog(`买入窗口内未触发超跌信号`, 'info')
    }

    // 计算收益率 (复用逻辑)
    let maxProfit30d = 0
    let medianProfit30d = 0
    if (buySignalIndex >= 0 && buySignalPrice > 0) {
      const rates30d = []
      let counted = 0
      for (let i = buySignalIndex; i < dates.length && counted < 30; i++) {
        const close = seriesData[i][1]
        rates30d.push(((close - buySignalPrice) / buySignalPrice) * 100)
        counted += 1
      }
      if (rates30d.length > 0) {
        maxProfit30d = Math.max(...rates30d)
        medianProfit30d = getMedianRate(rates30d)
      }
    }

    if (buySignalPrice > 0 && sellWindowPrices.length > 0) {
      const yieldRates = sellWindowPrices.map(price => ((price - buySignalPrice) / buySignalPrice) * 100)
      const medianRate = getMedianRate(yieldRates)
      const maxSellPrice = Math.max(...sellWindowPrices)
      const minSellPrice = Math.min(...sellWindowPrices)

      evaluationResult.value = {
        strategyProfit: sellSignalPrice > 0 ? ((sellSignalPrice - buySignalPrice) / buySignalPrice) * 100 : undefined,
        maxProfit: ((maxSellPrice - buySignalPrice) / buySignalPrice) * 100,
        minProfit: ((minSellPrice - buySignalPrice) / buySignalPrice) * 100,
        medianProfit: medianRate,
        maxProfit30d,
        medianProfit30d
      }
      addLog(`策略执行完毕，买入价格 ${buySignalPrice.toFixed(2)}，卖出窗口交易日 ${sellWindowPrices.length} 个`, 'info')
      if (sellSignalPrice > 0) {
        addLog(`策略实际收益率: ${evaluationResult.value.strategyProfit.toFixed(2)}%`, 'info')
      }
    } else {
      evaluationResult.value = {
        strategyProfit: 0,
        maxProfit: 0,
        minProfit: 0,
        medianProfit: 0,
        maxProfit30d: 0,
        medianProfit30d: 0
      }
    }
  } else if (selectedStrategyId.value === 'turtle') {
    let holdPrice = 0
    let sellSignalPrice = 0

    // 海龟交易法则逻辑
    for (let i = 20; i < dates.length; i++) {
      const date = dates[i]
      const close = seriesData[i][1]
      
      // 计算前20日最高价和前10日最低价
      const prev20Data = seriesData.slice(i - 20, i).map(d => d[1])
      const high20 = Math.max(...prev20Data)
      const prev10Data = seriesData.slice(i - 10, i).map(d => d[1])
      const low10 = Math.min(...prev10Data)

      if (date >= buyStart && date <= buyEnd && holdPrice === 0) {
        // 买入：创20日新高
        if (close > high20) {
          holdPrice = close
          buySignalIndex = i
          buySignalPrice = close
          const buyPrice = parseFloat(seriesData[i][3])
          signals.push({ index: i, type: 'B', price: buyPrice, date: date })
          addLog(`${date}: [买入] 海龟法则：突破20日新高 ${high20.toFixed(2)}，买入价格 ${holdPrice.toFixed(2)}`, 'buy')
        }
      } else if (holdPrice > 0 && date >= sellStart && date <= sellEnd) {
        // 卖出：跌破10日新低
        if (close < low10) {
          sellSignalPrice = close
          const sellPrice = parseFloat(seriesData[i][3])
          signals.push({ index: i, type: 'S', price: sellPrice, date: date })
          addLog(`${date}: [卖出] 海龟法则：跌破10日新低 ${low10.toFixed(2)}，卖出价格 ${close.toFixed(2)}`, 'sell')
          break
        }
      }
    }

    // 计算收益统计 (复用逻辑)
    if (buySignalPrice > 0 && sellWindowPrices.length > 0) {
      const yieldRates = sellWindowPrices.map(price => ((price - buySignalPrice) / buySignalPrice) * 100)
      const medianRate = getMedianRate(yieldRates)
      const maxSellPrice = Math.max(...sellWindowPrices)
      const minSellPrice = Math.min(...sellWindowPrices)

      evaluationResult.value = {
        strategyProfit: sellSignalPrice > 0 ? ((sellSignalPrice - buySignalPrice) / buySignalPrice) * 100 : undefined,
        maxProfit: ((maxSellPrice - buySignalPrice) / buySignalPrice) * 100,
        minProfit: ((minSellPrice - buySignalPrice) / buySignalPrice) * 100,
        medianProfit: medianRate,
        maxProfit30d: 0,
        medianProfit30d: 0
      }
      addLog(`策略执行完毕，买入价格 ${buySignalPrice.toFixed(2)}`, 'info')
    }
  } else if (selectedStrategyId.value === 'mean_reversion') {
    let holdPrice = 0
    let sellSignalPrice = 0

    // 均值回归策略逻辑 (使用布林线概念)
    for (let i = 20; i < dates.length; i++) {
      const date = dates[i]
      const close = seriesData[i][1]
      const currentMA20 = parseFloat(ma20[i])
      
      // 计算20日标准差
      const prev20Data = seriesData.slice(i - 20, i).map(d => d[1])
      const mean = prev20Data.reduce((a, b) => a + b) / 20
      const stdDev = Math.sqrt(prev20Data.map(x => Math.pow(x - mean, 2)).reduce((a, b) => a + b) / 20)
      const lowerBand = currentMA20 - 2 * stdDev

      if (date >= buyStart && date <= buyEnd && holdPrice === 0) {
        // 买入：触及布林线下轨 (低于均线2倍标准差)
        if (close < lowerBand) {
          holdPrice = close
          buySignalIndex = i
          buySignalPrice = close
          const buyPrice = parseFloat(seriesData[i][3])
          signals.push({ index: i, type: 'B', price: buyPrice, date: date })
          addLog(`${date}: [买入] 均值回归：触及布林线下轨 ${lowerBand.toFixed(2)}，买入价格 ${holdPrice.toFixed(2)}`, 'buy')
        }
      } else if (holdPrice > 0 && date >= sellStart && date <= sellEnd) {
        // 卖出：回归至均线
        if (close >= currentMA20) {
          sellSignalPrice = close
          const sellPrice = parseFloat(seriesData[i][3])
          signals.push({ index: i, type: 'S', price: sellPrice, date: date })
          addLog(`${date}: [卖出] 均值回归：回归20日均线 ${currentMA20.toFixed(2)}，卖出价格 ${close.toFixed(2)}`, 'sell')
          break
        }
      }
    }

    // 计算收益统计 (复用逻辑)
    if (buySignalPrice > 0 && sellWindowPrices.length > 0) {
      const yieldRates = sellWindowPrices.map(price => ((price - buySignalPrice) / buySignalPrice) * 100)
      evaluationResult.value = {
        strategyProfit: sellSignalPrice > 0 ? ((sellSignalPrice - buySignalPrice) / buySignalPrice) * 100 : undefined,
        maxProfit: yieldRates.length > 0 ? Math.max(...yieldRates) : 0,
        minProfit: yieldRates.length > 0 ? Math.min(...yieldRates) : 0,
        medianProfit: getMedianRate(yieldRates),
        maxProfit30d: 0,
        medianProfit30d: 0
      }
    }
  }
  
  tradingSignals.value = signals
  
  updateChartWithSignals()

  const getDateByOffset = (dateStr, monthsOffset) => {
    if (!dateStr) return ''
    const date = new Date(dateStr.replace(/-/g, '/'))
    if (Number.isNaN(date.getTime())) return ''
    const target = new Date(date)
    target.setMonth(target.getMonth() + monthsOffset)
    const yyyy = target.getFullYear()
    const mm = String(target.getMonth() + 1).padStart(2, '0')
    const dd = String(target.getDate()).padStart(2, '0')
    return `${yyyy}-${mm}-${dd}`
  }

  const getIndexByDate = (dates, targetDate) => {
    if (!targetDate) return 0
    for (let i = 0; i < dates.length; i++) {
      if (dates[i] >= targetDate) return i
    }
    return dates.length - 1
  }

  if (dates.length > 0) {
    const zoomStartDate = getDateByOffset(buyStart, -1)
    const zoomEndDate = getDateByOffset(sellEnd, 1)
    const startIndex = getIndexByDate(dates, zoomStartDate)
    const endIndex = getIndexByDate(dates, zoomEndDate)
    const startPercent = (startIndex / dates.length) * 100
    const endPercent = ((endIndex + 1) / dates.length) * 100
    chartInstance.dispatchAction({
      type: 'dataZoom',
      start: Math.max(0, Math.min(100, startPercent)),
      end: Math.max(0, Math.min(100, endPercent))
    })
  }
}

const updateChartWithSignals = () => {
  if (!chartInstance) return
  
  const markPoints = tradingSignals.value.map(sig => ({
    name: sig.type,
    coord: [sig.date, sig.price],
    value: sig.type,
    symbol: 'pin',
    symbolSize: 30,
    symbolOffset: [0, sig.type === 'B' ? -10 : 10],
    itemStyle: {
      color: sig.type === 'B' ? '#ef5350' : '#26a69a'
    },
    label: {
      show: true,
      position: 'inside',
      formatter: sig.type,
      color: '#fff',
      fontWeight: 'bold',
      fontSize: 12
    }
  }))
  
  console.log('更新标注点:', markPoints.length, markPoints)
  
  // 获取当前所有 series，确保只更新“K线”系列的 markPoint
  const option = chartInstance.getOption()
  const klineSeriesIndex = option.series.findIndex(s => s.name === 'K线')

  const formatDate = (str) => {
    if (!str || str.length !== 8) return ''
    return `${str.slice(0, 4)}-${str.slice(4, 6)}-${str.slice(6, 8)}`
  }
  const getFirstDateInWindow = (dates, start, end) => {
    if (!start || !end) return ''
    for (let i = 0; i < dates.length; i++) {
      if (dates[i] >= start && dates[i] <= end) return dates[i]
    }
    return ''
  }

  const dates = option.xAxis?.[0]?.data || []
  const buyStart = formatDate(strategyConfig.value.buyStart)
  const buyEnd = formatDate(strategyConfig.value.buyEnd)
  const sellStart = formatDate(strategyConfig.value.sellStart)
  const sellEnd = formatDate(strategyConfig.value.sellEnd)
  const buyStartDate = getFirstDateInWindow(dates, buyStart, buyEnd)
  const sellStartDate = getFirstDateInWindow(dates, sellStart, sellEnd)
  const markLines = []
  if (buyStartDate) {
    markLines.push({
      xAxis: buyStartDate,
      lineStyle: {
        color: '#ef5350',
        type: 'dashed',
        width: 1
      },
      label: {
        show: false
      }
    })
  }
  if (sellStartDate) {
    markLines.push({
      xAxis: sellStartDate,
      lineStyle: {
        color: '#26a69a',
        type: 'dashed',
        width: 1
      },
      label: {
        show: false
      }
    })
  }
  
  if (klineSeriesIndex !== -1) {
    // 构造一个新的 series 数组，只包含我们要更新的那一项
    // ECharts 会根据索引或名称自动合并
    const updatedSeries = option.series.map((s, idx) => {
      if (idx === klineSeriesIndex) {
        return {
          ...s,
          markPoint: {
            data: markPoints,
            animation: true,
            z: 10
          },
          markLine: {
            silent: true,
            symbol: 'none',
            data: markLines
          }
        }
      }
      return s
    })
    
    chartInstance.setOption({
      series: updatedSeries
    }, { notMerge: false }) // notMerge: false 表示合并模式
  }
}

// 跳转到第三方股票详情页面（A股跳转东方财富，港美股跳转富途）
const openStockDetail = (stockCode) => {
  if (!stockCode) return
  
  const code = stockCode.toUpperCase()
  const parts = code.split('.')
  let url = ''
  
  if (code.endsWith('.SH') || code.endsWith('.SZ')) {
    // A股：东方财富
    // 格式：https://quote.eastmoney.com/sz000001.html 或 https://quote.eastmoney.com/sh600000.html
    const [base, suffix] = parts
    const emCode = (suffix === 'SZ' ? 'sz' : 'sh') + base
    url = `https://quote.eastmoney.com/${emCode}.html`
  } else if (code.endsWith('.HK')) {
    // 港股：富途
    // 格式：https://www.futunn.com/stock/700-HK
    const [base] = parts
    url = `https://www.futunn.com/stock/${base}-HK`
  } else if (code.endsWith('.US')) {
    // 美股：富途
    // 格式：https://www.futunn.com/stock/AAPL-US
    // 处理 105.AAPL.US 这种情况
    const symbol = parts.length >= 3 ? parts[1] : parts[0]
    url = `https://www.futunn.com/stock/${symbol}-US`
  } else {
    // 兜底：东方财富（默认假设是A股）
    const emCode = (code.startsWith('6') ? 'sh' : 'sz') + code.split('.')[0]
    url = `https://quote.eastmoney.com/${emCode}.html`
  }
  
  window.open(url, '_blank')
}

onMounted(async () => {
  await initChart()
  await loadLocalStockList()
  // 加载自选股票列表
  await loadFavoriteStocks()
  
  // 启动时默认展示自选第一的股票，如果没有自选则展示平安银行
  if (favoriteStocks.value.length > 0) {
    stockCode.value = favoriteStocks.value[0].code
  } else {
    stockCode.value = '000001.SZ'
  }
  
  // 确保搜索框清空
  searchQuery.value = ''
  
  await loadStockData()
})
</script>

<style scoped>
.app-container {
  width: 100%;
  height: 100vh;
  display: flex;
  background: #1a1a1a;
  overflow: hidden;
  position: relative;
}

.favorites-sidebar {
  width: 120px;
  background: #1a1a1a;
  border-right: 1px solid #333;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}

.favorites-header {
  padding: 10px 12px;
  border-bottom: 1px solid #333;
  display: flex;
  align-items: center;
  gap: 6px;
}

.favorites-header h3 {
  margin: 0;
  color: #e0e0e0;
  font-size: 14px;
  font-weight: 600;
}

.favorites-count {
  color: #777;
  font-size: 12px;
}

.favorites-list {
  flex: 1;
  overflow-y: auto;
  padding: 5px;
}

.favorite-group {
  margin-bottom: 8px;
}

.favorite-group-header {
  padding: 6px 8px;
  background: #2a2a2a;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
  user-select: none;
}

.favorite-group-header:hover {
  background: #333;
}

.group-arrow {
  font-size: 10px;
  color: #777;
  transition: transform 0.2s;
  display: inline-block;
}

.group-arrow.collapsed {
  transform: rotate(-90deg);
}

.group-title {
  font-size: 12px;
  font-weight: 600;
  color: #bbb;
}

.group-count {
  font-size: 11px;
  color: #666;
}

.favorite-group-content {
  padding-left: 2px;
}

.favorite-item {
  padding: 8px 10px;
  margin-bottom: 4px;
  background: #252525;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.favorite-item:hover {
  background: #333;
}

.favorite-code {
  color: #2196f3;
  font-weight: 600;
  font-size: 14px;
  font-family: 'Courier New', monospace;
}

.favorite-name {
  color: #999;
  font-size: 12px;
}

.favorites-empty {
  padding: 20px;
  text-align: center;
  color: #666;
  font-size: 14px;
}

.main-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: visible;
}

.toolbar {
  padding: 2px 8px;
  background: #252525;
  border-bottom: 1px solid #333;
  display: block;
  overflow: visible;
  position: relative;
  z-index: 9999;
  margin-bottom: 2px;
}

.toolbar-scroll {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
  overflow: visible;
  position: relative;
  z-index: 1;
}

.search-section {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-shrink: 0;
}

.search-input-wrapper {
  position: relative;
  z-index: 2;
}

.stock-input {
  padding: 3px 6px;
  background: #1a1a1a;
  border: 1px solid #444;
  border-radius: 4px;
  color: #e0e0e0;
  font-size: 11px;
  width: 130px;
  outline: none;
  transition: border-color 0.3s;
}

.stock-input:focus {
  border-color: #2196f3;
}

.suggestions-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  min-width: 260px;
  margin-top: 4px;
  background: #252525;
  border: 1px solid #444;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
  z-index: 10000;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}

.suggestion-item {
  padding: 10px 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: background 0.2s;
  border-bottom: 1px solid #333;
}

.suggestion-item:last-child {
  border-bottom: none;
}

.suggestion-item:hover,
.suggestion-item.highlighted {
  background: #333;
  border-left: 3px solid #2196f3;
  padding-left: 12px;
}

.suggestion-code {
  color: #2196f3;
  font-weight: 500;
  font-family: 'Courier New', monospace;
}

.suggestion-name {
  color: #e0e0e0;
  font-size: 13px;
}

.search-btn {
  padding: 3px 8px;
  background: #2196f3;
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  font-size: 11px;
  transition: background 0.3s;
}

.search-btn:hover {
  background: #1976d2;
}

.fetch-latest-wrapper {
  display: flex;
  align-items: center;
  margin-left: 12px;
  white-space: nowrap;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #999;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
}

.checkbox-label.disabled-label {
  cursor: not-allowed;
  opacity: 0.6;
}

.checkbox-label.disabled-label input {
  cursor: not-allowed;
}

.checkbox-label input {
  cursor: pointer;
}

.period-section {
  display: flex;
  gap: 5px;
  flex-shrink: 0;
}

.period-btn {
  padding: 2px 6px;
  background: #333;
  border: 1px solid #444;
  border-radius: 4px;
  color: #999;
  cursor: pointer;
  font-size: 10px;
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

.zoom-section {
  display: flex;
  gap: 5px;
  flex-shrink: 0;
}

.zoom-btn {
  padding: 2px 5px;
  background: #2a2a2a;
  border: 1px solid #444;
  border-radius: 4px;
  color: #999;
  cursor: pointer;
  font-size: 10px;
  transition: all 0.3s;
}

.zoom-btn:hover {
  background: #333;
  color: #e0e0e0;
  border-color: #666;
}

.info-section {
  display: flex;
  gap: 4px;
  margin-left: auto;
  font-size: 9px;
  flex-wrap: nowrap;
  align-items: center;
  flex-shrink: 0;
}

.info-block {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 4px;
  min-width: auto;
  white-space: nowrap;
}

.info-label {
  color: #777;
  font-size: 9px;
}

.info-value {
  color: #e0e0e0;
  font-weight: 600;
  line-height: 1;
  font-size: 10px;
}

.info-value.code {
  color: #2196f3;
}

.info-value.code.clickable {
  cursor: pointer;
  text-decoration: underline;
  text-decoration-color: rgba(33, 150, 243, 0.5);
  transition: all 0.2s;
}

.info-value.code.clickable:hover {
  color: #42a5f5;
  text-decoration-color: #42a5f5;
}

.favorite-heart {
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 2px;
  transition: transform 0.2s;
  margin-right: 4px;
}

.favorite-heart:hover {
  transform: scale(1.1);
}

.favorite-heart svg {
  transition: all 0.2s;
}

.chart-container {
  flex: 1;
  position: relative;
  overflow: hidden;
  z-index: 0;
}

.chart {
  width: 100%;
  height: 100%;
  position: relative;
  z-index: 0;
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

/* 交易策略侧边栏样式 */
.strategy-sidebar {
  width: 280px;
  background: #1a1a1a;
  border-left: 1px solid #333;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  flex-shrink: 0;
}

.strategy-header {
  padding: 16px;
  border-bottom: 1px solid #333;
}

.strategy-header h3 {
  margin: 0;
  color: #e0e0e0;
  font-size: 16px;
}

.strategy-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.strategy-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-title {
  color: #2196f3;
  font-size: 14px;
  font-weight: 600;
  border-left: 3px solid #2196f3;
  padding-left: 8px;
}

.config-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.config-item label {
  color: #999;
  font-size: 12px;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 8px;
}

.date-input {
  flex: 1;
  background: #252525;
  border: 1px solid #444;
  border-radius: 4px;
  padding: 6px 8px;
  color: #e0e0e0;
  font-size: 12px;
  outline: none;
}

.date-range span {
  color: #666;
  font-size: 12px;
}

.strategy-option {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px;
  background: #252525;
  border-radius: 4px;
}

.radio-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #e0e0e0;
  font-size: 13px;
  cursor: pointer;
}

.strategy-desc {
  color: #777;
  font-size: 11px;
  line-height: 1.5;
  padding: 8px;
  background: #1a1a1a;
  border-radius: 4px;
}

.evaluation-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}

.eval-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #252525;
  border-radius: 4px;
}

.eval-label {
  color: #999;
  font-size: 12px;
}

.eval-value {
  font-weight: 600;
  font-size: 13px;
}

.profit-positive {
  color: #ef5350;
}

.profit-negative {
  color: #26a69a;
}

.strategy-actions {
  margin-top: auto;
  padding-top: 16px;
}

.run-strategy-btn {
  width: 100%;
  padding: 10px;
  background: #2196f3;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  transition: background 0.2s;
}

.run-strategy-btn:hover:not(:disabled) {
  background: #1976d2;
}

.run-strategy-btn:disabled {
  background: #333;
  color: #666;
  cursor: not-allowed;
}

/* 策略日志窗口样式 */
.strategy-log-window {
  height: 75px;
  background: #1a1a1a;
  border-top: 1px solid #333;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  resize: vertical;
  overflow: auto;
  min-height: 60px;
  max-height: 300px;
}

.log-header {
  padding: 8px 16px;
  background: #252525;
  border-bottom: 1px solid #333;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-header span {
  color: #2196f3;
  font-size: 12px;
  font-weight: 600;
}

.clear-log-btn {
  background: none;
  border: 1px solid #444;
  color: #999;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 3px;
  cursor: pointer;
}

.clear-log-btn:hover {
  background: #333;
  color: #e0e0e0;
}

.log-content {
  flex: 1;
  overflow-y: auto;
  padding: 8px 16px;
  font-family: 'Courier New', monospace;
  font-size: 12px;
}

.log-item {
  margin-bottom: 4px;
  display: flex;
  gap: 8px;
}

.log-time {
  color: #555;
  flex-shrink: 0;
}

.log-message {
  color: #ccc;
  word-break: break-all;
}

.log-message.buy {
  color: #ef5350;
  font-weight: 600;
}

.log-message.sell {
  color: #26a69a;
  font-weight: 600;
}

.log-message.info {
  color: #999;
}
</style>
