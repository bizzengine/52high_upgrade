from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
import json
from datetime import timedelta, datetime
import math
import os
import pytz  # 반드시 추가!

app = Flask(__name__)


@app.route('/success-rate')
def success_rate_analysis():
    """하락률별 성공률 분석 페이지"""
    return render_template('success_rate.html')

@app.route('/api/analyze-success-rate', methods=['POST'])
def analyze_success_rate():
    """하락률별 성공률 분석 API"""
    try:
        data = request.get_json()
        ticker = data.get('ticker', '').upper()
        target_increase_pct = float(data.get('target', 20)) / 100
        
        # 주가 데이터 다운로드
        stock_data = yf.download(ticker, start='2020-01-01', end='2030-07-01', auto_adjust=False)
        
        if isinstance(stock_data.columns, pd.MultiIndex):
            stock_data.columns = stock_data.columns.droplevel('Ticker')
        
        if stock_data.empty:
            return jsonify({'error': '유효하지 않은 티커입니다.'}), 400
        
        # 52주 고점과 하락률 계산
        stock_data['52W_High'] = stock_data['High'].rolling(window=252, min_periods=1).max()
        stock_data['Drawdown'] = (stock_data['Close'] - stock_data['52W_High']) / stock_data['52W_High']
        stock_data['Prev_Drawdown'] = stock_data['Drawdown'].shift(1)
        
        results = []
        
        # -5%부터 -80%까지 5% 단위로 분석
        for drawdown_pct in range(5, 95, 5):
            drawdown_threshold = -drawdown_pct / 100
            
            # 해당 하락률에 도달한 시점들 찾기
            buy_points = stock_data[
                (stock_data['Drawdown'] <= drawdown_threshold) &
                (stock_data['Prev_Drawdown'] > drawdown_threshold)
            ]
            
            if buy_points.empty:
                results.append({
                    'drawdown': drawdown_pct,
                    'successRate': 0,
                    'successCases': 0,
                    'failureCases': 0,
                    'totalCases': 0,
                    'avgDays': None
                })
                continue
            
            success_cases = 0
            total_cases = len(buy_points)
            success_days = []
            
            for buy_date in buy_points.index:
                try:
                    buy_price = stock_data.loc[buy_date, 'Close']
                    target_price = buy_price * (1 + target_increase_pct)
                    
                    # 매수일 이후 데이터에서 목표가 달성 여부 확인
                    idx = stock_data.index.get_loc(buy_date)
                    if idx >= len(stock_data) - 1:
                        continue
                    
                    # 목표 달성 여부를 확인하는 기간을 252 거래일 (약 1년)로 제한
                    future_data = stock_data.iloc[idx + 1:idx + 252] 
                    target_hit = future_data[future_data['High'] >= target_price]
                    
                    if not target_hit.empty:
                        success_cases += 1
                        achieve_date = target_hit.index[0]
                        # 실제 거래일 기준으로 일수 계산
                        days_to_achieve = len(stock_data.loc[buy_date:achieve_date]) - 1 
                        success_days.append(days_to_achieve)
                    
                except Exception as e:
                    # 특정 매수 시점 처리 중 오류 발생 시 다음으로 넘어감
                    continue
            
            failure_cases = total_cases - success_cases
            success_rate = (success_cases / total_cases * 100) if total_cases > 0 else 0
            avg_days = sum(success_days) / len(success_days) if success_days else None
            
            results.append({
                'drawdown': drawdown_pct,
                'successRate': round(success_rate, 1),
                'successCases': success_cases,
                'failureCases': failure_cases,
                'totalCases': total_cases,
                'avgDays': round(avg_days, 1) if avg_days else None
            })
        
        # 현재 주가 정보
        current_close = round(stock_data['Close'].iloc[-1], 2)
        current_high_52w = round(stock_data['52W_High'].iloc[-1], 2)
        current_drawdown = round((current_close - current_high_52w) / current_high_52w * 100, 2)
        
        return jsonify({
            'ticker': ticker,
            'targetRate': target_increase_pct * 100,
            'currentPrice': current_close,
            'currentHigh': current_high_52w,
            'currentDrawdown': current_drawdown,
            'results': results
        })
        
    except Exception as e:
        return jsonify({'error': f'분석 중 오류가 발생했습니다: {str(e)}'}), 500
    
if __name__ == '__main__':
    app.run(debug=True, port=4999)