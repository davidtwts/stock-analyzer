// Use relative path for deployment, or localhost for development
const API_BASE = window.location.hostname === 'localhost' ? 'http://localhost:8000' : '';

const { createApp, ref, computed, onMounted, onUnmounted, watch } = Vue;

createApp({
    setup() {
        const stocks = ref([]);
        const selectedStock = ref(null);
        const loading = ref(true);
        const lastUpdate = ref(null);
        const nextUpdate = ref(null);
        const marketStatus = ref('closed');

        let chart = null;
        let candleSeries = null;
        let maLines = {};
        let refreshInterval = null;

        const marketStatusClass = computed(() => {
            return marketStatus.value === 'open'
                ? 'bg-green-600'
                : 'bg-gray-600';
        });

        const formatTime = (isoString) => {
            if (!isoString) return '--:--';
            const date = new Date(isoString);
            return date.toLocaleTimeString('zh-TW', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        };

        const formatVolume = (volume) => {
            if (volume >= 100000000) {
                return (volume / 100000000).toFixed(1) + '億';
            } else if (volume >= 10000) {
                return (volume / 10000).toFixed(0) + '萬';
            } else if (volume >= 1000) {
                return (volume / 1000).toFixed(1) + 'k';
            }
            return volume.toString();
        };

        const fetchStocks = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/stocks`);
                const data = await res.json();
                stocks.value = data.stocks;
                lastUpdate.value = data.updated_at;
                marketStatus.value = data.market_status;
            } catch (err) {
                console.error('Failed to fetch stocks:', err);
            } finally {
                loading.value = false;
            }
        };

        const fetchStatus = async () => {
            try {
                const res = await fetch(`${API_BASE}/api/status`);
                const data = await res.json();
                nextUpdate.value = data.next_update;
            } catch (err) {
                console.error('Failed to fetch status:', err);
            }
        };

        const refresh = async () => {
            loading.value = true;
            try {
                await fetch(`${API_BASE}/api/refresh`);
                await fetchStocks();
                await fetchStatus();
            } catch (err) {
                console.error('Failed to refresh:', err);
            } finally {
                loading.value = false;
            }
        };

        const selectStock = async (stock) => {
            selectedStock.value = stock;
            await loadChart(stock.symbol);
        };

        const loadChart = async (symbol) => {
            try {
                const res = await fetch(`${API_BASE}/api/chart/${symbol}`);
                const data = await res.json();
                renderChart(data);
            } catch (err) {
                console.error('Failed to load chart:', err);
            }
        };

        const renderChart = (data) => {
            const container = document.getElementById('chart');
            if (!container) return;

            container.innerHTML = '';

            chart = LightweightCharts.createChart(container, {
                width: container.clientWidth,
                height: container.clientHeight,
                layout: {
                    background: { color: '#1f2937' },
                    textColor: '#9ca3af',
                },
                grid: {
                    vertLines: { color: '#374151' },
                    horzLines: { color: '#374151' },
                },
                crosshair: {
                    mode: LightweightCharts.CrosshairMode.Normal,
                },
                rightPriceScale: {
                    borderColor: '#374151',
                },
                timeScale: {
                    borderColor: '#374151',
                    timeVisible: true,
                },
            });

            candleSeries = chart.addCandlestickSeries({
                upColor: '#ef4444',
                downColor: '#22c55e',
                borderUpColor: '#ef4444',
                borderDownColor: '#22c55e',
                wickUpColor: '#ef4444',
                wickDownColor: '#22c55e',
            });

            candleSeries.setData(data.candles);

            const maColors = {
                ma5: '#fbbf24',
                ma10: '#60a5fa',
                ma20: '#a78bfa',
                ma60: '#f472b6',
            };

            Object.keys(maColors).forEach(maKey => {
                if (data.ma_lines[maKey]) {
                    const lineSeries = chart.addLineSeries({
                        color: maColors[maKey],
                        lineWidth: 1,
                    });

                    const maData = data.candles.map((candle, i) => ({
                        time: candle.time,
                        value: data.ma_lines[maKey][i],
                    })).filter(d => d.value !== null);

                    lineSeries.setData(maData);
                    maLines[maKey] = lineSeries;
                }
            });

            chart.timeScale().fitContent();
        };

        const handleResize = () => {
            if (chart) {
                const container = document.getElementById('chart');
                if (container) {
                    chart.applyOptions({
                        width: container.clientWidth,
                        height: container.clientHeight,
                    });
                }
            }
        };

        onMounted(async () => {
            await fetchStocks();
            await fetchStatus();
            refreshInterval = setInterval(async () => {
                await fetchStocks();
                await fetchStatus();
            }, 300000);
            window.addEventListener('resize', handleResize);
        });

        onUnmounted(() => {
            if (refreshInterval) {
                clearInterval(refreshInterval);
            }
            window.removeEventListener('resize', handleResize);
        });

        return {
            stocks,
            selectedStock,
            loading,
            lastUpdate,
            nextUpdate,
            marketStatus,
            marketStatusClass,
            formatTime,
            formatVolume,
            refresh,
            selectStock,
        };
    },
}).mount('#app');
