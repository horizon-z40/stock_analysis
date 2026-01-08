const { createApp, ref, onMounted, nextTick, watch } = Vue;

const app = createApp({
    setup() {
        // 响应式数据
        const stockCode = ref('');
        const selectedYear = ref('');
        const selectedPeriod = ref('minute');
        const years = ref([]);
        const loading = ref(false);
        const error = ref('');
        const stockInfo = ref({
            show: false,
            code: '',
            year: '',
            period: '',
            count: 0
        });
        const stockData = ref([]);
        
        // 图表引用
        const klineChartRef = ref(null);
        const volumeChartRef = ref(null);
        let klineChart = null;
        let volumeChart = null;

        // 周期名称映射
        const periodNames = {
            'minute': '分钟',
            'day': '日',
            'week': '周',
            'month': '月'
        };

        // 加载可用年份
        const loadYears = async () => {
            try {
                const response = await fetch('/api/years');
                const data = await response.json();
                if (data.success) {
                    years.value = data.years;
                }
            } catch (err) {
                console.error('加载年份失败:', err);
            }
        };

        // 初始化图表
        const initCharts = () => {
            nextTick(() => {
                if (klineChartRef.value && !klineChart) {
                    klineChart = echarts.init(klineChartRef.value);
                }
                if (volumeChartRef.value && !volumeChart) {
                    volumeChart = echarts.init(volumeChartRef.value);
                }
            });
        };

        // 查询股票
        const searchStock = async () => {
            if (!stockCode.value.trim()) {
                showError('请输入股票代码');
                return;
            }

            loading.value = true;
            error.value = '';

            try {
                let url = `/api/stock/${encodeURIComponent(stockCode.value.trim())}?period=${selectedPeriod.value}`;
                if (selectedYear.value) {
                    url += `&year=${selectedYear.value}`;
                }

                const response = await fetch(url);
                const data = await response.json();

                loading.value = false;

                if (data.success) {
                    stockData.value = data.data;
                    stockInfo.value = {
                        show: true,
                        code: data.stock_code,
                        year: data.year,
                        period: periodNames[data.period] || data.period,
                        count: data.count
                    };
                    
                    // 等待DOM更新后绘制图表
                    nextTick(() => {
                        drawCharts(data);
                    });
                } else {
                    showError(data.error || '查询失败');
                }
            } catch (err) {
                loading.value = false;
                showError('网络错误: ' + err.message);
                console.error('查询失败:', err);
            }
        };

        // 绘制图表
        const drawCharts = (data) => {
            drawKlineChart(data);
            drawVolumeChart(data);
        };

        // 绘制K线图
        const drawKlineChart = (data) => {
            if (!klineChart) {
                initCharts();
                return;
            }

            const period = data.period;
            const klineData = stockData.value.map(item => [
                item.trade_time,
                parseFloat(item.open),
                parseFloat(item.close),
                parseFloat(item.low),
                parseFloat(item.high)
            ]);

            const option = {
                title: {
                    text: `价格走势图 (${periodNames[period] || period})`,
                    left: 'center',
                    textStyle: {
                        fontSize: 18,
                        fontWeight: 'bold'
                    }
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: {
                        type: 'cross'
                    },
                    formatter: function(params) {
                        const dataIndex = params[0].dataIndex;
                        const item = stockData.value[dataIndex];
                        return `
                            <div style="padding: 8px;">
                                <div><strong>时间:</strong> ${item.trade_time}</div>
                                <div><strong>开盘:</strong> ${item.open}</div>
                                <div><strong>最高:</strong> ${item.high}</div>
                                <div><strong>最低:</strong> ${item.low}</div>
                                <div><strong>收盘:</strong> ${item.close}</div>
                                <div><strong>成交量:</strong> ${formatNumber(item.vol)}</div>
                                <div><strong>成交额:</strong> ${formatNumber(item.amount)}</div>
                            </div>
                        `;
                    }
                },
                grid: {
                    left: '10%',
                    right: '10%',
                    bottom: '15%',
                    top: '15%'
                },
                xAxis: {
                    type: 'category',
                    data: stockData.value.map(item => item.trade_time),
                    scale: true,
                    boundaryGap: false,
                    axisLine: { onZero: false },
                    splitLine: { show: false },
                    min: 'dataMin',
                    max: 'dataMax',
                    axisLabel: {
                        formatter: function(value) {
                            if (period === 'minute') {
                                return value.split(' ')[1] || value;
                            } else {
                                return value.split(' ')[0];
                            }
                        },
                        rotate: period === 'minute' ? 0 : 45
                    }
                },
                yAxis: {
                    scale: true,
                    splitArea: {
                        show: true
                    }
                },
                dataZoom: [
                    {
                        type: 'inside',
                        start: 80,
                        end: 100
                    },
                    {
                        show: true,
                        type: 'slider',
                        top: '90%',
                        start: 80,
                        end: 100
                    }
                ],
                series: [
                    {
                        name: 'K线',
                        type: 'candlestick',
                        data: klineData,
                        itemStyle: {
                            color: '#26a69a',
                            color0: '#ef5350',
                            borderColor: '#26a69a',
                            borderColor0: '#ef5350'
                        },
                        markPoint: {
                            data: [
                                {
                                    name: '最高值',
                                    type: 'max',
                                    valueDim: 'highest'
                                },
                                {
                                    name: '最低值',
                                    type: 'min',
                                    valueDim: 'lowest'
                                }
                            ]
                        }
                    },
                    {
                        name: 'MA5',
                        type: 'line',
                        data: calculateMA(5, stockData.value),
                        smooth: true,
                        lineStyle: {
                            opacity: 0.5
                        }
                    },
                    {
                        name: 'MA10',
                        type: 'line',
                        data: calculateMA(10, stockData.value),
                        smooth: true,
                        lineStyle: {
                            opacity: 0.5
                        }
                    },
                    {
                        name: 'MA20',
                        type: 'line',
                        data: calculateMA(20, stockData.value),
                        smooth: true,
                        lineStyle: {
                            opacity: 0.5
                        }
                    }
                ]
            };

            klineChart.setOption(option);
            klineChart.resize();
        };

        // 绘制成交量图
        const drawVolumeChart = (data) => {
            if (!volumeChart) {
                initCharts();
                return;
            }

            const period = data.period;
            const volumeData = stockData.value.map(item => parseFloat(item.vol));

            const option = {
                title: {
                    text: `成交量 (${periodNames[period] || period})`,
                    left: 'center',
                    textStyle: {
                        fontSize: 18,
                        fontWeight: 'bold'
                    }
                },
                tooltip: {
                    trigger: 'axis',
                    axisPointer: {
                        type: 'cross'
                    },
                    formatter: function(params) {
                        const dataIndex = params[0].dataIndex;
                        const item = stockData.value[dataIndex];
                        return `
                            <div style="padding: 8px;">
                                <div><strong>时间:</strong> ${item.trade_time}</div>
                                <div><strong>成交量:</strong> ${formatNumber(item.vol)}</div>
                                <div><strong>成交额:</strong> ${formatNumber(item.amount)}</div>
                            </div>
                        `;
                    }
                },
                grid: {
                    left: '10%',
                    right: '10%',
                    bottom: '15%',
                    top: '15%'
                },
                xAxis: {
                    type: 'category',
                    data: stockData.value.map(item => item.trade_time),
                    scale: true,
                    boundaryGap: false,
                    axisLine: { onZero: false },
                    splitLine: { show: false },
                    min: 'dataMin',
                    max: 'dataMax',
                    axisLabel: {
                        formatter: function(value) {
                            if (period === 'minute') {
                                return value.split(' ')[1] || value;
                            } else {
                                return value.split(' ')[0];
                            }
                        },
                        rotate: period === 'minute' ? 0 : 45
                    }
                },
                yAxis: {
                    scale: true,
                    splitArea: {
                        show: true
                    }
                },
                dataZoom: [
                    {
                        type: 'inside',
                        start: 80,
                        end: 100
                    },
                    {
                        show: true,
                        type: 'slider',
                        top: '90%',
                        start: 80,
                        end: 100
                    }
                ],
                series: [
                    {
                        name: '成交量',
                        type: 'bar',
                        data: volumeData,
                        itemStyle: {
                            color: function(params) {
                                const dataIndex = params.dataIndex;
                                if (dataIndex === 0) return '#26a69a';
                                const current = parseFloat(stockData.value[dataIndex].close);
                                const prev = parseFloat(stockData.value[dataIndex - 1].close);
                                return current >= prev ? '#26a69a' : '#ef5350';
                            }
                        }
                    }
                ]
            };

            volumeChart.setOption(option);
            volumeChart.resize();
        };

        // 计算移动平均线
        const calculateMA = (dayCount, data) => {
            const result = [];
            for (let i = 0; i < data.length; i++) {
                if (i < dayCount - 1) {
                    result.push('-');
                } else {
                    let sum = 0;
                    for (let j = 0; j < dayCount; j++) {
                        sum += parseFloat(data[i - j].close);
                    }
                    result.push((sum / dayCount).toFixed(2));
                }
            }
            return result;
        };

        // 格式化数字
        const formatNumber = (num) => {
            const n = parseFloat(num);
            if (n >= 100000000) {
                return (n / 100000000).toFixed(2) + '亿';
            } else if (n >= 10000) {
                return (n / 10000).toFixed(2) + '万';
            }
            return n.toLocaleString();
        };

        // 显示错误
        const showError = (message) => {
            error.value = message;
            setTimeout(() => {
                error.value = '';
            }, 5000);
        };

        // 窗口大小改变时调整图表
        const handleResize = () => {
            if (klineChart) {
                klineChart.resize();
            }
            if (volumeChart) {
                volumeChart.resize();
            }
        };

        // 监听周期变化，重新查询
        watch(selectedPeriod, () => {
            if (stockCode.value.trim()) {
                searchStock();
            }
        });

        // 组件挂载时初始化
        onMounted(() => {
            loadYears();
            initCharts();
            window.addEventListener('resize', handleResize);
        });

        return {
            stockCode,
            selectedYear,
            selectedPeriod,
            years,
            loading,
            error,
            stockInfo,
            klineChartRef,
            volumeChartRef,
            searchStock,
            initCharts
        };
    }
});

app.mount('#app');
