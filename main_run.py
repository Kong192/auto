import threading
import queue
import time
import pyupbit
import datetime
from collections import deque
import numpy

class Consumer(threading.Thread):
    def __init__(self, q):
        super().__init__()
        self.q = q
        self.ticker = "KRW-BTC"

        self.ma15 = deque(maxlen=15)
        self.ma20 = deque(maxlen=20)
        self.ma50 = deque(maxlen=50)
        self.ma120 = deque(maxlen=120)

        df = pyupbit.get_ohlcv(self.ticker, interval="minute1")
        self.ma15.extend(df['close'])
        self.ma20.extend(df['close'])
        self.ma50.extend(df['close'])
        self.ma120.extend(df['close'])

        # print(len(self.ma15), len(self.ma20), len(self.ma50), len(self.ma120))


    def run(self):
        price_curr = None
        hold_flag = False
        wait_flag = False

        with open("upbit.txt", "r") as f:
            key0 = f.readline().strip()
            key1 = f.readline().strip()

        upbit = pyupbit.Upbit(key0, key1)
        cash  = upbit.get_balance()
        print("Initial Cash : ", cash)

        i = 0

        while True:
            try:
                if not self.q.empty():
                    if price_curr != None:
                        self.ma15.append(price_curr)
                        self.ma20.append(price_curr)
                        self.ma50.append(price_curr)
                        self.ma120.append(price_curr)

                    curr_ma15 = sum(self.ma15) / len(self.ma15)
                    curr_ma20 = sum(self.ma20) / len(self.ma20)
                    curr_ma50 = sum(self.ma50) / len(self.ma50)
                    curr_ma120 = sum(self.ma120) / len(self.ma120)

                    bb_upper = curr_ma20 + 2 * numpy.std(self.ma20)
                    bb_under = curr_ma20 - 2 * numpy.std(self.ma20)

                    price_open = self.q.get()
                    if hold_flag == False:
                        price_buy  = curr_ma20
                        price_sell = price_buy * 1.01
                    wait_flag  = False

                price_curr = pyupbit.get_current_price(self.ticker)
                if price_curr == None:
                    continue

                # if hold_flag == False and wait_flag == False and \
                #     price_curr >= price_buy and curr_ma15 >= curr_ma50 and \
                #     curr_ma15 <= curr_ma50 * 1.03 and curr_ma120 <= curr_ma50 :
                if hold_flag == False and wait_flag == False and \
                    curr_ma20 > curr_ma50 and price_curr <= curr_ma20 :
                    # 0.05%
                    ret = upbit.buy_market_order(self.ticker, cash * 0.9995)
                    print("Buy Order", ret)
                    if ret == None or "error" in ret:
                        print("Buy Order Error")
                        continue

                    while True:
                        order = upbit.get_order(ret['uuid'])
                        if order != None and len(order['trades']) > 0:
                            print("Buy Order Completed", order)
                            break
                        else:
                            print("Waiting For Buy Order Being Completed")
                            time.sleep(0.5)

                    while True:
                        volume = upbit.get_balance(self.ticker)
                        if volume != None:
                            break
                        time.sleep(0.5)

                    while True:
                        price_sell = pyupbit.get_tick_size(price_sell)
                        ret = upbit.sell_limit_order(self.ticker, price_sell, volume)
                        if ret == None or 'error' in ret:
                            print("Sell Order Error")
                            time.sleep(0.5)
                        else:
                            print("Sell Order", ret)
                            hold_flag = True
                            break

                # print(price_curr, curr_ma15, curr_ma50, curr_ma120)

                if hold_flag == True:
                    uncomp = upbit.get_order(self.ticker)
                    if uncomp != None and len(uncomp) == 0:
                        cash = upbit.get_balance()
                        if cash == None:
                            continue

                        print("Sell Order Completed", cash)
                        hold_flag = False
                        wait_flag = True

                # 3 minutes
                if i == (5 * 60 * 3):
                    print(f"[{datetime.datetime.now()}] Now_Price {price_curr}, Target_Price {price_buy}, ma {curr_ma15:.2f}/{curr_ma50:.2f}/{curr_ma120:.2f}, hold_flag {hold_flag}, wait_flag {wait_flag}")
                    i = 0
                i += 1
            except:
                print("error")

            time.sleep(0.2)

class Producer(threading.Thread):
    def __init__(self, q):
        super().__init__()
        self.q = q

    def run(self):
        while True:
            price = pyupbit.get_current_price("KRW-BTC")
            self.q.put(price)
            time.sleep(60)

q = queue.Queue()
Producer(q).start()
Consumer(q).start()
