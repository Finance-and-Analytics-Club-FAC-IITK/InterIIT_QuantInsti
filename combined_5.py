from scipy.signal import savgol_filter
from blueshift.finance import commission, slippage
from blueshift.api import(  symbol,
                            order_target_percent,
                            set_commission,
                            set_slippage,
                            schedule_function,
                            date_rules,
                            time_rules,
                       )
import numpy as np
import copy
import pandas as pd

def initialize(context):
    """
        A function to define things to do at the start of the strategy
    """
    # universe selection
    context.securities = [symbol('WIPRO'), symbol('RELIANCE')]

    # define strategy parameters
    context.params = {'indicator_lookback':375,
                      'indicator_freq':'1d',
                      'buy_signal_threshold':0.5,
                      'sell_signal_threshold':-5,
                      'SMA_period_short':15,
                      'SMA_period_long':60,
                      'BBands_period':300,
                      'trade_freq':5,
                      'leverage':2}

    # variables to track signals and target portfolio
    context.signals = dict((security,0) for security in context.securities)
    context.target_position = dict((security,0) for security in context.securities)
    context.pivots = dict((security, []) for security in context.securities)
    context.support_pivots = dict((security, []) for security in context.securities)
    context.resistance_pivots = dict((security, []) for security in context.securities)
    context.new_support = dict((security, []) for security in context.securities)
    context.new_resistance = dict((security, []) for security in context.securities)
    context.new_pivots = dict((security, []) for security in context.securities)

    # set trading cost and slippage to zero
    set_commission(commission.PerShare(cost=0.0, min_trade_cost=0.0))
    set_slippage(slippage.FixedSlippage(0.00))
    
    freq = int(context.params['trade_freq'])
    schedule_function(run_strategy, date_rules.every_day(),
                      time_rules.every_nth_minute(freq))
    
    schedule_function(stop_trading, date_rules.every_day(),
                      time_rules.market_close(minutes=30))
    
    context.trade = True
    
def before_trading_start(context, data):
    context.trade = True
    
def stop_trading(context, data):
    context.trade = False

def run_strategy(context, data):
    """
        A function to define core strategy steps
    """
    if not context.trade:
        return
    
    generate_signals(context, data)
    generate_target_position(context, data)
    rebalance(context, data)

def rebalance(context,data):
    """
        A function to rebalance - all execution logic goes here
    """
    for security in context.securities:
        order_target_percent(security, context.target_position[security])

def generate_target_position(context, data):
    """
        A function to define target portfolio
    """
    num_secs = len(context.securities)
    weight = round(1.0/num_secs,2)*context.params['leverage']

    for security in context.securities:
        if context.signals[security] > context.params['buy_signal_threshold']:
            context.target_position[security] = weight
        elif context.signals[security] < context.params['sell_signal_threshold']:
            context.target_position[security] = -weight
        else:
            context.target_position[security] = 0

def pivotId(high, low, candle, num_before, num_after):

    if candle-num_before < 0 or candle+num_after >= len(high):
        return 0
    
    pivotIdLow=1
    pivotIdHigh=1
    for i in range(candle-num_before, candle+num_after):
        if(low[candle]>low[i]):
            pivotIdLow=0
        if(high[candle]<high[i]):
            pivotIdHigh=0
    if pivotIdLow and pivotIdHigh:
        return 3
    elif pivotIdLow:
        return 1
    elif pivotIdHigh:
        return 2
    else:
        return 0

def assign_strength_remove_noise(high, low, lis, s):

    updatedLis = []
    newLis = copy.deepcopy(lis)
    lisSorted = copy.deepcopy(lis)
    lisSorted.sort(key=lambda a: a[1])

    counter = 0
    for i in lisSorted:
        counter = counter + 1
    len2 = counter

    blacklisted = []
    blacklisted.append(0)

    for i in range(len2):
        if not(lisSorted[i][0] in blacklisted):
            for cnt in range(0, len2-i):
                if(abs(lisSorted[i][1]-lisSorted[i+cnt][1]) > s):
                    break

            max = i
            if cnt>1:
                for j in range(1, cnt):
                    if (lisSorted[i+j][0] >= lisSorted[max][0]):
                        blacklisted.append(lisSorted[max][0])
                        max = i+j
            
            updatedLis.append((lisSorted[max][0],lisSorted[max][1],cnt))
    updatedLis.sort(key=lambda a: a[0])
    return updatedLis

def morning_star(high, low, open, close):

    if (len(close)<3):
        return 0

    pres_close= close[-1]
    pres_open= open[-1]
    pres_high= high[-1]
    pres_low= low[-1]

    prev_close= close[-2]
    prev_open= open[-2]
    prev_high= high[-2]
    prev_low= low[-2]

    b_prev_close= close[-3]
    b_prev_open= open[-3]
    b_prev_high= high[-3]
    b_prev_low= low[-3]
    
    diff_last = close[-1] - open[-1]
    diff_second_last = close[-2] - open[-2] 

    return (max(prev_open, prev_close) < b_prev_close < b_prev_open 
    and pres_close > pres_open > max(prev_open, prev_close))

def piercing_pattern(high, low, open, close):

    if (len(close)<2):
        return 0

    pres_close= close[-1]
    pres_open= open[-1]
    pres_high= high[-1]
    pres_low= low[-1]

    prev_close= close[-2]
    prev_open= open[-2]
    prev_high= high[-2]
    prev_low= low[-2]


    if (prev_close < prev_open and pres_open < prev_low
     and prev_open > pres_close > prev_close + ((prev_open - prev_close) / 2)) :
        return 1

    else:
        return 0

def bullish_engulfing(high, low, open, close):

    if (len(close)<2):
        return 0

    pres_close= close[-1]
    pres_open= open[-1]
    pres_high= high[-1]
    pres_low= low[-1]

    prev_close= close[-2]
    prev_open= open[-2]
    prev_high= high[-2]
    prev_low= low[-2]


    if (pres_open >= prev_close > prev_open and pres_open > pres_close and prev_open >= pres_close 
    and pres_open - pres_close > prev_close - prev_open) :
        return 1
    else:
        return 0

def bullish_harami(high, low, open, close):

    if (len(close)<2):
        return 0

    pres_close= close[-1]
    pres_open= open[-1]
    pres_high= high[-1]
    pres_low= low[-1]

    prev_close= close[-2]
    prev_open= open[-2]
    prev_high= high[-2]
    prev_low= low[-2]


    if (prev_open > prev_close and prev_close <= pres_open < pres_close <= prev_open 
    and pres_close - pres_open < prev_open - prev_close) :
        return 1
    else:
        return 0

def generate_signals(context, data):
    """
        A function to define define the signal generation
    """
    try:
        price_data = data.history(context.securities, ['high', 'low', 'open', 'close'],
            context.params['indicator_lookback'],
            context.params['indicator_freq'])
    except:
        return

    for security in context.securities:
        px = price_data.xs(security)
        context.signals[security] = signal_function(context, px, context.params, security)


def signal_function(context, px, params, security):
    """
        The main trading logic goes here, called by generate_signals above
    # """
    NUM_BEFORE = 3
    NUM_AFTER = 3

    # pivot = context.pivots[security]
    # support_pivots = context.support_pivots[security]
    # resistance_pivots = context.resistance_pivots[security]
    open = px.open.values
    high = px.high.values
    low = px.low.values
    close = px.close.values

    s = np.mean(high - low)

    month_diff = len(close) // 30    
    if month_diff == 0:
        month_diff = 1
    smooth = int(2*month_diff + 3)
    close = savgol_filter(close, smooth , 3)

    for i in range(6, len(px) - 6):
        if pivotId(close, close, i, NUM_BEFORE, NUM_AFTER) == 1:
            context.pivots[security].append((i,close[i]))
        elif pivotId(close,close, i, NUM_BEFORE, NUM_AFTER) == 2:
            context.pivots[security].append((i,close[i]))

    context.new_pivots[security] =  assign_strength_remove_noise(close, close, context.pivots[security], s)

    for pivot in context.new_pivots[security]:
        idx, price, strength = pivot
        if(abs(close[-1] - price) < s/3 and strength>=2):
            if(morning_star(high, low, open, close) or piercing_pattern(high, low, open, close)
            or bullish_engulfing(high, low, open, close) or bullish_harami(high, low, open, close)):
                return 1
    return 0