from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
import json

app = Flask(__name__)

# tickers.json 파일 로드 (애플리케이션 시작 시 한 번만 로드)
try:
    with open('tickers.json', 'r', encoding='utf-8') as f:
        all_stock_data = json.load(f)
except FileNotFoundError:
    all_stock_data = []
    print("Error: tickers.json not found. Autocomplete will not work.")
except json.JSONDecodeError:
    all_stock_data = []
    print("Error: tickers.json is not a valid JSON file. Autocomplete will not work.")
except Exception as e:
    all_stock_data = []
    print(f"An unexpected error occurred while loading tickers.json: {e}")


def format_financial_number(value):
    """재무 수치를 적절한 단위로 포맷팅"""
    if pd.isna(value) or value is None:
        return None
    
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        return f"{value / 1_000_000_000:.2f}B"
    elif abs_value >= 1_000_000:
        return f"{value / 1_000_000:.2f}M"
    elif abs_value >= 1_000:
        return f"{value / 1_000:.2f}K"
    else:
        return f"{value:.2f}"

def calculate_match_score(stock, query):
    """검색 쿼리와 주식 정보의 매칭 점수 계산"""
    symbol = stock.get("symbol", "").upper()
    name = stock.get("name", "").upper()
    query_upper = query.upper()
    
    score = 0
    
    # 심볼 매칭 (가장 높은 점수)
    if symbol == query_upper:
        score += 1000  # 완전 일치
    elif symbol.startswith(query_upper):
        score += 500  # 시작 일치
    elif query_upper in symbol:
        score += 100  # 부분 일치
    
    # 회사명 매칭
    if query_upper in name:
        if name.startswith(query_upper):
            score += 200  # 이름 시작 일치
        else:
            score += 50   # 이름 부분 일치
    
    # 심볼 길이 보너스 (짧은 심볼이 더 일반적)
    if len(symbol) <= 4:
        score += 10
    
    return score

@app.route('/', methods=['GET', 'POST'])
def index():
    stock_name = None
    stock_symbol = None
    high_52_week = None
    current_price = None
    target_increase_pct = 3 # 기본값은 3% (HTML 폼의 기본값과 일치)
    price_levels_to_display = []
    error = None
    operating_income_formatted = None
    net_income_formatted = None
    latest_quarter_date_formatted = None 
    low_52_week_close = None # 52주 전저점 (Close 기준)
    low_this_year_close = None # 올해 최저 종가 (Close 기준)

    if request.method == 'POST':
        stock_symbol = request.form.get('stock_symbol', '').upper()
        try:
            target_increase_pct_raw = request.form.get('target_increase_pct', '3')
            target_increase_pct = float(target_increase_pct_raw) # 이제 0~100 사이 값
            if not (0 < target_increase_pct <= 100): # 0% 초과 100% 이하로 변경
                raise ValueError("목표 상승률은 0% 초과 100% 이하로 입력해주세요.")
            
            # 실제 계산에는 비율로 사용
            target_increase_pct_ratio = target_increase_pct / 100 

        except ValueError as e:
            error = f"목표 상승률 입력 오류: {e}"
        except Exception as e:
            error = f"목표 상승률 처리 중 오류가 발생했습니다: {e}"

        if not error:
            start_date = '2020-01-01' # 분석 시작 날짜는 넉넉하게 설정

            try:
                df = yf.download(stock_symbol, start=start_date, progress=False, auto_adjust=False)

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel('Ticker')

                df = df[df['Close'].notna()] # 종가 데이터가 있는 행만 사용
                df = df.sort_index()

                if df.empty:
                    error = f"'{stock_symbol}' 종목의 데이터를 찾을 수 없거나 데이터가 부족합니다. 심볼을 확인해주세요."
                
                if not error:
                    # 52주 신고점, 52주 전저점 계산
                    if len(df) >= 252: # 최소 252 거래일 데이터가 있을 경우
                        high_52_week = df['High'].tail(252).max()
                        low_52_week_close = df['Close'].tail(252).min()
                    else: # 252 거래일 데이터가 없으면 전체 기간 중 최고/최저 사용
                        high_52_week = df['High'].max()
                        low_52_week_close = df['Close'].min()

                    # 올해 최저 종가 계산
                    current_year = datetime.now().year
                    df_current_year = df.loc[df.index.year == current_year]
                    if not df_current_year.empty:
                        low_this_year_close = df_current_year['Close'].min()
                    else: # 올해 데이터가 없으면 전체 데이터 중 최저 사용 (대체)
                        low_this_year_close = df['Close'].min()


                    current_price = df['Close'].iloc[-1]

                    ticker = yf.Ticker(stock_symbol)
                    stock_info = ticker.info
                    stock_name = stock_info.get('longName', stock_symbol)

                    # 재무 데이터 가져오기
                    try:
                        financials = ticker.quarterly_financials 
                        if not financials.empty and 'Operating Income' in financials.index and 'Net Income' in financials.index:
                            latest_quarter_date = financials.columns[0] # 가장 최근 분기
                            latest_quarter_date_formatted = latest_quarter_date.strftime('%Y-%m-%d')
                            
                            operating_income = financials.loc['Operating Income', latest_quarter_date]
                            operating_income_formatted = format_financial_number(operating_income)
                            
                            net_income = financials.loc['Net Income', latest_quarter_date]
                            net_income_formatted = format_financial_number(net_income)
                                
                    except Exception as e:
                        print(f"재무 데이터 가져오기 실패 또는 데이터 없음: {e}")
                        operating_income_formatted = None
                        net_income_formatted = None
                        latest_quarter_date_formatted = None

            except Exception as e:
                print(f"Error fetching data for {stock_symbol}: {e}")
                error = f"데이터를 가져오는 중 오류가 발생했습니다: {e}. 정확한 종목 심볼을 입력했는지 확인해주세요."

        if not error and high_52_week and current_price: # 데이터가 성공적으로 로드된 경우에만 분석 진행
            actual_percent_drop = (1 - current_price / high_52_week) * 100 if high_52_week else 0

            # 52주 전저점 하락률 계산
            max_drop_52_week_val = (1 - low_52_week_close / high_52_week) * 100 if high_52_week and low_52_week_close else 0
            max_drop_52_week_price = low_52_week_close

            # 올해 최저 하락률 계산 (52주 신고점 대비)
            max_drop_this_year_val = (1 - low_this_year_close / high_52_week) * 100 if high_52_week and low_this_year_close else 0
            max_drop_this_year_price = low_this_year_close


            # 성공률 분석 로직
            df_for_analysis = df.copy()
            # 52주 신고점 계산 (롤링 윈도우)
            df_for_analysis['52W_High_Analysis'] = df_for_analysis['High'].rolling(window=252, min_periods=1).max()
            # 52주 신고점 대비 하락률 계산
            df_for_analysis['Drawdown_Analysis'] = (df_for_analysis['Close'] - df_for_analysis['52W_High_Analysis']) / df_for_analysis['52W_High_Analysis']
            df_for_analysis['Prev_Drawdown_Analysis'] = df_for_analysis['Drawdown_Analysis'].shift(1)

            success_analysis_data = {} 

            # 5% 단위로 하락률 구간 설정 (0%는 제외하고 5%부터 시작)
            for drawdown_pct_val in range(5, 95, 5): 
                drawdown_threshold = -drawdown_pct_val / 100

                # 특정 하락률에 처음 도달하는 시점 (매수 시점)
                buy_points = df_for_analysis[
                    (df_for_analysis['Drawdown_Analysis'] <= drawdown_threshold) &
                    (df_for_analysis['Prev_Drawdown_Analysis'] > drawdown_threshold)
                ]
                
                success_cases = 0
                total_cases = len(buy_points)
                success_days = []
                
                if not buy_points.empty:
                    for buy_date in buy_points.index:
                        try:
                            buy_price = df_for_analysis.loc[buy_date, 'Close']
                            target_price_for_success = buy_price * (1 + target_increase_pct_ratio) # 실제 비율 사용
                            
                            idx = df_for_analysis.index.get_loc(buy_date)
                            # 현재 매수 시점 이후 252 거래일 (약 1년) 데이터만 고려
                            if idx >= len(df_for_analysis) - 1:
                                continue # 마지막 데이터는 분석 불가

                            future_data = df_for_analysis.iloc[idx + 1:min(idx + 252 + 1, len(df_for_analysis))] # 252거래일 + 현재일 포함
                            
                            if future_data.empty:
                                continue

                            # 목표 가격 달성 여부 확인 (고가 기준)
                            target_hit = future_data[future_data['High'] >= target_price_for_success]
                            
                            if not target_hit.empty:
                                success_cases += 1
                                achieve_date = target_hit.index[0]
                                # 달성까지 걸린 거래일 수
                                days_to_achieve = len(df_for_analysis.loc[buy_date:achieve_date]) - 1 
                                success_days.append(days_to_achieve)
                            
                        except Exception as e:
                            # print(f"분석 중 오류 발생 ({buy_date}): {e}") # 디버깅용
                            continue
                
                failure_cases = total_cases - success_cases
                success_rate = (success_cases / total_cases * 100) if total_cases > 0 else 0
                avg_days = sum(success_days) / len(success_days) if success_days else None
                
                success_analysis_data[drawdown_pct_val] = {
                    'successRate': round(success_rate, 1),
                    'successCases': success_cases,
                    'failureCases': failure_cases,
                    'totalCases': total_cases,
                    'avgDays': round(avg_days, 1) if avg_days else None
                }

            # 표시할 가격 레벨 데이터 구성
            price_levels_to_display = []

            # 0% 하락률 (신고점) 데이터 추가
            price_levels_to_display.append({
                "percent_drop": 0,
                "target_price": high_52_week,
                "is_current": False,
                "is_max_drop_1_year": False,
                "is_max_drop_this_year": False,
                **success_analysis_data.get(0, {'successRate': None, 'successCases': None, 'failureCases': None, 'totalCases': None, 'avgDays': None})
            })

            # 표준 하락률 레벨 추가 (5% 단위)
            for percent_drop_val in range(5, 81, 5):
                target_price_level = high_52_week * (1 - percent_drop_val / 100)
                price_levels_to_display.append({
                    "percent_drop": float(percent_drop_val), # 소수점 처리
                    "target_price": round(target_price_level, 2),
                    "is_current": False,
                    "is_max_drop_1_year": False,
                    "is_max_drop_this_year": False,
                    **success_analysis_data.get(percent_drop_val, {'successRate': None, 'successCases': None, 'failureCases': None, 'totalCases': None, 'avgDays': None})
                })
            
            # 현재가 데이터
            current_price_data = {
                "percent_drop": actual_percent_drop,
                "target_price": current_price,
                "is_current": True,
                "is_max_drop_1_year": False,
                "is_max_drop_this_year": False,
                'successRate': None, 'successCases': None, 'failureCases': None, 'totalCases': None, 'avgDays': None
            }

            # 52주 전저점 데이터
            max_drop_52_week_data = {
                "percent_drop": max_drop_52_week_val,
                "target_price": max_drop_52_week_price,
                "is_current": False,
                "is_max_drop_1_year": True,
                "is_max_drop_this_year": False,
                'successRate': None, 'successCases': None, 'failureCases': None, 'totalCases': None, 'avgDays': None
            }

            # 올해 최저 하락 데이터
            max_drop_this_year_data = { 
                "percent_drop": max_drop_this_year_val,
                "target_price": max_drop_this_year_price,
                "is_current": False,
                "is_max_drop_1_year": False,
                "is_max_drop_this_year": True, 
                'successRate': None, 'successCases': None, 'failureCases': None, 'totalCases': None, 'avgDays': None
            }

            # 특별한 가격 레벨들을 삽입 (중복 방지 및 순서 유지)
            # 현재가가 0% 하락률보다 크거나 같고, 첫 번째 표준 하락률보다 작을 경우 0%와 5% 사이에 삽입
            if 0 <= actual_percent_drop < 5:
                # 0% 하락률 바로 다음에 현재가 삽입
                price_levels_to_display.insert(1, current_price_data) 
            else:
                # 적절한 위치에 삽입 (이미 존재하는 하락률과 겹치지 않게)
                inserted = False
                for i in range(1, len(price_levels_to_display)):
                    if price_levels_to_display[i-1]["percent_drop"] < actual_percent_drop <= price_levels_to_display[i]["percent_drop"]:
                        price_levels_to_display.insert(i, current_price_data)
                        inserted = True
                        break
                if not inserted: # 모든 표준 레벨보다 클 경우 마지막에 추가
                    price_levels_to_display.append(current_price_data)

            # 52주 전저점 데이터 삽입 (현재가와 겹치지 않게)
            inserted = False
            for i in range(len(price_levels_to_display)):
                if price_levels_to_display[i]["percent_drop"] == max_drop_52_week_data["percent_drop"] and price_levels_to_display[i].get("is_max_drop_1_year") == True:
                    inserted = True # 이미 같은 52주 전저점 데이터가 있음 (겹치는 5% 간격에 포함되어)
                    break
                if price_levels_to_display[i]["percent_drop"] < max_drop_52_week_data["percent_drop"]:
                    if i + 1 < len(price_levels_to_display) and price_levels_to_display[i+1]["percent_drop"] > max_drop_52_week_data["percent_drop"]:
                        price_levels_to_display.insert(i+1, max_drop_52_week_data)
                        inserted = True
                        break
                elif i == 0 and max_drop_52_week_data["percent_drop"] < price_levels_to_display[0]["percent_drop"]: # 0%보다 작은 경우 (이런 경우는 거의 없겠지만)
                    price_levels_to_display.insert(0, max_drop_52_week_data)
                    inserted = True
                    break
            if not inserted: # 아직 삽입되지 않았다면 맨 뒤에 추가
                price_levels_to_display.append(max_drop_52_week_data)

            # 올해 최저 하락률 데이터 삽입 (다른 특별 행들과 겹치지 않게)
            inserted = False
            for i in range(len(price_levels_to_display)):
                if price_levels_to_display[i]["percent_drop"] == max_drop_this_year_data["percent_drop"] and price_levels_to_display[i].get("is_max_drop_this_year") == True:
                    inserted = True # 이미 같은 올해 최저 하락률 데이터가 있음
                    break
                if price_levels_to_display[i]["percent_drop"] < max_drop_this_year_data["percent_drop"]:
                    if i + 1 < len(price_levels_to_display) and price_levels_to_display[i+1]["percent_drop"] > max_drop_this_year_data["percent_drop"]:
                        price_levels_to_display.insert(i+1, max_drop_this_year_data)
                        inserted = True
                        break
                elif i == 0 and max_drop_this_year_data["percent_drop"] < price_levels_to_display[0]["percent_drop"]:
                    price_levels_to_display.insert(0, max_drop_this_year_data)
                    inserted = True
                    break
            if not inserted: # 아직 삽입되지 않았다면 맨 뒤에 추가
                price_levels_to_display.append(max_drop_this_year_data)


            # 최종적으로 하락률 기준으로 정렬
            price_levels_to_display.sort(key=lambda x: x['percent_drop'])
            
            # 음수 하락률 (즉, 신고점보다 높은 가격)은 0으로 표시
            for item in price_levels_to_display:
                if item['percent_drop'] < 0:
                    item['percent_drop'] = 0.00
            

    return render_template('index.html',
                           stock_name=stock_name,
                           stock_symbol=stock_symbol,
                           high_52_week=high_52_week,
                           current_price=current_price,
                           target_increase_pct=target_increase_pct, # 다시 0~100 값으로 전달
                           price_levels=price_levels_to_display,
                           operating_income_formatted=operating_income_formatted,
                           net_income_formatted=net_income_formatted,
                           latest_quarter_date_formatted=latest_quarter_date_formatted, 
                           error=error)

@app.route('/search_stock', methods=['GET'])
def search_stock():
    query = request.args.get('query', '').strip()
    suggestions = []
    
    if not query or len(query) < 1:
        return jsonify([])
    
    # tickers.json에서 로드된 데이터를 사용
    if all_stock_data:
        # 매칭 점수 계산 및 정렬
        matches = []
        for stock in all_stock_data:
            symbol = stock.get("symbol", "").upper()
            name = stock.get("name", "").upper()
            query_upper = query.upper()
            
            # 심볼이나 이름에 쿼리가 포함되는 경우만 고려
            if query_upper in symbol or query_upper in name:
                score = calculate_match_score(stock, query)
                matches.append({
                    "stock": stock,
                    "score": score
                })
        
        # 점수 순으로 정렬 (높은 점수가 먼저)
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        # 상위 10개 결과 반환
        for match in matches[:10]:
            stock = match["stock"]
            suggestions.append({
                "symbol": stock.get("symbol", ""),
                "name": stock.get("name", ""),
                "rank": stock.get("rank", ""),  # rank 필드 추가
            })
    
    return jsonify(suggestions)

if __name__ == '__main__':
    app.run(debug=True, port=7000)