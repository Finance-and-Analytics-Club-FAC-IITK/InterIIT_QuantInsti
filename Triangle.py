"""
    Title: Buy and Hold (NSE)
    Description: This is a long only strategy which rebalances the 
        portfolio weights every month at month start.
    Style tags: Systematic
    Asset class: Equities, Futures, ETFs, Currencies and Commodities
    Dataset: NSE
"""
from blueshift.api import(    symbol,
                            order_target_percent,
                            schedule_function,
                            date_rules,
                            time_rules,
                            set_stoploss
                       )
import numpy as np
import pandas as pd

from scipy.stats import linregress
def initialize(context):
    """
        A function to define things to do at the start of the strategy
    """
    
    # universe selection
    context.securities = [
                               symbol('MARUTI'),
                               symbol('AMARAJABAT'),
                               symbol('BPCL'),                               
                               symbol('BAJFINANCE'),
                               symbol('HDFCBANK'),
                               symbol('ASIANPAINT'),
                               symbol('TCS')
                             ]
    context.flag = 0
    # Call rebalance function on the first trading day of each month after 2.5 hours from market open
    schedule_function(rebalance,
                    date_rules.every_day(),
                    time_rules.market_open(hours=2, minutes=30))

def pivotId(df, candle, num_before, num_after):
    if candle < num_before   or candle + num_after >= len(df):
        return 0
    
    pivotIdLow=1
    pivotIdHigh=1
    for i in range( candle - num_before, candle + num_after):
        if(df.low[candle]>df.low[i]):
            pivotIdLow=0
        if(df.high[candle]<df.high[i]):
            pivotIdHigh=0
    if pivotIdLow and pivotIdHigh:
        return 3
    elif pivotIdLow:
        return 1
    elif pivotIdHigh:
        return 2
    else:
        return 0

def pointPosition(x, df):
    if x['Pivot'] == 1:
        return x['low']-(0.01 * df.high.max())
    elif x['Pivot'] == 2:
        return x['high']+(0.01 * df.high.max())
    else:
        return np.nan

def rebalance(context,data):
    
    stock_data = data.history(context.securities, ['close', 'open', 'high', 'low', 'volume'], 50, '1d' )
    for security in context.securities:
        try:
            df = stock_data.xs(security) 
            df['Id'] = np.arange(1, len(df)+1)       
            NUM_BEFORE = 3
            NUM_AFTER = 3
            # pivotId(df, 4, NUM_BEFORE, NUM_AFTER)
            df['Pivot'] = df.apply(lambda row: pivotId(df, int(row.Id)-1, NUM_BEFORE, NUM_AFTER), axis=1)
            df['PointPosition'] = df.apply(lambda row: pointPosition(row, df), axis=1)
            # pd.set_option("display.max_rows", None, "display.max_columns", None)

            RECENT_HIGH_PIVOT_POINT = 0
            RECENT_LOW_PIVOT_POINT = 0

            FEASIBLE_HIGH_PIVOT_POINTS = np.array([])
            FEASIBLE_LOW_PIVOT_POINTS = np.array([])
            FEASIBLE_HIGH = np.array([])
            FEASIBLE_LOW = np.array([])

            for i in reversed(range(len(df))):
                if df.Pivot[i] == 2 and RECENT_HIGH_PIVOT_POINT == 0:
                    RECENT_HIGH_PIVOT_POINT = df.Id[i]
                    FEASIBLE_HIGH = np.append(FEASIBLE_HIGH, df.high[i])
                if df.Pivot[i] == 1 and RECENT_LOW_PIVOT_POINT == 0:
                    RECENT_LOW_PIVOT_POINT = df.Id[i]
                    FEASIBLE_LOW = np.append(FEASIBLE_LOW, df.low[i])
                if RECENT_HIGH_PIVOT_POINT != 0 and RECENT_LOW_PIVOT_POINT != 0:
                    break
            
            
            FEASIBLE_HIGH_PIVOT_POINTS = np.append(FEASIBLE_HIGH_PIVOT_POINTS, RECENT_HIGH_PIVOT_POINT)
            FEASIBLE_LOW_PIVOT_POINTS = np.append(FEASIBLE_LOW_PIVOT_POINTS, RECENT_LOW_PIVOT_POINT)

            dfHigh=df[df['Pivot'] == 2]
            dfLow=df[df['Pivot'] == 1]
            # print(dfLow)
            # prdfLow['PointPosition'] == dfLow.PointPosition.min()
            MAX_HIGH_PIVOT_POINT = dfHigh.loc[dfHigh['PointPosition'] == dfHigh.PointPosition.max(), 'Id'].iloc[0]
            MIN_LOW_PIVOT_POINT  = dfLow.loc[dfLow['PointPosition'] == dfLow.PointPosition.min(),  'Id'].iloc[0]

            FEASIBLE_HIGH_PIVOT_POINTS = np.append(FEASIBLE_HIGH_PIVOT_POINTS, MAX_HIGH_PIVOT_POINT)
            FEASIBLE_HIGH = np.append(FEASIBLE_HIGH, dfHigh.loc[dfHigh['PointPosition'] == dfHigh.PointPosition.max(), 'high'])
            FEASIBLE_LOW_PIVOT_POINTS = np.append(FEASIBLE_LOW_PIVOT_POINTS, MIN_LOW_PIVOT_POINT)
            FEASIBLE_LOW = np.append(FEASIBLE_LOW, dfLow.loc[dfLow['PointPosition'] == dfLow.PointPosition.min(), 'low'])

            dfHigh = dfHigh[dfHigh['Id'] > MAX_HIGH_PIVOT_POINT]
            dfLow = dfLow[dfLow['Id'] > MIN_LOW_PIVOT_POINT]

            # if not dfHigh.loc[dfHigh['PointPosition'] == dfHigh.PointPosition.max(), 'Id'].empty:
            FEASIBLE_HIGH_PIVOT_POINTS = np.append(FEASIBLE_HIGH_PIVOT_POINTS, dfHigh.loc[dfHigh['PointPosition'] == dfHigh.PointPosition.max(), 'Id'].iloc[0])
            # print(FEASIBLE_HIGH_PIVOT_POINTS)
            # if not dfHigh.loc[dfHigh['PointPosition'] == dfHigh.PointPosition.max(), 'high'].empty:
            FEASIBLE_HIGH = np.append(FEASIBLE_HIGH, dfHigh.loc[dfHigh['PointPosition'] == dfHigh.PointPosition.max(), 'high'].iloc[0])

            # if not dfLow.loc[dfLow['PointPosition'] == dfLow.PointPosition.min(), 'Id'].empty:
            FEASIBLE_LOW_PIVOT_POINTS = np.append(FEASIBLE_LOW_PIVOT_POINTS, dfLow.loc[dfLow['PointPosition'] == dfLow.PointPosition.min(), 'Id'].iloc[0])

            # if not dfLow.loc[dfLow['PointPosition'] == dfLow.PointPosition.min(), 'low'].empty:
            FEASIBLE_LOW = np.append(FEASIBLE_LOW, dfLow.loc[dfLow['PointPosition'] == dfLow.PointPosition.min(), 'low'].iloc[0])

            # if not FEASIBLE_LOW_PIVOT_POINTS.empty and not FEASIBLE_LOW.empty:
            #     slmin, intercmin, rmin, pmin, semin = linregress(FEASIBLE_LOW_PIVOT_POINTS, FEASIBLE_LOW)
            #     if(df['close'].iloc[-1] < slmin * df['close'].iloc[-1] + intercmin):
            #         order_target_percent(context.long_portfolio[i], 0)
            # if not FEASIBLE_HIGH_PIVOT_POINTS.empty and not FEASIBLE_HIGH.empty:
            #     slmax, intercmax, rmax, pmax, semax = linregress(FEASIBLE_HIGH_PIVOT_POINTS, FEASIBLE_HIGH)
            #     if(df['close'].iloc[-1] > slmax * df['close'].iloc[-1] + intercmax):
            #         order_target_percent(context.long_portfolio[i], 1/(round(len(context.long_portfolio),2)))

            slmin, intercmin, rmin, pmin, semin = linregress(FEASIBLE_LOW_PIVOT_POINTS, FEASIBLE_LOW)
            slmax, intercmax, rmax, pmax, semax = linregress(FEASIBLE_HIGH_PIVOT_POINTS, FEASIBLE_HIGH)
            
            if(df['close'].iloc[-1] < slmin * df['close'].iloc[-1] + intercmin and context.flag == 1):
                order_target_percent(security, 0)
            elif(df['close'].iloc[-1] > slmax * df['close'].iloc[-1] + intercmax and context.flag == 0):
                order_target_percent(security,0.13)
                # set_stoploss(security, "PERCENT", 0.01)
        except:
            print("Not Found")
        


            