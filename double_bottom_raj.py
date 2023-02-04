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

def initialize(context):
    """
        A function to define things to do at the start of the strategy
    """
    # universe selection
    context.securities = [symbol('TCS'), symbol('WIPRO')]

    # define strategy parameters
    context.params = {'indicator_lookback':375,
                      'indicator_freq':'1m',
                      'buy_signal_threshold':0.5,
                      'sell_signal_threshold':-0.5,
                      'SMA_period_short':15,
                      'SMA_period_long':60,
                      'BBands_period':300,
                      'trade_freq':1,
                      'leverage':2}

    # variables to track signals and target portfolio
    context.signals = dict((security,0) for security in context.securities)
    context.target_position = dict((security,0) for security in context.securities)

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
    low  = px.low.values
    close  = px.close.values

    x_data = np.linspace(1, len(low), len(low))
    y_data = low
    if(len(low)<2):
        return 0

    # x values for the polynomial fit, 200 points
    x = np.linspace(1, len(low), len(low))

    # polynomial fit of degree xx
    pol = np.polyfit(x_data, y_data, 17)
    y_pol = np.polyval(pol, x)

    data = y_pol

    #           ___ detection of local minimums and maximums ___
    min_max = np.diff(np.sign(np.diff(data))).nonzero()[0] + 1          # local min & max
    l_min = (np.diff(np.sign(np.diff(data))) > 0).nonzero()[0] + 1      # local min
    l_max = (np.diff(np.sign(np.diff(data))) < 0).nonzero()[0] + 1      # local max
    # +1 due to the fact that diff reduces the original index number
    
    #extend the suspected x range:
    delta = 10  # how many ticks to the left and to the right from local minimum on x axis

    dict_i = dict()
    dict_x = dict()

    df_len = len(low)                    # number of rows in dataset

    for element in l_min:                            # x coordinates of suspected minimums
        l_bound = element - delta                    # lower bound (left)
        u_bound = element + delta                    # upper bound (right)
        x_range = range(l_bound, u_bound + 1)        # range of x positions where we SUSPECT to find a low
        dict_x[element] = x_range                    # just helpful dictionary that holds suspected x ranges for further visualization strips

        y_loc_list = list()
        for x_element in x_range:
            if x_element > 0 and x_element < df_len:                # need to stay within the dataframe
                #y_loc_list.append(ticker_df.Low.iloc[x_element])   # list of suspected y values that can be a minimum
                y_loc_list.append(low[x_element])
        
        dict_i[element] = y_loc_list

    y_delta = 0.12                               # percentage distance between average lows
    threshold = min(low) * 1.15      # setting threshold higher than the global low

    y_dict = dict()
    mini = list()
    suspected_bottoms = list()
                                              #   BUG somewhere here
    for key in dict_i.keys():                     # for suspected minimum x position  
        mn = sum(dict_i[key])/len(dict_i[key])    # this is averaging out the price around that suspected minimum
                                                  # if the range of days is too high the average will not make much sense
        
        price_min = min(dict_i[key])    
        mini.append(price_min)                    # lowest value for price around suspected 
    
        l_y = mn * (1.0 - y_delta)                #these values are trying to get an U shape, but it is kinda useless 
        u_y = mn * (1.0 + y_delta)
        y_dict[key] = [l_y, u_y, mn, price_min]
    
    # tops = []
    
    for key_i in y_dict.keys():    
        for key_j in y_dict.keys():    
            if (key_i != key_j) and (y_dict[key_i][3] < threshold):
                suspected_bottoms.append(key_i)
                # tops.append()
    
    flag = 0
    for bot in suspected_bottoms:
        if(close[-1] == bot):
            flag = 1
    
    if(flag):
        return 1
    else:
        return 0