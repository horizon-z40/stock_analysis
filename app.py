from flask import Flask, render_template, jsonify, request
import os
import pandas as pd
from datetime import datetime
import glob
import sys
import requests

app = Flask(__name__)

# 数据目录
DATA_DIR = 'stock'
# 股票列表文件
STOCK_LIST_FILE = 'stock_list.csv'

def aggregate_data(df, period='minute'):
    """
    将分钟级数据聚合为不同周期
    period: 'minute', 'day', 'week', 'month'
    """
    if period == 'minute':
        return df.copy()
    
    # 设置trade_time为索引
    df_indexed = df.set_index('trade_time')
    
    if period == 'day':
        # 按日聚合
        aggregated = df_indexed.resample('D').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'vol': 'sum',
            'amount': 'sum'
        })
    elif period == 'week':
        # 按周聚合（周一到周日）
        aggregated = df_indexed.resample('W').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'vol': 'sum',
            'amount': 'sum'
        })
    elif period == 'month':
        # 按月聚合
        aggregated = df_indexed.resample('M').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'vol': 'sum',
            'amount': 'sum'
        })
    else:
        return df.copy()
    
    # 重置索引，将trade_time变回列
    aggregated = aggregated.reset_index()
    # 删除空值行（可能因为非交易日产生）
    aggregated = aggregated.dropna()
    
    return aggregated

def find_stock_file(stock_code, year=None):
    """
    查找股票数据文件
    stock_code: 股票代码，如 "000001.SZ" 或 "000001"
    year: 年份，如果为None则查找最新年份
    """
    # 标准化股票代码格式
    if '.' not in stock_code:
        # 尝试添加.SZ或.SH后缀
        filename_sz = f"{stock_code}.SZ.csv"
        filename_sh = f"{stock_code}.SH.csv"
    else:
        filename_sz = f"{stock_code}.csv"
        filename_sh = None
    
    # 如果指定了年份，只在该年份目录查找
    if year:
        years = [str(year)]
    else:
        # 查找所有年份目录，按降序排列
        years = sorted([d for d in os.listdir(DATA_DIR) 
                       if os.path.isdir(os.path.join(DATA_DIR, d)) and d.isdigit()], 
                      reverse=True)
    
    # 遍历年份目录查找文件
    for y in years:
        year_dir = os.path.join(DATA_DIR, y)
        if filename_sh:
            file_path = os.path.join(year_dir, filename_sh)
            if os.path.exists(file_path):
                return file_path, y
        
        file_path = os.path.join(year_dir, filename_sz)
        if os.path.exists(file_path):
            return file_path, y
    
    return None, None

def find_all_stock_files(stock_code, year=None):
    """
    查找所有年份的股票数据文件
    stock_code: 股票代码，如 "000001.SZ" 或 "000001"
    year: 年份，如果为None则查找所有年份
    返回: [(文件路径, 年份), ...] 列表
    """
    # 标准化股票代码格式
    if '.' not in stock_code:
        filename_sz = f"{stock_code}.SZ.csv"
        filename_sh = f"{stock_code}.SH.csv"
    else:
        filename_sz = f"{stock_code}.csv"
        filename_sh = None
    
    files = []
    
    # 确定要查找的年份列表
    if year:
        years = [str(year)]
    else:
        # 查找所有年份目录，按升序排列（从早到晚）
        years = sorted([d for d in os.listdir(DATA_DIR) 
                       if os.path.isdir(os.path.join(DATA_DIR, d)) and d.isdigit()])
    
    # 遍历所有年份目录查找文件
    for y in years:
        year_dir = os.path.join(DATA_DIR, y)
        if filename_sh:
            file_path = os.path.join(year_dir, filename_sh)
            if os.path.exists(file_path):
                files.append((file_path, y))
        
        file_path = os.path.join(year_dir, filename_sz)
        if os.path.exists(file_path):
            files.append((file_path, y))
    
    return files


def normalize_stock_code_with_market(stock_code):
    """
    标准化股票代码，返回 eastmoney 所需的 secid
    secid 规则：
      - 深市: 0.代码
      - 沪市: 1.代码
    """
    code = stock_code.upper()
    if '.' in code:
        base, suffix = code.split('.', 1)
    else:
        base, suffix = code, ''

    if suffix == 'SZ':
        market_flag = '0'
    elif suffix == 'SH':
        market_flag = '1'
    else:
        # 未提供后缀时，根据首位数字简单判断
        # 沪市一般以6开头，其余视为深市
        market_flag = '1' if base.startswith('6') else '0'

    return f"{market_flag}.{base}"

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/stock/<stock_code>')
def get_stock_data(stock_code):
    """
    获取股票数据API
    参数:
    - stock_code: 股票代码，如 "000001.SZ" 或 "000001"
    - year: 可选，年份，如 "2025"
    - period: 可选，时间周期，如 "minute", "day", "week", "month"，默认为 "minute"
    """
    year = request.args.get('year', None)
    if year:
        try:
            year = int(year)
        except:
            year = None
    
    period = request.args.get('period', 'minute')
    if period not in ['minute', 'day', 'week', 'month']:
        period = 'minute'
    
    # 查找所有年份的文件
    files = find_all_stock_files(stock_code, year)
    
    if not files:
        return jsonify({
            'success': False,
            'error': f'未找到股票代码 {stock_code} 的数据'
        }), 404
    
    try:
        # 读取所有文件并合并数据
        dfs = []
        years_found = []
        
        for file_path, file_year in files:
            df_year = pd.read_csv(file_path)
            dfs.append(df_year)
            years_found.append(file_year)
        
        # 合并所有数据
        df = pd.concat(dfs, ignore_index=True)
        
        # 确保trade_time是datetime类型
        df['trade_time'] = pd.to_datetime(df['trade_time'])
        
        # 按时间排序
        df = df.sort_values('trade_time')
        
        # 去除重复数据（如果有）
        df = df.drop_duplicates(subset=['trade_time'], keep='first')
        
        # 根据周期聚合数据
        df = aggregate_data(df, period)
        
        # 确保trade_time格式化为字符串
        df['trade_time'] = df['trade_time'].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 转换为列表格式，方便前端使用
        data = {
            'success': True,
            'stock_code': stock_code,
            'year': ','.join(sorted(set(years_found))),  # 所有找到的年份
            'period': period,
            'data': df.to_dict('records'),
            'count': len(df)
        }
        
        return jsonify(data)
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'读取数据时出错: {str(e)}'
        }), 500

@app.route('/api/years')
def get_available_years():
    """获取可用的年份列表"""
    years = sorted([d for d in os.listdir(DATA_DIR) 
                   if os.path.isdir(os.path.join(DATA_DIR, d)) and d.isdigit()], 
                  reverse=True)
    return jsonify({
        'success': True,
        'years': years
    })


@app.route('/api/stock_info/<stock_code>')
def get_stock_info(stock_code):
    """
    通过东财接口获取股票基础信息（公司名称、总市值、市盈率、市净率）
    """
    secid = normalize_stock_code_with_market(stock_code)
    url = 'https://push2.eastmoney.com/api/qt/stock/get'
    params = {
        'secid': secid,
        'fields': 'f57,f58,f116,f162,f167'  # f167是市净率(PB)
    }

    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get('data')
        if not data:
            return jsonify({'success': False, 'error': '未获取到基础信息'}), 404

        result = {
            'success': True,
            'stock_code': data.get('f57') or stock_code,
            'name': data.get('f58'),
            'market_cap': data.get('f116'),  # 总市值（元）
            'pe_ttm': data.get('f162'),  # 市盈率(PE)
            'pb': data.get('f167'),  # 市净率(PB)
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取基础信息失败: {str(e)}'}), 500

@app.route('/api/stocks/<year>')
def get_stocks_by_year(year):
    """获取指定年份的所有股票代码列表"""
    year_dir = os.path.join(DATA_DIR, str(year))
    if not os.path.isdir(year_dir):
        return jsonify({
            'success': False,
            'error': f'年份 {year} 不存在'
        }), 404
    
    csv_files = glob.glob(os.path.join(year_dir, '*.csv'))
    stocks = [os.path.basename(f).replace('.csv', '') for f in csv_files]
    stocks.sort()
    
    return jsonify({
        'success': True,
        'year': year,
        'stocks': stocks,
        'count': len(stocks)
    })

@app.route('/api/search_stocks')
def search_stocks():
    """
    搜索股票代码和公司名称
    参数:
    - q: 搜索关键词（股票代码或公司名称）
    - limit: 返回结果数量限制，默认10
    """
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)
    
    if not query:
        return jsonify({
            'success': True,
            'results': [],
            'count': 0
        })
    
    try:
        # 读取股票列表文件
        if not os.path.exists(STOCK_LIST_FILE):
            return jsonify({
                'success': False,
                'error': '股票列表文件不存在'
            }), 404
        
        df = pd.read_csv(STOCK_LIST_FILE)
        
        # 搜索：匹配股票代码或公司名称
        mask = (
            df['code'].str.contains(query, case=False, na=False) |
            df['name'].str.contains(query, case=False, na=False)
        )
        
        results = df[mask].head(limit)
        
        # 转换为列表格式
        stock_list = results.apply(lambda row: {
            'code': row['code'],
            'name': row['name']
        }, axis=1).tolist()
        
        return jsonify({
            'success': True,
            'results': stock_list,
            'count': len(stock_list)
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'搜索失败: {str(e)}'
        }), 500

if __name__ == '__main__':
    # 支持通过环境变量或命令行参数指定端口
    port = 8080  # 默认端口
    if 'PORT' in os.environ:
        port = int(os.environ['PORT'])
    elif len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"警告: 无效的端口号 '{sys.argv[1]}', 使用默认端口 {port}")
    
    print(f"服务器启动在 http://localhost:{port}")
    print(f"请在浏览器中访问: http://localhost:{port}")
    app.run(debug=True, host='0.0.0.0', port=port)

