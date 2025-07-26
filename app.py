from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST']) # GET과 POST 요청 모두 처리
def index():
    stock_name = None
    stock_symbol = None
    high_52_week = None
    current_price = None
    target_increase_pct = 3 # 기본값
    price_levels_to_display = []
    error = None

    if request.method == 'POST':
        stock_symbol = request.form.get('stock_symbol', '').upper()
        try:
            target_increase_pct_str = request.form.get('target_increase_pct', '3')
            target_increase_pct = float(target_increase_pct_str) / 100
            if not (0 < target_increase_pct <= 1.0):
                raise ValueError("목표 상승률은 0% 초과 100% 이하로 입력해주세요.")

        except ValueError as e:
            error = f"목표 상승률 입력 오류: {e}"
        except Exception as e:
            error = f"목표 상승률 처리 중 오류가 발생했습니다: {e}"

        if not error: # 목표 상승률에 오류가 없으면 주식 분석 진행
            start_date = '2020-01-01'

            try:
                df = yf.download(stock_symbol, start=start_date, progress=False, auto_adjust=False)

                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel('Ticker')

                df = df[df['Close'].notna()]
                df = df.sort_index()

                if df.empty:
                    error = f"'{stock_symbol}' 종목의 데이터를 찾을 수 없거나 데이터가 부족합니다. 심볼을 확인해주세요."
                
                if not error: # 데이터 로드에 오류가 없으면 계속 진행
                    if len(df) >= 252:
                        high_52_week = df['High'].tail(252).max()
                    else:
                        high_52_week = df['High'].max()

                    current_price = df['Close'].iloc[-1]

                    ticker = yf.Ticker(stock_symbol)
                    stock_info = ticker.info
                    stock_name = stock_info.get('longName', stock_symbol)

            except Exception as e:
                print(f"Error fetching data for {stock_symbol}: {e}")
                error = f"데이터를 가져오는 중 오류가 발생했습니다: {e}. 정확한 종목 심볼을 입력했는지 확인해주세요."

        if not error: # 주식 데이터 로드에 오류가 없으면 분석 진행
            actual_percent_drop = (1 - current_price / high_52_week) * 100

            try:
                this_year = datetime.today().year
                start_of_year = datetime(this_year, 1, 1)
                df_this_year = df[df.index.tz_localize(None) >= start_of_year]

                if not df_this_year.empty:
                    low_this_year = df_this_year['Close'].min()
                    max_drop_1_year_val = (1 - low_this_year / high_52_week) * 100
                    max_drop_1_year_price = high_52_week * (1 - max_drop_1_year_val / 100)
                else:
                    max_drop_1_year_val = 0
                    max_drop_1_year_price = high_52_week
            except Exception as e:
                print(f"Error calculating this year's low: {e}")
                max_drop_1_year_val = 0
                max_drop_1_year_price = high_52_week

            # ====== 추가.py의 성공률 분석 로직 통합 시작 ======
            df_for_analysis = df.copy()
            df_for_analysis['52W_High_Analysis'] = df_for_analysis['High'].rolling(window=252, min_periods=1).max()
            df_for_analysis['Drawdown_Analysis'] = (df_for_analysis['Close'] - df_for_analysis['52W_High_Analysis']) / df_for_analysis['52W_High_Analysis']
            df_for_analysis['Prev_Drawdown_Analysis'] = df_for_analysis['Drawdown_Analysis'].shift(1)

            success_analysis_data = {} 

            for drawdown_pct_val in range(5, 95, 5): # 5, 10, ..., 90
                drawdown_threshold = -drawdown_pct_val / 100

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
                            target_price_for_success = buy_price * (1 + target_increase_pct)
                            
                            idx = df_for_analysis.index.get_loc(buy_date)
                            if idx >= len(df_for_analysis) - 1:
                                continue
                            
                            future_data = df_for_analysis.iloc[idx + 1:idx + 252] 
                            target_hit = future_data[future_data['High'] >= target_price_for_success]
                            
                            if not target_hit.empty:
                                success_cases += 1
                                achieve_date = target_hit.index[0]
                                days_to_achieve = len(df_for_analysis.loc[buy_date:achieve_date]) - 1 
                                success_days.append(days_to_achieve)
                            
                        except Exception as e:
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
            # ====== 추가.py의 성공률 분석 로직 통합 끝 ======

            standard_price_levels = [{
                "percent_drop": 0,
                "target_price": high_52_week,
                "is_current": False,
                **success_analysis_data.get(0, {'successRate': None, 'successCases': None, 'failureCases': None, 'totalCases': None, 'avgDays': None})
            }]
            for percent_drop_val in range(5, 81, 5):
                target_price_level = high_52_week * (1 - percent_drop_val / 100)
                standard_price_levels.append({
                    "percent_drop": percent_drop_val,
                    "target_price": round(target_price_level, 2),
                    "is_current": False,
                    **success_analysis_data.get(percent_drop_val, {'successRate': None, 'successCases': None, 'failureCases': None, 'totalCases': None, 'avgDays': None})
                })

            current_price_data = {
                "percent_drop": actual_percent_drop,
                "target_price": current_price,
                "is_current": True,
                'successRate': None, 'successCases': None, 'failureCases': None, 'totalCases': None, 'avgDays': None
            }

            max_drop_1_year_data = {
                "percent_drop": max_drop_1_year_val,
                "target_price": max_drop_1_year_price,
                "is_current": False,
                "is_max_drop_1_year": True,
                'successRate': None, 'successCases': None, 'failureCases': None, 'totalCases': None, 'avgDays': None
            }

            price_levels_to_display = []
            inserted_current = False
            inserted_max_drop = False

            price_levels_to_display.append(standard_price_levels[0])

            for i in range(1, len(standard_price_levels)):
                current_level_data = standard_price_levels[i]

                if not inserted_current and actual_percent_drop > standard_price_levels[i-1]["percent_drop"] and actual_percent_drop <= current_level_data["percent_drop"]:
                    price_levels_to_display.append(current_price_data)
                    inserted_current = True
                elif not inserted_current and i == 1 and actual_percent_drop <= standard_price_levels[0]["percent_drop"]:
                    price_levels_to_display.insert(1, current_price_data)
                    inserted_current = True

                if not inserted_max_drop and max_drop_1_year_data["percent_drop"] > standard_price_levels[i-1]["percent_drop"] and max_drop_1_year_data["percent_drop"] <= current_level_data["percent_drop"]:
                    if inserted_current and current_price_data["percent_drop"] == max_drop_1_year_data["percent_drop"]:
                        idx = price_levels_to_display.index(current_price_data)
                        price_levels_to_display.insert(idx + 1, max_drop_1_year_data)
                    else:
                        price_levels_to_display.append(max_drop_1_year_data)
                    inserted_max_drop = True

                price_levels_to_display.append(current_level_data)

            if not inserted_current:
                price_levels_to_display.append(current_price_data)
            if not inserted_max_drop:
                price_levels_to_display.append(max_drop_1_year_data)

            price_levels_to_display.sort(key=lambda x: x['percent_drop'])
            
            # target_increase_pct를 100을 곱하여 템플릿에 전달 (퍼센트 형식으로)
            target_increase_pct = target_increase_pct * 100

    return render_template('index.html',
                           stock_name=stock_name,
                           stock_symbol=stock_symbol,
                           high_52_week=high_52_week,
                           current_price=current_price,
                           target_increase_pct=target_increase_pct,
                           price_levels=price_levels_to_display,
                           error=error)

@app.route('/search_stock', methods=['GET'])
def search_stock():
    return jsonify([])  # 자동 완성 비활성화

if __name__ == '__main__':
    app.run(debug=True, port=7000)