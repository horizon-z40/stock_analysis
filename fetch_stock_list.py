#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取A股所有公司的股票代码和公司名称对应关系
支持多种数据源：akshare、东方财富API
"""

import json
import os
import sys
import time
from datetime import datetime
import pandas as pd

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False
    print("警告: 未安装akshare库，将使用东方财富API")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    print("错误: 未安装requests库，无法使用API方式获取数据")
    sys.exit(1)


def normalize_stock_code(code):
    """标准化股票代码格式"""
    code = str(code).strip()
    # 如果是6位数字，添加市场后缀
    if code.isdigit() and len(code) == 6:
        if code.startswith('6'):
            return f"{code}.SH"
        else:
            return f"{code}.SZ"
    return code


def get_stocks_by_akshare():
    """
    使用akshare获取A股、港股和美股股票列表
    返回: [(code, name), ...]
    """
    print("正在使用akshare获取股票列表...")
    stocks = []
    
    # 1. 获取沪深A股
    try:
        print("正在获取沪深A股列表...")
        df_a = ak.stock_info_a_code_name()
        for _, row in df_a.iterrows():
            code = str(row['code']).zfill(6)
            name = str(row['name']).strip()
            if code.startswith('6'):
                code_with_suffix = f"{code}.SH"
            else:
                code_with_suffix = f"{code}.SZ"
            stocks.append((code_with_suffix, name))
        print(f"已获取 {len(df_a)} 只A股股票")
    except Exception as e:
        print(f"获取A股列表失败: {e}")

    # 2. 获取港股
    try:
        print("正在获取港股列表...")
        df_hk = ak.stock_hk_spot_em()
        for _, row in df_hk.iterrows():
            code = str(row['代码']).strip()
            name = str(row['名称']).strip()
            # 港股代码通常为5位，带 .HK 后缀
            code_with_suffix = f"{code}.HK"
            stocks.append((code_with_suffix, name))
        print(f"已获取 {len(df_hk)} 只港股股票")
    except Exception as e:
        print(f"获取港股列表失败: {e}")
    
    # 3. 获取美股
    try:
        print("正在获取美股列表...")
        df_us = ak.stock_us_spot_em()
        for _, row in df_us.iterrows():
            code = str(row['代码']).strip()
            name = str(row['名称']).strip()
            # 美股代码通常带市场标识，如 105.AAPL
            # 保持原样或统一后缀
            code_with_suffix = f"{code}.US"
            stocks.append((code_with_suffix, name))
        print(f"已获取 {len(df_us)} 只美股股票")
    except Exception as e:
        print(f"获取美股列表失败: {e}")
    
    print(f"总计获取 {len(stocks)} 只股票")
    return stocks if stocks else None


def get_stocks_by_eastmoney():
    """
    使用东方财富API获取A股、港股和美股股票列表
    返回: [(code, name), ...]
    """
    print("正在使用东方财富API获取股票列表...")
    stocks = []
    
    # 1. 沪深A股
    print("正在通过API获取沪深A股列表...")
    url_a = "https://82.push2.eastmoney.com/api/qt/clist/get"
    page = 1
    while True:
        params = {
            'pn': page, 'pz': 100, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f3',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23'
        }
        try:
            resp = requests.get(url_a, params=params, timeout=10).json()
            diff = resp.get('data', {}).get('diff', [])
            if not diff: break
            for item in diff:
                code = str(item.get('f12', '')).strip()
                name = str(item.get('f14', '')).strip()
                if code and name and len(code) == 6:
                    suffix = ".SH" if code.startswith('6') else ".SZ"
                    stocks.append((f"{code}{suffix}", name))
            if len(diff) < 100: break
            page += 1
        except: break
    print(f"当前累计股票数: {len(stocks)}")

    # 2. 港股
    print("正在通过API获取港股列表...")
    url_hk = "https://82.push2.eastmoney.com/api/qt/clist/get"
    page = 1
    while True:
        params = {
            'pn': page, 'pz': 100, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f3',
            'fs': 'm:128+t:3,m:128+t:4,m:128+t:1,m:128+t:2' # 港股主板、创业板等
        }
        try:
            resp = requests.get(url_hk, params=params, timeout=10).json()
            diff = resp.get('data', {}).get('diff', [])
            if not diff: break
            for item in diff:
                code = str(item.get('f12', '')).strip()
                name = str(item.get('f14', '')).strip()
                if code and name:
                    stocks.append((f"{code}.HK", name))
            if len(diff) < 100: break
            page += 1
        except: break
    
    # 3. 美股
    print("正在通过API获取美股列表...")
    url_us = "https://82.push2.eastmoney.com/api/qt/clist/get"
    page = 1
    while True:
        params = {
            'pn': page, 'pz': 100, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f3',
            'fs': 'm:105,m:106,m:107' # 纳斯达克、纽交所、美交所
        }
        try:
            resp = requests.get(url_us, params=params, timeout=10).json()
            diff = resp.get('data', {}).get('diff', [])
            if not diff: break
            for item in diff:
                code = str(item.get('f12', '')).strip()
                # 美股东财 API 返回的代码可能已经包含 105. 等前缀
                name = str(item.get('f14', '')).strip()
                if code and name:
                    # 如果代码不包含前缀，我们需要根据市场添加
                    # 但通常 f12 已经带了市场标识
                    stocks.append((f"{code}.US", name))
            if len(diff) < 100: break
            page += 1
        except: break

    print(f"最终总计获取 {len(stocks)} 只股票")
    return stocks


try:
    from pypinyin import lazy_pinyin, Style
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False
    print("警告: 未安装pypinyin库，搜索建议将不支持拼音")

def get_pinyin(text):
    """获取中文文本的拼音（不带声调）"""
    if not HAS_PYPINYIN or not text:
        return ''
    return ''.join(lazy_pinyin(str(text), style=Style.NORMAL))

def get_pinyin_initial(text):
    """获取中文文本的拼音首字母"""
    if not HAS_PYPINYIN or not text:
        return ''
    return ''.join([p[0].upper() for p in lazy_pinyin(str(text), style=Style.FIRST_LETTER)])

def save_stock_list(stocks, output_file='stock_list.json'):
    """
    保存股票列表到文件
    支持JSON和CSV格式，包含拼音字段以提升搜索性能
    """
    if not stocks:
        print("没有股票数据可保存")
        return
    
    # 去重（按代码）
    unique_stocks = {}
    for code, name in stocks:
        if code not in unique_stocks:
            unique_stocks[code] = name
    
    print(f"正在生成 {len(unique_stocks)} 只股票的拼音字段...")
    stocks_list = []
    count = 0
    total = len(unique_stocks)
    
    for code, name in sorted(unique_stocks.items()):
        pinyin = get_pinyin(name).lower().replace(' ', '')
        pinyin_initials = get_pinyin_initial(name).replace(' ', '')
        stocks_list.append({
            'code': code,
            'name': name,
            'pinyin': pinyin,
            'pinyin_initials': pinyin_initials
        })
        count += 1
        if count % 1000 == 0:
            print(f"进度: {count}/{total}")
    
    # 保存为JSON
    json_file = output_file if output_file.endswith('.json') else f"{output_file}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total': len(stocks_list),
            'stocks': stocks_list
        }, f, ensure_ascii=False, indent=2)
    
    print(f"已保存 {len(stocks_list)} 只股票到 {json_file}")
    
    # 同时保存为CSV格式（便于查看和后端加载）
    csv_file = json_file.replace('.json', '.csv')
    df = pd.DataFrame(stocks_list)
    df.to_csv(csv_file, index=False, encoding='utf-8')
    
    print(f"已保存CSV格式到 {csv_file}")
    
    return json_file, csv_file


def main():
    """主函数"""
    print("=" * 60)
    print("A股股票代码和公司名称获取工具")
    print("=" * 60)
    
    # 优先使用akshare（更稳定）
    stocks = None
    if HAS_AKSHARE:
        stocks = get_stocks_by_akshare()
    
    # 如果akshare失败，使用东方财富API
    if not stocks:
        if HAS_REQUESTS:
            stocks = get_stocks_by_eastmoney()
        else:
            print("错误: 没有可用的数据源")
            sys.exit(1)
    
    if not stocks:
        print("错误: 未能获取到股票数据")
        sys.exit(1)
    
    # 保存数据
    output_file = 'stock_list.json'
    if len(sys.argv) > 1:
        output_file = sys.argv[1]
    
    json_file, csv_file = save_stock_list(stocks, output_file)
    
    print("\n" + "=" * 60)
    print("完成！")
    print(f"JSON文件: {json_file}")
    print(f"CSV文件: {csv_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()
