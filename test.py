import yfinance as yf
import pandas as pd

def get_latest_quarterly_financials(stock_symbol):
    """
    주어진 종목 심볼에 대해 yfinance를 사용하여 가장 최근 분기의 영업이익과 순이익을 반환합니다.
    """
    ticker = yf.Ticker(stock_symbol)
    
    try:
        # 분기별 재무제표 데이터 가져오기
        quarterly_financials = ticker.quarterly_financials
        
        if quarterly_financials.empty:
            print(f"[{stock_symbol}]에 대한 분기 재무 데이터를 찾을 수 없습니다.")
            return None, None, None
        
        # 가장 최근 분기의 컬럼 (날짜)
        latest_quarter_date = quarterly_financials.columns[0]
        print(f"[{stock_symbol}] 가장 최근 분기 종료일: {latest_quarter_date.strftime('%Y-%m-%d')}")
        
        operating_income = None
        net_income = None
        
        # 영업이익 (Operating Income)
        if 'Operating Income' in quarterly_financials.index:
            operating_income = quarterly_financials.loc['Operating Income', latest_quarter_date]
            print(f"  - 영업이익: {operating_income:,.2f}")
        else:
            print("  - 영업이익 데이터를 찾을 수 없습니다.")
            
        # 순이익 (Net Income)
        if 'Net Income' in quarterly_financials.index:
            net_income = quarterly_financials.loc['Net Income', latest_quarter_date]
            print(f"  - 순이익: {net_income:,.2f}")
        else:
            print("  - 순이익 데이터를 찾을 수 없습니다.")
            
        return latest_quarter_date, operating_income, net_income
        
    except Exception as e:
        print(f"[{stock_symbol}] 분기 재무 데이터를 가져오는 중 오류 발생: {e}")
        return None, None, None

if __name__ == "__main__":
    # 테스트할 종목 심볼 (예: Apple)
    symbol = "MOH"
    
    print(f"--- {symbol} 최근 분기 재무 데이터 확인 ---")
    date, op_income, net_income = get_latest_quarterly_financials(symbol)
    
    print("\n" + "="*50 + "\n")

    # 다른 종목 테스트 (예: Microsoft)
    symbol2 = "MSFT"
    print(f"--- {symbol2} 최근 분기 재무 데이터 확인 ---")
    date2, op_income2, net_income2 = get_latest_quarterly_financials(symbol2)

    print("\n" + "="*50 + "\n")

    # 데이터가 없는 종목 테스트 (예: 존재하지 않는 심볼)
    symbol3 = "NONEXISTENTSTOCK"
    print(f"--- {symbol3} 최근 분기 재무 데이터 확인 ---")
    date3, op_income3, net_income3 = get_latest_quarterly_financials(symbol3)