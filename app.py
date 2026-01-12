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
      - 港股: 116.代码
      - 美股: 代码 (通常已包含市场前缀如 105.AAPL)
    """
    code = stock_code.upper()
    if '.' in code:
        parts = code.split('.')
        base = parts[0]
        suffix = parts[-1]
    else:
        base, suffix = code, ''

    if suffix == 'SZ':
        return f"0.{base}"
    elif suffix == 'SH':
        return f"1.{base}"
    elif suffix == 'HK':
        return f"116.{base}"
    elif suffix == 'US':
        # 美股代码在 stock_list.json 中存为 "105.AAPL.US"
        # 实际 API 需要 "105.AAPL"
        if len(parts) >= 3:
            return ".".join(parts[:-1])
        return base # 兜底
    else:
        # 未提供后缀时，根据首位数字简单判断
        if len(base) <= 5 and base.isdigit():
            return f"116.{base}"
        return f"1.{base}" if base.startswith('6') else f"0.{base}"

def fetch_latest_stock_data_from_ak(stock_code, start_date="20250329", end_date=None):
    """
    使用 akshare 抓取特定的股票数据，支持 A 股、港股和美股
    """
    if ak is None:
        print("未安装 akshare，无法抓取最新数据")
        return None
        
    # 提取代码和后缀
    parts = stock_code.split('.')
    suffix = parts[-1].upper()
    
    # 基础代码（去掉 .US, .SZ, .SH 等）
    if suffix in ['US', 'SZ', 'SH', 'HK']:
        code = ".".join(parts[:-1])
    else:
        code = stock_code
    
    try:
        formatted_start = start_date.replace('-', '').replace('/', '')
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        formatted_end = end_date.replace('-', '').replace('/', '')
        
        print(f"正在从 akshare 抓取 {stock_code} 的数据，从 {formatted_start} 到 {formatted_end}")
        
        if suffix == 'HK':
            df = ak.stock_hk_hist(symbol=code, period="daily", start_date=formatted_start, end_date=formatted_end, adjust="")
        elif suffix == 'US':
            # 美股接口 symbol 需要带市场标识，如 105.AAPL
            df = ak.stock_us_hist(symbol=code, period="daily", start_date=formatted_start, end_date=formatted_end, adjust="")
        else:
            # A 股
            # A 股接口 symbol 只需要 6 位代码
            pure_code = code.split('.')[0]
            df = ak.stock_zh_a_hist(symbol=pure_code, period="daily", start_date=formatted_start, end_date=formatted_end, adjust="")
        
        if df is None or df.empty:
            print(f"未获取到 {stock_code} 在该时间段的数据")
            return None
        
        # 重命名列以匹配本地格式
        df = df.rename(columns={
            '日期': 'trade_time',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'vol',
            '成交额': 'amount'
        })
        
        df['trade_time'] = pd.to_datetime(df['trade_time'])
        cols = ['trade_time', 'open', 'close', 'high', 'low', 'vol', 'amount']
        df = df[cols]
        
        return df
    except Exception as e:
        print(f"抓取最新数据失败: {e}")
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
        'fields': 'f43,f57,f58,f59,f116,f162,f163,f167'  # f43最新价, f59价格精度, f57代码, f58名称, f116总市值, f162市盈率(TTM), f163市盈率(静), f167是市净率(PB)
    }

    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        payload = resp.json()
        data = payload.get('data')
        if not data:
            return jsonify({'success': False, 'error': '未获取到基础信息'}), 404

        # 东财接口返回的价格通常需要根据 f59 字段的精度进行除法转换
        # 市盈率和市净率通常固定除以 100
        def safe_div_precision(val, precision):
            if val is None or val == '-' or val == '':
                return None
            try:
                f_val = float(val)
                if f_val == 0 and val == '-':
                    return None
                return f_val / (10 ** precision)
            except (ValueError, TypeError):
                return None

        def safe_div_100(val):
            return safe_div_precision(val, 2)

        def safe_float(val):
            if val is None or val == '-':
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None
        
        # 获取价格精度，默认为 2
        price_precision = data.get('f59', 2)
        
        result = {
            'success': True,
            'stock_code': data.get('f57') or stock_code,
            'name': data.get('f58'),
            'price': safe_div_precision(data.get('f43'), price_precision),
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
    获取股票历史市盈率 PE-TTM 数据，支持 A 股、港股和美股
    """
    if ak is None:
        return jsonify({'success': False, 'error': '未安装 akshare'}), 500
    
    # 提取代码和后缀
    parts = stock_code.split('.')
    suffix = parts[-1].upper()
    
    if suffix in ['US', 'SZ', 'SH', 'HK']:
        code = ".".join(parts[:-1])
    else:
        code = stock_code
    
    try:
        print(f"正在从 akshare 抓取 {stock_code} 的历史 PE-TTM 数据")
        
        if suffix == 'HK':
            # 港股历史估值接口
            df = ak.stock_hk_valuation_baidu(symbol=code, indicator="市盈率(TTM)", period="全部")
        elif suffix == 'US':
            # 美股通常通过历史行情计算或使用特定接口
            # 百度估值接口可能不支持美股，尝试美股估值接口
            try:
                # 尝试通过百度估值接口（部分美股支持）
                df = ak.stock_us_valuation_baidu(symbol=code, indicator="市盈率(TTM)", period="全部")
            except:
                return jsonify({'success': False, 'error': '暂不支持该美股的 PE 数据'}), 404
        else:
            # A 股历史估值接口
            pure_code = code.split('.')[0]
            df = ak.stock_zh_valuation_baidu(symbol=pure_code, indicator="市盈率(TTM)", period="全部")
        
        if df is None or df.empty:
            return jsonify({'success': False, 'error': '未获取到历史 PE 数据'}), 404
        
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
    加载股票列表并缓存拼音字段，直接从CSV读取预计算好的拼音
    """
    if not os.path.exists(STOCK_LIST_FILE):
        return []
    mtime = os.path.getmtime(STOCK_LIST_FILE)
    if STOCK_LIST_PINYIN_CACHE['stocks'] is not None and STOCK_LIST_PINYIN_CACHE['mtime'] == mtime:
        return STOCK_LIST_PINYIN_CACHE['stocks']

    try:
        df = pd.read_csv(STOCK_LIST_FILE)
        # 如果 CSV 中没有拼音列，则手动计算（向下兼容）
        if 'pinyin' not in df.columns or 'pinyin_initials' not in df.columns:
            print(f"警告: {STOCK_LIST_FILE} 中缺少拼音列，正在实时计算...")
            df['name'] = df['name'].astype(str)
            df['pinyin'] = df['name'].apply(lambda x: get_pinyin(x).lower().replace(' ', ''))
            df['pinyin_initials'] = df['name'].apply(lambda x: get_pinyin_initial(x).replace(' ', ''))
        
        # 填充 NaN
        df['pinyin'] = df['pinyin'].fillna('')
        df['pinyin_initials'] = df['pinyin_initials'].fillna('')
        
        stocks = df.apply(lambda row: {
            'code': str(row['code']),
            'name': str(row['name']),
            'pinyin': str(row['pinyin']),
            'pinyin_initials': str(row['pinyin_initials'])
        }, axis=1).tolist()

        STOCK_LIST_PINYIN_CACHE['stocks'] = stocks
        STOCK_LIST_PINYIN_CACHE['mtime'] = mtime
        return stocks
    except Exception as e:
        print(f"加载股票列表失败: {e}")
        return []

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
        # 优先从缓存的列表中搜索，避免重复读取 CSV 和计算
        all_stocks = load_stock_list_with_pinyin()
        if not all_stocks:
            return jsonify({'success': True, 'results': [], 'count': 0})

        query_lower = query.lower().replace(' ', '')
        query_upper = query.upper().replace(' ', '')
        query_no_space = query.replace(' ', '')
        
        results = []
        for stock in all_stocks:
            code = stock['code']
            name = stock['name'].replace(' ', '')
            pinyin = stock['pinyin']
            initials = stock['pinyin_initials']
            
            # 匹配逻辑：代码包含、名称包含、拼音包含、首字母包含
            if (query_upper in code.upper() or 
                query_no_space in name or 
                query_lower in pinyin or 
                query_upper in initials):
                results.append({
                    'code': stock['code'],
                    'name': stock['name']
                })
                if len(results) >= limit:
                    break
        
        return jsonify({
            'success': True,
            'results': results,
            'count': len(results)
        })
    
    except Exception as e:
        print(f"搜索股票出错: {e}")
        return jsonify({
            'success': False,
            'error': f'搜索股票失败: {str(e)}'
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
    import socket
    
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return '127.0.0.1'

    # 支持通过环境变量或命令行参数指定端口
    port = 8080  # 默认端口
    if 'PORT' in os.environ:
        port = int(os.environ['PORT'])
    elif len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"警告: 无效的端口号 '{sys.argv[1]}', 使用默认端口 {port}")
    
    local_ip = get_local_ip()
    print(f"\n" + "="*50)
    print(f"服务器已启动！")
    print(f"本地访问: http://localhost:{port}")
    print(f"局域网访问: http://{local_ip}:{port}")
    print(f"="*50 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=port)
