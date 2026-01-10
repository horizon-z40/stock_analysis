# 股票策略回测系统

一个基于Web的股票策略回测系统，支持分钟级股票数据查询和可视化展示。

## 功能特点

- 📊 股票价格走势K线图展示（类似富途界面）
- 📈 成交量柱状图展示
- 🔍 支持按股票代码查询（如：000001.SZ 或 000001）
- 📅 支持按年份筛选数据
- ⏰ 支持多种时间周期展示：分钟、日、周、月
- 📱 响应式设计，支持移动端访问
- ⚡ 实时数据加载和图表交互
- 📉 MA5/MA10/MA20移动平均线

## 数据格式

数据保存在 `data` 目录下：
- 每年一个目录，如 `2025`
- 每个文件为一只股票的分钟级数据，文件名格式：`000001.SZ.csv`
- CSV文件包含以下列：`trade_time`, `open`, `high`, `low`, `close`, `vol`, `amount`

## 安装和运行

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动服务

默认端口5001：
```bash
python3 app.py
```

指定端口（例如使用8080端口）：
```bash
python3 app.py 8080
```

或使用环境变量：
```bash
PORT=8080 python3 app.py
```

### 3. 访问系统

打开浏览器访问：http://localhost:5001

（如果使用了自定义端口，请访问对应的端口）

## 使用方法

1. 在输入框中输入股票代码（如：`000001.SZ` 或 `000001`）
2. 可选择年份（默认使用最新年份）
3. 选择时间周期：分钟、日、周、月（默认分钟）
4. 按回车或点击"查询"按钮
5. 系统将显示该股票的价格走势K线图和成交量图

### 时间周期说明

- **分钟**：显示原始分钟级数据
- **日**：将分钟数据聚合为日K线（开盘、最高、最低、收盘）
- **周**：将分钟数据聚合为周K线
- **月**：将分钟数据聚合为月K线

## API接口

### 获取股票数据
```
GET /api/stock/<stock_code>?year=2025&period=day
```

参数说明：
- `stock_code`: 股票代码（必需）
- `year`: 年份（可选，默认最新年份）
- `period`: 时间周期（可选，默认"minute"）
  - `minute`: 分钟级数据
  - `day`: 日级数据
  - `week`: 周级数据
  - `month`: 月级数据

### 获取可用年份列表
```
GET /api/years
```

### 获取指定年份的所有股票代码
```
GET /api/stocks/<year>
```

## 技术栈

- 后端：Flask (Python)
- 前端：Vue 3 + HTML + CSS
- 图表库：ECharts 5.4.3
- 数据处理：Pandas

## 项目结构

```
股票回测/
├── app.py                 # Flask后端应用
├── fetch_stock_list.py    # 获取A股股票代码列表脚本
├── requirements.txt       # Python依赖
├── README.md             # 项目说明
├── data/                 # 股票数据目录
│   ├── 2024/
│   └── 2025/
├── templates/            # HTML模板
│   └── index.html
└── static/               # 静态资源
    ├── css/
    │   └── style.css
    └── js/
        └── main.js
```

## 获取股票代码列表

项目提供了一个脚本用于获取A股所有公司的股票代码和公司名称对应关系：

```bash
python3 fetch_stock_list.py
```

脚本会生成两个文件：
- `stock_list.json`: JSON格式，包含完整的股票信息
- `stock_list.csv`: CSV格式，便于查看和编辑

### 脚本功能

- 支持两种数据源：
  - **akshare**（推荐）：免费Python库，数据稳定
  - **东方财富API**：备用数据源
- 自动添加市场后缀（.SH 或 .SZ）
- 自动去重
- 支持自定义输出文件名

### 使用示例

```bash
# 使用默认文件名
python3 fetch_stock_list.py

# 指定输出文件名
python3 fetch_stock_list.py my_stock_list.json
```

### 输出格式

**JSON格式** (`stock_list.json`):
```json
{
  "update_time": "2025-01-XX XX:XX:XX",
  "total": 5000,
  "stocks": [
    {"code": "000001.SZ", "name": "平安银行"},
    {"code": "000002.SZ", "name": "万科A"},
    ...
  ]
}
```

**CSV格式** (`stock_list.csv`):
```csv
code,name
000001.SZ,平安银行
000002.SZ,万科A
...
```

## 注意事项

- 确保 `data` 目录下有对应年份的数据文件
- 股票代码格式支持：`000001.SZ`、`000001.SH` 或 `000001`（自动识别）
- 数据文件必须是CSV格式，包含必需的7列数据
- 获取股票列表需要网络连接，建议定期更新股票列表
