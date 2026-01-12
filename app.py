from flask import Flask, render_template, jsonify, request
import os
import pandas as pd
from datetime import datetime
import glob
import sys
import requests
import json
from pypinyin import lazy_pinyin, Style
try:
    import akshare as ak
except ImportError:
    ak = None

app = Flask(__name__)

# 数据目录
DATA_DIR = 'data'
# 远程数据缓存目录
REMOTE_CACHE_DIR = os.path.join(DATA_DIR, 'remote_cache')
# 远程数据拉取记录文件
REMOTE_LOG_FILE = os.path.join(REMOTE_CACHE_DIR, 'fetch_log.json')
# 股票列表文件
STOCK_LIST_FILE = 'stock_list.csv'
# 自选股票文件
FAVORITE_STOCKS_FILE = 'favorite_stocks.json'

def aggregate_data(df, period='day'):
    """
    将日级数据聚合为不同周期
    period: 'day', 'week', 'month'
    """
    if period == 'day':
        return df.copy()
    
    # 设置trade_time为索引
    df_indexed = df.set_index('trade_time')
    
    if period == 'week':
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
        years = [f"{year}_by_day"]
    else:
        # 查找所有日级年份目录，按降序排列
        if not os.path.exists(DATA_DIR):
            years = []
        else:
            years = sorted([d for d in os.listdir(DATA_DIR) 
                           if os.path.isdir(os.path.join(DATA_DIR, d)) and d.endswith('_by_day')], 
                          reverse=True)
    
    # 遍历年份目录查找文件
    for y_dir in years:
        year_dir = os.path.join(DATA_DIR, y_dir)
        y = y_dir.replace('_by_day', '') # 提取纯年份
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
        years = [f"{year}_by_day"]
    else:
        # 查找所有日级年份目录，按升序排列（从早到晚）
        if not os.path.exists(DATA_DIR):
            years = []
        else:
            years = sorted([d for d in os.listdir(DATA_DIR) 
                           if os.path.isdir(os.path.join(DATA_DIR, d)) and d.endswith('_by_day')])
    
    # 遍历所有年份目录查找文件
    for y_dir in years:
        year_dir = os.path.join(DATA_DIR, y_dir)
        y = y_dir.replace('_by_day', '') # 提取纯年份
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

def fetch_latest_stock_data_from_ak(stock_code, start_date="20250329", end_date=None):
    """
    使用 akshare 抓取特定的股票数据
    """
    if ak is None:
        print("未安装 akshare，无法抓取最新数据")
        return None
        
    # 提取6位代码
    code = stock_code.split('.')[0]
    try:
        # 获取历史数据
        # start_date 格式 YYYYMMDD
        formatted_start = start_date.replace('-', '')
        
        # 如果未指定结束日期，使用今天日期
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        formatted_end = end_date.replace('-', '')
        
        print(f"正在从 akshare 抓取 {code} 的数据，从 {formatted_start} 到 {formatted_end}")
        
        # period="daily", adjust="" (不复权，与本地数据一致)
        df = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=formatted_start, end_date=formatted_end, adjust="")
        
        if df is None or df.empty:
            print(f"未获取到 {code} 在该时间段的数据")
            return None
        
        # 重命名列以匹配本地格式
        # akshare 返回列名: ['日期', '开盘', '收盘', '最高', '最低', '成交量', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率']
        # 本地格式: trade_time,open,close,high,low,vol,amount
        df = df.rename(columns={
            '日期': 'trade_time',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'vol',
            '成交额': 'amount'
        })
        
        # 确保列存在并按顺序排列
        df['trade_time'] = pd.to_datetime(df['trade_time'])
        
        # 过滤掉不需要的列
        cols = ['trade_time', 'open', 'close', 'high', 'low', 'vol', 'amount']
        df = df[cols]
        
        return df
    except Exception as e:
        print(f"抓取最新数据失败: {e}")
        import traceback
        traceback.print_exc()
        return None

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
    - period: 可选，时间周期，如 "day", "week", "month"，默认为 "day"
    - fetch_latest: 可选，是否抓取最新数据 (2025-03-29之后)
    """
    year = request.args.get('year', None)
    if year:
        try:
            year = int(year)
        except:
            year = None
    
    period = request.args.get('period', 'day')
    if period not in ['day', 'week', 'month']:
        period = 'day'
    
    fill_missing_data = request.args.get('fill_missing_data', 'false').lower() == 'true'
    remote_data = request.args.get('remote_data', 'false').lower() == 'true'
    
    # 查找所有年份的文件
    files = [] if remote_data else find_all_stock_files(stock_code, year)
    
    if not files and not fill_missing_data and not remote_data:
        return jsonify({
            'success': False,
            'error': f'未找到股票代码 {stock_code} 的数据'
        }), 404
    
    try:
        # 读取所有文件并合并数据
        dfs = []
        years_found = []
        
        if not remote_data:
            for file_path, file_year in files:
                df_year = pd.read_csv(file_path)
                dfs.append(df_year)
                years_found.append(file_year)
        else:
            # 远程数据缓存逻辑
            today = datetime.now().strftime('%Y-%m-%d')
            cache_file = os.path.join(REMOTE_CACHE_DIR, f"{stock_code}_remote.csv")
            
            # 检查是否有缓存记录
            fetch_log = {}
            if os.path.exists(REMOTE_LOG_FILE):
                try:
                    with open(REMOTE_LOG_FILE, 'r') as f:
                        fetch_log = json.load(f)
                except:
                    fetch_log = {}
            
            # 判断是否需要重新拉取
            last_fetch_date = fetch_log.get(stock_code)
            if last_fetch_date == today and os.path.exists(cache_file):
                print(f"远程数据日期未变 ({today})，直接从本地缓存读取: {stock_code}")
                df_remote = pd.read_csv(cache_file)
                dfs.append(df_remote)
                years_found.append("2018_now_remote_cached")
            else:
                print(f"尝试从远程抓取 2018 至今的数据: {stock_code}")
                # 2018-01-01 至今
                fetch_end_date = datetime.now().strftime('%Y%m%d')
                df_remote = fetch_latest_stock_data_from_ak(stock_code, start_date="20180101", end_date=fetch_end_date)
                if df_remote is not None and not df_remote.empty:
                    print(f"成功抓取远程数据，共 {len(df_remote)} 条，保存至缓存")
                    # 创建目录
                    os.makedirs(REMOTE_CACHE_DIR, exist_ok=True)
                    # 保存到本地缓存
                    df_remote.to_csv(cache_file, index=False)
                    # 更新拉取日志
                    fetch_log[stock_code] = today
                    with open(REMOTE_LOG_FILE, 'w') as f:
                        json.dump(fetch_log, f)
                    
                    dfs.append(df_remote)
                    years_found.append("2018_now_remote")
                else:
                    print(f"抓取远程数据失败或为空: {stock_code}")
                    # 如果抓取失败但本地有旧缓存，则先用旧缓存
                    if os.path.exists(cache_file):
                        print(f"远程抓取失败，回退使用旧缓存数据: {stock_code}")
                        df_remote = pd.read_csv(cache_file)
                        dfs.append(df_remote)
                        years_found.append("2018_now_remote_cached_fallback")
        
        # 如果需要补齐缺失数据
        if fill_missing_data and not remote_data:
            # 1. 尝试补齐 2024 年数据 (2024-06-29至2024-12-31)
            print(f"尝试补齐 2024 年数据: {stock_code}")
            df_2024 = fetch_latest_stock_data_from_ak(stock_code, start_date="20240629", end_date="20241231")
            if df_2024 is not None and not df_2024.empty:
                print(f"成功补齐 2024 年数据，共 {len(df_2024)} 条")
                dfs.append(df_2024)
                years_found.append("2024_fill")
            
            # 2. 尝试抓取 2025 年至今的数据
            print(f"尝试抓取最新数据: {stock_code}")
            df_latest = fetch_latest_stock_data_from_ak(stock_code, "2025-03-29")
            if df_latest is not None and not df_latest.empty:
                print(f"成功抓取到最新数据，共 {len(df_latest)} 条，最新日期: {df_latest['trade_time'].max()}")
                dfs.append(df_latest)
                years_found.append("2025+")
        
        if not dfs:
            return jsonify({
                'success': False,
                'error': f'未找到股票代码 {stock_code} 的数据'
            }), 404
            
        # 合并所有数据
        df = pd.concat(dfs, ignore_index=True)
        
        # 确保trade_time是datetime类型
        df['trade_time'] = pd.to_datetime(df['trade_time'])
        
        # 按时间排序
        df = df.sort_values('trade_time')
        
        # 去重（防止补齐数据与本地数据重叠）
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
        import traceback
        traceback.print_exc()
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
        'fields': 'f43,f57,f58,f116,f162,f163,f167'  # f43最新价, f162市盈率(TTM), f163市盈率(静), f167是市净率(PB)
    }

    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get('data')
        if not data:
            return jsonify({'success': False, 'error': '未获取到基础信息'}), 404

        # 东财接口返回的价格、市盈率和市净率通常需要除以100
        def safe_div_100(val):
            if val is None or val == '-' or val == '':
                return None
            try:
                # 尝试转换为浮点数
                f_val = float(val)
                # 如果值是 0 或非常接近 0，且原始数据是 '-'，返回 None
                if f_val == 0 and val == '-':
                    return None
                return f_val / 100.0
            except (ValueError, TypeError):
                return None

        def safe_float(val):
            if val is None or val == '-':
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        
        result = {
            'success': True,
            'stock_code': data.get('f57') or stock_code,
            'name': data.get('f58'),
            'price': safe_div_100(data.get('f43')),
            'market_cap': safe_float(data.get('f116')),  # 总市值（元）
            'pe_ttm': safe_div_100(data.get('f162')),
            'pe_static': safe_div_100(data.get('f163')),
            'pb': safe_div_100(data.get('f167')),
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': f'获取基础信息失败: {str(e)}'}), 500

@app.route('/api/stock_pe/<stock_code>')
def get_stock_pe_history(stock_code):
    """
    获取股票历史市盈率 PE-TTM 数据
    """
    if ak is None:
        return jsonify({'success': False, 'error': '未安装 akshare'}), 500
    
    # 提取6位代码
    code = stock_code.split('.')[0]
    try:
        print(f"正在从 akshare 抓取 {code} 的历史 PE-TTM 数据")
        # 获取全部历史 PE-TTM
        df = ak.stock_zh_valuation_baidu(symbol=code, indicator="市盈率(TTM)", period="全部")
        
        if df is None or df.empty:
            return jsonify({'success': False, 'error': '未获取到历史 PE 数据'}), 404
        
        # 转换格式为 [{date: '2023-01-01', value: 15.5}, ...]
        # akshare 返回列名: ['date', 'value']
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        data_list = df.to_dict('records')
        
        return jsonify({
            'success': True,
            'stock_code': stock_code,
            'data': data_list,
            'count': len(data_list)
        })
    except Exception as e:
        print(f"获取历史 PE 失败: {e}")
        return jsonify({'success': False, 'error': f'获取历史 PE 失败: {str(e)}'}), 500

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

def get_pinyin(text):
    """
    获取中文文本的拼音（不带声调）
    """
    if not text or pd.isna(text):
        return ''
    return ''.join(lazy_pinyin(str(text), style=Style.NORMAL))

def get_pinyin_initial(text):
    """
    获取中文文本的拼音首字母
    """
    if not text or pd.isna(text):
        return ''
    return ''.join([p[0].upper() for p in lazy_pinyin(str(text), style=Style.FIRST_LETTER)])

STOCK_LIST_PINYIN_CACHE = {
    'mtime': None,
    'stocks': None
}

def load_stock_list_with_pinyin():
    """
    加载股票列表并缓存拼音字段，避免重复计算
    """
    if not os.path.exists(STOCK_LIST_FILE):
        return []
    mtime = os.path.getmtime(STOCK_LIST_FILE)
    if STOCK_LIST_PINYIN_CACHE['stocks'] is not None and STOCK_LIST_PINYIN_CACHE['mtime'] == mtime:
        return STOCK_LIST_PINYIN_CACHE['stocks']

    df = pd.read_csv(STOCK_LIST_FILE)
    df['name'] = df['name'].astype(str)
    df['pinyin'] = df['name'].apply(lambda x: get_pinyin(x).lower().replace(' ', ''))
    df['pinyin_initials'] = df['name'].apply(lambda x: get_pinyin_initial(x).replace(' ', ''))
    stocks = df.apply(lambda row: {
        'code': row['code'],
        'name': row['name'],
        'pinyin': row['pinyin'],
        'pinyin_initials': row['pinyin_initials']
    }, axis=1).tolist()

    STOCK_LIST_PINYIN_CACHE['stocks'] = stocks
    STOCK_LIST_PINYIN_CACHE['mtime'] = mtime
    return stocks

@app.route('/api/stock_list')
def get_stock_list():
    """
    获取股票列表（包含拼音字段，供前端联想搜索）
    """
    try:
        stocks = load_stock_list_with_pinyin()
        return jsonify({
            'success': True,
            'results': stocks,
            'count': len(stocks)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取股票列表失败: {str(e)}'
        }), 500

@app.route('/api/search_stocks')
def search_stocks():
    """
    搜索股票代码和公司名称（支持拼音搜索）
    参数:
    - q: 搜索关键词（股票代码、公司名称或拼音）
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
        
        # 将查询词转换为小写（用于拼音匹配），并去除空格
        query_lower = query.lower().replace(' ', '')
        query_upper = query.upper().replace(' ', '')
        query_no_space = query.replace(' ', '')
        
        # 基础匹配：股票代码和中文名称（忽略名称中的空格）
        code_mask = df['code'].astype(str).str.contains(query, case=False, na=False)
        # 匹配时去除公司名称中的空格
        name_mask = df['name'].astype(str).str.replace(' ', '', regex=False).str.contains(query_no_space, case=False, na=False)
        
        # 如果基础匹配已有结果，直接返回（性能优化）
        basic_mask = code_mask | name_mask
        if basic_mask.sum() >= limit:
            results = df[basic_mask].head(limit)
        else:
            # 需要拼音匹配，计算所有名称的拼音
            # 为了提高性能，只对未匹配的行计算拼音
            unmatched_df = df[~basic_mask].copy()
            
            if len(unmatched_df) > 0:
                # 计算拼音全拼和首字母（去除空格）
                unmatched_df['_pinyin'] = unmatched_df['name'].apply(lambda x: get_pinyin(str(x)).lower().replace(' ', ''))
                unmatched_df['_pinyin_initials'] = unmatched_df['name'].apply(lambda x: get_pinyin_initial(str(x)).replace(' ', ''))
                
                # 拼音匹配（查询词已去除空格）
                pinyin_mask = unmatched_df['_pinyin'].str.contains(query_lower, na=False)
                initials_mask = unmatched_df['_pinyin_initials'].str.contains(query_upper, na=False)
                
                # 合并所有匹配结果
                pinyin_matched = unmatched_df[pinyin_mask | initials_mask].drop(columns=['_pinyin', '_pinyin_initials'], errors='ignore')
                results = pd.concat([df[basic_mask], pinyin_matched]).head(limit)
            else:
                results = df[basic_mask].head(limit)
        
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

def load_favorite_stocks():
    """加载自选股票列表"""
    if os.path.exists(FAVORITE_STOCKS_FILE):
        try:
            with open(FAVORITE_STOCKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_favorite_stocks(stocks):
    """保存自选股票列表"""
    try:
        with open(FAVORITE_STOCKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(stocks, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"保存自选股票失败: {e}")
        return False

@app.route('/api/favorites', methods=['GET'])
def get_favorites():
    """获取所有自选股票"""
    try:
        stocks = load_favorite_stocks()
        return jsonify({
            'success': True,
            'stocks': stocks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取自选股票失败: {str(e)}'
        }), 500

@app.route('/api/favorites', methods=['POST'])
def add_favorite():
    """添加自选股票"""
    try:
        data = request.get_json()
        stock_code = data.get('stock_code')
        stock_name = data.get('stock_name', '')
        
        if not stock_code:
            return jsonify({
                'success': False,
                'error': '股票代码不能为空'
            }), 400
        
        stocks = load_favorite_stocks()
        
        # 检查是否已存在
        if any(s.get('code') == stock_code for s in stocks):
            return jsonify({
                'success': False,
                'error': '该股票已在自选列表中'
            }), 400
        
        # 添加新股票
        stocks.append({
            'code': stock_code,
            'name': stock_name,
            'added_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
        
        if save_favorite_stocks(stocks):
            return jsonify({
                'success': True,
                'message': '添加成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '保存失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'添加自选股票失败: {str(e)}'
        }), 500

@app.route('/api/favorites', methods=['DELETE'])
def remove_favorite():
    """删除自选股票"""
    try:
        stock_code = request.args.get('stock_code')
        
        if not stock_code:
            return jsonify({
                'success': False,
                'error': '股票代码不能为空'
            }), 400
        
        stocks = load_favorite_stocks()
        stocks = [s for s in stocks if s.get('code') != stock_code]
        
        if save_favorite_stocks(stocks):
            return jsonify({
                'success': True,
                'message': '删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '保存失败'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'删除自选股票失败: {str(e)}'
        }), 500

@app.route('/api/favorites/check', methods=['GET'])
def check_favorite():
    """检查股票是否在自选列表中"""
    try:
        stock_code = request.args.get('stock_code')
        
        if not stock_code:
            return jsonify({
                'success': False,
                'is_favorite': False
            })
        
        stocks = load_favorite_stocks()
        is_favorite = any(s.get('code') == stock_code for s in stocks)
        
        return jsonify({
            'success': True,
            'is_favorite': is_favorite
        })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'检查失败: {str(e)}'
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
