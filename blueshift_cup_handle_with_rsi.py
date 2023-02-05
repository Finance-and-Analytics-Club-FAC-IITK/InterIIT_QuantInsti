from blueshift.library.technicals.indicators import rsi, ema

from blueshift.finance import commission, slippage
from blueshift.api import(  symbol,
                            order_target_percent,
                            set_commission,
                            set_slippage,
                            schedule_function,
                            date_rules,
                            time_rules,
                       )

def initialize(context):
    """
        A function to define things to do at the start of the strategy
    """
    # universe selection
    context.securities = [symbol('TATAPOWER'),symbol('NTPC'),symbol('POWERGRID'),symbol('GAIL'),symbol('IOC'),symbol('RELIANCE'),symbol('BPCL'),symbol('ONGC'),symbol('ADANITRANS')]

    # define strategy parameters
    context.params = {'indicator_lookback':375,
                      'indicator_freq':'1m',
                      'buy_signal_threshold':0.5,
                      'sell_signal_threshold':-0.5,
                      'SMA_period_short':15,
                      'SMA_period_long':60,
                      'RSI_period':60,
                      'trade_freq':30,
                      'leverage':1,
                      'pip_cost':0.00003}

    # variables to track signals and target portfolio
    context.signals = dict((security,0) for security in context.securities)
    context.target_position = dict((security,0) for security in context.securities)
    context.flag = dict((security,0) for security in context.securities)

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


def generate_signals(context, data):
    """
        A function to define define the signal generation
    """
    try:
        price_data = data.history(context.securities, ['open','high','low','close'],
            context.params['indicator_lookback'], context.params['indicator_freq'])
    except:
        return

    for security in context.securities:
        px = price_data.xs(security)
        context.signals[security] = signal_function(context, px, context.params, security)

def signal_function(context, px, params, security):
    """
        The main trading logic goes here, called by generate_signals above
    """
    close = px.close.values
    high = px.high.values
    low = px.low.values
    
    ind1 = rsi(px, params['RSI_period'])
    ind2 = ema(px, params['SMA_period_short'])
    ind3 = ema(px, params['SMA_period_long'])

    cbb=close[-60]
    cb = min(close)
    cbindex = close.argmin()
    close_1 = close[cbindex:]
    
    hs = max(close_1)
    hs_index = close_1.argmax()

    close_2 = close_1[hs_index:]
    hb = min(close_2)

    check_ratio = hs/cbb

    if ( check_ratio>0.9 and close[-1]>hb and context.flag[security]==0 and (hs-cb)/(hs-hb) > 3):
        context.flag[security] = 1
        return 1
    elif ind1 > 60 and ind2-ind3 > 0 and context.flag[security]==1:
        return -1
    else:
        return 0