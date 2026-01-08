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
    使用akshare获取A股股票列表
    返回: [(code, name), ...]
    """
    print("正在使用akshare获取A股股票列表...")
    stocks = []
    
    try:
        # 获取沪深A股股票列表
        df = ak.stock_info_a_code_name()
        
        for _, row in df.iterrows():
            code = str(row['code']).zfill(6)  # 确保6位数字
            name = str(row['name']).strip()
            # 添加市场后缀
            if code.startswith('6'):
                code_with_suffix = f"{code}.SH"
            else:
                code_with_suffix = f"{code}.SZ"
            stocks.append((code_with_suffix, name))
        
        print(f"成功获取 {len(stocks)} 只股票")
        return stocks
    
    except Exception as e:
        print(f"使用akshare获取数据失败: {e}")
        return None


def get_stocks_by_eastmoney():
    """
    使用东方财富API获取A股股票列表
    返回: [(code, name), ...]
    """
    print("正在使用东方财富API获取A股股票列表...")
    stocks = []
    
    # 东方财富API - 获取沪深A股列表
    url = "https://82.push2.eastmoney.com/api/qt/clist/get"
    
    # 分页获取，每页100条
    page = 1
    page_size = 100
    max_pages = 100  # 最多获取100页，约10000只股票
    
    while page <= max_pages:
        params = {
            'pn': page,
            'pz': page_size,
            'po': 1,
            'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2,
            'invt': 2,
            'fid': 'f3',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23'  # 沪深A股
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('data') and data['data'].get('diff'):
                diff = data['data']['diff']
                if not diff:
                    break
                
                for item in diff:
                    code = str(item.get('f12', '')).strip()  # 股票代码
                    name = str(item.get('f14', '')).strip()   # 股票名称
                    
                    if code and name and len(code) == 6 and code.isdigit():
                        # 添加市场后缀
                        if code.startswith('6'):
                            code_with_suffix = f"{code}.SH"
                        else:
                            code_with_suffix = f"{code}.SZ"
                        stocks.append((code_with_suffix, name))
                
                print(f"已获取第 {page} 页，累计 {len(stocks)} 只股票")
                
                # 如果返回的数据少于page_size，说明已经是最后一页
                if len(diff) < page_size:
                    break
                
                page += 1
                time.sleep(0.2)  # 避免请求过快
            else:
                break
        
        except Exception as e:
            print(f"获取第 {page} 页数据失败: {e}")
            page += 1
            time.sleep(1)
    
    print(f"成功获取 {len(stocks)} 只股票")
    return stocks


def save_stock_list(stocks, output_file='stock_list.json'):
    """
    保存股票列表到文件
    支持JSON和CSV格式
    """
    if not stocks:
        print("没有股票数据可保存")
        return
    
    # 去重（按代码）
    unique_stocks = {}
    for code, name in stocks:
        if code not in unique_stocks:
            unique_stocks[code] = name
    
    stocks_list = [{'code': code, 'name': name} for code, name in sorted(unique_stocks.items())]
    
    # 保存为JSON
    json_file = output_file if output_file.endswith('.json') else f"{output_file}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total': len(stocks_list),
            'stocks': stocks_list
        }, f, ensure_ascii=False, indent=2)
    
    print(f"已保存 {len(stocks_list)} 只股票到 {json_file}")
    
    # 同时保存为CSV格式（便于查看）
    csv_file = json_file.replace('.json', '.csv')
    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write('code,name\n')
        for stock in stocks_list:
            f.write(f"{stock['code']},{stock['name']}\n")
    
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
